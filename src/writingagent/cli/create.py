"""Project creation: the `new` command (book/article), the manual-mode outline gate,
and the autonomous-flag resolution shared by `new` and `write`."""
from __future__ import annotations

import sys

from .. import brain, nodes, orchestrator
from ..brain import ArticlePaths, BookPaths
from ._common import _spin

__all__ = [
    "cmd_new",
    "_cmd_new_book",
    "_cmd_new_article",
    "_outline_gate",
    "_autonomous_value",
]


def cmd_new(args, cfg, settings, uid):
    from .. import skills as skills_mod
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
    print(f"     Next: python writingagent.py run --book-id {book_id}")


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
    print(f"     Next: python writingagent.py run --book-id {article_id}")


def _autonomous_value(args, settings) -> bool:
    """Resolve the autonomous flag. An explicit --autonomous / --no-autonomous wins;
    otherwise fall back to settings.autonomous. (The old `store_true` default of False
    silently shadowed the setting, so `autonomous: true` never took effect.)"""
    flag = getattr(args, "autonomous", None)
    return settings.autonomous if flag is None else flag
