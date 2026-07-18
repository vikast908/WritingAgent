"""The article (section) pipeline: outline -> per-section divergent draft/critique/
commit -> assemble -> produce (cohesion + polish) -> learn. Mirrors the book pipeline
in book.py; shared leaf helpers live in common.py. Re-exported via the package facade.
"""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor

from .. import brain, compositor, concurrency, fields, humanizer, llm, nodes, registers, render, retrieval
from .. import schemas as S
from .. import skills as skills_mod
from ..brain import ArticlePaths
from ..config import ModelConfig
from .common import (
    _BUDGET_PAUSE_MSG,
    _CITE,
    _REF_BLOCK,
    _apply_run_control,
    _base_run_state,
    _consolidate_section_refs,
    _crit_better,
    _deep_docs,
    _divergent_first_draft,
    _draft_glimpse,
    _escalate,
    _finalize_unit,
    _insight_note,
    _length_note,
    _log_run_complete,
    _manuscript_section_bodies,
    _mark_escalated,
    _merge_fix_notes,
    _record_author,
    _record_preference,
    _register_sources,
    _renumber_citations,
    _reoutline_units,
    _replace_manuscript_section,
    _research_brief_prefix,
    _revise_weakest_unit,
    _run_learner,
    _save_version,
    _strip_section_prefix,
    _svg_diagram_figure,
    _verify_claims_gate,
    _with_intake,
    _writer_tool_runner,
    reconcile_unit_images,
)
from .export import _unique_sources, build_evidence_report

__all__ = [
    'start_article',
    '_run_article',
    '_section_fetch',
    '_process_article_section',
    '_commit_section',
    '_assemble_article_context',
    '_produce_article',
    '_apply_top_reader_fix',
    '_rewrite_section_draft',
    '_save_and_patch_section',
    '_targeted_section_revise',
    '_learn_article',
]


def start_article(
    cfg: ModelConfig, settings, uid: str, abstract: str,
    chosen: S.ArticleAngle, article_id_override: str | None,
    num_sections: int, max_revisions: int,
    autonomous: bool = False, humanize: bool | None = None,
    intake: str | None = None, author: str | None = None,
) -> str:
    from ..config import apply_cost_mode
    cfg, settings, _cost = apply_cost_mode(cfg, settings)   # budget mode pins lean knobs
    if getattr(settings, "cost_mode", "standard") == "budget":
        max_revisions = min(max_revisions, settings.max_revisions)  # the arg bakes into state
    # SEO from the start (plan §24.1): thread a target keyword into the writer + critic via the
    # intake, so the piece is written FOR it (title/opening/headings) instead of scored against
    # it after the fact. Post-validation apply_seo then locks in the title/meta.
    kw = (getattr(settings, "seo_keyword", "") or "").strip()
    if kw:
        seo_line = (f"SEO: the piece targets the primary search keyword \"{kw}\". Use it naturally "
                    "in the title, the opening paragraph, and at least one subheading; weave close "
                    "variants through the body. Do not keyword-stuff.")
        intake = (intake.rstrip() + "\n\n" + seo_line) if intake else seo_line
    brain.ensure_user(uid)
    _record_author(uid, author)
    # Register/field (plan §22): inferred from the editorial angle unless pinned in settings.
    register = registers.infer(chosen.angle if chosen else "", "article",
                               explicit=getattr(settings, "register", ""))
    outline = nodes.build_article_outline(
        cfg, _with_intake(abstract, intake), chosen, num_sections,
        structure=fields.resolve(register, getattr(settings, "field", "")))
    article_id = article_id_override or brain.slugify(outline.title)
    paths = ArticlePaths(article_id, uid).ensure()

    brain.write_json(paths.angle_json, chosen.model_dump())
    brain.write_json(paths.outline_json, outline.model_dump())
    brain.write_text(paths.outline_md, render.render_outline_md(outline))
    if intake:
        brain.write_text(paths.root / "intake.md", intake)

    # The thesis: the piece's contestable argument. Generated once here, injected into
    # every section's writer + critic call - the difference between arguing and covering.
    thesis = nodes.generate_thesis(cfg, abstract, chosen, outline)
    brain.write_json(paths.root / "thesis.json", thesis.model_dump())
    brain.write_text(paths.root / "thesis.md", nodes.render_thesis(thesis))

    state = {
        **_base_run_state(uid, abstract, intake=intake, author=author,
                          max_revisions=max_revisions, autonomous=autonomous,
                          humanize=humanize, settings=settings),
        "article_id": article_id, "mode": "article",
        "phase": "sections", "num_sections": len(outline.sections),
        "current_section": 1,
        # Genre/register profile (plan §22): tailors the anti-slop contract, craft metrics,
        # style anchor, the critic's register overrides, and the outline field structure.
        "register": register,
        "field": getattr(settings, "field", "") or "",
        "citation_style": getattr(settings, "citation_style", "") or "",
        "article_cohesion": settings.article_cohesion,
        "strip_inline_citations": settings.strip_inline_citations,
        "rank_references": settings.rank_references,
        "table_read": settings.table_read,
        "table_read_revise": settings.table_read_revise,
        "divergent_skeletons": settings.divergent_skeletons,
        "verify_claims": settings.verify_claims,
        "escalate_on_contradiction": False,
    }
    brain.write_json(paths.run_state, state)
    return article_id


def _run_article(cfg, paths: ArticlePaths, state, outline, *, force, log, ask=None, control=None):
    if state.get("pending_review"):
        log(f"[!] Section {state['current_section']} awaits review. "
            f"Run: review --chapter {state['current_section']} --instruction \"...\"")
        return state

    prefetch: dict[int, object] = {}
    pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="unit-prefetch")
    try:
        # Macro-agentic path (plan §21.3): a RunPolicy chooses the next macro-action over the
        # whole article. The DEFAULT policy stays on the legacy loop below, so the equivalence
        # guarantee + the unit-only trace are untouched; only llm/trace policies drive run_loop.
        if state.get("controller") == "agentic" and state.get("agentic_policy") in ("llm", "trace"):
            from .. import agentic
            agentic.run_loop(cfg, state, log=log, run_ops=_article_run_ops(
                cfg, paths, outline, prefetch, pool, log, ask, control))
            return _finish_article(paths, state, log)
        while state["phase"] != "done":
            if _apply_run_control(control, state, paths, log):
                return state
            phase = state["phase"]
            llm.set_unit(phase)
            if phase == "sections":
                n = state["current_section"]
                if n > state["num_sections"]:
                    state["phase"] = "produce"
                    brain.write_json(paths.run_state, state)
                    continue
                # Prefetch section n+1's research/images/skills while section n is
                # being written/critiqued (see the book loop in run()).
                for k in (n, n + 1):
                    if (k <= state["num_sections"] and k not in prefetch
                            and brain.read_text(paths.section(k)) is None):
                        prefetch[k] = pool.submit(
                            _section_fetch, cfg, paths, outline, state, k, log)
                pf = prefetch.pop(n, None)
                if state.get("controller") == "agentic":
                    # Self-directing path (plan §21): gather research / prior-section
                    # context before drafting; `draft` is the unchanged section episode.
                    from .. import agentic
                    section = outline.sections[n - 1]
                    ops = agentic.UnitOps(
                        paths=paths, unit_label=f"sec{n:02d}",
                        research_on=bool(state.get("use_researcher")), has_canon=(n > 1),
                        draft=lambda extra, _pf=pf, _n=n: _process_article_section(
                            cfg, paths, outline, state, _n, log,
                            prefetched=_pf, ask=ask, extra_context=extra),
                        research=lambda q, _sec=section: agentic.unit_research_article(
                            cfg, outline, _sec, q, log),
                        read_canon=lambda q, _n=n: _assemble_article_context(paths, _n),
                    )
                    outcome = agentic.run_unit(cfg, state, ops=ops, log=log)
                else:
                    outcome = _process_article_section(cfg, paths, outline, state, n, log,
                                                       prefetched=pf, ask=ask)
                if outcome == "escalate":
                    _mark_escalated(state, paths, "section",
                                    f"[!] Section {n} escalated. Resolve with `review` then `run`.", log)
                    return state
                state["committed"] += 1
                state["current_section"] = n + 1
                brain.write_json(paths.run_state, state)
            elif phase == "produce":
                _produce_article(cfg, paths, outline, state, log=log)
                state["phase"] = "learn"
                brain.write_json(paths.run_state, state)
            elif phase == "learn":
                _learn_article(cfg, paths, outline, log=log)
                # Clean up intermediates only AFTER learning - the learner reads the
                # eval_*.json critic findings that cleanup deletes.
                paths.cleanup_sections()
                state["phase"] = "done"
                brain.write_json(paths.run_state, state)
    except llm.BudgetExceeded as e:
        log(_BUDGET_PAUSE_MSG.format(err=e))
        return state
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return _finish_article(paths, state, log)


def _finish_article(paths, state, log) -> dict:
    """Completion footer - only when the run actually reached `done` (not a pause)."""
    if state.get("phase") == "done":
        _log_run_complete("Article", paths.article_id, paths.manuscript, log)
    return state


# Caps on the agent's optional structural moves (bounded autonomy; token budget is the backstop).
_MAX_REOUTLINE = 2
_MAX_REVISE = 3


def _section_tool_runner(cfg, outline, section, paths, n, state, log):
    """(tools, runner) for the writer's in-generation tool use on a section (plan §21 Phase 3).
    The writer may call `research` (a web brief) or `read_canon` (prior-section context) WHILE
    drafting; the runner dispatches to the same implementations the unit controller uses."""
    from .. import agentic
    return _writer_tool_runner(
        state,
        research=lambda q: agentic.unit_research_article(cfg, outline, section, q, log),
        read_canon=lambda q: _assemble_article_context(paths, n))


def _article_run_ops(cfg, paths: ArticlePaths, outline, prefetch, pool, log, ask, control):
    """Build the RunOps the macro-controller drives for an article (plan §21.3).

    Article structure is linear (draft each section -> produce -> learn -> done), so the
    legal set is one action per step and the LLM/trace policy follows it; the real
    self-direction is at the unit level (research/read_canon before each section, via the
    unit controller invoked inside the `draft` action)."""
    from .. import agentic

    def _draft(state, log):
        n = state["current_section"]
        for k in (n, n + 1):
            if (k <= state["num_sections"] and k not in prefetch
                    and brain.read_text(paths.section(k)) is None):
                prefetch[k] = pool.submit(_section_fetch, cfg, paths, outline, state, k, log)
        pf = prefetch.pop(n, None)
        section = outline.sections[n - 1]
        ops = agentic.UnitOps(
            paths=paths, unit_label=f"sec{n:02d}",
            research_on=bool(state.get("use_researcher")), has_canon=(n > 1),
            draft=lambda extra, _pf=pf, _n=n: _process_article_section(
                cfg, paths, outline, state, _n, log, prefetched=_pf, ask=ask, extra_context=extra),
            research=lambda q, _sec=section: agentic.unit_research_article(cfg, outline, _sec, q, log),
            read_canon=lambda q, _n=n: _assemble_article_context(paths, _n),
        )
        outcome = agentic.run_unit(cfg, state, ops=ops, log=log)
        if outcome == "escalate":
            _mark_escalated(state, paths, "section",
                            f"[!] Section {n} escalated. Resolve with `review` then `run`.", log)
            return "pause"
        state["committed"] += 1
        state["current_section"] = n + 1
        if state["current_section"] > state["num_sections"]:
            state["phase"] = "produce"
        brain.write_json(paths.run_state, state)
        return "continue"

    def _reoutline(state, log):
        """Regenerate the not-yet-written sections' plan (committed sections + total count
        preserved), so the agent can fix a plan that's going wrong (§21 #2/#4)."""
        from .. import schemas as S

        def _build(count):
            angle = S.ArticleAngle(title=getattr(outline, "title", "") or "",
                                   angle=getattr(outline, "angle", "") or "",
                                   audience=getattr(outline, "audience", "") or "", hook="")
            return nodes.build_article_outline(
                cfg, state.get("abstract", ""), angle, count,
                structure=fields.resolve(state.get("register"), state.get("field", ""))).sections
        return _reoutline_units(
            state, paths, unit_word="section", current_key="current_section",
            count_key="num_sections", units=outline.sections, build_fresh=_build,
            persist=lambda: brain.write_json(paths.outline_json, outline.model_dump()), log=log)

    def _revise(state, log):
        """Rewrite the weakest committed section to lift its score (§21 #3)."""
        return _revise_weakest_unit(
            state, paths, unit_prefix="sec", unit_word="section",
            committed_path=paths.section, draft_path=paths.section_draft,
            process=lambda n: _process_article_section(cfg, paths, outline, state, n, log, ask=ask),
            log=log)

    def dispatch(action, state, log):
        llm.set_unit(state.get("phase"))
        if action == "draft":
            return _draft(state, log)
        if action == "reoutline":
            return _reoutline(state, log)
        if action == "revise":
            return _revise(state, log)
        if action == "escalate":
            _mark_escalated(state, paths, "section",
                            "[!] Controller escalated. Resolve with `review` then `run`.", log)
            return "pause"
        if action == "produce":
            _produce_article(cfg, paths, outline, state, log=log)
            state["phase"] = "learn"
            brain.write_json(paths.run_state, state)
            return "continue"
        if action == "learn":
            _learn_article(cfg, paths, outline, log=log)
            paths.cleanup_sections()
            state["phase"] = "done"
            brain.write_json(paths.run_state, state)
            return "continue"
        return "continue"

    def legal_actions(state):
        phase = state.get("phase")
        if phase == "done":
            return []
        acts: list[str] = []
        if phase == "sections":
            acts.append("draft")
            if state.get("reoutlines", 0) < _MAX_REOUTLINE:
                acts.append("reoutline")
        elif phase == "produce":
            acts.append("produce")
        elif phase == "learn":
            acts.append("learn")
        # revise a weak committed unit any time before assembly (drafting or about to produce).
        if (phase in ("sections", "produce") and state.get("committed", 0) >= 1
                and state.get("revisions_done", 0) < _MAX_REVISE):
            acts.append("revise")
        acts.append("escalate")                               # the agent may always defer
        return acts

    def default_next(state):
        phase = state.get("phase")
        return {"sections": "draft", "produce": "produce", "learn": "learn"}.get(phase, "done")

    return agentic.RunOps(
        paths=paths, legal_actions=legal_actions, default_next=default_next, dispatch=dispatch,
        step_budget=lambda st: st.get("num_sections", 6) + _MAX_REOUTLINE + _MAX_REVISE + 4,
        control_check=lambda st: _apply_run_control(control, st, paths, log))


def _section_fetch(cfg, paths: ArticlePaths, outline, state, n, log) -> dict:
    """Network-bound inputs for section n (research, images, skills) - independent of
    any section's prose, so _run_article prefetches it for section n+1 (see
    _chapter_fetch)."""
    from types import SimpleNamespace
    section = outline.sections[n - 1]

    def _do_research():
        # Returns (brief_prefix, sources, source_text). source_text is the raw fetched
        # material (deep: full page text; shallow: search snippets) - the ground truth the
        # claim-verification gate checks cited claims against. Empty when research is off.
        if not state.get("use_researcher"):
            return ("", [], "")
        from .. import search as search_mod
        base_query = section.search_query or f"{outline.title} {section.heading}"
        if state.get("deep_research"):
            from .. import deep_research as dr
            docs = _deep_docs(
                cfg, f"{outline.title} ({outline.angle})",
                f"{section.heading}. {section.purpose}", base_query, log=log)
            # Two strengths from the same fetch: a short excerpt for SYNTHESIS (token
            # cost) and the full fetched text as the VERIFICATION ground truth - the
            # claim gate BLOCKS on "unsupported", so it must read the whole page, not
            # the synthesis cut (a true claim past char 1500 is not a fabrication).
            synth_text = dr.format_documents(docs) or ""
            vchars = int(state.get("verify_excerpt_chars") or 0)
            source_text = dr.format_documents(
                docs, excerpt_chars=vchars if vchars > 0 else 10**9) or ""
            brief = nodes.deep_research_article(cfg, outline, section, synth_text or None)
            # Real fetched sources are more reliable than LLM-copied URLs; prefer them.
            sources = [S.Source(title=d.title, url=d.url) for d in docs] or list(brief.sources)
            prefix = _research_brief_prefix(brief.facts, brief.style_cues, sources=sources)
            return (prefix, sources, source_text)
        results = search_mod.web_search(base_query, max_results=5)
        web_results = search_mod.format_results(results)
        if results:
            log(f"   fetched {len(results)} web result(s) for: {base_query[:60]}")
        brief = nodes.research_article(cfg, outline, section, web_results=web_results or None)
        prefix = _research_brief_prefix(brief.facts, brief.style_cues, sources=brief.sources)
        return (prefix, brief.sources, web_results or "")

    def _do_images():
        if not (state.get("use_images") and section.include_image):
            return None
        from .. import images as img_mod
        ctx = getattr(section, "purpose", "") or getattr(section, "heading", "")
        # image_source=generate: make one with an image model first; any failure falls
        # through to the Wikimedia fetch, then to an SVG diagram (the original chain).
        if state.get("image_source") == "generate":
            prompt = (f'A clean, professional editorial illustration for a section titled '
                      f'"{section.heading}" in a piece about {outline.title}. {ctx} '
                      f'No text, captions, or watermarks in the image.')
            gen = img_mod.generate_image(
                section.heading, prompt, paths.images / f"section_{n:02d}_gen.png",
                model=state.get("image_model", ""),
                provider_id=state.get("image_provider", ""), log=log)
            if gen:
                return [gen.to_markdown("1")]
        got = img_mod.search_wikimedia(f"{section.heading} {outline.title}", max_results=2)
        if got:
            log(f"   fetched {len(got)} image(s) from Wikimedia Commons")
            return [r.to_markdown(str(i + 1)) for i, r in enumerate(got)]
        # No image - generate an SVG diagram instead
        return _svg_diagram_figure(
            cfg, label=section.heading, context=ctx,
            engine=state.get("diagram_engine", "auto"),
            spec_path=paths.root / "versions" / f"section_{n:02d}.diagram.spec.json",
            svg_path=paths.images / f"section_{n:02d}_diagram.svg", log=log)

    def _do_skills():
        # Skills - use angle as genre proxy
        embed_cache = None
        if state.get("use_embeddings"):
            embed_cache = brain.INDEX_DIR / "embed_cache.json"
        proxy = SimpleNamespace(genre=outline.angle, tone="informative",
                                themes=[outline.title])
        return retrieval.relevant_skills(
            paths.uid, proxy,  # type: ignore[arg-type]
            use_embeddings=bool(state.get("use_embeddings")), embed_cache=embed_cache,
        )

    return concurrency.gather(
        {"research": _do_research, "images": _do_images, "skills": _do_skills})


def _process_article_section(cfg, paths: ArticlePaths, outline, state, n, log,
                             prefetched=None, ask=None, extra_context=None) -> str:
    llm.set_unit(f"sec{n:02d}")
    section = outline.sections[n - 1]

    # Resume guard (see _process_chapter): committed section file present but state
    # not advanced => crash window; don't reprocess.
    if brain.read_text(paths.section(n)) is not None:
        log(f"\n== Section {n}: {section.heading} ==")
        log("   [resume] already committed - advancing")
        return "commit"

    out: dict = {}
    if prefetched is not None:
        try:
            out = prefetched.result()
        except Exception:  # noqa: BLE001 - prefetch is an optimisation, never fatal
            out = {}
    if not out:
        out = _section_fetch(cfg, paths, outline, state, n, log)
    context_prefix, sources, source_text = out.get("research") or ("", [], "")
    images: list[str] | None = out.get("images")

    # Prior section summaries
    article_context = _assemble_article_context(paths, n)
    # extra_context: research/canon the agentic controller gathered before drafting
    # (plan §21.3). None in the fixed pipeline => identical behaviour there.
    prefix = (extra_context.rstrip() + "\n\n") if extra_context else ""
    full_context = (prefix + context_prefix + article_context).strip() or None

    skill_pairs = out.get("skills") or []
    skill_names = [name for name, _ in skill_pairs]
    skill_bodies = [body for _, body in skill_pairs]
    watch = brain.read_text(brain.watch_list(paths.uid))
    requirements = (state.get("intake") or "").strip() or None  # author's upfront answers

    # Per-section word target: the outline's per-section value, falling back to an
    # even share of the article-wide target.
    target = section.target_words or (
        outline.target_word_count // max(1, len(outline.sections))
        if outline.target_word_count else 0)

    instruction = brain.read_text(paths.instruction_of(n))
    fix_notes = instruction
    # After an escalation, revise the draft the human actually reviewed.
    base_draft = brain.read_text(paths.section_draft(n)) if instruction else None
    max_rev = state["max_revisions"]
    threshold = state.get("escalate_below_confidence", 0.0)
    min_insight = int(state.get("min_insight", 0) or 0)
    research_on = bool(state.get("use_researcher"))
    thesis_md = brain.read_text(paths.root / "thesis.md")
    thesis_brief_md = nodes.thesis_brief(thesis_md)   # critic/judge: claim+arguments only (F4)
    skeletons = bool(state.get("divergent_skeletons"))
    register = state.get("register") or None     # genre/register profile (plan §22)
    # Compositor (plan §23): persona voice (register-gated) > user voice > gold + emotion cue.
    voice = compositor.voice(paths.uid, register, state.get("persona"), state.get("emotion"), log=log)
    crit: S.Critique | None = None
    draft = ""
    best: tuple[str, S.Critique] | None = None
    approved_attempt = -1
    # Agentic-only knobs (plan §21): the multi-agent fact-check panel and one bounded
    # mid-unit research pull. Both are no-ops under the fixed pipeline / default policy,
    # so the equivalence guarantee (test_agentic_default_matches_pipeline) holds.
    agentic_on = state.get("controller") == "agentic"
    # The panel runs the same verify_claims node as _verify_claims_gate, so it must inherit
    # that gate's evidence-strength policy (common.py): a snippet-only source is too thin to
    # confidently REFUTE a claim, so the panel may only BLOCK when the ground truth is
    # full-text (deep_research). Otherwise a majority of verifiers reading a 200-char snippet
    # could tank a true claim - the exact false-refutation the verify gate guards against.
    panel_on = (agentic_on and bool(state.get("agentic_factcheck_panel"))
                and bool(source_text) and bool(state.get("deep_research")))
    did_research = False
    # In-generation tool use (plan §21 Phase 3): when enabled, the writer may call research /
    # read_canon WHILE drafting. Built once per section; None => the plain writer.
    _tools, _tool_runner = _section_tool_runner(
        cfg, outline, section, paths, n, state, log) if (agentic_on and state.get("agentic_inline_tools")) \
        else (None, None)

    def _write(notes, base, temperature=None, skeleton=False, skills=None):
        # Skeleton mode (divergent_skeletons, opt-in): divergent variants are drafted short
        # so the judge picks a winner cheaply; only the winner is expanded to full length,
        # cutting discarded-draft completion tokens (~60%). skills= overrides the default set
        # (used by the ablation duel to draft a variant with one skill held out).
        if skeleton:
            notes = ((notes + "\n\n") if notes else "") + (
                "Write a SHORT SKELETON of this section (~one third of target): the thesis "
                "move, the structure as a few topic sentences, and the 2-3 most important "
                "specifics. This draft is for SELECTION, not publication.")
            ln = _length_note(0, max(target // 3, 250)) if target else None
        else:
            ln = _length_note(0, target)
        draft_ = nodes.write_article_section(
            cfg, outline, section, fix_notes=notes, context=full_context,
            skills=skill_bodies if skills is None else skills, images=images, base_draft=base,
            requirements=requirements, thesis=thesis_md, voice=voice,
            length_note=ln, temperature=temperature, register=register,
            tools=_tools, tool_runner=_tool_runner)
        # De-tell BEFORE critique (see book.py:_write): kills the dominant class of
        # pro-tier revision churn and lets the critic review ship-form prose. The
        # commit-time humanize then finds nothing left to rewrite.
        if state.get("humanize"):
            return humanizer.humanize(cfg, draft_, register)
        return humanizer.mechanical_clean(draft_, registers.get(register).allow_em_dash)

    def _critique(d):
        return nodes.critique_article_section(
            cfg, outline, section, d, context=full_context, watch_list=watch,
            requirements=requirements, thesis=thesis_brief_md, research_on=research_on,
            watch_blocking=bool(state.get("watch_blocking", True)),
            length_note=_length_note(len(d.split()), target), register=register)

    n_div = max(1, int(state.get("divergent_drafts", 1) or 1))
    _unit_tag = f"section_{n:02d}"
    _unit_desc = f'section {n}: "{section.heading}"'
    judge_note = ""
    log(f"\n== Section {n}: {section.heading} ==")
    for attempt in range(max_rev + 1):
        if attempt == 0 and n_div > 1 and not base_draft:
            duel = None
            if state.get("skill_duels") and skill_pairs and not skeletons:
                target_skill = skills_mod.pick_duel_target(paths.uid, skill_names)
                if target_skill:
                    duel = {"name": target_skill,
                            "ablated": [b for nm, b in skill_pairs if nm != target_skill]}
            draft, crit, judge_note = _divergent_first_draft(
                cfg, paths, unit_tag=_unit_tag, unit_desc=_unit_desc, n_div=n_div,
                fix_notes=fix_notes, write=_write, critique=_critique,
                thesis_brief=thesis_brief_md, ask=ask,
                autonomous=bool(state.get("autonomous")),
                use_judge=bool(state.get("tournament_judge", True)),
                skeletons=skeletons, log=log, duel=duel)
        else:
            log(f"   writing ({'draft' if attempt == 0 else f'revision {attempt}'})...")
            draft = _write(fix_notes, base_draft)
            _save_version(paths, _unit_tag, draft,
                          label="draft" if attempt == 0 else f"revision {attempt}")
            log("   critiquing...")
            crit = _critique(draft)
        glimpse = _draft_glimpse(draft)
        if glimpse:
            log(f'   · opens: "{glimpse}"')
        # Claim verification: cited claims the source doesn't support become BLOCKING
        # (turns the critic's `evidence` opinion into a structural check).
        crit, verify_note = _verify_claims_gate(cfg, state, draft, source_text, crit, log)
        # Agentic fact-check panel (plan §21.10): before APPROVING, run an adversarial
        # N-voter audit over the same draft. A majority-refute blocks the approval this
        # attempt - the existing revision loop then handles it (bounded by max_rev, after
        # which _finalize_unit's autonomous "commit best" still applies, so it can't hang).
        if panel_on and crit.verdict == "approve":
            from .. import agentic
            passed, _refutes = agentic.panels.fact_check_panel(cfg, draft, source_text, log=log)
            if not passed:
                crit.blocking.append(S.BlockingIssue(
                    type="evidence", where="(fact-check panel)",
                    detail="A majority of independent fact-check verifiers found a cited "
                           "claim the source does not support.",
                    fix="Recheck each cited claim against its source; cite what the source "
                        "actually says, soften the claim, or cut it."))
                crit.verdict = "revise"
        # Agentic critique panel (plan §21.10): a diverse-lens majority review before approving.
        if (agentic_on and bool(state.get("agentic_critique_panel"))
                and crit.verdict == "approve"):
            from .. import agentic

            def _critique_lens(lens, _d=draft, _ctx=full_context, _wl=watch,
                               _tgt=target, _req=requirements, _th=thesis_brief_md, _ro=research_on):
                return nodes.critique_article_section(
                    cfg, outline, section, _d, context=_ctx, watch_list=_wl,
                    length_note=_length_note(len(_d.split()), _tgt), requirements=_req,
                    thesis=_th, research_on=_ro,
                    watch_blocking=bool(state.get("watch_blocking", True)), lens=lens,
                    register=register)
            passed, _blocks = agentic.panels.critique_panel(_critique_lens, log=log)
            if not passed:
                crit.blocking.append(S.BlockingIssue(
                    type="quality", where="(critique panel)",
                    detail="A majority of independent reviewers (distinct lenses) raised a "
                           "blocking concern with this section.",
                    fix="Address the strongest shared concern: tighten vague claims, ground "
                        "them concretely, and cut filler."))
                crit.verdict = "revise"
        brain.write_json(paths.section_eval(n),
                         {"section": n, "attempt": attempt, **crit.model_dump()})
        log(f"   verdict={crit.verdict} confidence={crit.confidence:.2f} "
            f"blocking={len(crit.blocking)} insight={crit.insight}")
        if best is None or _crit_better(crit, best[1]):
            best = (draft, crit)
        low_conf = crit.confidence < threshold
        low_insight = bool(min_insight) and crit.insight < min_insight
        if crit.verdict == "approve" and not low_conf and not low_insight:
            approved_attempt = attempt
            break
        if (crit.verdict == "escalate" or low_conf) and not state.get("autonomous"):
            break
        if attempt == max_rev:
            log("   revision cap reached")
            break
        fix_notes = _merge_fix_notes(instruction, crit)
        if judge_note:
            fix_notes += f"\n\nAlso address the judge's note on the chosen draft: {judge_note}"
            judge_note = ""
        if verify_note:
            fix_notes += "\n\n" + verify_note
        if low_insight and crit.verdict == "approve":
            log(f"   insight {crit.insight}/5 below bar {min_insight} -> sharpening")
            fix_notes = (fix_notes + "\n\n" if fix_notes else "") + _insight_note(crit, min_insight)
        if crit.blocking:
            log(f"   · critic flagged: {crit.blocking[0].detail.strip()[:90]}")
            _record_preference(paths, f"## Revision ({_unit_desc}, attempt {attempt}->{attempt + 1})\n"
                               "Fixed: " + "; ".join(f"{b.type}: {b.detail}"
                                                     for b in crit.blocking[:3]))
        # Phase 3 (plan §21): pull targeted research IN RESPONSE to an evidence gap the
        # critique surfaced, once per unit. Agentic-only + researcher-on, so the fixed
        # pipeline is byte-identical. The brief is prepended to full_context, which the
        # `_write` closure reads by free-var late binding (verified by the Phase-3 test).
        if (agentic_on and research_on and not did_research
                and any(b.type == "evidence" for b in crit.blocking)):
            from .. import agentic
            gap = next(b for b in crit.blocking if b.type == "evidence")
            query = f"{section.heading}: {gap.detail}"[:200]
            brief = agentic.unit_research_article(cfg, outline, section, query, log) or ""
            if brief:
                full_context = (brief.rstrip() + "\n\n" + (full_context or "")).strip() or None
            did_research = True
            agentic.trace.append(paths, {
                "unit": f"sec{n:02d}", "action": "research", "query": query,
                "reason": "evidence gap", "result": f"+{len(brief)} chars"})
        base_draft = draft

    assert crit is not None and best is not None
    if approved_attempt >= 0 or state.get("autonomous"):
        draft, crit, first_pass = _finalize_unit(
            state, approved_attempt=approved_attempt, best=best, draft=draft,
            crit=crit, instruction=instruction, log=log)
        if state.get("craft_passes", True):   # surgical show-don't-tell / de-passive (plan §22)
            from .. import surgery
            draft = surgery.apply(cfg, draft, register)
        # Guarantee a generated diagram appears (the writer places images unreliably);
        # log any suggested image it skipped to rejected.jsonl for review (plan §26).
        draft = reconcile_unit_images(paths, n, f"sec{n:02d}", draft, images, log)
        _commit_section(cfg, paths, section, n, draft, skill_names, sources, first_pass,
                        log, humanize=bool(state.get("humanize")), register=register)
        paths.section_draft(n).unlink(missing_ok=True)
        if agentic_on:   # label the controller's gather decisions with this unit's outcome (§21.11)
            from .. import agentic
            agentic.trace.append(paths, {"scope": "unit-outcome", "unit": f"sec{n:02d}",
                                         "first_pass": bool(first_pass), "insight": crit.insight,
                                         "revised": instruction is not None})
        return "commit"
    _escalate(paths, n, crit, draft, state=state, unit="section")
    return "escalate"


def _commit_section(cfg, paths: ArticlePaths, section, n, draft, skill_names, sources,
                    first_pass, log, *, humanize: bool = False, register: str | None = None) -> None:
    # 1. Renumber in-text [N] citations from this section's local source numbering to
    #    the article-wide registry numbering, so they match the final References list.
    registry = brain.read_json(paths.sources_json) or []
    mapping = _register_sources(registry, sources)
    draft = _renumber_citations(draft, mapping)
    brain.write_json(paths.sources_json, registry)

    # 2. Humanize and summarize concurrently (both derive from the same approved text;
    #    the humanizer preserves content). A real summary, not draft[:800] - the next
    #    sections' continuity context must reflect what this section said, not how it
    #    opened.
    tasks = {"summary": lambda: nodes.summarize_section(cfg, section, draft)}
    if humanize:
        log("   humanizing...")
        tasks["humanized"] = lambda: humanizer.humanize(cfg, draft, register)
    out = concurrency.gather(tasks, strict=True)

    final = out.get("humanized") or draft
    # Crash-safety ordering (A-016): write the continuity summary BEFORE the section .md
    # (the resume guard's "committed" marker), so a crash can't leave a committed section
    # whose summary - the context the next sections read - never landed.
    brain.write_text(paths.section_summary(n), out["summary"])
    brain.write_text(paths.section(n), final)
    _save_version(paths, f"section_{n:02d}", final, label="committed")

    skills_mod.record_chapter(paths.uid, skill_names, first_pass)
    brain.append_text(paths.revision_log,
                      f"## Section {n} committed (first_pass={first_pass})")
    log(f"   [OK] committed section {n}")


def _assemble_article_context(paths: ArticlePaths, section_num: int) -> str:
    """Return summaries of the preceding 3 sections for writer/critic context."""
    summaries = []
    for n in range(max(1, section_num - 3), section_num):
        s = brain.read_text(paths.section_summary(n))
        if s:
            summaries.append(f"### Summary of section {n}\n{s}")
    if summaries:
        return "## Prior section summaries\n" + "\n\n".join(summaries)
    return ""


def _produce_article(cfg, paths: ArticlePaths, outline, state, *, log) -> None:
    sections_md = []
    for p in sorted(paths.root.glob("section_*.md")):
        if not p.name.endswith(".summary.md"):
            sections_md.append(p.read_text(encoding="utf-8"))

    # Resume guard: if a crash landed between section cleanup and the phase advance,
    # re-entering produce with no section files must NOT overwrite the assembled
    # manuscript with an empty one.
    if not sections_md and brain.read_text(paths.manuscript):
        log("   [resume] manuscript already assembled - skipping production")
        return

    # De-duplicate sources by URL. Commit-time _register_sources already dedupes, so
    # this is a safety net; order (= citation numbering) is first-seen and stable.
    unique = _unique_sources(paths)

    # Normalize section structure before assembly:
    #  - drop "Section N:" heading prefixes (the producer owns numbering)
    #  - reconcile references. With registry-managed sources the commit-time renumbering
    #    already governs, so just strip any stray writer-emitted "References" block.
    #    Without them, consolidate the per-section lists into one global, renumbered list.
    sections_md = [_strip_section_prefix(s) for s in sections_md]
    extracted_refs: list[str] = []
    if unique:
        sections_md = [_REF_BLOCK.sub("", s).rstrip() for s in sections_md]
    else:
        sections_md, extracted_refs = _consolidate_section_refs(sections_md)

    # Whole-article cohesion pass: smooth transitions and cross-section repetition.
    # Guarded - if the edit loses headings or shrinks the body too much, keep the
    # original (this pass must never be able to lose content).
    body = "\n\n---\n\n".join(sections_md)
    if sections_md and state.get("article_cohesion"):
        log("   cohesion pass over the assembled article...")
        try:
            edited = nodes.cohesion_edit(cfg, outline, body, register=state.get("register") or None)
        except Exception:  # noqa: BLE001 - cohesion is best-effort polish
            edited = ""
        if (edited
                and len(edited.split()) >= 0.6 * len(body.split())
                and edited.count("## ") >= body.count("## ") * 0.8):
            body = edited
        else:
            log("   cohesion edit rejected by guard - keeping original sections")

    # ── References + citations (deterministic, see polish.py) ────────────────
    from .. import polish
    body = polish.strip_model_figures(body)         # safety net: producer owns figures
    body = polish.strip_reference_dumps(body)       # references live ONLY at the end
    keywords = (brain.read_text(paths.root / "thesis.md") or "") + "\n" + \
        "\n".join(re.findall(r"(?m)^#+ (.+)$", body))
    refs_md = ""
    # Citation style from the register (academic→APA, journalism→AP, ...) unless pinned.
    cite_style = state.get("citation_style") or registers.get(state.get("register")).citation_style
    if cite_style == "none":
        unique = []                                 # this register doesn't carry a reference list
    if unique and state.get("rank_references", True):
        scored = polish.score_sources(unique, body, keywords)
        refs_md = polish.build_references(scored, style=cite_style)
    elif unique:                                    # ranking off: keep a plain dated list
        lines = ["## References", ""]
        for i, s in enumerate(unique, 1):
            entry = f"{i}. [{s.get('title', 'Source')}]({s.get('url', '')})"
            if s.get("date"):
                entry += f" - {s['date']}"
            lines.append(entry)
        refs_md = "\n".join(lines)
    elif extracted_refs:
        refs_md = "\n".join(["## References", ""]
                            + [f"{i}. {t}" for i, t in enumerate(extracted_refs, 1)])
    elif _CITE.search(body):
        log("   [!] citations present but NO verified sources captured - they are "
            "model-generated and unverifiable. Enable the researcher "
            "(/set use_researcher true) for grounded citations.")
    # Strip the now-orphaned inline [N] markers from the prose (sourcing lives in the
    # end list). Done AFTER scoring, which needs the markers to weight influence.
    # The [N]-cited form is kept for the table read below: the cold reader judges
    # sourcing, and handing it the stripped prose manufactured a false "nothing is
    # cited" distrust signal that table_read_revise then acted on.
    body_cited = body
    if state.get("strip_inline_citations", True):
        body = polish.strip_inline_citations(body)

    # Header block. Reading time is prose-only (code blocks + the references list are
    # not read at prose speed) - a raw split() overstates it for technical pieces.
    read_time = polish.read_time_min(body)
    author = (state.get("author") or "").strip()
    header_lines = [
        f"# {outline.title}", "",
        f"*{outline.angle}*", "",
        f"**Estimated read time:** {read_time} min  ",
    ]
    if author:   # omit the byline entirely when unknown - no "[AUTHOR NAME]" placeholder
        header_lines.append(f"**By:** {author}")
    header_lines += ["", "---", ""]
    header = "\n".join(header_lines)

    parts = [header, body]
    if refs_md:
        parts.append("\n---\n\n" + refs_md)
    brain.write_text(paths.manuscript, "\n\n---\n\n".join(parts))
    # NOTE: intermediate section/eval files are cleaned up after the LEARN phase -
    # the learner needs the eval_*.json critic findings (cleaning here starved it).
    log(f"   [production] {len(sections_md)} sections, {len(unique)} sources -> {paths.manuscript}")

    # Shareable evidence report (thesis + influence-ranked sources) - deterministic, the
    # proof behind "argues a thesis, cites real sources". Best-effort; never fails production.
    try:
        build_evidence_report(paths.uid, paths.article_id, log=log)
    except Exception:  # noqa: BLE001
        pass

    # Table read: a cold read of the WHOLE piece as a skeptical target-audience reader.
    # Catches boredom curves and trust breaks no per-section critic can see. Report-only,
    # best-effort - it informs the human (and `revise`), it never rewrites anything.
    if state.get("table_read") and body.strip():
        log("   table read (skeptical reader pass)...")
        try:
            report = nodes.table_read(cfg, outline, body_cited)
            brain.write_text(paths.root / "table_read.md", report)
            log("   [table-read] report -> table_read.md "
                "(act on it with: revise --chapter N --instruction \"...\")")
        except Exception as e:  # noqa: BLE001 - a missing report must not fail production
            log(f"   [table-read] skipped ({type(e).__name__})")

    # Closed table-read loop (autonomous only): turn the reader's single highest-impact
    # fix into one bounded, targeted revision instead of only printing a report. Default
    # off; every draft is version-snapshotted, so the change is auditable and reversible.
    if state.get("table_read_revise") and state.get("autonomous") and body.strip():
        _apply_top_reader_fix(cfg, paths, outline, state, log=log)


def _apply_top_reader_fix(cfg, paths: ArticlePaths, outline, state, *, log) -> None:
    """Generate a structured reader report and apply its single top fix to the implicated
    section as one bounded revision (write -> critique -> optional fix pass -> humanize),
    patching the section file and the assembled manuscript. No-ops when the report has no
    actionable, section-scoped fix. Never raises - a finished run must not fail here."""
    body = brain.read_text(paths.manuscript) or ""
    try:
        report = nodes.reader_report(cfg, outline, body)
    except Exception as e:  # noqa: BLE001
        log(f"   [reader-loop] skipped ({type(e).__name__})")
        return
    fix = (report.top_fix or "").strip()
    sec = report.top_fix_section
    if not fix or not isinstance(sec, int) or not (1 <= sec <= len(outline.sections)):
        log("   [reader-loop] no actionable section-scoped fix - report only")
        return
    log(f'   [reader-loop] applying top reader fix to section {sec}: "{fix[:70]}"')
    try:
        _targeted_section_revise(cfg, paths, outline, state, sec, fix, log=log)
    except Exception as e:  # noqa: BLE001
        log(f"   [reader-loop] revision skipped ({type(e).__name__})")


def _rewrite_section_draft(cfg, paths: ArticlePaths, outline, state, section, n: int,
                           instruction: str, base: str, *, log, verbose: bool = False,
                           length_target: bool = False) -> str:
    """Produce a revised, ready-to-save draft of section n from `instruction`: write to the
    instruction, critique once, run a single conditional fix pass, humanize (when on), and
    strip the heading prefix. The rewrite half shared by the reader-loop revise and the
    post-completion `revise` command. Deltas: `verbose` emits the interactive progress logs
    (the reader loop runs silent mid-pipeline); `length_target` puts a per-section word
    target on the writer calls (the reader-loop path does; `revise` historically did not)."""
    thesis_md = brain.read_text(paths.root / "thesis.md")
    register = state.get("register") or None
    voice = compositor.voice(paths.uid, register, state.get("persona"), state.get("emotion"), log=log)
    watch = brain.read_text(brain.watch_list(paths.uid))
    requirements = (state.get("intake") or "").strip() or None
    target = section.target_words or (
        outline.target_word_count // max(1, len(outline.sections))
        if outline.target_word_count else 0)
    write_ln = _length_note(0, target) if length_target else None
    if verbose:
        log(f"== Revising section {n}: {section.heading} ==")
        log("   rewriting to your instruction...")
    draft = nodes.write_article_section(
        cfg, outline, section, fix_notes=instruction, base_draft=base,
        thesis=thesis_md, voice=voice, requirements=requirements, length_note=write_ln,
        register=register)
    if verbose:
        log("   critiquing...")
    crit = nodes.critique_article_section(
        cfg, outline, section, draft, thesis=thesis_md,
        context=_assemble_article_context(paths, n) or None, watch_list=watch,
        requirements=requirements, research_on=bool(state.get("use_researcher")),
        length_note=_length_note(len(draft.split()), target), register=register)
    if crit.blocking and crit.verdict != "approve":
        if verbose:
            log(f"   {len(crit.blocking)} blocking issue(s) - one fix pass...")
        draft = nodes.write_article_section(
            cfg, outline, section, fix_notes=_merge_fix_notes(instruction, crit),
            base_draft=draft, thesis=thesis_md, voice=voice, requirements=requirements,
            length_note=write_ln, register=register)
    if state.get("humanize"):
        if verbose:
            log("   humanizing...")
        draft = humanizer.humanize(cfg, draft, register)
    return _strip_section_prefix(draft).strip()


def _save_and_patch_section(paths: ArticlePaths, n: int, draft: str, ms: str,
                            instruction: str, *, save_label: str, log_label: str) -> None:
    """Persist a revised section draft: snapshot a version, overwrite the per-section file
    (if it still exists - cleaned up after assembly), and patch the section's body inside the
    assembled manuscript. Append the revision-log entry. Shared save half of both revise paths."""
    _save_version(paths, f"section_{n:02d}", draft, label=save_label)
    if brain.read_text(paths.section(n)) is not None:
        brain.write_text(paths.section(n), draft)
    if ms:
        patched = _replace_manuscript_section(ms, n - 1, draft)
        if patched:
            brain.write_text(paths.manuscript, patched)
    brain.append_text(paths.revision_log, f"## Section {n} {log_label}\n{instruction}")


def _targeted_section_revise(cfg, paths: ArticlePaths, outline, state, n: int,
                             instruction: str, *, log) -> None:
    """Apply one instruction to section n in-place (no confirm UI, no usage reset - it
    runs mid-pipeline). Mirrors revise_unit's article path; patches the section file (if
    present) and the manuscript. Canon-free: a post-write polish, not a re-run."""
    section = outline.sections[n - 1]
    ms = brain.read_text(paths.manuscript) or ""
    base = brain.read_text(paths.section(n))
    if base is None:
        bodies = _manuscript_section_bodies(ms)
        if n > len(bodies):
            return
        base = bodies[n - 1]
    draft = _rewrite_section_draft(cfg, paths, outline, state, section, n, instruction,
                                   base, log=log, length_target=True)
    _save_and_patch_section(paths, n, draft, ms, instruction,
                            save_label="reader-fix", log_label="reader-loop revision")
    log(f"   [reader-loop] section {n} revised -> manuscript patched")


def _learn_article(cfg, paths: ArticlePaths, outline, *, log) -> None:
    instructions = "\n\n".join(
        f"### section {p.stem}\n{p.read_text(encoding='utf-8')}"
        for p in sorted(paths.root.glob("instruction_*.md"))
    )
    findings = []
    for p in sorted(paths.root.glob("eval_*.json")):
        data = brain.read_json(p) or {}
        findings += [f"- [{b['type']}] {b['detail']}" for b in data.get("blocking", [])]
    article_as_plan = S.BookPlan(
        title=outline.title, premise=outline.angle,
        genre="long-form article", tone="informative", audience=outline.angle[:100],
        themes=[], constraints=[], world_rules=[], main_characters=[],
    )
    _run_learner(cfg, paths, article_as_plan, instructions, "\n".join(findings), log=log)
