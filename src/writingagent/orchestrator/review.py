"""Human-in-the-loop review + evaluation surface: approve a stalled escalation,
revise a committed chapter/section, run a persona table-read, and score a finished
project. Sits above the book and article pipelines (imports from both).
"""
from __future__ import annotations

import re

from .. import brain, humanizer, llm, nodes, retrieval
from .. import schemas as S
from ..brain import ArticlePaths, BookPaths
from ..config import ModelConfig
from ..store import Store
from .article import (
    _commit_section,
    _rewrite_section_draft,
    _save_and_patch_section,
)
from .book import _commit, run_production
from .common import (
    _length_note,
    _load,
    _manuscript_section_bodies,
    _merge_fix_notes,
    _save_version,
)

__all__ = [
    'approve_escalation',
    '_confirm_revision',
    'run_table_read',
    'evaluate_project',
    'revise_unit',
]


def approve_escalation(cfg: ModelConfig, uid: str, book_id: str, *, log=print) -> dict | None:
    """Commit a stalled (escalated) chapter/section draft AS-IS - the human read it and
    decided the critic was wrong. Runs the normal commit path (summary, canon, humanize)
    so continuity for later units is intact, then clears the review so `run` resumes.

    Returns the updated state, or None when there is nothing pending to approve."""
    art = ArticlePaths(book_id, uid)
    if art.run_state.exists():
        state = brain.read_json(art.run_state) or {}
        n = state.get("current_section")
        draft = brain.read_text(art.section_draft(n)) if n else None
        if not (state.get("pending_review") and draft):
            return None
        outline = S.ArticleOutline(**brain.read_json(art.outline_json))
        _commit_section(cfg, art, outline.sections[n - 1], n, draft, [], [], False,
                        log, humanize=bool(state.get("humanize")))
        art.section_draft(n).unlink(missing_ok=True)
        state.update(pending_review=False, review_kind=None,
                     committed=state.get("committed", 0) + 1, current_section=n + 1)
        brain.write_json(art.run_state, state)
        log(f"[OK] Section {n} approved as-is. Run `run` to continue.")
        return state
    paths, state, plan, toc = _load(uid, book_id)
    n = state.get("current_chapter")
    draft = brain.read_text(paths.ch_draft(n)) if n else None
    if not (state.get("pending_review") and draft):
        return None
    store = Store.open(paths)
    try:
        _commit(cfg, paths, plan, toc.chapters[n - 1], store, n, draft, [], False,
                log, humanize=bool(state.get("humanize")), sources=[])
    finally:
        store.close()
    paths.ch_draft(n).unlink(missing_ok=True)
    state.update(pending_review=False, review_kind=None,
                 committed=state.get("committed", 0) + 1, current_chapter=n + 1)
    brain.write_json(paths.run_state, state)
    log(f"[OK] Chapter {n} approved as-is. Run `run` to continue.")
    return state


# ── Post-completion revision (`revise` command) ───────────────────────────────
def _confirm_revision(cfg, old: str, new: str, confirm, log) -> bool:
    """Show the semantic change summary, then let `confirm` gate the write.
    No callback (CLI/non-TTY/chat) = auto-accept, with the summary still logged."""
    summary = ""
    try:
        summary = nodes.change_summary(cfg, old, new)
    except Exception:  # noqa: BLE001 - the summary is informative, never blocking
        pass
    if summary:
        log("   what changed (semantic):\n" + summary)
    if confirm is not None and not confirm(old, new, summary):
        log("[i] revision discarded - nothing was changed.")
        return False
    return True


def run_table_read(cfg: ModelConfig, uid: str, book_id: str, persona: str | None = None,
                   *, log=print):
    """On-demand table read of a finished manuscript, optionally as a specific persona.
    Returns the report path. Works for articles and (via a pseudo-outline) books."""
    llm.set_project(book_id)
    art = ArticlePaths(book_id, uid)
    if art.run_state.exists():
        paths = art
        outline = S.ArticleOutline(**brain.read_json(art.outline_json))
    else:
        paths = BookPaths(book_id, uid)
        plan = S.BookPlan(**(brain.read_json(paths.root / "plan.json") or {}))
        outline = S.ArticleOutline(title=plan.title, angle=f"{plan.premise} ({plan.audience})",
                                   target_word_count=0, sections=[])
    body = brain.read_text(paths.manuscript)
    if not body:
        raise FileNotFoundError(f"No manuscript for '{book_id}'. Run it first.")
    log(f"   table read{' as: ' + persona if persona else ''}...")
    report = nodes.table_read(cfg, outline, body, persona=persona)
    name = f"table_read_{brain.slugify(persona)}.md" if persona else "table_read.md"
    out = paths.root / name
    brain.write_text(out, report)
    log(f"[OK] reader report -> {out}")
    return out


def evaluate_project(cfg: ModelConfig, uid: str, book_id: str, *, log=print) -> dict:
    """Post-hoc quality report (`eval`): deterministic metrics + a pro-model rubric.

    Deterministic side: words, AI-tell count (the humanizer's lexicon as a scanner),
    structural style metrics, citation/source coverage. Judged side: 5-dimension
    rubric with quote-backed strengths/weaknesses. Writes eval_report.md and returns
    {"scores": {...}, "metrics": {...}, "report_path": Path}."""
    llm.set_project(book_id)
    art = ArticlePaths(book_id, uid)
    is_article = art.run_state.exists()
    paths = art if is_article else BookPaths(book_id, uid)
    body = brain.read_text(paths.manuscript)
    if not body:
        raise FileNotFoundError(f"No manuscript for '{book_id}'. Run it first.")

    if is_article:
        outline = S.ArticleOutline(**brain.read_json(art.outline_json))
        context = f"{outline.title} - {outline.angle}"
        thesis = brain.read_text(art.root / "thesis.md")
        if thesis:
            context += "\n\nThesis:\n" + thesis
    else:
        plan = S.BookPlan(**(brain.read_json(paths.root / "plan.json") or {}))
        context = f"{plan.title} ({plan.genre}) - {plan.premise}; audience: {plan.audience}"

    # Deterministic metrics - free, reproducible, no judge noise.
    tells = humanizer.find_tell_sentences(body, cap=999)
    citations = len(set(re.findall(r"\[(\d+)\]", body)))
    sources = len(brain.read_json(paths.sources_json) or [])
    metrics = {
        "words": len(body.split()),
        "ai_tells": len(tells),
        "citations": citations,
        "verified_sources": sources,
        "structural": humanizer.structural_report(body),
    }

    log("   judging against the rubric (pro model, whole manuscript)...")
    ev = nodes.evaluate_manuscript(cfg, context, body)
    scores = {"insight": ev.insight, "clarity": ev.clarity, "structure": ev.structure,
              "evidence": ev.evidence, "persuasiveness": ev.persuasiveness}

    lines = [f"# Quality report - {book_id}", "",
             "## Scores (1-5, judged against published work in genre)", ""]
    lines += [f"- **{k}**: {v}/5" for k, v in scores.items()]
    lines += ["", "## Deterministic metrics", "",
              f"- words: {metrics['words']:,}",
              f"- AI-tell sentences remaining: {metrics['ai_tells']}",
              f"- citations: {metrics['citations']} in text · "
              f"{metrics['verified_sources']} verified sources",
              metrics["structural"], "",
              "## Strengths", *(f"- {s}" for s in ev.strengths), "",
              "## Weaknesses", *(f"- {w}" for w in ev.weaknesses), "",
              "## Verdict", ev.summary, "",
              "_Act on weaknesses with:  revise --chapter N --instruction \"...\"_"]
    report_path = paths.root / "eval_report.md"
    brain.write_text(report_path, "\n".join(lines))
    log(f"[OK] eval report -> {report_path}")
    return {"scores": scores, "metrics": metrics, "report_path": report_path,
            "strengths": ev.strengths, "weaknesses": ev.weaknesses, "summary": ev.summary}


def revise_unit(cfg: ModelConfig, uid: str, book_id: str, n: int, instruction: str,
                *, log=print, confirm=None) -> None:
    """Rewrite ONE chapter/section of a finished (or in-progress) piece to the human's
    instruction, re-critique once, and patch the committed file + assembled manuscript.
    Closes the gap between 'pipeline done' and 'author satisfied' without a full re-run.

    `confirm(old, new, semantic_summary) -> bool`, when given, gates the write: the
    caller shows a diff and the human accepts or discards (nothing is touched on
    discard). Books: the chapter file is rewritten and production re-assembles the
    manuscript. Canon is NOT re-extracted (a post-completion polish must not mutate
    the knowledge base later chapters were already written against)."""
    llm.reset_usage()
    llm.set_project(book_id)

    art = ArticlePaths(book_id, uid)
    if art.run_state.exists():
        state = brain.read_json(art.run_state) or {}
        outline = S.ArticleOutline(**brain.read_json(art.outline_json))
        if not (1 <= n <= len(outline.sections)):
            raise ValueError(f"Section {n} out of range (1-{len(outline.sections)}).")
        section = outline.sections[n - 1]
        base = brain.read_text(art.section(n))
        ms = brain.read_text(art.manuscript) or ""
        if base is None:   # finished article - per-section files were cleaned up
            bodies = _manuscript_section_bodies(ms)
            if n > len(bodies):
                raise FileNotFoundError(f"Section {n} not found in the manuscript.")
            base = bodies[n - 1]
        # Shared rewrite half (write -> critique -> one fix pass -> humanize -> strip),
        # with the interactive progress logs. The critic gets the same context the pipeline
        # critic had: prior-section summaries (empty after cleanup - acceptable), watch-list,
        # intake, length. (Historically the writer calls here carried no per-section target.)
        draft = _rewrite_section_draft(cfg, art, outline, state, section, n, instruction,
                                       base, log=log, verbose=True)
        if not _confirm_revision(cfg, base, draft, confirm, log):
            return
        _save_and_patch_section(art, n, draft, ms, instruction,
                                save_label="revise", log_label="post-completion revision")
        log(f"[OK] Section {n} revised. Re-export to refresh output files.")
        return

    paths, state, plan, toc = _load(uid, book_id)
    register = state.get("register") or None
    voice = brain.style_exemplars(uid, register)
    if not (1 <= n <= len(toc.chapters)):
        raise ValueError(f"Chapter {n} out of range (1-{len(toc.chapters)}).")
    blueprint = toc.chapters[n - 1]
    base = brain.read_text(paths.ch(n))
    if base is None:
        raise FileNotFoundError(f"Chapter {n} has not been committed yet - use `review` instead.")
    # Same context the pipeline critic had: canon + dependency summaries + excerpts,
    # watch-list, intake, length target.
    watch = brain.read_text(brain.watch_list(uid))
    requirements = (state.get("intake") or "").strip() or None
    store = Store.open(paths)
    try:
        context = retrieval.assemble_context(store, paths, blueprint)
    finally:
        store.close()
    log(f"== Revising chapter {n}: {blueprint.title} ==")
    log("   rewriting to your instruction...")
    draft = nodes.write_chapter(cfg, plan, blueprint, fix_notes=instruction,
                                base_draft=base, voice=voice,
                                requirements=requirements, register=register)
    log("   critiquing...")
    crit = nodes.critique_chapter(
        cfg, plan, blueprint, draft, context=context, watch_list=watch,
        requirements=requirements, register=register,
        length_note=_length_note(len(draft.split()), blueprint.target_words))
    if crit.blocking and crit.verdict != "approve":
        log(f"   {len(crit.blocking)} blocking issue(s) - one fix pass...")
        draft = nodes.write_chapter(cfg, plan, blueprint,
                                    fix_notes=_merge_fix_notes(instruction, crit),
                                    base_draft=draft, voice=voice,
                                    requirements=requirements, register=register)
    if state.get("humanize"):
        log("   humanizing...")
        draft = humanizer.humanize(cfg, draft, register)
    if not _confirm_revision(cfg, base, draft, confirm, log):
        return
    _save_version(paths, f"ch{n:02d}", draft, label="revise")
    brain.write_text(paths.ch(n), draft)
    brain.append_text(paths.revision_log, f"## Chapter {n} post-completion revision\n{instruction}")
    if brain.read_text(paths.manuscript):
        log("   re-assembling manuscript...")
        run_production(cfg, uid, book_id, log=log)
    log(f"[OK] Chapter {n} revised. Re-export to refresh output files.")
