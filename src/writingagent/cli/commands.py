"""The core project commands: run, status, review, revise, versions, brief,
tableread, eval, read, memory, produce, consolidate, skills, delete, list, config."""
from __future__ import annotations

import sys

from .. import brain, orchestrator, ui
from .. import skills as skills_mod
from ..brain import ArticlePaths, BookPaths
from ._common import _console, _paths_for, _print_diff, _project_word_count, _resolve_book

__all__ = [
    "cmd_run", "cmd_status", "cmd_review", "cmd_revise", "cmd_versions", "cmd_brief",
    "cmd_tableread", "cmd_eval", "cmd_read", "cmd_memory", "cmd_produce",
    "cmd_consolidate", "cmd_skills", "cmd_seed_skills", "cmd_delete", "cmd_list", "cmd_config",
]


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
    print(f"[OK] Recorded instruction for chapter {args.chapter}. Now: python writingagent.py run "
          f"--book-id {book_id}")


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
            duel = f" duel_wr={r['duel_wr']} ({r['duels']})" if r["duels"] else ""
            print(f"- {r['name']:<28} {r['status']:<10} applied={r['applied']} "
                  f"p_skill={r['p_skill']} p_base={r['p_base']}{duel}")
        return
    from rich.table import Table
    t = Table(box=None, show_header=True, header_style=ui.DIM, padding=(0, 3, 0, 0))
    t.add_column("skill", style=f"bold {ui.GOLD}", no_wrap=True)
    t.add_column("status", style=ui.PARCH)
    t.add_column("used", justify="right", style=ui.DIM)
    t.add_column("first-pass  (vs baseline)", style=ui.PARCH)
    t.add_column("duels  (vs 50/50)", style=ui.PARCH)
    for r in rows:
        if r["duels"]:
            duel_cell = ui.efficacy_bar(r["duel_wr"], 0.5)
            duel_cell.append(f"  ({r['duels']})", style=ui.DIM)
        else:
            duel_cell = "[dim]—[/]"
        t.add_row(r["name"], r["status"], str(r["applied"]),
                  ui.efficacy_bar(r["p_skill"], r["p_base"]), duel_cell)
    console.print(t)


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
