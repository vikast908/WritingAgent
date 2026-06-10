"""CLI for the Book Agent (plan.md §13). Subcommands:
new, run, status, review, read, memory, produce, consolidate, skills, config.
"""
from __future__ import annotations

import argparse
import sys

from . import brain, nodes, orchestrator
from . import skills as skills_mod
from .brain import BookPaths
from .config import load_config, load_settings


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
    sys.exit("Multiple projects — specify --book-id: " + ids)


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


def _cmd_new_book(args, cfg, settings, uid, abstract):
    print("\n== Planning directions ==")
    directions = nodes.planner_directions(cfg, abstract).directions
    for i, d in enumerate(directions, 1):
        print(f"\n[{i}] {d.title}\n    {d.premise}\n    tone: {d.tone} | hook: {d.hook}")
    idx = args.pick or int(input(f"\nPick a direction [1-{len(directions)}]: ").strip())
    chosen = directions[idx - 1]
    chapters = args.chapters or settings.num_chapters
    max_rev = args.max_revisions if args.max_revisions is not None else settings.max_revisions
    print(f"\n-> {chosen.title}\n== Building plan + TOC ==")
    book_id = orchestrator.start_book(cfg, settings, uid, abstract, chosen,
                                      args.book_id, chapters, max_rev,
                                      autonomous=getattr(args, "autonomous", settings.autonomous),
                                      humanize=(False if getattr(args, "no_humanize", False) else None))
    print(f"\n[OK] Created book '{book_id}'.")
    print(f"     Next: python book.py run --book-id {book_id}")


def _cmd_new_article(args, cfg, settings, uid, abstract):
    print("\n== Planning angles ==")
    angles = nodes.plan_article_angles(cfg, abstract).angles
    for i, a in enumerate(angles, 1):
        print(f"\n[{i}] {a.title}\n    {a.angle}\n    audience: {a.audience} | hook: {a.hook}")
    idx = args.pick or int(input(f"\nPick an angle [1-{len(angles)}]: ").strip())
    chosen = angles[idx - 1]
    num_sections = args.chapters or settings.num_sections
    max_rev = args.max_revisions if args.max_revisions is not None else settings.max_revisions
    print(f"\n-> {chosen.title}\n== Building outline ==")
    article_id = orchestrator.start_article(cfg, settings, uid, abstract, chosen,
                                            args.book_id, num_sections, max_rev,
                                            autonomous=getattr(args, "autonomous", settings.autonomous),
                                            humanize=(False if getattr(args, "no_humanize", False) else None))
    print(f"\n[OK] Created article '{article_id}'.")
    print(f"     Next: python book.py run --book-id {article_id}")


def cmd_run(args, cfg, settings, uid):
    orchestrator.run(cfg, uid, _resolve_book(uid, args.book_id),
                     force=getattr(args, "force", False))


def cmd_status(args, cfg, settings, uid):
    st = orchestrator.status(uid, _resolve_book(uid, args.book_id))
    mode = st.get("mode", "book")
    print(f"mode: {mode}  |  phase: {st.get('phase')}")
    if mode == "article":
        print(f"section: {st.get('current_section')}/{st.get('num_sections')} "
              f"(committed {st.get('committed')})")
    else:
        print(f"chapter: {st.get('current_chapter')}/{st.get('num_chapters')} "
              f"(committed {st.get('committed')})")
    print(f"pending_review: {st.get('pending_review')}")
    if st.get("open_reviews"):
        print("open reviews: " + ", ".join(st["open_reviews"]))


def cmd_review(args, cfg, settings, uid):
    if args.chapter is None or not args.instruction:
        sys.exit("review needs --chapter and --instruction")
    book_id = _resolve_book(uid, args.book_id)
    orchestrator.record_instruction(uid, book_id, args.chapter, args.instruction)
    print(f"[OK] Recorded instruction for chapter {args.chapter}. Now: python book.py run "
          f"--book-id {book_id}")


def cmd_read(args, cfg, settings, uid):
    paths = BookPaths(_resolve_book(uid, args.book_id), uid)
    if args.manuscript:
        target = paths.manuscript
    elif args.summary:
        target = paths.ch_summary(args.chapter or 1)
    else:
        target = paths.ch(args.chapter or 1)
    text = brain.read_text(target)
    print(text if text else f"(not found: {target})")


def cmd_memory(args, cfg, settings, uid):
    print(orchestrator.memory_summary(uid, _resolve_book(uid, args.book_id)))


def cmd_produce(args, cfg, settings, uid):
    orchestrator.run_production(cfg, uid, _resolve_book(uid, args.book_id))


def cmd_consolidate(args, cfg, settings, uid):
    orchestrator.run_consolidation(cfg, uid, _resolve_book(uid, args.book_id))


def cmd_skills(args, cfg, settings, uid):
    rows = skills_mod.list_skills(uid)
    if not rows:
        print(f"No skills for user '{uid}' yet.")
        return
    for r in rows:
        print(f"- {r['name']:<28} {r['status']:<10} applied={r['applied']} "
              f"p_skill={r['p_skill']} p_base={r['p_base']}")


_EXPORT_FORMATS = ["pdf", "epub", "html", "docx", "txt", "md"]
_EXPORT_FNS = {
    "pdf":  lambda uid, bid: orchestrator.export_pdf(uid, bid),
    "epub": lambda uid, bid: orchestrator.export_epub(uid, bid),
    "html": lambda uid, bid: orchestrator.export_html(uid, bid),
    "docx": lambda uid, bid: orchestrator.export_docx(uid, bid),
    "txt":  lambda uid, bid: orchestrator.export_txt(uid, bid),
    "md":   lambda uid, bid: orchestrator.export_md(uid, bid),
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
    _EXPORT_FNS[fmt](uid, book_id)


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
                          help="Output format — omit to choose interactively")
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
    _COMMANDS[args.command](args, cfg, settings, args.user)


if __name__ == "__main__":
    main()
