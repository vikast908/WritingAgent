"""Project lifecycle / state helpers: delete a project, record a review instruction,
flip autonomous<->manual on an existing run, read run status, and summarize the canon.
Used by the CLI/API and the run loop. Leaf-level (brain/store only).
"""
from __future__ import annotations

from .. import brain
from ..brain import ArticlePaths, BookPaths
from ..store import Store

__all__ = [
    'delete_book',
    'record_instruction',
    'apply_autonomous',
    'apply_controller',
    'status',
    'memory_summary',
]


def delete_book(uid: str, book_id: str) -> None:
    """Permanently delete a project (book or article) and its index database."""
    import shutil

    # Refuse traversal/absolute ids, and never rmtree a path outside the brain dir.
    if not (brain.is_safe_id(uid) and brain.is_safe_id(book_id)):
        raise ValueError(f"Refusing to delete: unsafe id '{book_id}'.")
    _brain_root = brain.BRAIN.resolve()

    def _confine(p):
        if _brain_root not in p.resolve().parents:
            raise ValueError(f"Refusing to delete a path outside the brain: {p}")

    def _rmtree(root):
        _confine(root)
        try:
            shutil.rmtree(root)
        except PermissionError as e:
            # A file is locked (e.g. open in Word/LibreOffice on Windows).
            locked = getattr(e, "filename", None) or str(e)
            raise PermissionError(
                f"Cannot delete - a file is open in another program.\n"
                f"  Close it and try again: {locked}"
            ) from None

    art = ArticlePaths(book_id, uid)
    if art.root.exists():
        _rmtree(art.root)
        if art.index_db.exists():
            art.index_db.unlink(missing_ok=True)
        return
    paths = BookPaths(book_id, uid)
    if not paths.root.exists():
        raise FileNotFoundError(f"Project '{book_id}' not found.")
    _rmtree(paths.root)
    if paths.index_db.exists():
        paths.index_db.unlink(missing_ok=True)


def record_instruction(uid: str, book_id: str, n: int, instruction: str) -> None:
    art = ArticlePaths(book_id, uid)
    if art.run_state.exists():
        brain.append_text(art.instruction_of(n), instruction)
        brain.append_text(art.revision_log, f"## Section {n} human instruction\n{instruction}")
        state = brain.read_json(art.run_state) or {}
        state["pending_review"] = False
        state["review_kind"] = None
        brain.write_json(art.run_state, state)
        return
    paths = BookPaths(book_id, uid)
    brain.append_text(paths.instruction_of(n), instruction)
    brain.append_text(paths.revision_log, f"## Chapter {n} human instruction\n{instruction}")
    state = brain.read_json(paths.run_state) or {}
    state["pending_review"] = False
    state["review_kind"] = None
    brain.write_json(paths.run_state, state)


def apply_autonomous(uid: str, book_id: str, autonomous: bool, settings) -> dict | None:
    """Switch an existing project between autonomous and manual run modes.

    `autonomous` is baked into the run_state at creation (start_book/start_article),
    so flipping it afterwards means rewriting that state: re-derive the escalation
    thresholds the orchestrator reads each run, and - when turning autonomous ON over
    a chapter/section that already escalated - clear the pending review so the next
    `run` resumes and commits the best draft instead of waiting for a human.
    Consolidation reviews still gate on `--force`, so those are left untouched.

    Returns the updated state, or None if the project has no run_state.
    """
    art = ArticlePaths(book_id, uid)
    paths = art if art.run_state.exists() else BookPaths(book_id, uid)
    state = brain.read_json(paths.run_state)
    if state is None:
        return None
    state["autonomous"] = autonomous
    state["escalate_below_confidence"] = (
        0.0 if autonomous else settings.escalate_below_confidence)
    state["escalate_on_contradiction"] = (
        False if autonomous else settings.escalate_on_contradiction)
    if (autonomous and state.get("pending_review")
            and state.get("review_kind") in ("chapter", "section")):
        state["pending_review"] = False
        state["review_kind"] = None
    brain.write_json(paths.run_state, state)
    return state


def apply_controller(uid: str, book_id: str, agentic: bool, settings) -> dict | None:
    """Switch an existing project between the agentic controller and the fixed pipeline.

    The controller is baked into the run_state at creation (start_book/start_article),
    so flipping it afterwards means rewriting that state: set ``controller`` and re-derive
    the controller's policy from settings, so an existing project can become agentic (or go
    back to the pipeline) without recreating it.

    Returns the updated state, or None if the project has no run_state.
    """
    art = ArticlePaths(book_id, uid)
    paths = art if art.run_state.exists() else BookPaths(book_id, uid)
    state = brain.read_json(paths.run_state)
    if state is None:
        return None
    state["controller"] = "agentic" if agentic else "pipeline"
    state["agentic_policy"] = settings.agentic_policy
    brain.write_json(paths.run_state, state)
    return state


def status(uid: str, book_id: str) -> dict:
    art = ArticlePaths(book_id, uid)
    if art.run_state.exists():
        state = brain.read_json(art.run_state) or {}
        return {**state, "open_reviews": []}
    paths = BookPaths(book_id, uid)
    state = brain.read_json(paths.run_state) or {}
    pending = sorted(p.name for p in paths.reviews.glob("ch*.md")) if paths.reviews.exists() else []
    return {**state, "open_reviews": pending}


def memory_summary(uid: str, book_id: str) -> str:
    art = ArticlePaths(book_id, uid)
    if art.run_state.exists():
        return "(memory not available for articles)"
    paths = BookPaths(book_id, uid)
    store = Store.open(paths)
    try:
        return store.memory_summary()
    finally:
        store.close()
