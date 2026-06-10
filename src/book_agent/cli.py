"""CLI for the Book Agent (plan.md §13). Subcommands:
new, run, status, review, read, memory, produce, consolidate, skills, config.
"""
from __future__ import annotations

import argparse
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


def _cmd_new_book(args, cfg, settings, uid, abstract):
    directions = _spin("planning directions", lambda: nodes.planner_directions(cfg, abstract)).directions
    for i, d in enumerate(directions, 1):
        print(f"\n[{i}] {d.title}\n    {d.premise}\n    tone: {d.tone} | hook: {d.hook}")
    idx = args.pick or int(input(f"\nPick a direction [1-{len(directions)}]: ").strip())
    chosen = directions[idx - 1]
    chapters = args.chapters or settings.num_chapters
    max_rev = args.max_revisions if args.max_revisions is not None else settings.max_revisions
    print(f"\n-> {chosen.title}")
    book_id = _spin("building plan + TOC", lambda: orchestrator.start_book(
        cfg, settings, uid, abstract, chosen, args.book_id, chapters, max_rev,
        autonomous=getattr(args, "autonomous", settings.autonomous),
        humanize=(False if getattr(args, "no_humanize", False) else None)))
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
    print(f"\n-> {chosen.title}")
    article_id = _spin("building outline", lambda: orchestrator.start_article(
        cfg, settings, uid, abstract, chosen, args.book_id, num_sections, max_rev,
        autonomous=getattr(args, "autonomous", settings.autonomous),
        humanize=(False if getattr(args, "no_humanize", False) else None)))
    print(f"\n[OK] Created article '{article_id}'.")
    print(f"     Next: python book.py run --book-id {article_id}")


def cmd_run(args, cfg, settings, uid):
    orchestrator.run(cfg, uid, _resolve_book(uid, args.book_id),
                     force=getattr(args, "force", False))


def cmd_status(args, cfg, settings, uid):
    book_id = _resolve_book(uid, args.book_id)
    st = orchestrator.status(uid, book_id)
    mode = st.get("mode", "book")
    is_article = mode == "article"
    cur_key, tot_key = (("current_section", "num_sections") if is_article
                        else ("current_chapter", "num_chapters"))
    words = _project_word_count(uid, book_id, mode)
    console = _console()

    if not console:
        print(f"mode: {mode}  |  phase: {st.get('phase')}")
        unit = "section" if is_article else "chapter"
        print(f"{unit}: {st.get(cur_key)}/{st.get(tot_key)} (committed {st.get('committed')})")
        if words:
            print(f"words: {words} (~{ui.reading_time_min(words)} min read)")
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
        body.append(f"\n{words:,} words   ·   ~{ui.reading_time_min(words)} min read", style=ui.DIM)
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


def cmd_read(args, cfg, settings, uid):
    # Articles and books store a manuscript/sections at different paths; pick the
    # right one so `read --manuscript` works for both project types.
    paths = _paths_for(uid, _resolve_book(uid, args.book_id))
    if args.manuscript:
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


def cmd_export(args, cfg, settings, uid):
    book_id = _resolve_book(uid, args.book_id)
    fmt = getattr(args, "format", None)
    if not fmt:
        choices = "  ".join(_EXPORT_FORMATS)
        print(f"\nExport formats:  {choices}")
        fmt = input("Format [pdf]: ").strip().lower() or "pdf"
        if fmt not in _EXPORT_FORMATS:
            sys.exit(f"Unknown format '{fmt}'. Choose from: {', '.join(_EXPORT_FORMATS)}")
    out = _EXPORT_FNS[fmt](uid, book_id)
    console = _console()
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


def cmd_seed_skills(args, cfg, settings, uid):
    n = skills_mod.seed_builtin(uid)
    print(f"Seeded {n} new built-in skill(s) for user '{uid}'.")


def cmd_delete(args, cfg, settings, uid):
    if getattr(args, "name", None) and not args.book_id:
        args.book_id = args.name
    book_id = _resolve_book(uid, args.book_id)
    if not getattr(args, "yes", False):
        confirm = input(f"Delete '{book_id}' permanently? [y/N] ").strip().lower()
        if confirm not in ("y", "yes"):
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
    "new": cmd_new, "run": cmd_run, "status": cmd_status, "review": cmd_review,
    "read": cmd_read, "memory": cmd_memory, "produce": cmd_produce,
    "consolidate": cmd_consolidate, "skills": cmd_skills, "config": cmd_config,
    "list": cmd_list, "export": cmd_export, "seed-skills": cmd_seed_skills,
    "delete": cmd_delete,
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
    p_new.add_argument("--autonomous", action="store_true",
                       help="No human-in-the-loop: never pause; commit the best draft")
    p_new.add_argument("--no-humanize", action="store_true",
                       help="Skip the humanizer pass that strips AI tells")

    p_run = sub.add_parser("run", parents=[common], help="Drive the pipeline until done or escalation")
    p_run.add_argument("--force", action="store_true", help="Proceed past a consolidation review")
    sub.add_parser("status", parents=[common], help="Show run state + open reviews")

    p_rev = sub.add_parser("review", parents=[common], help="Answer an escalation")
    p_rev.add_argument("--chapter", type=int)
    p_rev.add_argument("--instruction")

    p_read = sub.add_parser("read", parents=[common], help="Print chapter/summary/manuscript")
    p_read.add_argument("--chapter", type=int)
    p_read.add_argument("--summary", action="store_true")
    p_read.add_argument("--manuscript", action="store_true")

    sub.add_parser("memory", parents=[common], help="Inspect canon + graph")
    sub.add_parser("produce", parents=[common], help="Run Production (front/back matter + assembly)")
    sub.add_parser("consolidate", parents=[common], help="Run a consolidation pass")
    sub.add_parser("skills", parents=[common], help="List learned skills + efficacy")
    sub.add_parser("config", parents=[common], help="Show model routing + settings")
    sub.add_parser("list", parents=[common], help="List books for the user")
    p_export = sub.add_parser("export", parents=[common], help="Export the manuscript (pdf/epub/html/docx/txt/md)")
    p_export.add_argument("--format", choices=_EXPORT_FORMATS, default=None,
                          help="Output format - omit to choose interactively")
    sub.add_parser("seed-skills", parents=[common], help="Install built-in craft skills")
    p_del = sub.add_parser("delete", parents=[common], help="Permanently delete a book")
    p_del.add_argument("name", nargs="?", help="Book ID to delete (positional shorthand)")
    p_del.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    return ap


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
    from . import llm as _llm
    _llm.configure_headroom(settings.use_headroom)
    _llm.configure_timeout(settings.request_timeout)
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
