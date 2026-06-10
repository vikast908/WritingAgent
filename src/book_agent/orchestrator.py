"""Durable on-disk state machine (plan.md §6).

The brain on disk IS the checkpoint: every step persists to run_state.json + committed
markdown, so `run()` is resumable across process restarts and human pauses. (This fulfils
the plan's checkpoint/resume requirement without LangGraph's in-memory interrupt machinery;
LangGraph can wrap this engine later - see plan §12 note.)

Phases: chapters -> consolidate -> production -> learn -> done.
Per chapter: write -> critique -> (approve→commit | revise<cap→rewrite | cap/escalate→ESCALATE).
"""
from __future__ import annotations

from . import brain, concurrency, humanizer, llm, nodes, render, retrieval
from . import schemas as S
from . import skills as skills_mod
from .brain import ArticlePaths, BookPaths
from .config import ModelConfig, Settings
from .store import Store


# ── Setup (human picks a direction, then autonomous) ─────────────────────────
def start_book(
    cfg: ModelConfig, settings: Settings, uid: str, abstract: str,
    chosen: S.Direction, book_id_override: str | None,
    num_chapters: int, max_revisions: int, autonomous: bool = False,
    humanize: bool | None = None,
) -> str:
    plan = nodes.planner_expand(cfg, abstract, chosen)
    book_id = book_id_override or brain.slugify(plan.title)
    paths = BookPaths(book_id, uid).ensure()
    brain.ensure_user(uid)

    brain.write_json(paths.root / "plan.json", plan.model_dump())
    brain.write_text(paths.book_plan, render.render_plan_md(plan))

    toc = nodes.build_toc(cfg, plan, num_chapters)
    brain.write_json(paths.root / "toc.json", toc.model_dump())
    brain.write_text(paths.toc, render.render_toc_md(toc))

    state = {
        "uid": uid, "book_id": book_id, "abstract": abstract,
        "phase": "chapters", "num_chapters": len(toc.chapters),
        "max_revisions": max_revisions, "consolidate_every": settings.consolidate_every,
        "current_chapter": 1, "committed": 0, "pending_review": False,
        "use_researcher": settings.use_researcher,
        "autonomous": autonomous,
        "humanize": settings.humanize if humanize is None else humanize,
        "use_images": settings.use_images,
        "use_embeddings": settings.use_embeddings,
        # Autonomous runs never pause: no confidence/contradiction escalation.
        "escalate_below_confidence": 0.0 if autonomous else settings.escalate_below_confidence,
        "escalate_on_contradiction": False if autonomous else settings.escalate_on_contradiction,
    }
    brain.write_json(paths.run_state, state)
    return book_id


def _load(uid: str, book_id: str):
    paths = BookPaths(book_id, uid)
    state = brain.read_json(paths.run_state)
    if state is None:
        raise FileNotFoundError(f"No run_state for book '{book_id}'. Run `book new` first.")
    plan = S.BookPlan(**brain.read_json(paths.root / "plan.json"))
    toc = S.TOC(**brain.read_json(paths.root / "toc.json"))
    return paths, state, plan, toc


# ── Main driver ──────────────────────────────────────────────────────────────
def run(cfg: ModelConfig, uid: str, book_id: str, *, force: bool = False, log=print) -> dict:
    llm.reset_usage()
    # Detect whether this is a book or an article (check articles/ first, then books/)
    art_paths = ArticlePaths(book_id, uid)
    if art_paths.run_state.exists():
        state = brain.read_json(art_paths.run_state)
        if state is None:
            raise FileNotFoundError(f"No run_state for article '{book_id}'.")
        outline = S.ArticleOutline(**brain.read_json(art_paths.outline_json))
        return _run_article(cfg, art_paths, state, outline, force=force, log=log)
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
    try:
        while state["phase"] != "done":
            phase = state["phase"]
            if phase == "chapters":
                n = state["current_chapter"]
                if n > state["num_chapters"]:
                    state["phase"] = "consolidate"
                    brain.write_json(paths.run_state, state)
                    continue
                outcome = _process_chapter(cfg, paths, plan, toc, store, state, n, log)
                if outcome == "escalate":
                    state["pending_review"] = True
                    state["review_kind"] = "chapter"
                    brain.write_json(paths.run_state, state)
                    log(f"[!] Chapter {n} escalated. Resolve with `book review` then `book run`.")
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
        log(f"[OK] Book '{book_id}' complete. Manuscript: {paths.manuscript}")
        _summary = llm.usage_summary()
        if _summary:
            log("   " + _summary)
        return state
    finally:
        store.close()


# ── Per-chapter loop ─────────────────────────────────────────────────────────
def _process_chapter(cfg, paths, plan, toc, store, state, n, log) -> str:
    blueprint = toc.chapters[n - 1]
    # Resume guard: if this chapter was already committed on a prior run but the
    # state advance didn't land (crash between _commit and the run_state write),
    # don't re-draft/re-extract - that would duplicate canon facts. Just advance.
    if brain.read_text(paths.ch(n)) is not None:
        log(f"\n== Chapter {n}: {blueprint.title} ==")
        log("   [resume] already committed - advancing")
        return "commit"
    base_context = retrieval.assemble_context(store, paths, blueprint)

    # Research and image-fetch are independent network-bound steps - run them
    # concurrently (the chapter chain itself stays sequential for continuity).
    def _do_research():
        if not state.get("use_researcher"):
            return None
        from . import search as search_mod
        query = search_mod.build_query(plan, blueprint)
        results = search_mod.web_search(query, max_results=5)
        web_results = search_mod.format_results(results)
        if results:
            log(f"   fetched {len(results)} web result(s) for: {query[:60]}")
        brief = nodes.research(cfg, plan, blueprint, web_results=web_results or None)
        return ("## Research brief\n" + "\n".join(
            ["### Facts", *(f"- {f}" for f in brief.facts),
             "### Style cues", *(f"- {s}" for s in brief.style_cues)]) + "\n\n")

    def _do_images():
        if not state.get("use_images"):
            return None
        from . import images as img_mod
        query = f"{blueprint.title} {blueprint.purpose} {plan.genre}"
        fetched = img_mod.search_wikimedia(query, max_results=2)
        if fetched:
            log(f"   fetched {len(fetched)} image(s) from Wikimedia Commons")
            return [r.to_markdown(str(i + 1)) for i, r in enumerate(fetched)]
        # No Wikimedia image - generate an SVG diagram instead
        svg_text = nodes.generate_svg_diagram(cfg, blueprint.title, blueprint.purpose or "")
        svg_dir = paths.root / "images"
        svg_dir.mkdir(parents=True, exist_ok=True)
        svg_path = svg_dir / f"ch{n:02d}_diagram.svg"
        svg_path.write_text(svg_text, encoding="utf-8")
        log(f"   generated SVG diagram -> {svg_path.name}")
        return [f"![{blueprint.title} diagram](images/ch{n:02d}_diagram.svg)\n"
                f"*Figure: {blueprint.title}*"]

    fetched = concurrency.gather({"research": _do_research, "images": _do_images})
    research_prefix = fetched.get("research")
    images: list[str] | None = fetched.get("images")
    context = (research_prefix + base_context) if research_prefix else base_context

    # Skill retrieval: semantic when enabled and sentence-transformers is installed.
    embed_cache = None
    if state.get("use_embeddings"):
        embed_cache = brain._ROOT / ".index" / "embed_cache.json"
    skill_pairs = retrieval.relevant_skills(
        paths.uid, plan,
        use_embeddings=bool(state.get("use_embeddings")),
        embed_cache=embed_cache,
    )
    skill_names = [name for name, _ in skill_pairs]
    skill_bodies = [body for _, body in skill_pairs]

    instruction = brain.read_text(paths.instruction_of(n))  # from a prior review, if any
    fix_notes = instruction
    max_rev = state["max_revisions"]
    threshold = state.get("escalate_below_confidence", 0.0)
    crit: S.Critique | None = None
    draft = ""
    approved_attempt = -1

    log(f"\n== Chapter {n}: {blueprint.title} ==")
    for attempt in range(max_rev + 1):
        log(f"   writing ({'draft' if attempt == 0 else f'revision {attempt}'})...")
        draft = nodes.write_chapter(cfg, plan, blueprint, fix_notes=fix_notes,
                                    context=context, skills=skill_bodies, images=images)
        log("   critiquing...")
        crit = nodes.critique_chapter(cfg, plan, blueprint, draft, context=context)
        brain.write_json(paths.eval_of(n),
                         {"chapter_id": n, "attempt": attempt, **crit.model_dump()})
        log(f"   verdict={crit.verdict} confidence={crit.confidence:.2f} "
            f"blocking={len(crit.blocking)} nits={len(crit.nits)}")
        low_conf = crit.confidence < threshold
        if crit.verdict == "approve" and not low_conf:
            approved_attempt = attempt
            break
        if (crit.verdict == "escalate" or low_conf) and not state.get("autonomous"):
            if low_conf and crit.verdict != "escalate":
                log(f"   low confidence ({crit.confidence:.2f} < {threshold}) -> escalate")
            break
        if attempt == max_rev:
            log("   revision cap reached")
            break
        fix_notes = render.render_fix_notes(crit)

    assert crit is not None
    will_commit = approved_attempt >= 0 or state.get("autonomous")
    if will_commit and state.get("humanize"):
        log("   humanizing...")
        draft = humanizer.humanize(cfg, draft)
    if approved_attempt >= 0:
        first_pass = approved_attempt == 0 and instruction is None
        _commit(cfg, paths, plan, blueprint, store, n, draft, skill_names, first_pass, log)
        return "commit"
    if state.get("autonomous"):
        log("   autonomous: committing best (unapproved) draft")
        _commit(cfg, paths, plan, blueprint, store, n, draft, skill_names, False, log)
        return "commit"
    _escalate(paths, n, crit, draft)
    return "escalate"


def _commit(cfg, paths, plan, blueprint, store, n, draft, skill_names, first_pass, log) -> None:
    brain.write_text(paths.ch(n), draft)
    summary = nodes.summarize_chapter(cfg, blueprint, draft)
    brain.write_text(paths.ch_summary(n), summary)

    known = store.canon_context()
    extraction = nodes.extract_canon(cfg, blueprint, draft, known)
    store.update_from_extraction(n, extraction)
    store.render_canon(paths)
    store.index_documents(paths)

    skills_mod.record_chapter(paths.uid, skill_names, first_pass)
    brain.append_text(paths.revision_log,
                      f"## Chapter {n} committed (first_pass={first_pass}, "
                      f"skills_applied={skill_names or '[]'})")
    log(f"   [OK] committed chapter {n} (+ summary, canon, index)")


def _escalate(paths, n, crit: S.Critique, draft: str) -> None:
    brain.write_text(paths.ch_draft(n), draft)
    lines = [
        f"# Review needed - chapter {n}", "",
        f"- verdict: {crit.verdict}", f"- confidence: {crit.confidence:.2f}", "",
        "## Blocking",
        *(f"- [{b.type}] {b.where}: {b.detail}\n  fix: {b.fix}" for b in crit.blocking),
        "", "## Nits", *(f"- {x}" for x in crit.nits), "",
        "## Your directed instructions",
        "_Run: book review --chapter N --instruction \"...\" - then book run to resume._",
    ]
    brain.write_text(paths.review_of(n), "\n".join(lines))
    brain.append_text(paths.revision_log, f"## Chapter {n} ESCALATED ({crit.verdict})")


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
        if humanize:
            draft = humanizer.humanize(cfg, draft)
        brain.write_text(paths.ch(n), draft)
        brain.write_text(paths.ch_summary(n), nodes.summarize_chapter(cfg, bp, draft))
        ex = nodes.extract_canon(cfg, bp, draft, store.canon_context())
        store.update_from_extraction(n, ex)
        store.render_canon(paths)
        store.index_documents(paths)
        brain.append_text(paths.revision_log,
                          f"## Chapter {n} repaired ({len(relevant)} contradiction(s))")
        log(f"   [repair] rewrote chapter {n} for {len(relevant)} contradiction(s)")


def _production(cfg, paths, plan, store, *, log) -> None:
    pplan = nodes.plan_production(cfg, plan)
    author_meta = brain.read_text(brain.user_profile(paths.uid))
    toc_md = brain.read_text(paths.toc)

    # Front/back-matter components are independent of one another - generate them
    # concurrently, then write in order. (Keyed by index to tolerate duplicate names.)
    tasks = {}
    for i, comp in enumerate(pplan.front_matter):
        tasks[f"front:{i}"] = (
            lambda c=comp: nodes.generate_component(cfg, plan, c, "front", author_meta, toc_md))
    for i, comp in enumerate(pplan.back_matter):
        tasks[f"back:{i}"] = (
            lambda c=comp: nodes.generate_component(cfg, plan, c, "back", author_meta, toc_md))
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
    uid = paths.uid
    instructions = "\n\n".join(
        f"### chapter {p.stem[2:4]}\n{p.read_text(encoding='utf-8')}"
        for p in sorted(paths.instructions.glob("ch*.md"))
    )
    findings = []
    for p in sorted(paths.eval.glob("ch*.json")):
        data = brain.read_json(p) or {}
        findings += [f"- [{b['type']}] {b['detail']}" for b in data.get("blocking", [])]
    existing = "\n".join(p.stem for p in brain.skills_dir(uid).glob("*.md"))

    out = nodes.learn(cfg, plan, instructions, "\n".join(findings), existing)
    for prop in out.skills:
        skills_mod.write_skill(uid, prop)
    watch = ["# Avoid list (watch-list)", ""] + [f"- {w.pattern} - {w.why}" for w in out.watch_items]
    brain.write_text(brain.watch_list(uid), "\n".join(watch))
    statuses = skills_mod.reconcile(uid)
    log(f"   [learn] +{len(out.skills)} skills, {len(out.watch_items)} watch items; "
        f"reconciled {len(statuses)} skills")


# ── CLI-facing helpers ───────────────────────────────────────────────────────
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


def status(uid: str, book_id: str) -> dict:
    art = ArticlePaths(book_id, uid)
    if art.run_state.exists():
        state = brain.read_json(art.run_state) or {}
        return {**state, "open_reviews": []}
    paths = BookPaths(book_id, uid)
    state = brain.read_json(paths.run_state) or {}
    pending = sorted(p.name for p in paths.reviews.glob("ch*.md")) if paths.reviews.exists() else []
    return {**state, "open_reviews": pending}


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


def _export_paths_and_title(uid: str, project_id: str):
    """Return (root_path, manuscript_path, title) for either article or book."""
    art = ArticlePaths(project_id, uid)
    if art.run_state.exists():
        state = brain.read_json(art.run_state) or {}
        title = state.get("article_id", project_id)
        return art.root, art.manuscript, title
    bk = BookPaths(project_id, uid)
    plan_data = brain.read_json(bk.root / "plan.json") or {}
    title = plan_data.get("title", project_id)
    return bk.root, bk.manuscript, title


def export_pdf(uid: str, book_id: str, *, log=print):
    from . import export
    root, manuscript, title = _export_paths_and_title(uid, book_id)
    md = brain.read_text(manuscript)
    if not md:
        raise FileNotFoundError(f"No manuscript for '{book_id}'. Run it first.")
    out = root / "manuscript.pdf"
    export.markdown_to_pdf(md, out, title=title)
    log(f"[OK] PDF -> {out}")
    return out


def export_epub(uid: str, book_id: str, *, log=print):
    from . import export
    root, manuscript, title = _export_paths_and_title(uid, book_id)
    md = brain.read_text(manuscript)
    if not md:
        raise FileNotFoundError(f"No manuscript for '{book_id}'. Run it first.")
    author_meta = brain.read_text(brain.user_profile(uid)) or ""
    import re as _re
    m = _re.search(r"(?m)^name:\s*(.+)$", author_meta)
    author = m.group(1).strip() if m else uid
    out = root / "manuscript.epub"
    export.markdown_to_epub(md, out, title=title, author=author)
    log(f"[OK] EPUB -> {out}")
    return out


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


# ── Article pipeline ──────────────────────────────────────────────────────────

def start_article(
    cfg: ModelConfig, settings, uid: str, abstract: str,
    chosen: S.ArticleAngle, article_id_override: str | None,
    num_sections: int, max_revisions: int,
    autonomous: bool = False, humanize: bool | None = None,
) -> str:
    outline = nodes.build_article_outline(cfg, abstract, chosen, num_sections)
    article_id = article_id_override or brain.slugify(outline.title)
    paths = ArticlePaths(article_id, uid).ensure()
    brain.ensure_user(uid)

    brain.write_json(paths.angle_json, chosen.model_dump())
    brain.write_json(paths.outline_json, outline.model_dump())
    brain.write_text(paths.outline_md, render.render_outline_md(outline))

    state = {
        "uid": uid, "article_id": article_id, "abstract": abstract,
        "mode": "article",
        "phase": "sections", "num_sections": len(outline.sections),
        "max_revisions": max_revisions, "current_section": 1,
        "committed": 0, "pending_review": False,
        "use_researcher": settings.use_researcher,
        "autonomous": autonomous,
        "humanize": settings.humanize if humanize is None else humanize,
        "use_images": settings.use_images,
        "use_embeddings": settings.use_embeddings,
        "escalate_below_confidence": 0.0 if autonomous else settings.escalate_below_confidence,
        "escalate_on_contradiction": False,
    }
    brain.write_json(paths.run_state, state)
    return article_id


def _run_article(cfg, paths: ArticlePaths, state, outline, *, force, log):
    if state.get("pending_review"):
        log(f"[!] Section {state['current_section']} awaits review. "
            f"Run: review --chapter {state['current_section']} --instruction \"...\"")
        return state

    while state["phase"] != "done":
        phase = state["phase"]
        if phase == "sections":
            n = state["current_section"]
            if n > state["num_sections"]:
                state["phase"] = "produce"
                brain.write_json(paths.run_state, state)
                continue
            outcome = _process_article_section(cfg, paths, outline, state, n, log)
            if outcome == "escalate":
                state["pending_review"] = True
                state["review_kind"] = "section"
                brain.write_json(paths.run_state, state)
                log(f"[!] Section {n} escalated. Resolve with `review` then `run`.")
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
            state["phase"] = "done"
            brain.write_json(paths.run_state, state)
    log(f"[OK] Article '{paths.article_id}' complete. Manuscript: {paths.manuscript}")
    _summary = llm.usage_summary()
    if _summary:
        log("   " + _summary)
    return state


def _process_article_section(cfg, paths: ArticlePaths, outline, state, n, log) -> str:
    from types import SimpleNamespace
    section = outline.sections[n - 1]

    # Resume guard (see _process_chapter): committed section file present but state
    # not advanced => crash window; don't reprocess.
    if brain.read_text(paths.section(n)) is not None:
        log(f"\n== Section {n}: {section.heading} ==")
        log("   [resume] already committed - advancing")
        return "commit"

    # Research and image-fetch are independent network steps - run concurrently.
    def _do_research():
        if not state.get("use_researcher"):
            return ("", [])
        from . import search as search_mod
        query = section.search_query or f"{outline.title} {section.heading}"
        results = search_mod.web_search(query, max_results=5)
        web_results = search_mod.format_results(results)
        if results:
            log(f"   fetched {len(results)} web result(s) for: {query[:60]}")
        brief = nodes.research_article(cfg, outline, section, web_results=web_results or None)
        prefix = ("## Research brief\n" + "\n".join([
            "### Facts", *(f"- {f}" for f in brief.facts),
            "### Style cues", *(f"- {s}" for s in brief.style_cues),
            "### Sources", *(f"- [{s.title}]({s.url})" for s in brief.sources),
        ]) + "\n\n")
        return (prefix, brief.sources)

    def _do_images():
        if not (state.get("use_images") and section.include_image):
            return None
        from . import images as img_mod
        got = img_mod.search_wikimedia(f"{section.heading} {outline.title}", max_results=2)
        if got:
            log(f"   fetched {len(got)} image(s) from Wikimedia Commons")
            return [r.to_markdown(str(i + 1)) for i, r in enumerate(got)]
        # No Wikimedia image - generate an SVG diagram instead
        ctx = getattr(section, "purpose", "") or getattr(section, "heading", "")
        svg_text = nodes.generate_svg_diagram(cfg, section.heading, ctx)
        paths.images.mkdir(parents=True, exist_ok=True)
        svg_path = paths.images / f"section_{n:02d}_diagram.svg"
        svg_path.write_text(svg_text, encoding="utf-8")
        log(f"   generated SVG diagram -> {svg_path.name}")
        return [f"![{section.heading} diagram](images/section_{n:02d}_diagram.svg)\n"
                f"*Figure: {section.heading}*"]

    out = concurrency.gather({"research": _do_research, "images": _do_images})
    context_prefix, sources = out.get("research") or ("", [])
    images: list[str] | None = out.get("images")

    # Prior section summaries
    article_context = _assemble_article_context(paths, n)
    full_context = (context_prefix + article_context).strip() or None

    # Skills - use angle as genre proxy
    embed_cache = None
    if state.get("use_embeddings"):
        embed_cache = brain._ROOT / ".index" / "embed_cache.json"
    proxy = SimpleNamespace(genre=outline.angle, tone="informative",
                            themes=[outline.title])
    skill_pairs = retrieval.relevant_skills(
        paths.uid, proxy,  # type: ignore[arg-type]
        use_embeddings=bool(state.get("use_embeddings")), embed_cache=embed_cache,
    )
    skill_names = [name for name, _ in skill_pairs]
    skill_bodies = [body for _, body in skill_pairs]

    instruction = brain.read_text(paths.instruction_of(n))
    fix_notes = instruction
    max_rev = state["max_revisions"]
    threshold = state.get("escalate_below_confidence", 0.0)
    crit: S.Critique | None = None
    draft = ""
    approved_attempt = -1

    log(f"\n== Section {n}: {section.heading} ==")
    for attempt in range(max_rev + 1):
        log(f"   writing ({'draft' if attempt == 0 else f'revision {attempt}'})...")
        draft = nodes.write_article_section(cfg, outline, section,
                                            fix_notes=fix_notes, context=full_context,
                                            skills=skill_bodies, images=images)
        log("   critiquing...")
        crit = nodes.critique_article_section(cfg, outline, section, draft,
                                               context=full_context)
        brain.write_json(paths.section_eval(n),
                         {"section": n, "attempt": attempt, **crit.model_dump()})
        log(f"   verdict={crit.verdict} confidence={crit.confidence:.2f} "
            f"blocking={len(crit.blocking)}")
        low_conf = crit.confidence < threshold
        if crit.verdict == "approve" and not low_conf:
            approved_attempt = attempt
            break
        if (crit.verdict == "escalate" or low_conf) and not state.get("autonomous"):
            break
        if attempt == max_rev:
            log("   revision cap reached")
            break
        fix_notes = render.render_fix_notes(crit)

    assert crit is not None
    will_commit = approved_attempt >= 0 or state.get("autonomous")
    if will_commit and state.get("humanize"):
        log("   humanizing...")
        draft = humanizer.humanize(cfg, draft)
    if approved_attempt >= 0:
        first_pass = approved_attempt == 0 and instruction is None
        _commit_section(paths, n, draft, skill_names, sources, first_pass, log)
        return "commit"
    if state.get("autonomous"):
        log("   autonomous: committing best draft")
        _commit_section(paths, n, draft, skill_names, sources, False, log)
        return "commit"
    _escalate(paths, n, crit, draft)
    return "escalate"


def _commit_section(paths: ArticlePaths, n, draft, skill_names, sources, first_pass, log) -> None:
    brain.write_text(paths.section(n), draft)
    summary = draft[:800]
    brain.write_text(paths.section_summary(n), summary)

    existing = brain.read_json(paths.sources_json) or []
    existing.extend([s.model_dump() if hasattr(s, "model_dump") else s for s in sources])
    brain.write_json(paths.sources_json, existing)

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

    # De-duplicate sources by URL
    raw_sources = brain.read_json(paths.sources_json) or []
    seen_urls: set = set()
    unique: list = []
    for s in raw_sources:
        url = s.get("url", "") if isinstance(s, dict) else getattr(s, "url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique.append(s if isinstance(s, dict) else s.model_dump())

    # Build references section
    refs_md = ""
    if unique:
        lines = ["## References", ""]
        for i, s in enumerate(unique, 1):
            title = s.get("title", "Source")
            url = s.get("url", "")
            date = s.get("date", "")
            entry = f"{i}. [{title}]({url})"
            if date:
                entry += f" - {date}"
            lines.append(entry)
        refs_md = "\n".join(lines)

    # Header block
    total_words = sum(len(sec.split()) for sec in sections_md)
    read_time = max(1, round(total_words / 200))
    header = "\n".join([
        f"# {outline.title}", "",
        f"*{outline.angle}*", "",
        f"**Estimated read time:** {read_time} min  ",
        "**By:** [AUTHOR NAME]", "",
        "---", "",
    ])

    parts = [header] + sections_md
    if refs_md:
        parts.append("\n---\n\n" + refs_md)
    brain.write_text(paths.manuscript, "\n\n---\n\n".join(parts))
    # Clean up intermediate section files - keep only manuscript + images + metadata
    paths.cleanup_sections()
    log(f"   [production] {len(sections_md)} sections, {len(unique)} sources -> {paths.manuscript}")


def _learn_article(cfg, paths: ArticlePaths, outline, *, log) -> None:
    uid = paths.uid
    instructions = "\n\n".join(
        f"### section {p.stem}\n{p.read_text(encoding='utf-8')}"
        for p in sorted(paths.root.glob("instruction_*.md"))
    )
    findings = []
    for p in sorted(paths.root.glob("eval_*.json")):
        data = brain.read_json(p) or {}
        findings += [f"- [{b['type']}] {b['detail']}" for b in data.get("blocking", [])]
    existing = "\n".join(p.stem for p in brain.skills_dir(uid).glob("*.md"))
    article_as_plan = S.BookPlan(
        title=outline.title, premise=outline.angle,
        genre="long-form article", tone="informative", audience=outline.angle[:100],
        themes=[], constraints=[], world_rules=[], main_characters=[],
    )
    out = nodes.learn(cfg, article_as_plan, instructions, "\n".join(findings), existing)
    for prop in out.skills:
        skills_mod.write_skill(uid, prop)
    watch = ["# Avoid list (watch-list)", ""] + [f"- {w.pattern} - {w.why}"
                                                   for w in out.watch_items]
    brain.write_text(brain.watch_list(uid), "\n".join(watch))
    skills_mod.reconcile(uid)
    log(f"   [learn] +{len(out.skills)} skills, {len(out.watch_items)} watch items")


def export_html(uid: str, book_id: str, *, log=print):
    from . import export
    root, manuscript, title = _export_paths_and_title(uid, book_id)
    md = brain.read_text(manuscript)
    if not md:
        raise FileNotFoundError(f"No manuscript for '{book_id}'. Run it first.")
    out = root / "manuscript.html"
    export.markdown_to_html(md, out, title=title)
    log(f"[OK] HTML -> {out}")
    return out


def export_docx(uid: str, book_id: str, *, log=print):
    from . import export
    root, manuscript, title = _export_paths_and_title(uid, book_id)
    md = brain.read_text(manuscript)
    if not md:
        raise FileNotFoundError(f"No manuscript for '{book_id}'. Run it first.")
    out = root / "manuscript.docx"
    export.markdown_to_docx(md, out, title=title)
    log(f"[OK] DOCX -> {out}")
    return out


def export_txt(uid: str, book_id: str, *, log=print):
    from . import export
    root, manuscript, title = _export_paths_and_title(uid, book_id)
    md = brain.read_text(manuscript)
    if not md:
        raise FileNotFoundError(f"No manuscript for '{book_id}'. Run it first.")
    out = root / "manuscript.txt"
    export.markdown_to_txt(md, out, title=title)
    log(f"[OK] TXT -> {out}")
    return out


def export_md(uid: str, book_id: str, *, log=print):
    from . import export
    root, manuscript, title = _export_paths_and_title(uid, book_id)
    md = brain.read_text(manuscript)
    if not md:
        raise FileNotFoundError(f"No manuscript for '{book_id}'. Run it first.")
    out = root / "manuscript_export.md"
    export.markdown_to_md(md, out, title=title)
    log(f"[OK] MD -> {out}")
    return out
