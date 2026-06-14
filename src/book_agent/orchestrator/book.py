"""The book (chapter) pipeline: plan/TOC -> per-chapter divergent draft/critique/
commit -> periodic + final consolidation -> production (front/back matter + assembly)
-> learn. `run()` is the public entry point and also dispatches articles to
article._run_article. Shared leaf helpers live in common.py.
"""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor

from .. import brain, concurrency, humanizer, llm, nodes, render, retrieval
from .. import schemas as S
from .. import skills as skills_mod
from ..brain import ArticlePaths, BookPaths
from ..config import ModelConfig, Settings, load_settings
from ..store import Store
from .article import _run_article
from .common import (
    _BUDGET_PAUSE_MSG,
    _NONFICTION_RE,
    _apply_run_control,
    _base_run_state,
    _crit_better,
    _deep_docs,
    _divergent_first_draft,
    _draft_glimpse,
    _escalate,
    _finalize_unit,
    _insight_note,
    _length_note,
    _load,
    _log_run_complete,
    _mark_escalated,
    _merge_fix_notes,
    _record_author,
    _record_preference,
    _register_sources,
    _run_learner,
    _save_version,
    _with_intake,
)
from .manage import apply_autonomous

__all__ = [
    'start_book',
    'run',
    '_chapter_fetch',
    '_process_chapter',
    '_commit',
    '_write_consolidation_review',
    '_consolidation',
    '_repair_contradictions',
    '_BIBLIO_RE',
    '_production',
    '_assemble_manuscript',
    '_learn',
    'run_production',
    'run_consolidation',
]


def start_book(
    cfg: ModelConfig, settings: Settings, uid: str, abstract: str,
    chosen: S.Direction, book_id_override: str | None,
    num_chapters: int, max_revisions: int, autonomous: bool = False,
    humanize: bool | None = None, intake: str | None = None, author: str | None = None,
) -> str:
    brain.ensure_user(uid)
    _record_author(uid, author)
    plan = nodes.planner_expand(cfg, _with_intake(abstract, intake), chosen)
    book_id = book_id_override or brain.slugify(plan.title)
    paths = BookPaths(book_id, uid).ensure()

    brain.write_json(paths.root / "plan.json", plan.model_dump())
    brain.write_text(paths.book_plan, render.render_plan_md(plan))
    if intake:
        brain.write_text(paths.root / "intake.md", intake)

    toc = nodes.build_toc(cfg, plan, num_chapters)
    brain.write_json(paths.root / "toc.json", toc.model_dump())
    brain.write_text(paths.toc, render.render_toc_md(toc))

    state = {
        **_base_run_state(uid, abstract, intake=intake, author=author,
                          max_revisions=max_revisions, autonomous=autonomous,
                          humanize=humanize, settings=settings),
        "book_id": book_id,
        "phase": "chapters", "num_chapters": len(toc.chapters),
        "consolidate_every": settings.consolidate_every,
        "current_chapter": 1,
        # Autonomous runs never pause on contradictions either.
        "escalate_on_contradiction": False if autonomous else settings.escalate_on_contradiction,
    }
    brain.write_json(paths.run_state, state)
    return book_id


def run(cfg: ModelConfig, uid: str, book_id: str, *, force: bool = False,
        autonomous: bool | None = None, log=print, ask=None, control=None) -> dict:
    llm.reset_usage()
    llm.set_project(book_id)                                   # telemetry attribution
    llm.set_run_budget(load_settings().max_run_tokens)         # cost kill-switch
    # An explicit autonomous/manual override (from `run --autonomous` or `/auto`)
    # rewrites the project's run_state before this run reads it, so switching to
    # autonomous over an escalated unit clears the pending review and resumes.
    if autonomous is not None:
        apply_autonomous(uid, book_id, autonomous, load_settings())
    # Detect whether this is a book or an article (check articles/ first, then books/)
    art_paths = ArticlePaths(book_id, uid)
    if art_paths.run_state.exists():
        state = brain.read_json(art_paths.run_state)
        if state is None:
            raise FileNotFoundError(f"No run_state for article '{book_id}'.")
        outline = S.ArticleOutline(**brain.read_json(art_paths.outline_json))
        return _run_article(cfg, art_paths, state, outline, force=force, log=log, ask=ask,
                            control=control)
    paths = BookPaths(book_id, uid)
    state = brain.read_json(paths.run_state)
    if state is None:
        raise FileNotFoundError(f"No run_state for book '{book_id}'. Run `new` first.")
    plan = S.BookPlan(**brain.read_json(paths.root / "plan.json"))
    toc = S.TOC(**brain.read_json(paths.root / "toc.json"))
    if state.get("pending_review"):
        if force and state.get("review_kind") == "consolidation":
            state["pending_review"] = False
            if state.get("phase") == "consolidate":
                state["final_acked"] = True
            brain.write_json(paths.run_state, state)
            log("[i] --force: proceeding past the consolidation review.")
        elif state.get("review_kind") == "consolidation":
            log(f"[!] Consolidation review pending. Resume with: book run --book-id {book_id} --force")
            return state
        else:
            log(f"[!] Chapter {state['current_chapter']} awaits review. "
                f"Run: book review --book-id {book_id} --chapter {state['current_chapter']} "
                f'--instruction "..."')
            return state

    store = Store.open(paths)
    prefetch: dict[int, object] = {}
    pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="unit-prefetch")
    try:
        while state["phase"] != "done":
            if _apply_run_control(control, state, paths, log):
                return state
            phase = state["phase"]
            llm.set_unit(phase)
            if phase == "chapters":
                n = state["current_chapter"]
                if n > state["num_chapters"]:
                    state["phase"] = "consolidate"
                    brain.write_json(paths.run_state, state)
                    continue
                # Prefetch network inputs for this chapter and the next: chapter n+1's
                # research/images/skills depend only on the plan/TOC, so they download
                # while chapter n is being written and critiqued. Results are
                # disk-cached, so prefetch work before an escalation isn't wasted.
                for k in (n, n + 1):
                    if (k <= state["num_chapters"] and k not in prefetch
                            and brain.read_text(paths.ch(k)) is None):
                        prefetch[k] = pool.submit(
                            _chapter_fetch, cfg, paths, plan, toc, state, k, log)
                outcome = _process_chapter(cfg, paths, plan, toc, store, state, n, log,
                                           prefetched=prefetch.pop(n, None), ask=ask)
                if outcome == "escalate":
                    _mark_escalated(state, paths, "chapter",
                                    f"[!] Chapter {n} escalated. Resolve with `book review` then `book run`.",
                                    log)
                    return state
                state["committed"] += 1
                state["current_chapter"] = n + 1
                brain.write_json(paths.run_state, state)
                if (state["committed"] % state["consolidate_every"] == 0
                        and not state.get("skip_next_consolidation")):
                    report = _consolidation(cfg, paths, plan, store, tag=f"after-ch{n:02d}", log=log)
                    if state.get("escalate_on_contradiction") and report.contradictions:
                        _write_consolidation_review(paths, f"after-ch{n:02d}", report)
                        state.update(pending_review=True, review_kind="consolidation",
                                     skip_next_consolidation=True)
                        brain.write_json(paths.run_state, state)
                        log(f"[!] Consolidation found {len(report.contradictions)} contradiction(s) "
                            f"-> review. Resume with: book run --force")
                        return state
                state["skip_next_consolidation"] = False
                brain.write_json(paths.run_state, state)
            elif phase == "consolidate":
                report = _consolidation(cfg, paths, plan, store, tag="final", log=log)
                if (state.get("escalate_on_contradiction") and report.contradictions
                        and not state.get("final_acked")):
                    _write_consolidation_review(paths, "final", report)
                    state.update(pending_review=True, review_kind="consolidation")
                    brain.write_json(paths.run_state, state)
                    log(f"[!] Final consolidation found {len(report.contradictions)} contradiction(s) "
                        f"-> review. Resume with: book run --force")
                    return state
                if state.get("autonomous") and report.contradictions:
                    _repair_contradictions(cfg, paths, plan, toc, store, report,
                                           humanize=bool(state.get("humanize")), log=log)
                    _consolidation(cfg, paths, plan, store, tag="final-postrepair", log=log)
                state["phase"] = "production"
                brain.write_json(paths.run_state, state)
            elif phase == "production":
                _production(cfg, paths, plan, store, log=log)
                state["phase"] = "learn"
                brain.write_json(paths.run_state, state)
            elif phase == "learn":
                _learn(cfg, paths, plan, log=log)
                state["phase"] = "done"
                brain.write_json(paths.run_state, state)
        _log_run_complete("Book", book_id, paths.manuscript, log)
        return state
    except llm.BudgetExceeded as e:
        # Nothing committed mid-flight is lost: the resume guards make a re-run
        # pick up exactly where this one stopped.
        log(_BUDGET_PAUSE_MSG.format(err=e))
        return state
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
        store.close()


# ── Per-chapter loop ─────────────────────────────────────────────────────────
def _chapter_fetch(cfg, paths, plan, toc, state, n, log) -> dict:
    """Network-bound inputs for chapter n: research brief, images, skill pages.

    None of this depends on any chapter's prose - only on the plan/TOC - so run()
    prefetches it for chapter n+1 while chapter n is still being written/critiqued.
    The prose chain itself stays sequential for continuity.
    """
    blueprint = toc.chapters[n - 1]

    def _do_research():
        """Returns (research_prefix_md, sources) - sources feed the book-level
        registry so production can emit a real bibliography."""
        if not state.get("use_researcher"):
            return (None, [])
        from .. import search as search_mod
        base_query = search_mod.build_query(plan, blueprint)
        if state.get("deep_research"):
            from .. import deep_research as dr
            docs = _deep_docs(
                cfg, f"{plan.genre}: {plan.title} - {plan.premise}",
                f"{blueprint.title}. {blueprint.purpose}", base_query, log=log)
            brief = nodes.deep_research(cfg, plan, blueprint, dr.format_documents(docs) or None)
            lines = ["## Research brief",
                     "### Facts", *(f"- {f}" for f in brief.facts),
                     "### Style cues", *(f"- {s}" for s in brief.style_cues),
                     "### Comparisons", *(f"- {c}" for c in brief.comparisons)]
            if docs:
                lines += ["### Sources", *(f"- [{d.title}]({d.url})" for d in docs)]
            sources = [S.Source(title=d.title, url=d.url) for d in docs]
            return ("\n".join(lines) + "\n\n", sources)
        results = search_mod.web_search(base_query, max_results=5)
        web_results = search_mod.format_results(results)
        if results:
            log(f"   fetched {len(results)} web result(s) for: {base_query[:60]}")
        brief = nodes.research(cfg, plan, blueprint, web_results=web_results or None)
        prefix = ("## Research brief\n" + "\n".join(
            ["### Facts", *(f"- {f}" for f in brief.facts),
             "### Style cues", *(f"- {s}" for s in brief.style_cues)]) + "\n\n")
        return (prefix, [S.Source(title=r.title, url=r.url) for r in results])

    def _do_images():
        if not state.get("use_images"):
            return None
        from .. import images as img_mod
        query = f"{blueprint.title} {blueprint.purpose} {plan.genre}"
        fetched = img_mod.search_wikimedia(query, max_results=2)
        if fetched:
            log(f"   fetched {len(fetched)} image(s) from Wikimedia Commons")
            return [r.to_markdown(str(i + 1)) for i, r in enumerate(fetched)]
        # No Wikimedia image: generate an SVG diagram - but only for non-fiction-ish
        # genres. A "concept diagram" dropped into a novel chapter is always wrong.
        if not _NONFICTION_RE.search(plan.genre or ""):
            return None
        svg_text = nodes.generate_svg_diagram(
            cfg, blueprint.title, blueprint.purpose or "",
            engine=state.get("diagram_engine", "auto"),
            on_spec=lambda sp: brain.write_text(
                paths.root / "versions" / f"ch{n:02d}.diagram.spec.json", sp.model_dump_json(indent=2)))
        svg_dir = paths.root / "images"
        svg_dir.mkdir(parents=True, exist_ok=True)
        svg_path = svg_dir / f"ch{n:02d}_diagram.svg"
        svg_path.write_text(svg_text, encoding="utf-8")
        log(f"   generated SVG diagram -> {svg_path.name}")
        return [f"![{blueprint.title} diagram](images/ch{n:02d}_diagram.svg)\n"
                f"*Figure: {blueprint.title}*"]

    def _do_skills():
        # Semantic when enabled and sentence-transformers is installed. In the
        # gather because the first embeddings call pays the model load (seconds).
        embed_cache = None
        if state.get("use_embeddings"):
            embed_cache = brain.INDEX_DIR / "embed_cache.json"
        return retrieval.relevant_skills(
            paths.uid, plan,
            use_embeddings=bool(state.get("use_embeddings")),
            embed_cache=embed_cache,
        )

    return concurrency.gather(
        {"research": _do_research, "images": _do_images, "skills": _do_skills})


def _process_chapter(cfg, paths, plan, toc, store, state, n, log, prefetched=None,
                     ask=None) -> str:
    llm.set_unit(f"ch{n:02d}")
    blueprint = toc.chapters[n - 1]
    # Resume guard: if this chapter was already committed on a prior run but the
    # state advance didn't land (crash between _commit and the run_state write),
    # don't re-draft/re-extract - that would duplicate canon facts. Just advance.
    if brain.read_text(paths.ch(n)) is not None:
        log(f"\n== Chapter {n}: {blueprint.title} ==")
        log("   [resume] already committed - advancing")
        return "commit"
    base_context = retrieval.assemble_context(store, paths, blueprint)

    fetched: dict = {}
    if prefetched is not None:
        try:
            fetched = prefetched.result()
        except Exception:  # noqa: BLE001 - prefetch is an optimisation, never fatal
            fetched = {}
    if not fetched:
        fetched = _chapter_fetch(cfg, paths, plan, toc, state, n, log)
    research_prefix, ch_sources = fetched.get("research") or (None, [])
    images: list[str] | None = fetched.get("images")
    context = (research_prefix + base_context) if research_prefix else base_context

    skill_pairs = fetched.get("skills") or []
    skill_names = [name for name, _ in skill_pairs]
    skill_bodies = [body for _, body in skill_pairs]
    watch = brain.read_text(brain.watch_list(paths.uid))
    requirements = (state.get("intake") or "").strip() or None  # author's upfront answers

    instruction = brain.read_text(paths.instruction_of(n))  # from a prior review, if any
    fix_notes = instruction
    # After an escalation the human's instruction refers to the draft they reviewed -
    # give the writer that draft as the revision base instead of starting from scratch.
    base_draft = brain.read_text(paths.ch_draft(n)) if instruction else None
    max_rev = state["max_revisions"]
    threshold = state.get("escalate_below_confidence", 0.0)
    min_insight = int(state.get("min_insight", 0) or 0)
    voice = brain.voice_exemplars(paths.uid)
    crit: S.Critique | None = None
    draft = ""
    best: tuple[str, S.Critique] | None = None
    approved_attempt = -1

    # skeleton kwarg: a book chapter has no skeleton mode (that's an article token
    # optimisation); it's accepted so _divergent_first_draft can call _write/_critique
    # with one signature across chapters and sections. skills= overrides the default set
    # (used by the ablation duel to draft a variant with one skill held out).
    def _write(notes, base, temperature=None, skeleton=False, skills=None):
        return nodes.write_chapter(cfg, plan, blueprint, fix_notes=notes,
                                   context=context, images=images,
                                   skills=skill_bodies if skills is None else skills,
                                   base_draft=base, requirements=requirements, voice=voice,
                                   length_note=_length_note(0, blueprint.target_words),
                                   temperature=temperature)

    def _critique(d):
        return nodes.critique_chapter(
            cfg, plan, blueprint, d, context=context, watch_list=watch,
            skills=skill_bodies, requirements=requirements,
            watch_blocking=bool(state.get("watch_blocking", True)),
            length_note=_length_note(len(d.split()), blueprint.target_words))

    n_div = max(1, int(state.get("divergent_drafts", 1) or 1))
    _unit_tag = f"ch{n:02d}"
    _unit_desc = f'chapter {n}: "{blueprint.title}"'
    judge_note = ""
    log(f"\n== Chapter {n}: {blueprint.title} ==")
    for attempt in range(max_rev + 1):
        if attempt == 0 and n_div > 1 and not base_draft:
            duel = None
            if state.get("skill_duels") and skill_pairs:
                target = skills_mod.pick_duel_target(paths.uid, skill_names)
                if target:
                    duel = {"name": target,
                            "ablated": [b for nm, b in skill_pairs if nm != target]}
            draft, crit, judge_note = _divergent_first_draft(
                cfg, paths, unit_tag=_unit_tag, unit_desc=_unit_desc, n_div=n_div,
                fix_notes=fix_notes, write=_write, critique=_critique, thesis_brief=None,
                ask=ask, autonomous=bool(state.get("autonomous")),
                use_judge=bool(state.get("tournament_judge", True)), skeletons=False,
                log=log, duel=duel)
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
        brain.write_json(paths.eval_of(n),
                         {"chapter_id": n, "attempt": attempt, **crit.model_dump()})
        log(f"   verdict={crit.verdict} confidence={crit.confidence:.2f} "
            f"blocking={len(crit.blocking)} nits={len(crit.nits)} insight={crit.insight}")
        if best is None or _crit_better(crit, best[1]):
            best = (draft, crit)
        low_conf = crit.confidence < threshold
        low_insight = bool(min_insight) and crit.insight < min_insight
        if crit.verdict == "approve" and not low_conf and not low_insight:
            approved_attempt = attempt
            break
        if (crit.verdict == "escalate" or low_conf) and not state.get("autonomous"):
            if low_conf and crit.verdict != "escalate":
                log(f"   low confidence ({crit.confidence:.2f} < {threshold}) -> escalate")
            break
        if attempt == max_rev:
            log("   revision cap reached")
            break
        fix_notes = _merge_fix_notes(instruction, crit)
        if judge_note:
            fix_notes += f"\n\nAlso address the judge's note on the chosen draft: {judge_note}"
            judge_note = ""
        if low_insight and crit.verdict == "approve":
            log(f"   insight {crit.insight}/5 below bar {min_insight} -> sharpening")
            fix_notes = (fix_notes + "\n\n" if fix_notes else "") + _insight_note(crit, min_insight)
        if crit.blocking:
            _record_preference(paths, f"## Revision ({_unit_desc}, attempt {attempt}->{attempt + 1})\n"
                               "Fixed: " + "; ".join(f"{b.type}: {b.detail}"
                                                     for b in crit.blocking[:3]))
        base_draft = draft   # revise the latest attempt, not regenerate from notes alone

    assert crit is not None and best is not None
    if approved_attempt >= 0 or state.get("autonomous"):
        draft, crit, first_pass = _finalize_unit(
            state, approved_attempt=approved_attempt, best=best, draft=draft,
            crit=crit, instruction=instruction, log=log)
        _commit(cfg, paths, plan, blueprint, store, n, draft, skill_names, first_pass,
                log, humanize=bool(state.get("humanize")), sources=ch_sources)
        paths.ch_draft(n).unlink(missing_ok=True)   # escalation draft resolved
        return "commit"
    _escalate(paths, n, crit, draft)
    return "escalate"


def _commit(cfg, paths, plan, blueprint, store, n, draft, skill_names, first_pass, log,
            *, humanize: bool = False, sources=()) -> None:
    # The humanizer rewrite, the summary, and the canon extraction all derive from the
    # same approved draft, so they run as one concurrent batch instead of three serial
    # LLM round-trips. Summary/extraction read the pre-humanized draft - the humanizer
    # preserves content, so the facts are identical. strict=True: a failed summary or
    # extraction aborts the commit (nothing written -> the resume guard re-runs the
    # chapter), exactly as the sequential version did.
    known = store.canon_context()
    tasks = {
        "summary": lambda: nodes.summarize_chapter(cfg, blueprint, draft),
        "extraction": lambda: nodes.extract_canon(cfg, blueprint, draft, known),
    }
    if humanize:
        log("   humanizing...")
        tasks["humanized"] = lambda: humanizer.humanize(cfg, draft)
    out = concurrency.gather(tasks, strict=True)

    final = out.get("humanized") or draft
    brain.write_text(paths.ch(n), final)
    brain.write_text(paths.ch_summary(n), out["summary"])
    _save_version(paths, f"ch{n:02d}", final, label="committed")
    extraction = out["extraction"]
    store.update_from_extraction(n, extraction)
    store.render_canon(paths, names=[ch.name for ch in extraction.characters])
    store.index_chapter(paths, n)

    if sources:
        # Book-level source registry (deduped by URL) - production turns this into a
        # real bibliography instead of inventing one.
        registry = brain.read_json(paths.sources_json) or []
        _register_sources(registry, sources)
        brain.write_json(paths.sources_json, registry)

    skills_mod.record_chapter(paths.uid, skill_names, first_pass)
    brain.append_text(paths.revision_log,
                      f"## Chapter {n} committed (first_pass={first_pass}, "
                      f"skills_applied={skill_names or '[]'})")
    log(f"   [OK] committed chapter {n} (+ summary, canon, index)")


# ── Consolidation / Production / Learner ─────────────────────────────────────
def _write_consolidation_review(paths, tag, report) -> None:
    lines = [f"# Consolidation review - {tag}", "",
             f"{len(report.contradictions)} contradiction(s) found:", ""]
    lines += [f"- [{c.kind}] ch{c.chapters}: {c.detail}\n  fix: {c.fix}"
              for c in report.contradictions]
    lines += ["", f"Full report: consolidation/{tag}.md",
              "Fix canon/chapters as needed, then resume with: `book run --force`"]
    brain.write_text(paths.reviews / f"consolidation-{tag}.md", "\n".join(lines))
    brain.append_text(paths.revision_log, f"## Consolidation ESCALATED ({tag})")


def _consolidation(cfg, paths, plan, store, *, tag, log):
    summaries = "\n\n".join(
        f"### ch{p.stem[2:4]}\n{p.read_text(encoding='utf-8')}"
        for p in sorted(paths.chapters.glob("ch*.summary.md"))
    )
    report = nodes.consolidate(cfg, plan, summaries, store.canon_context())
    contradictions = [f"- [{c.kind}] ch{c.chapters}: {c.detail}\n  fix: {c.fix}"
                      for c in report.contradictions] or ["- none"]
    dups = [f"- {d}" for d in report.duplicate_facts] or ["- none"]
    threads = [f"- {t}" for t in report.unresolved_threads] or ["- none"]
    notes = [f"- {x}" for x in report.notes] or ["- none"]
    md = [f"# Consolidation report ({tag})", "",
          "## Contradictions", *contradictions,
          "", "## Duplicate facts", *dups,
          "", "## Unresolved threads", *threads,
          "", "## Notes", *notes]
    brain.write_text(paths.consolidation / f"{tag}.md", "\n".join(md))
    log(f"   [consolidate:{tag}] contradictions={len(report.contradictions)} "
        f"unresolved={len(report.unresolved_threads)}")
    return report


def _repair_contradictions(cfg, paths, plan, toc, store, report, *, humanize, log,
                           max_chapters=2) -> None:
    """Autonomous best-effort fix: rewrite the chapters a contradiction cites (bounded, 1 round)."""
    targets: list[int] = []
    for c in report.contradictions:
        for ch in c.chapters:
            if isinstance(ch, int) and 1 <= ch <= len(toc.chapters) and ch not in targets:
                targets.append(ch)
    for n in targets[:max_chapters]:
        bp = toc.chapters[n - 1]
        relevant = [c for c in report.contradictions if n in c.chapters]
        notes = ("Resolve these continuity issues found across the finished book; keep the rest of "
                 "the chapter intact:\n"
                 + "\n".join(f"- {c.detail} (fix: {c.fix})" for c in relevant))
        context = retrieval.assemble_context(store, paths, bp)
        draft = nodes.write_chapter(cfg, plan, bp, fix_notes=notes, context=context)
        known = store.canon_context()   # main thread: sqlite conns are thread-bound
        tasks = {
            "summary": lambda b=bp, d=draft: nodes.summarize_chapter(cfg, b, d),
            "extraction": lambda b=bp, d=draft, k=known: nodes.extract_canon(cfg, b, d, k),
        }
        if humanize:
            tasks["humanized"] = lambda d=draft: humanizer.humanize(cfg, d)
        out = concurrency.gather(tasks, strict=True)
        brain.write_text(paths.ch(n), out.get("humanized") or draft)
        brain.write_text(paths.ch_summary(n), out["summary"])
        ex = out["extraction"]
        store.update_from_extraction(n, ex)
        store.render_canon(paths, names=[c.name for c in ex.characters])
        store.index_chapter(paths, n)
        brain.append_text(paths.revision_log,
                          f"## Chapter {n} repaired ({len(relevant)} contradiction(s))")
        log(f"   [repair] rewrote chapter {n} for {len(relevant)} contradiction(s)")


_BIBLIO_RE = re.compile(r"bibliograph|reference|works.?cited|sources|further.?reading",
                        re.IGNORECASE)


def _production(cfg, paths, plan, store, *, log) -> None:
    sources = brain.read_json(paths.sources_json) or []
    pplan = nodes.plan_production(cfg, plan, num_sources=len(sources))
    author_meta = brain.read_text(brain.user_profile(paths.uid))
    toc_md = brain.read_text(paths.toc)
    sources_md = "\n".join(
        f"{i}. {s.get('title', 'Source')} - {s.get('url', '')}"
        for i, s in enumerate(sources, 1)) or None

    # Front/back-matter components are independent of one another - generate them
    # concurrently, then write in order. (Keyed by index to tolerate duplicate names.)
    # Bibliography-style components get the ACTUAL research sources used during the
    # run; without them the prompt (correctly) forbids inventing entries.
    tasks = {}
    for i, comp in enumerate(pplan.front_matter):
        tasks[f"front:{i}"] = (
            lambda c=comp: nodes.generate_component(cfg, plan, c, "front", author_meta, toc_md))
    for i, comp in enumerate(pplan.back_matter):
        tasks[f"back:{i}"] = (
            lambda c=comp: nodes.generate_component(
                cfg, plan, c, "back", author_meta, toc_md,
                sources_md=sources_md if _BIBLIO_RE.search(c) else None))
    generated = concurrency.gather(tasks)
    for i, comp in enumerate(pplan.front_matter):
        content = generated.get(f"front:{i}")
        if content:
            brain.write_text(paths.frontmatter / f"{brain.slugify(comp)}.md", content)
    for i, comp in enumerate(pplan.back_matter):
        content = generated.get(f"back:{i}")
        if content:
            brain.write_text(paths.backmatter / f"{brain.slugify(comp)}.md", content)

    _assemble_manuscript(paths, plan, pplan)
    log(f"   [production] front={len(pplan.front_matter)} back={len(pplan.back_matter)} "
        f"-> {paths.manuscript}")


def _assemble_manuscript(paths, plan, pplan: S.ProductionPlan) -> None:
    parts: list[str] = []
    if not pplan.front_matter:  # the title-page front-matter component already carries the title
        parts += [f"# {plan.title}", ""]
    for comp in pplan.front_matter:
        body = brain.read_text(paths.frontmatter / f"{brain.slugify(comp)}.md")
        if body:
            parts += [body, "", "---", ""]
    for p in sorted(paths.chapters.glob("ch*.md")):
        if p.name.endswith((".draft.md", ".summary.md")):
            continue
        parts += [p.read_text(encoding="utf-8"), "", "---", ""]
    for comp in pplan.back_matter:
        body = brain.read_text(paths.backmatter / f"{brain.slugify(comp)}.md")
        if body:
            parts += [body, "", "---", ""]
    brain.write_text(paths.manuscript, "\n".join(parts))


def _learn(cfg, paths, plan, *, log) -> None:
    instructions = "\n\n".join(
        f"### chapter {p.stem[2:4]}\n{p.read_text(encoding='utf-8')}"
        for p in sorted(paths.instructions.glob("ch*.md"))
    )
    findings = []
    for p in sorted(paths.eval.glob("ch*.json")):
        data = brain.read_json(p) or {}
        findings += [f"- [{b['type']}] {b['detail']}" for b in data.get("blocking", [])]
    _run_learner(cfg, paths, plan, instructions, "\n".join(findings), log=log)


# ── CLI-facing helpers ───────────────────────────────────────────────────────


def run_production(cfg: ModelConfig, uid: str, book_id: str, *, log=print) -> None:
    paths, _, plan, _ = _load(uid, book_id)
    store = Store.open(paths)
    try:
        _production(cfg, paths, plan, store, log=log)
    finally:
        store.close()


def run_consolidation(cfg: ModelConfig, uid: str, book_id: str, *, log=print) -> None:
    paths, _, plan, _ = _load(uid, book_id)
    store = Store.open(paths)
    try:
        _consolidation(cfg, paths, plan, store, tag="manual", log=log)
    finally:
        store.close()
