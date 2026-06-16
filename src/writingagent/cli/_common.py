"""Shared leaf helpers for the CLI seams: the Rich console, project resolution,
path selection, word counting, the spinner, and the unified diff printer."""
from __future__ import annotations

import sys

from .. import brain, ui
from ..brain import ArticlePaths, BookPaths

__all__ = [
    "_console",
    "_project_word_count",
    "_paths_for",
    "_resolve_book",
    "_spin",
    "_print_diff",
]

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


def _spin(label: str, fn):
    """Run a slow LLM call under a spinner when a Rich console is available."""
    console = _console()
    if console:
        with console.status(f"[{ui.GOLD}]{label}[/]", spinner="dots", spinner_style=ui.GOLD):
            return fn()
    print(f"\n== {label} ==")
    return fn()


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
