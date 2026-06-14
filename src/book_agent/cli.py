"""CLI for the Book Agent (plan.md §13). Subcommands:
new, run, status, review, read, memory, produce, consolidate, skills, config.
"""
from __future__ import annotations

import argparse
import re
import sys

from . import brain, nodes, orchestrator, ui
from . import skills as skills_mod
from .brain import ArticlePaths, BookPaths
from .config import load_config, load_settings

_CONSOLE = None
_CONSOLE_INIT = False


def _console():
    """Shared Rich console (None if Rich is unavailable). Honors NO_COLOR / --plain."""
    global _CONSOLE, _CONSOLE_INIT
    if not _CONSOLE_INIT:
        _CONSOLE = ui.make_console()
        _CONSOLE_INIT = True
    return _CONSOLE


def _project_word_count(uid: str, book_id: str, mode: str) -> int:
    """Word count from the assembled manuscript, falling back to committed parts."""
    if mode == "article":
        p = ArticlePaths(book_id, uid)
        txt = brain.read_text(p.manuscript)
        if txt:
            return ui.word_count(txt)
        if p.root.exists():
            return sum(ui.word_count(f.read_text(encoding="utf-8"))
                       for f in p.root.glob("section_*.md")
                       if not f.name.endswith(".summary.md"))
        return 0
    p = BookPaths(book_id, uid)
    txt = brain.read_text(p.manuscript)
    if txt:
        return ui.word_count(txt)
    if p.chapters.exists():
        return sum(ui.word_count(f.read_text(encoding="utf-8"))
                   for f in p.chapters.glob("ch*.md")
                   if not f.name.endswith((".draft.md", ".summary.md")))
    return 0


def _paths_for(uid: str, project_id: str):
    """Return the right paths object for a project: ArticlePaths if it's an
    article, else BookPaths. Both expose .manuscript / .ch(n) / .ch_summary(n),
    so callers can stay project-type agnostic."""
    art = ArticlePaths(project_id, uid)
    if art.run_state.exists():
        return art
    return BookPaths(project_id, uid)


def _resolve_book(uid: str, book_id: str | None) -> str:
    if book_id:
        if not brain.is_safe_id(book_id):
            sys.exit(f"Invalid --book-id '{book_id}' (use letters, digits, - . _).")
        # Exact id wins; otherwise resolve an excerpt/typo to a confident single
        # project ("--book-id voicebot" -> the full slug). Ambiguous/unknown falls
        # through unchanged, so downstream errors exactly as before.
        if book_id not in {p[0] for p in brain.list_projects(uid)}:
            resolved, _cands = brain.resolve_project(uid, book_id)
            if resolved:
                return resolved
        return book_id
    projects = brain.list_projects(uid)
    if len(projects) == 1:
        return projects[0][0]
    if not projects:
        sys.exit(f"No projects for user '{uid}'. Create one with `book new`.")
    ids = ", ".join(p[0] for p in projects)
    sys.exit("Multiple projects - specify --book-id: " + ids)


def cmd_new(args, cfg, settings, uid):
    skills_mod.seed_builtin(uid)
    mode = settings.mode
    label = "Article topic" if mode == "article" else "Book abstract"
    abstract = args.abstract or input(f"{label}: ").strip()
    if not abstract:
        sys.exit("No abstract provided.")
    if mode == "article":
        _cmd_new_article(args, cfg, settings, uid, abstract)
    else:
        _cmd_new_book(args, cfg, settings, uid, abstract)


def _spin(label: str, fn):
    """Run a slow LLM call under a spinner when a Rich console is available."""
    console = _console()
    if console:
        with console.status(f"[{ui.GOLD}]{label}[/]", spinner="dots", spinner_style=ui.GOLD):
            return fn()
    print(f"\n== {label} ==")
    return fn()


def _outline_gate(uid, project_id, abstract, create_fn, *, is_article, gate_on: bool):
    """Manual-mode checkpoint after `new`: show the outline (and thesis) BEFORE any
    prose is written. Reviewing 6 headings costs the human 30 seconds; a bad outline
    costs the whole run. Enter accepts; 'r' regenerates; 'g' regenerates with guidance.
    Skipped for autonomous runs and non-interactive stdin (tests, pipes, CI)."""
    if not gate_on or not sys.stdin.isatty():
        return project_id
    for _round in range(3):   # cap regenerations - the planner won't improve forever
        paths = ArticlePaths(project_id, uid) if is_article else BookPaths(project_id, uid)
        outline_md = brain.read_text(paths.outline_md if is_article else paths.toc) or ""
        print("\n" + outline_md.strip())
        thesis_md = brain.read_text(paths.root / "thesis.md") if is_article else None
        if thesis_md:
            claim = next((ln for ln in thesis_md.splitlines() if ln.startswith("**Claim:**")), "")
            if claim:
                print(f"\n{claim}")
        ans = input("\n[Enter] start writing · r regenerate outline · "
                    "g regenerate with guidance: ").strip().lower()
        if ans not in ("r", "g"):
            return project_id
        if ans == "g":
            guidance = input("guidance for the planner: ").strip()
            if guidance:
                abstract = f"{abstract}\n\nAuthor guidance (honor exactly): {guidance}"
        orchestrator.delete_book(uid, project_id)
        project_id = create_fn(abstract)
    return project_id


def _cmd_new_book(args, cfg, settings, uid, abstract):
    directions = _spin("planning directions", lambda: nodes.planner_directions(cfg, abstract)).directions
    for i, d in enumerate(directions, 1):
        print(f"\n[{i}] {d.title}\n    {d.premise}\n    tone: {d.tone} | hook: {d.hook}")
    idx = args.pick or int(input(f"\nPick a direction [1-{len(directions)}]: ").strip())
    chosen = directions[idx - 1]
    chapters = args.chapters or settings.num_chapters
    max_rev = args.max_revisions if args.max_revisions is not None else settings.max_revisions
    autonomous = _autonomous_value(args, settings)
    print(f"\n-> {chosen.title}")

    def _create(abs_):
        return _spin("building plan + TOC", lambda: orchestrator.start_book(
            cfg, settings, uid, abs_, chosen, args.book_id, chapters, max_rev,
            autonomous=autonomous,
            humanize=(False if getattr(args, "no_humanize", False) else None)))
    book_id = _outline_gate(uid, _create(abstract), abstract, _create,
                            is_article=False, gate_on=not autonomous)
    print(f"\n[OK] Created book '{book_id}'.")
    print(f"     Next: python book.py run --book-id {book_id}")


def _cmd_new_article(args, cfg, settings, uid, abstract):
    angles = _spin("planning angles", lambda: nodes.plan_article_angles(cfg, abstract)).angles
    for i, a in enumerate(angles, 1):
        print(f"\n[{i}] {a.title}\n    {a.angle}\n    audience: {a.audience} | hook: {a.hook}")
    idx = args.pick or int(input(f"\nPick an angle [1-{len(angles)}]: ").strip())
    chosen = angles[idx - 1]
    num_sections = args.chapters or settings.num_sections
    max_rev = args.max_revisions if args.max_revisions is not None else settings.max_revisions
    autonomous = _autonomous_value(args, settings)
    print(f"\n-> {chosen.title}")

    def _create(abs_):
        return _spin("building outline", lambda: orchestrator.start_article(
            cfg, settings, uid, abs_, chosen, args.book_id, num_sections, max_rev,
            autonomous=autonomous,
            humanize=(False if getattr(args, "no_humanize", False) else None)))
    article_id = _outline_gate(uid, _create(abstract), abstract, _create,
                               is_article=True, gate_on=not autonomous)
    print(f"\n[OK] Created article '{article_id}'.")
    print(f"     Next: python book.py run --book-id {article_id}")


# ── Autonomous "write" flow: interview once, then run to a finished file ───────
def _autonomous_value(args, settings) -> bool:
    """Resolve the autonomous flag. An explicit --autonomous / --no-autonomous wins;
    otherwise fall back to settings.autonomous. (The old `store_true` default of False
    silently shadowed the setting, so `autonomous: true` never took effect.)"""
    flag = getattr(args, "autonomous", None)
    return settings.autonomous if flag is None else flag


def _quick_research(settings, topic: str) -> str | None:
    """A fast, best-effort web peek so the interview can ask sharper questions. Never
    blocks: researcher off, offline, or any error -> None and the flow continues."""
    if not settings.use_researcher:
        return None
    try:
        from . import search as search_mod
        results = search_mod.web_search(topic, max_results=3)
        return search_mod.format_results(results) or None
    except Exception:  # noqa: BLE001 - research is optional
        return None


def _ask_batch(console, intro: str, items: list[tuple[str, str]]) -> list[str]:
    """Show every question upfront, then collect answers one line at a time.
    `items` is [(question, default)]; an empty answer takes the default."""
    answers: list[str] = []
    if console:
        from rich.markup import escape
        console.print(f"\n[bold {ui.GOLD}]{escape(intro)}[/]\n")
        for i, (q, d) in enumerate(items, 1):
            dflt = f"  [dim](default: {escape(d)})[/]" if d else ""
            console.print(f"  [{ui.GOLD}]{i}.[/] {escape(q)}{dflt}")
        console.print()
        for i, (_q, d) in enumerate(items, 1):
            raw = console.input(f"  [{ui.GOLD}]{i} ›[/] ").strip()
            answers.append(raw or d)
    else:
        print("\n" + intro + "\n")
        for i, (q, d) in enumerate(items, 1):
            print(f"  {i}. {q}" + (f"  (default: {d})" if d else ""))
        print()
        for i, (_q, d) in enumerate(items, 1):
            answers.append(input(f"  {i} > ").strip() or d)
    return answers


def _pick_approach(console, topic: str, items: list[str]) -> int:
    """Show candidate angles/directions; return the chosen 1-based index (default 1)."""
    if console:
        from rich.markup import escape
        console.print(f"\n[bold {ui.GOLD}]Approaches[/] [dim]for: {escape(topic)}[/]")
        for i, it in enumerate(items, 1):
            console.print(f"  [{ui.GOLD}]{i}[/]  {escape(it)}")
        raw = console.input("\n  [dim]pick an approach[/] [dim][1]:[/] ").strip()
    else:
        print(f"\nApproaches for: {topic}")
        for i, it in enumerate(items, 1):
            print(f"  {i}  {it}")
        raw = input("\n  pick an approach [1]: ").strip()
    try:
        idx = int(raw or "1")
    except ValueError:
        idx = 1
    return max(1, min(idx, len(items)))


def _render_intake(topic: str, approach: str, qa_pairs, author: str) -> str:
    lines = ["# Author requirements (captured upfront)", "",
             f"Topic: {topic}", f"Approach: {approach}", "", "## Answers"]
    for q, a in qa_pairs:
        a = (a or "").strip()
        if a:
            lines.append(f"- **{q}**\n  {a}")
    if author:
        lines.append(f"- **Author / byline:** {author}")
    return "\n".join(lines)


def _conduct_interview(cfg, settings, uid, topic, mode, console):
    """Gather everything upfront: pick an approach, then answer one batch of tailored
    questions. Returns (chosen, intake_md, export_format, author)."""
    research = _quick_research(settings, topic)
    if mode == "article":
        angles = _spin("studying the topic + planning angles",
                       lambda: nodes.plan_article_angles(cfg, topic)).angles
        approach_items = [f"{a.title} - {a.angle}  (for {a.audience})" for a in angles]
        choices = angles
    else:
        dirs = _spin("planning directions",
                     lambda: nodes.planner_directions(cfg, topic)).directions
        approach_items = [f"{d.title} - {d.premise}  (tone: {d.tone})" for d in dirs]
        choices = dirs
    idx = _pick_approach(console, topic, approach_items)
    chosen = choices[idx - 1]

    chosen_focus = f"{topic}\n\nChosen approach: {approach_items[idx - 1]}"
    iv = _spin("preparing your questions",
               lambda: nodes.interview(cfg, chosen_focus, mode, research)).questions

    default_fmt = "docx" if mode == "article" else "pdf"
    qa_items = [(q.question, q.suggestion or "") for q in iv]
    qa_items.append(("Your name for the byline / author credit (Enter to skip)", ""))
    qa_items.append((f"Output file format ({' / '.join(_EXPORT_FORMATS)}, or 'all')", default_fmt))
    answers = _ask_batch(
        console, "A few questions - then I'll research, write, self-edit, and hand you "
                 "the finished piece. No more interruptions:", qa_items)

    fmts, _bad = _resolve_formats(answers[-1] or default_fmt)
    if not fmts:                       # empty or all-unrecognised -> the mode default
        fmts = [default_fmt]
    author = answers[-2].strip()
    qa_pairs = list(zip([q.question for q in iv], answers[:-2], strict=False))
    return chosen, _render_intake(topic, approach_items[idx - 1], qa_pairs, author), fmts, author


def cmd_write(args, cfg, settings, uid):
    """One-shot autonomous flow: topic -> upfront interview -> full run -> exported file."""
    skills_mod.seed_builtin(uid)
    mode = settings.mode
    label = "Article topic" if mode == "article" else "Book idea"
    topic = args.abstract or input(f"{label}: ").strip()
    if not topic:
        sys.exit("No topic provided.")
    console = _console()

    chosen, intake_md, fmts, author = _conduct_interview(cfg, settings, uid, topic, mode, console)

    units = args.chapters or (settings.num_sections if mode == "article"
                              else settings.num_chapters)
    max_rev = args.max_revisions if args.max_revisions is not None else settings.max_revisions
    humanize = False if getattr(args, "no_humanize", False) else None

    if mode == "article":
        pid = _spin("building the outline", lambda: orchestrator.start_article(
            cfg, settings, uid, topic, chosen, args.book_id, units, max_rev,
            autonomous=True, humanize=humanize, intake=intake_md, author=author))
    else:
        pid = _spin("building the plan + chapters", lambda: orchestrator.start_book(
            cfg, settings, uid, topic, chosen, args.book_id, units, max_rev,
            autonomous=True, humanize=humanize, intake=intake_md, author=author))

    msg = (f"Writing '{pid}' autonomously - research, drafting, self-review, assembly. "
           "This can take a while; no more questions.")
    if console:
        console.print(f"\n[{ui.GOLD}]{msg}[/]")
    else:
        print("\n" + msg)

    if console:
        from .shell import run_with_dashboard
        run_with_dashboard(cfg, uid, pid, console)
    else:
        orchestrator.run(cfg, uid, pid, log=print)

    exported = []
    for fmt in fmts:
        try:
            out = _EXPORT_FNS[fmt](uid, pid)
        except Exception as e:  # noqa: BLE001 - one format failing must not lose the rest
            _export_failed(console, fmt, e)
            continue
        exported.append(out)
        _report_export(console, fmt, out)
    if exported and console:
        tail = f"exported {len(exported)} formats" if len(exported) > 1 else "finished"
        console.print(f"\n  [bold {ui.ON_CLR}]✓ done[/]  [{ui.DIM}]{tail}[/]")
    return pid


def cmd_run(args, cfg, settings, uid):
    orchestrator.run(cfg, uid, _resolve_book(uid, args.book_id),
                     force=getattr(args, "force", False),
                     autonomous=getattr(args, "autonomous", None))


def cmd_status(args, cfg, settings, uid):
    book_id = _resolve_book(uid, args.book_id)
    st = orchestrator.status(uid, book_id)
    mode = st.get("mode", "book")
    is_article = mode == "article"
    cur_key, tot_key = (("current_section", "num_sections") if is_article
                        else ("current_chapter", "num_chapters"))
    words = _project_word_count(uid, book_id, mode)
    # Reading time: prose-only from the assembled manuscript when it exists (code blocks +
    # references aren't read at prose speed); fall back to the live word count mid-run.
    _mtext = brain.read_text(_paths_for(uid, book_id).manuscript) or ""
    read_src = _mtext if _mtext else words
    console = _console()

    if not console:
        print(f"mode: {mode}  |  phase: {st.get('phase')}")
        unit = "section" if is_article else "chapter"
        print(f"{unit}: {st.get(cur_key)}/{st.get(tot_key)} (committed {st.get('committed')})")
        if words:
            print(f"words: {words} (~{ui.reading_time_min(read_src)} min read)")
        print(f"pending_review: {st.get('pending_review')}")
        if st.get("open_reviews"):
            print("open reviews: " + ", ".join(st["open_reviews"]))
        return

    from rich.console import Group
    from rich.panel import Panel
    from rich.text import Text
    phases = ui.PHASES_ARTICLE if is_article else ui.PHASES_BOOK
    unit = "section" if is_article else "chapter"
    cur, tot = st.get(cur_key, "?"), st.get(tot_key, "?")
    if isinstance(cur, int) and isinstance(tot, int):
        cur = min(cur, tot)   # current increments past total at completion - clamp for display
    body = Text()
    body.append(f"{unit} {cur}/{tot}", style=ui.PARCH)
    body.append(f"   ·   committed {st.get('committed', 0)}", style=ui.DIM)
    if words:
        body.append(f"\n{words:,} words   ·   ~{ui.reading_time_min(read_src)} min read", style=ui.DIM)
    if st.get("pending_review"):
        body.append(f"\n⚠ review pending - resume:  review --chapter {st.get(cur_key)} "
                    f'--instruction "..."', style=f"bold {ui.ERR}")
    elif st.get("open_reviews"):
        body.append("\nopen reviews: " + ", ".join(st["open_reviews"]), style=ui.DIM)
    console.print(Panel(
        Group(ui.phase_stepper(phases, st.get("phase", "")), Text(""), body),
        title=f"[{ui.GOLD}]{book_id}[/]  [{ui.DIM}]{mode}[/]",
        title_align="left", border_style=ui.RULE, padding=(1, 2)))


def cmd_review(args, cfg, settings, uid):
    if args.chapter is None or not args.instruction:
        sys.exit("review needs --chapter and --instruction")
    book_id = _resolve_book(uid, args.book_id)
    orchestrator.record_instruction(uid, book_id, args.chapter, args.instruction)
    print(f"[OK] Recorded instruction for chapter {args.chapter}. Now: python book.py run "
          f"--book-id {book_id}")


def _print_diff(old: str, new: str) -> None:
    """Colored unified diff (plain text when Rich is unavailable)."""
    import difflib
    lines = list(difflib.unified_diff(old.splitlines(), new.splitlines(),
                                      fromfile="before", tofile="after", lineterm=""))
    console = _console()
    for ln in lines[:400]:   # cap - a total rewrite would flood the terminal
        if console:
            style = (ui.ON_CLR if ln.startswith("+") else
                     ui.ERR if ln.startswith("-") else ui.DIM)
            console.print(f"[{style}]{ln}[/]", highlight=False, markup=True)
        else:
            print(ln)
    if len(lines) > 400:
        print(f"  ... diff truncated ({len(lines) - 400} more lines)")


def cmd_revise(args, cfg, settings, uid):
    """Post-completion revision: rewrite one committed chapter/section to an instruction."""
    if args.chapter is None or not args.instruction:
        sys.exit('revise needs --chapter and --instruction (e.g. revise --chapter 3 '
                 '--instruction "more technical, add a benchmark table")')
    book_id = _resolve_book(uid, args.book_id)

    confirm = None
    if sys.stdin.isatty():
        def confirm(old, new, summary):  # noqa: ARG001 - summary already logged upstream
            _print_diff(old, new)
            return ui.is_affirmative(input("\napply this revision? [Y/n] "), default=True)
    orchestrator.revise_unit(cfg, uid, book_id, args.chapter, args.instruction,
                             confirm=confirm)


def cmd_versions(args, cfg, settings, uid):
    """List draft snapshots (every variant, revision, committed final, revise output)."""
    paths = _paths_for(uid, _resolve_book(uid, args.book_id))
    d = paths.root / "versions"
    files = sorted(d.glob("*.md")) if d.exists() else []
    if args.chapter:
        tags = (f"section_{args.chapter:02d}", f"ch{args.chapter:02d}")
        files = [f for f in files if f.name.startswith(tags)]
    if not files:
        print("(no versions yet - drafts are snapshotted as they are written)")
        return
    import datetime
    for f in files:
        text = f.read_text(encoding="utf-8")
        first = text.splitlines()[0].strip("<!- >") if text.startswith("<!--") else ""
        words = len(text.split())
        ts = datetime.datetime.fromtimestamp(f.stat().st_mtime).strftime("%H:%M:%S")
        print(f"  {f.stem:<22} {words:>6} words   {ts}   {first}")
    print("\nread one:  read --chapter N --v K")


def cmd_brief(args, cfg, settings, uid):
    """The goal panel: what this piece is supposed to be. Writers forget the brief."""
    book_id = _resolve_book(uid, args.book_id)
    art = ArticlePaths(book_id, uid)
    lines = [f"# Brief - {book_id}", ""]
    if art.run_state.exists():
        outline = brain.read_json(art.outline_json) or {}
        lines += [f"**Title:** {outline.get('title', '?')}",
                  f"**Angle:** {outline.get('angle', '?')}",
                  f"**Target length:** ~{outline.get('target_word_count', '?')} words", ""]
        thesis = brain.read_text(art.root / "thesis.md")
        if thesis:
            lines += ["## Thesis", thesis, ""]
        intake = brain.read_text(art.root / "intake.md")
        if intake:
            lines += ["## Author requirements", intake, ""]
    else:
        plan = brain.read_json(BookPaths(book_id, uid).root / "plan.json") or {}
        lines += [f"**Title:** {plan.get('title', '?')}",
                  f"**Genre / tone:** {plan.get('genre', '?')} · {plan.get('tone', '?')}",
                  f"**Audience:** {plan.get('audience', '?')}",
                  f"**Premise:** {plan.get('premise', '?')}", ""]
    voice = brain.voice_exemplars(uid, max_chars=1)
    watch = brain.read_text(brain.watch_list(uid))
    lines.append(f"_voice exemplars: {'on' if voice else 'none'} · "
                 f"watch-list: {'active' if watch else 'none'}_")
    text = "\n".join(lines)
    console = _console()
    if console:
        from rich.markdown import Markdown
        console.print(Markdown(text))
    else:
        print(text)


def cmd_tableread(args, cfg, settings, uid):
    """On-demand skeptical-reader pass, optionally as a specific persona."""
    book_id = _resolve_book(uid, args.book_id)
    out = orchestrator.run_table_read(cfg, uid, book_id, persona=getattr(args, "persona", None))
    text = brain.read_text(out) or ""
    console = _console()
    if console:
        from rich.markdown import Markdown
        console.print(Markdown(text))
    else:
        print(text)


def cmd_eval(args, cfg, settings, uid):
    """Quality report: deterministic metrics + judged 5-dimension rubric."""
    book_id = _resolve_book(uid, args.book_id)
    result = orchestrator.evaluate_project(cfg, uid, book_id)
    console = _console()
    if not console:
        for k, v in result["scores"].items():
            print(f"  {k:<15} {v}/5")
        print(f"\n{result['summary']}\nreport: {result['report_path']}")
        return
    from rich.table import Table
    t = Table(box=None, show_header=False, padding=(0, 3, 0, 2))
    t.add_column(style=f"bold {ui.GOLD}", no_wrap=True)
    t.add_column(style=ui.PARCH)
    for k, v in result["scores"].items():
        bar = "█" * v + "░" * (5 - v)
        clr = ui.ON_CLR if v >= 4 else (ui.PARCH if v >= 3 else ui.ERR)
        t.add_row(k, f"[{clr}]{bar}[/]  {v}/5")
    m = result["metrics"]
    console.print(t)
    console.print(f"  [dim]{m['words']:,} words · {m['ai_tells']} AI-tell sentences · "
                  f"{m['citations']} citations ({m['verified_sources']} verified)[/]")
    console.print(f"\n  {result['summary']}")
    console.print(f"  [dim]full report: {result['report_path']}[/]")


def cmd_read(args, cfg, settings, uid):
    # Articles and books store a manuscript/sections at different paths; pick the
    # right one so `read --manuscript` works for both project types.
    paths = _paths_for(uid, _resolve_book(uid, args.book_id))
    if getattr(args, "v", None):
        n = args.chapter or 1
        tag = (f"section_{n:02d}" if isinstance(paths, ArticlePaths) else f"ch{n:02d}")
        target = paths.root / "versions" / f"{tag}.v{args.v:02d}.md"
    elif args.manuscript:
        target = paths.manuscript
    elif args.summary:
        target = paths.ch_summary(args.chapter or 1)
    else:
        target = paths.ch(args.chapter or 1)
    text = brain.read_text(target)
    if not text:
        print(f"(not found: {target})")
        return
    console = _console()
    if not console:
        print(text)
        return
    from rich.markdown import Markdown
    md = Markdown(text)
    if args.manuscript:                 # long - page through it
        with console.pager(styles=True):
            console.print(md)
    else:
        console.print(md)


def cmd_memory(args, cfg, settings, uid):
    text = orchestrator.memory_summary(uid, _resolve_book(uid, args.book_id))
    console = _console()
    if console:
        from rich.markdown import Markdown
        console.print(Markdown(text))
    else:
        print(text)


def cmd_produce(args, cfg, settings, uid):
    orchestrator.run_production(cfg, uid, _resolve_book(uid, args.book_id))


def cmd_consolidate(args, cfg, settings, uid):
    orchestrator.run_consolidation(cfg, uid, _resolve_book(uid, args.book_id))


def cmd_skills(args, cfg, settings, uid):
    rows = skills_mod.list_skills(uid)
    if not rows:
        print(f"No skills for user '{uid}' yet.")
        return
    console = _console()
    if not console:
        for r in rows:
            print(f"- {r['name']:<28} {r['status']:<10} applied={r['applied']} "
                  f"p_skill={r['p_skill']} p_base={r['p_base']}")
        return
    from rich.table import Table
    t = Table(box=None, show_header=True, header_style=ui.DIM, padding=(0, 3, 0, 0))
    t.add_column("skill", style=f"bold {ui.GOLD}", no_wrap=True)
    t.add_column("status", style=ui.PARCH)
    t.add_column("used", justify="right", style=ui.DIM)
    t.add_column("efficacy  (vs baseline)", style=ui.PARCH)
    for r in rows:
        t.add_row(r["name"], r["status"], str(r["applied"]),
                  ui.efficacy_bar(r["p_skill"], r["p_base"]))
    console.print(t)


_EXPORT_FORMATS = ["pdf", "epub", "html", "docx", "txt", "md"]


def _QUIET(*_a, **_k):   # suppress the exporters' own log line; cmd_export prints its own
    return None


_EXPORT_FNS = {
    "pdf":  lambda uid, bid: orchestrator.export_pdf(uid, bid, log=_QUIET),
    "epub": lambda uid, bid: orchestrator.export_epub(uid, bid, log=_QUIET),
    "html": lambda uid, bid: orchestrator.export_html(uid, bid, log=_QUIET),
    "docx": lambda uid, bid: orchestrator.export_docx(uid, bid, log=_QUIET),
    "txt":  lambda uid, bid: orchestrator.export_txt(uid, bid, log=_QUIET),
    "md":   lambda uid, bid: orchestrator.export_md(uid, bid, log=_QUIET),
}


# Split a format request on any reasonable separator: whitespace, comma,
# semicolon, slash, middot, ampersand, plus.
_FMT_SEP = re.compile(r"[\s,;/·&+]+")
# Connector/filler words ignored in plain-English requests ("pdf, epub and word",
# "give me pdf or docx please") - they're noise, not unknown formats.
_FMT_FILLER = frozenset({
    "and", "or", "plus", "also", "then", "the", "a", "an", "to", "in", "into", "as",
    "with", "of", "format", "formats", "file", "files", "version", "versions",
    "please", "me", "i", "want", "need", "would", "like", "export", "exports", "give",
})
# "all" and its plain-English synonyms expand to every format.
_FMT_ALL = frozenset({"all", "everything", "every", "each", "both"})
# Synonyms so natural words resolve to a format id.
_FMT_ALIASES = {
    "word": "docx", "doc": "docx", "msword": "docx", "ms-word": "docx",
    "markdown": "md", "mkd": "md",
    "text": "txt", "plain": "txt", "plaintext": "txt",
    "web": "html", "webpage": "html", "website": "html", "htm": "html",
    "ebook": "epub", "e-book": "epub",
}
_FMT_STRIP = ".,;:!?'\"()[]{}"


def _resolve_formats(raw: str) -> tuple[list[str], list[str]]:
    """Parse an export request into (formats, unknown).

    Understands a single format, a list in any separator (comma, semicolon, slash,
    ·, &, +, or just spaces), 'all', and plain English - "pdf, epub and word",
    "give me markdown & pdf please", "everything". Connector words are ignored;
    common synonyms (word→docx, markdown→md, ebook→epub) are mapped. Order is
    preserved, duplicates removed - so even the whole 'pdf · epub · …' choices line
    resolves to every format."""
    out: list[str] = []
    bad: list[str] = []
    seen: set[str] = set()

    def add(fmt: str) -> None:
        if fmt not in seen:
            seen.add(fmt)
            out.append(fmt)

    for tok in _FMT_SEP.split((raw or "").strip().lower()):
        tok = tok.strip(_FMT_STRIP)
        if not tok or tok in _FMT_FILLER:
            continue
        if tok in _FMT_ALL:
            for f in _EXPORT_FORMATS:
                add(f)
        elif tok in _EXPORT_FORMATS:
            add(tok)
        elif tok in _FMT_ALIASES:
            add(_FMT_ALIASES[tok])
        else:
            bad.append(tok)
    return out, bad


def _report_export(console, fmt: str, out) -> None:
    if console and out is not None:
        kb = out.stat().st_size / 1024
        # Rich renders an OSC-8 hyperlink in terminals that support it.
        # Path.as_uri() yields a valid file:// URI on Windows, macOS, and Linux.
        try:
            uri = out.resolve().as_uri()
        except ValueError:
            uri = str(out)
        console.print(f"  [bold {ui.ON_CLR}]✓ {fmt}[/]  "
                      f"[link={uri}]{out}[/]  [{ui.DIM}]({kb:.0f} KB)[/]")
    else:
        print(f"[OK] {fmt} -> {out}")


def _export_failed(console, fmt: str, e: Exception) -> None:
    """One format failing must never abort the rest - but the message should preserve
    momentum: say WHY and HOW to recover, not just dump the exception. Special-cases
    the two common, fully-recoverable causes (file open elsewhere; optional dep missing)."""
    s = str(e)
    locked = (isinstance(e, PermissionError) or getattr(e, "winerror", None) == 32
              or "being used by another process" in s.lower() or "permission denied" in s.lower())
    if locked:
        hint = f"the open file is locked — close it in your viewer, then  export {fmt}"
    elif isinstance(e, ModuleNotFoundError) or "No module named" in s:
        mod = s.split("'")[1] if "'" in s else "the optional dependency"
        hint = f"needs an optional package —  pip install {mod}  then  export {fmt}"
    else:
        hint = f"{type(e).__name__}: {e}  —  retry with  export {fmt}"
    if console:
        console.print(f"  [bold {ui.ERR}]✗ {fmt}[/]  [{ui.DIM}]{hint}[/]")
        console.print(f"  [{ui.DIM}](other formats were still written)[/]")
    else:
        print(f"[FAIL] {fmt}: {hint}  (other formats were still written)")


def cmd_export(args, cfg, settings, uid):
    book_id = _resolve_book(uid, args.book_id)
    console = _console()
    # Request can come positionally (`export all`, `export pdf epub`) or via --format.
    raw = " ".join(getattr(args, "formats", None) or [])
    if getattr(args, "format", None):
        raw = f"{raw} {args.format}".strip()
    if not raw:
        choices = "  ·  ".join(_EXPORT_FORMATS)
        if console:
            console.print(f"  [{ui.GOLD}]formats[/]  [dim]{choices}  ·  all[/]")
            raw = console.input(f"  [{ui.INK}]format[/] [dim][pdf, or 'all']:[/] ").strip() or "pdf"
        else:
            print(f"\nExport formats:  {choices}  ·  all")
            raw = input("Format [pdf]: ").strip() or "pdf"
    formats, bad = _resolve_formats(raw)
    if bad:
        valid = ", ".join(_EXPORT_FORMATS)
        note = f"unknown format(s): {', '.join(bad)} - choose from {valid}, or 'all'"
        if console:
            console.print(f"  [{ui.ERR}]{note}[/]")
        elif not formats:
            sys.exit(f"Unknown format(s): {', '.join(bad)}. Choose from {valid}, or 'all'.")
    if not formats:
        if console:
            console.print(f"  [{ui.ERR}]nothing to export[/]")
            return
        sys.exit("No formats to export.")
    ok = 0
    for fmt in formats:
        try:
            out = _EXPORT_FNS[fmt](uid, book_id)
        except Exception as e:  # noqa: BLE001 - one bad format must not abort the others
            _export_failed(console, fmt, e)
            continue
        ok += 1
        _report_export(console, fmt, out)
    if len(formats) > 1:
        line = f"exported {ok}/{len(formats)} formats"
        console.print(f"  [{ui.DIM}]{line}[/]") if console else print(line)


_DELIVERABLE = {"pdf": "manuscript.pdf", "epub": "manuscript.epub",
                "html": "manuscript.html", "docx": "manuscript.docx",
                "txt": "manuscript.txt", "md": "manuscript_export.md"}


def cmd_polish(args, cfg, settings, uid):
    """Deterministically re-fix an existing manuscript (references, citations,
    figures) with no LLM call, then refresh its exports."""
    book_id = _resolve_book(uid, args.book_id)
    console = _console()
    log = (lambda m: console.print(m)) if console else print
    orchestrator.repolish_manuscript(uid, book_id, settings, log=log)
    out_dir = brain.resolve_export_dir(uid, book_id)
    raw = getattr(args, "format", None)
    if raw:
        formats, _bad = _resolve_formats(raw)
    else:   # refresh whatever deliverables already exist; nothing -> just the .md source
        formats = [f for f, name in _DELIVERABLE.items() if (out_dir / name).exists()]
    if console:
        console.print(f"  [bold {ui.ON_CLR}]✓ polished[/]  [dim]{book_id}[/]")
    for fmt in formats:
        try:
            out = _EXPORT_FNS[fmt](uid, book_id)
        except Exception as e:  # noqa: BLE001 - one format must not abort the rest
            _export_failed(console, fmt, e)
            continue
        _report_export(console, fmt, out)


def cmd_seed_skills(args, cfg, settings, uid):
    n = skills_mod.seed_builtin(uid)
    print(f"Seeded {n} new built-in skill(s) for user '{uid}'.")


def cmd_delete(args, cfg, settings, uid):
    if getattr(args, "name", None) and not args.book_id:
        args.book_id = args.name
    book_id = _resolve_book(uid, args.book_id)
    if not getattr(args, "yes", False):
        if not ui.is_affirmative(input(f"Delete '{book_id}' permanently? [y/N] ")):
            print("Aborted.")
            return
    orchestrator.delete_book(uid, book_id)
    print(f"[OK] Deleted '{book_id}'.")


def cmd_list(args, cfg, settings, uid):
    projects = brain.list_projects(uid)
    if not projects:
        print(f"No projects for user '{uid}'.")
    else:
        for pid, ptype in projects:
            print(f"{pid}  [{ptype}]")


def cmd_config(args, cfg, settings, uid):
    print(brain.read_text(brain._ROOT / "config" / "models.yaml") or "(no models.yaml)")
    print(brain.read_text(brain._ROOT / "config" / "settings.yaml") or "(no settings.yaml)")


_COMMANDS = {
    "new": cmd_new, "write": cmd_write, "run": cmd_run, "status": cmd_status, "review": cmd_review,
    "revise": cmd_revise, "versions": cmd_versions, "brief": cmd_brief,
    "tableread": cmd_tableread, "eval": cmd_eval,
    "read": cmd_read, "memory": cmd_memory, "produce": cmd_produce,
    "consolidate": cmd_consolidate, "skills": cmd_skills, "config": cmd_config,
    "list": cmd_list, "export": cmd_export, "seed-skills": cmd_seed_skills,
    "delete": cmd_delete, "polish": cmd_polish,
}


def build_parser(settings):
    ap = argparse.ArgumentParser(prog="book", description="Book Agent CLI (see plan.md §13).")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--user", default=settings.default_user)
    common.add_argument("--book-id")
    common.add_argument("--plain", action="store_true", help="Disable colour/styling")
    sub = ap.add_subparsers(dest="command", required=True)

    p_new = sub.add_parser("new", parents=[common], help="Create a book (plan + TOC)")
    p_new.add_argument("--abstract")
    p_new.add_argument("--pick", type=int)
    p_new.add_argument("--chapters", type=int)
    p_new.add_argument("--max-revisions", type=int)
    # Tri-state so the settings.autonomous default isn't shadowed by a store_true False.
    p_new.add_argument("--autonomous", dest="autonomous", action="store_const", const=True,
                       default=None, help="Never pause; commit the best draft (overrides setting)")
    p_new.add_argument("--no-autonomous", dest="autonomous", action="store_const", const=False,
                       help="Force human-in-the-loop review (overrides settings.autonomous)")
    p_new.add_argument("--no-humanize", action="store_true",
                       help="Skip the humanizer pass that strips AI tells")

    # `write`: interview once, then run fully autonomously to a finished, exported file.
    p_write = sub.add_parser(
        "write", parents=[common],
        help="Interview upfront, then autonomously research + write + export a finished file")
    p_write.add_argument("--abstract", help="Topic/idea (prompted if omitted)")
    p_write.add_argument("--chapters", type=int, help="Number of chapters/sections")
    p_write.add_argument("--max-revisions", type=int)
    p_write.add_argument("--no-humanize", action="store_true",
                         help="Skip the humanizer pass that strips AI tells")

    p_run = sub.add_parser("run", parents=[common], help="Drive the pipeline until done or escalation")
    p_run.add_argument("--force", action="store_true", help="Proceed past a consolidation review")
    # Tri-state (default None): switch the project's run mode as it resumes. --autonomous
    # also unblocks an escalated unit so the run finishes without pausing.
    p_run.add_argument("--autonomous", dest="autonomous", action="store_const", const=True,
                       default=None, help="Stop pausing for review; commit best drafts and finish")
    p_run.add_argument("--manual", dest="autonomous", action="store_const", const=False,
                       help="Re-enable human-in-the-loop review at each chapter/section")
    sub.add_parser("status", parents=[common], help="Show run state + open reviews")

    p_rev = sub.add_parser("review", parents=[common], help="Answer an escalation")
    p_rev.add_argument("--chapter", type=int)
    p_rev.add_argument("--instruction")

    p_revise = sub.add_parser("revise", parents=[common],
                              help="Rewrite one committed chapter/section of a finished piece")
    p_revise.add_argument("--chapter", type=int, help="Chapter/section number to rewrite")
    p_revise.add_argument("--instruction", help="What to change, in your words")

    p_read = sub.add_parser("read", parents=[common], help="Print chapter/summary/manuscript")
    p_read.add_argument("--chapter", type=int)
    p_read.add_argument("--summary", action="store_true")
    p_read.add_argument("--manuscript", action="store_true")
    p_read.add_argument("--v", type=int, help="Read draft version K of the chapter (see `versions`)")

    p_versions = sub.add_parser("versions", parents=[common],
                                help="List draft snapshots (variants, revisions, finals)")
    p_versions.add_argument("--chapter", type=int, help="Only this chapter/section")

    sub.add_parser("brief", parents=[common], help="Show the goal: thesis, audience, length")

    p_tr = sub.add_parser("tableread", parents=[common],
                          help="Skeptical-reader pass over the finished piece")
    p_tr.add_argument("--as", dest="persona",
                      help='Read as a specific persona (e.g. "a CTO evaluating vendors")')

    sub.add_parser("eval", parents=[common],
                   help="Quality report: judged rubric + deterministic metrics")

    sub.add_parser("memory", parents=[common], help="Inspect canon + graph")
    sub.add_parser("produce", parents=[common], help="Run Production (front/back matter + assembly)")
    sub.add_parser("consolidate", parents=[common], help="Run a consolidation pass")
    sub.add_parser("skills", parents=[common], help="List learned skills + efficacy")
    sub.add_parser("config", parents=[common], help="Show model routing + settings")
    sub.add_parser("list", parents=[common], help="List books for the user")
    p_export = sub.add_parser("export", parents=[common],
                              help="Export the manuscript (pdf/epub/html/docx/txt/md, or all)")
    p_export.add_argument("formats", nargs="*",
                          help="Format(s): pdf epub html docx txt md, or 'all' "
                               "(omit to choose interactively)")
    p_export.add_argument("--format", default=None,
                          help="Output format(s), e.g. 'pdf' or 'all' (alternative to the positional)")

    p_polish = sub.add_parser("polish", parents=[common],
                              help="Re-fix an existing manuscript (references, citations, figures) - no LLM, then re-export")
    p_polish.add_argument("--format", default=None,
                          help="Formats to re-export (default: those already present, or 'all')")
    sub.add_parser("seed-skills", parents=[common], help="Install built-in craft skills")
    p_del = sub.add_parser("delete", parents=[common], help="Permanently delete a book")
    p_del.add_argument("name", nargs="?", help="Book ID to delete (positional shorthand)")
    p_del.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    return ap


def _apply_provider(llm_mod, settings) -> None:
    """Select the model host from BOOK_AGENT_PROVIDER (if set) or settings.provider.

    An unknown id is a warning, not a crash - configure_provider leaves the default
    (OpenRouter) in place, so a typo never bricks startup."""
    import os
    choice = os.getenv("BOOK_AGENT_PROVIDER") or settings.provider
    try:
        llm_mod.configure_provider(choice)
        from . import providers
        settings.provider = providers.resolve(choice)   # keep settings in sync so the
        #   banner / _stack_label / key-warning reflect the ACTUAL active provider
    except ValueError as e:
        print(f"warning: {e}", file=sys.stderr)
        if choice != settings.provider:
            try:
                llm_mod.configure_provider(settings.provider)
            except ValueError:
                pass


def main() -> None:
    for _stream in (sys.stdout, sys.stderr):  # Windows consoles default to cp1252
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    try:
        from dotenv import load_dotenv
        load_dotenv(brain._ROOT / ".env")  # anchored to the project, not the current directory
    except ImportError:
        pass

    settings = load_settings()
    cfg = load_config()
    ui.apply_theme(settings.theme)   # before the shell import - it copies the palette
    from . import llm as _llm
    _llm.configure_headroom(settings.use_headroom)
    _llm.configure_timeout(settings.request_timeout)
    _apply_provider(_llm, settings)
    if len(sys.argv) == 1:  # bare `book` / `python book.py` -> interactive shell (TUI)
        from .shell import run_shell
        run_shell(build_parser(settings), _COMMANDS, cfg, settings)
        return
    args = build_parser(settings).parse_args()
    ui.set_plain(getattr(args, "plain", False))
    if not brain.is_safe_id(args.user):
        sys.exit(f"Invalid --user '{args.user}' (use letters, digits, - . _).")
    _COMMANDS[args.command](args, cfg, settings, args.user)


if __name__ == "__main__":
    main()
