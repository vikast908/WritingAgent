"""Durable on-disk state machine (plan.md §6).

The brain on disk IS the checkpoint: every step persists to run_state.json + committed
markdown, so `run()` is resumable across process restarts and human pauses. (This fulfils
the plan's checkpoint/resume requirement without LangGraph's in-memory interrupt machinery;
LangGraph can wrap this engine later - see plan §12 note.)

Phases: chapters -> consolidate -> production -> learn -> done.
Per chapter: write -> critique -> (approve→commit | revise<cap→rewrite | cap/escalate→ESCALATE).
"""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor

from . import brain, concurrency, humanizer, llm, nodes, render, retrieval
from . import schemas as S
from . import skills as skills_mod
from .brain import ArticlePaths, BookPaths
from .config import ModelConfig, Settings, load_settings
from .store import Store

_BUDGET_PAUSE_MSG = ("[!] {err} - run paused. Raise the cap (/set max_run_tokens N, "
                     "0 = unlimited) or just run again to continue with a fresh budget.")


# ── Deep-research query planning ─────────────────────────────────────────────
def _research_queries(cfg, topic: str, focus: str, *seed_queries: str, log=print) -> list[str]:
    """Build the query set for the deep researcher: LLM-expanded queries first
    (most targeted), then deterministic seeds as a fallback. The LLM step is
    best-effort - if it fails we still search with the seeds. `gather_documents`
    de-dupes and drops empties, so order-and-overlap here is harmless."""
    proposed: list[str] = []
    try:
        proposed = list(nodes.propose_search_queries(cfg, topic, focus).queries)
    except Exception:  # noqa: BLE001 - query expansion is optional; seeds still work
        log("   [deep] query expansion failed; using seed queries")
    return proposed + [q for q in seed_queries if q]


def _deep_docs(cfg, topic: str, focus: str, seed_query: str, log=print):
    """Gather deep-research documents with the LLM query expansion overlapped with a
    warm-up search for the deterministic seed query. Search results are disk-cached,
    so the warmed seed search is a cache hit inside gather_documents - the seed's
    network time hides behind the expansion LLM call instead of adding to it."""
    from . import deep_research as dr
    from . import search as search_mod
    out = concurrency.gather({
        "proposed": lambda: _research_queries(cfg, topic, focus, log=log),
        "warm": lambda: search_mod.web_search(seed_query, max_results=5),
    })
    return dr.gather_documents((out.get("proposed") or []) + [seed_query], log=log)


# ── Revision-loop helpers ─────────────────────────────────────────────────────
def _merge_fix_notes(instruction: str | None, crit: S.Critique) -> str:
    """Revision notes for the next attempt. The human instruction must survive every
    round - it used to be overwritten by the first critique."""
    notes = render.render_fix_notes(crit)
    if instruction:
        return (f"Human reviewer instruction (highest priority - always honor):\n"
                f"{instruction}\n\nCritique notes:\n{notes}")
    return notes


def _crit_better(a: S.Critique, b: S.Critique) -> bool:
    """True when critique a judges its draft better than b judges its own:
    approve beats non-approve, then fewer blocking issues, then higher insight,
    then higher confidence."""
    if (a.verdict == "approve") != (b.verdict == "approve"):
        return a.verdict == "approve"
    if len(a.blocking) != len(b.blocking):
        return len(a.blocking) < len(b.blocking)
    if a.insight != b.insight:
        return a.insight > b.insight
    return a.confidence > b.confidence


# Sampling temperatures for divergent first drafts (attempt 0, best-of-N): conservative,
# default, and adventurous. The critic picks the winner; revisions refine it.
_DIVERGENT_TEMPS = (0.7, 1.0, 1.2)


def _draft_glimpse(draft: str) -> str:
    """First prose line of a draft, for the dashboard - what is it actually writing?"""
    return next((ln.strip() for ln in draft.splitlines()
                 if ln.strip() and not ln.lstrip().startswith(("#", "!", "```"))), "")[:76]


def _pick_variant(drafts: dict, crits: dict, ask, log) -> tuple[str, S.Critique]:
    """Choose among divergent drafts. The critic ranks them; in manual interactive
    runs (ask provided) the human gets the final say - taste is exactly what the
    human is in the loop for. Enter accepts the critic's pick."""
    keys = list(drafts)
    best = keys[0]
    for k in keys:
        if _crit_better(crits[k], crits[best]):
            best = k
    if ask is None:
        return drafts[best], crits[best]
    lines = []
    for i, k in enumerate(keys, 1):
        c = crits[k]
        star = "  ← critic's pick" if k == best else ""
        lines.append(f"  [{i}] {c.verdict} · insight {c.insight}/5 · "
                     f"{len(c.blocking)} blocking{star}\n"
                     f'      "{_draft_glimpse(drafts[k])}"')
    try:
        choice = ask("Variant drafts ready:\n" + "\n".join(lines)
                     + f"\npick [1-{len(keys)}, Enter = critic's pick]: ")
        idx = int(str(choice).strip()) - 1
        if 0 <= idx < len(keys):
            best = keys[idx]
            log(f"   human picked variant {idx + 1}")
    except (ValueError, TypeError):
        pass   # Enter / noise → critic's pick
    return drafts[best], crits[best]


def _insight_note(crit: S.Critique, bar: int) -> str:
    """Revision note for a draft that is correct but generic."""
    return (f"The draft is publishable-correct but generic (insight {crit.insight}/5; "
            f"the bar is {bar}). Sharpen the argument: lead with the contestable claim, "
            "replace each generic statement with a specific fact, example, or number, "
            "and cut every sentence that could appear unchanged in another piece on "
            "this topic.")


def _length_note(word_count: int, target: int) -> str | None:
    """The word-count line the writer/critic prompts key off (None when no target)."""
    if not target:
        return None
    if word_count:
        return f"Draft word count: {word_count} words (target ~{target} words)."
    return f"Target length: ~{target} words."


# Genres where an auto-generated concept diagram is appropriate (book image fallback).
_NONFICTION_RE = re.compile(
    r"non-?fiction|technical|guide|how-?to|textbook|reference|tutorial|business|"
    r"science|history|self-?help|essay|journalism|education|manual", re.IGNORECASE)


# ── Source registry (stable citation numbering) ──────────────────────────────
_CITE = re.compile(r"\[(\d+)\](?!\()")   # [3] but not a markdown link label [3](...)


def _register_sources(registry: list[dict], sources) -> dict[int, int]:
    """Add a unit's sources to the project-wide registry (deduped by URL, first-seen
    order) and return {local_number: global_number}. Global number = 1-based position
    in the registry, which is exactly the final References numbering - so in-text
    citations rewritten with this map always match the reference list."""
    by_url = {s.get("url"): i + 1 for i, s in enumerate(registry) if s.get("url")}
    mapping: dict[int, int] = {}
    for local, s in enumerate(sources, 1):
        d = s if isinstance(s, dict) else s.model_dump()
        url = (d.get("url") or "").strip()
        if not url:
            continue   # un-linkable source: leave its citations untouched
        if url not in by_url:
            registry.append(d)
            by_url[url] = len(registry)
        mapping[local] = by_url[url]
    return mapping


def _renumber_citations(text: str, mapping: dict[int, int]) -> str:
    """Rewrite in-text [n] citations from per-unit numbering to registry numbering.
    Two-phase (via placeholders) so swaps like {1->3, 3->1} can't collide."""
    if not mapping or all(k == v for k, v in mapping.items()):
        return text
    def _sub(m):
        n = int(m.group(1))
        return f"[\x00{mapping[n]}\x00]" if n in mapping else m.group(0)
    return _CITE.sub(_sub, text).replace("\x00", "")


# A section heading the LLM prefixed with "Section N:" / "Section N -" - the producer
# owns numbering, so strip the prefix and keep the real title.
_SECTION_PREFIX = re.compile(r"(?im)^(#{1,4}\s*)Section\s+\d+\s*[:.–—-]\s*")
# A trailing References block the section writer emitted on its own (the producer
# assembles the real one). Cuts from the References heading to the end of the section.
_REF_BLOCK = re.compile(r"(?ims)\n#{1,4}\s*References\b.*\Z")
# One reference entry inside such a block: "[3] Author (2009)..." up to the next marker.
_REF_ENTRY = re.compile(r"\[(\d+)\]\s*(.*?)(?=\s*\[\d+\]|\Z)", re.DOTALL)


def _strip_section_prefix(md: str) -> str:
    return _SECTION_PREFIX.sub(r"\1", md)


def _consolidate_section_refs(sections_md: list[str]) -> tuple[list[str], list[str]]:
    """Merge writer-emitted per-section reference lists into one global list.

    Each section may end with its own '## References' block numbered locally ([1], [2]
    that reset every section). This pulls those blocks out, dedupes entries by text,
    renumbers each section's in-text [n] citations to the global sequence, and returns
    (cleaned_sections, global_entries). Used when there are no registry-managed sources
    (e.g. the researcher was off); otherwise the registry numbering already governs.
    """
    global_entries: list[str] = []
    text_to_global: dict[str, int] = {}
    cleaned: list[str] = []
    for sec in sections_md:
        m = _REF_BLOCK.search(sec)
        if not m:
            cleaned.append(sec)
            continue
        body, block = sec[:m.start()], sec[m.start():]
        local_to_global: dict[int, int] = {}
        for em in _REF_ENTRY.finditer(block):
            entry = " ".join(em.group(2).split()).strip(" .")
            if not entry:
                continue
            key = entry.lower()
            if key not in text_to_global:
                global_entries.append(entry)
                text_to_global[key] = len(global_entries)
            local_to_global[int(em.group(1))] = text_to_global[key]
        cleaned.append(_renumber_citations(body, local_to_global).rstrip())
    return cleaned, global_entries


# ── Upfront-intake plumbing (answers gathered once, before the autonomous run) ─
def _with_intake(abstract: str, intake: str | None) -> str:
    """Fold the author's upfront answers into the abstract the planner sees, so the
    plan/outline (length, depth, sections, audience) reflects them from the start."""
    if not intake:
        return abstract
    return (abstract + "\n\nAUTHOR REQUIREMENTS (gathered upfront - honor these in the "
            "structure, depth, audience, and angle):\n" + intake)


def _record_author(uid: str, author: str | None) -> None:
    """Persist the author's name to user/profile.md (if given and not already set) so
    Production can fill bylines/copyright instead of escalating for a missing fact."""
    if not author or not author.strip():
        return
    prof = brain.user_profile(uid)
    if brain.read_text(prof):
        return   # never clobber an existing profile
    brain.ensure_user(uid)
    brain.write_text(prof, f"name: {author.strip()}\n")


# ── Setup (human picks a direction, then autonomous) ─────────────────────────
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
        "uid": uid, "book_id": book_id, "abstract": abstract,
        "intake": intake or "", "author": author or "",
        "phase": "chapters", "num_chapters": len(toc.chapters),
        "max_revisions": max_revisions, "consolidate_every": settings.consolidate_every,
        "current_chapter": 1, "committed": 0, "pending_review": False,
        "use_researcher": settings.use_researcher,
        "deep_research": settings.deep_research,
        "autonomous": autonomous,
        "humanize": settings.humanize if humanize is None else humanize,
        "use_images": settings.use_images,
        "use_embeddings": settings.use_embeddings,
        "divergent_drafts": settings.divergent_drafts,
        "min_insight": settings.min_insight,
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
def run(cfg: ModelConfig, uid: str, book_id: str, *, force: bool = False,
        autonomous: bool | None = None, log=print, ask=None) -> dict:
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
        return _run_article(cfg, art_paths, state, outline, force=force, log=log, ask=ask)
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
        from . import search as search_mod
        base_query = search_mod.build_query(plan, blueprint)
        if state.get("deep_research"):
            from . import deep_research as dr
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
        from . import images as img_mod
        query = f"{blueprint.title} {blueprint.purpose} {plan.genre}"
        fetched = img_mod.search_wikimedia(query, max_results=2)
        if fetched:
            log(f"   fetched {len(fetched)} image(s) from Wikimedia Commons")
            return [r.to_markdown(str(i + 1)) for i, r in enumerate(fetched)]
        # No Wikimedia image: generate an SVG diagram - but only for non-fiction-ish
        # genres. A "concept diagram" dropped into a novel chapter is always wrong.
        if not _NONFICTION_RE.search(plan.genre or ""):
            return None
        svg_text = nodes.generate_svg_diagram(cfg, blueprint.title, blueprint.purpose or "")
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

    def _write(notes, base, temperature=None):
        return nodes.write_chapter(cfg, plan, blueprint, fix_notes=notes,
                                   context=context, skills=skill_bodies, images=images,
                                   base_draft=base, requirements=requirements, voice=voice,
                                   length_note=_length_note(0, blueprint.target_words),
                                   temperature=temperature)

    def _critique(d):
        return nodes.critique_chapter(
            cfg, plan, blueprint, d, context=context, watch_list=watch,
            skills=skill_bodies, requirements=requirements,
            length_note=_length_note(len(d.split()), blueprint.target_words))

    n_div = max(1, int(state.get("divergent_drafts", 1) or 1))
    log(f"\n== Chapter {n}: {blueprint.title} ==")
    for attempt in range(max_rev + 1):
        if attempt == 0 and n_div > 1 and not base_draft:
            # Divergent first drafts: varied temperatures in parallel, critic picks the
            # winner, revisions refine it (selection for strength over convergence).
            temps = _DIVERGENT_TEMPS[:n_div]
            log(f"   drafting {len(temps)} variants (temps {', '.join(map(str, temps))})...")
            drafts = concurrency.gather(
                {f"v{i}": (lambda t=t, fn=fix_notes: _write(fn, None, t))
                 for i, t in enumerate(temps)},
                strict=True)
            log("   critiquing variants...")
            crits = concurrency.gather(
                {k: (lambda d=d: _critique(d)) for k, d in drafts.items()}, strict=True)
            picker_ask = None if state.get("autonomous") else ask
            draft, crit = _pick_variant(drafts, crits, picker_ask, log)
            log(f"   picked variant ({sum(1 for c in crits.values() if c.verdict == 'approve')}"
                f"/{len(temps)} approved)")
        else:
            log(f"   writing ({'draft' if attempt == 0 else f'revision {attempt}'})...")
            draft = _write(fix_notes, base_draft)
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
        if low_insight and crit.verdict == "approve":
            log(f"   insight {crit.insight}/5 below bar {min_insight} -> sharpening")
            fix_notes = (fix_notes + "\n\n" if fix_notes else "") + _insight_note(crit, min_insight)
        base_draft = draft   # revise the latest attempt, not regenerate from notes alone

    assert crit is not None and best is not None
    if approved_attempt >= 0 or state.get("autonomous"):
        if approved_attempt < 0:
            draft, crit = best   # commit the best-judged attempt, not the last one
            log(f"   autonomous: committing best draft "
                f"(blocking={len(crit.blocking)}, confidence={crit.confidence:.2f})")
        first_pass = approved_attempt == 0 and instruction is None
        state.setdefault("insights", []).append(crit.insight)   # quality history for the summary card
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

    brain.write_text(paths.ch(n), out.get("humanized") or draft)
    brain.write_text(paths.ch_summary(n), out["summary"])
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


def _praised_passages(uid: str, max_chars: int = 4000) -> str:
    """Passages the human marked great via /praise - positive signal for the learner."""
    d = brain.voice_dir(uid)
    if not d.exists():
        return ""
    chunks: list[str] = []
    total = 0
    for p in sorted(d.glob("praised-*.md")):
        text = (brain.read_text(p) or "").strip()
        if not text:
            continue
        take = text[: max(0, max_chars - total)]
        chunks.append(f"### {p.stem}\n{take}")
        total += len(take)
        if total >= max_chars:
            break
    return "\n\n".join(chunks)


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

    out = nodes.learn(cfg, plan, instructions, "\n".join(findings), existing,
                      praised=_praised_passages(uid))
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
def _manuscript_section_bodies(ms: str) -> list[str]:
    """Section bodies from an assembled manuscript (skips header + References).
    Tolerates the doubled '---' separators the header block produces."""
    bodies = []
    for part in ms.split("\n\n---\n\n"):
        s = re.sub(r"^(?:-{3,}\s*)+", "", part.strip()).strip()
        if s.startswith("## ") and not s.startswith("## References"):
            bodies.append(s)
    return bodies


def _replace_manuscript_section(ms: str, idx: int, new_body: str) -> str | None:
    """Replace the idx-th (0-based) section body in an assembled manuscript.
    Returns the new manuscript, or None when idx is out of range."""
    parts = ms.split("\n\n---\n\n")
    count = -1
    for i, part in enumerate(parts):
        s = re.sub(r"^(?:-{3,}\s*)+", "", part.strip()).strip()
        if s.startswith("## ") and not s.startswith("## References"):
            count += 1
            if count == idx:
                prefix = part[: part.find(s)] if s and s in part else ""
                parts[i] = prefix + new_body
                return "\n\n---\n\n".join(parts)
    return None


def revise_unit(cfg: ModelConfig, uid: str, book_id: str, n: int, instruction: str,
                *, log=print) -> None:
    """Rewrite ONE chapter/section of a finished (or in-progress) piece to the human's
    instruction, re-critique once, and patch the committed file + assembled manuscript.
    Closes the gap between 'pipeline done' and 'author satisfied' without a full re-run.

    Books: the chapter file is rewritten and production re-assembles the manuscript.
    Canon is NOT re-extracted (a post-completion polish must not mutate the knowledge
    base later chapters were already written against)."""
    llm.reset_usage()
    llm.set_project(book_id)
    voice = brain.voice_exemplars(uid)

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
        thesis_md = brain.read_text(art.root / "thesis.md")
        log(f"== Revising section {n}: {section.heading} ==")
        log("   rewriting to your instruction...")
        draft = nodes.write_article_section(
            cfg, outline, section, fix_notes=instruction, base_draft=base,
            thesis=thesis_md, voice=voice,
            requirements=(state.get("intake") or "").strip() or None)
        log("   critiquing...")
        crit = nodes.critique_article_section(
            cfg, outline, section, draft, thesis=thesis_md,
            research_on=bool(state.get("use_researcher")))
        if crit.blocking and crit.verdict != "approve":
            log(f"   {len(crit.blocking)} blocking issue(s) - one fix pass...")
            draft = nodes.write_article_section(
                cfg, outline, section, fix_notes=_merge_fix_notes(instruction, crit),
                base_draft=draft, thesis=thesis_md, voice=voice)
        if state.get("humanize"):
            log("   humanizing...")
            draft = humanizer.humanize(cfg, draft)
        draft = _strip_section_prefix(draft).strip()
        if brain.read_text(art.section(n)) is not None:
            brain.write_text(art.section(n), draft)
        if ms:
            patched = _replace_manuscript_section(ms, n - 1, draft)
            if patched:
                brain.write_text(art.manuscript, patched)
        brain.append_text(art.revision_log, f"## Section {n} post-completion revision\n{instruction}")
        log(f"[OK] Section {n} revised. Re-export to refresh output files.")
        return

    paths, state, plan, toc = _load(uid, book_id)
    if not (1 <= n <= len(toc.chapters)):
        raise ValueError(f"Chapter {n} out of range (1-{len(toc.chapters)}).")
    blueprint = toc.chapters[n - 1]
    base = brain.read_text(paths.ch(n))
    if base is None:
        raise FileNotFoundError(f"Chapter {n} has not been committed yet - use `review` instead.")
    log(f"== Revising chapter {n}: {blueprint.title} ==")
    log("   rewriting to your instruction...")
    draft = nodes.write_chapter(cfg, plan, blueprint, fix_notes=instruction,
                                base_draft=base, voice=voice,
                                requirements=(state.get("intake") or "").strip() or None)
    log("   critiquing...")
    crit = nodes.critique_chapter(cfg, plan, blueprint, draft)
    if crit.blocking and crit.verdict != "approve":
        log(f"   {len(crit.blocking)} blocking issue(s) - one fix pass...")
        draft = nodes.write_chapter(cfg, plan, blueprint,
                                    fix_notes=_merge_fix_notes(instruction, crit),
                                    base_draft=draft, voice=voice)
    if state.get("humanize"):
        log("   humanizing...")
        draft = humanizer.humanize(cfg, draft)
    brain.write_text(paths.ch(n), draft)
    brain.append_text(paths.revision_log, f"## Chapter {n} post-completion revision\n{instruction}")
    if brain.read_text(paths.manuscript):
        log("   re-assembling manuscript...")
        run_production(cfg, uid, book_id, log=log)
    log(f"[OK] Chapter {n} revised. Re-export to refresh output files.")


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
    export.markdown_to_pdf(md, out, title=title, base_dir=root)
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
    export.markdown_to_epub(md, out, title=title, author=author, base_dir=root)
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
    intake: str | None = None, author: str | None = None,
) -> str:
    brain.ensure_user(uid)
    _record_author(uid, author)
    outline = nodes.build_article_outline(cfg, _with_intake(abstract, intake), chosen, num_sections)
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
        "uid": uid, "article_id": article_id, "abstract": abstract,
        "intake": intake or "", "author": author or "",
        "mode": "article",
        "phase": "sections", "num_sections": len(outline.sections),
        "max_revisions": max_revisions, "current_section": 1,
        "committed": 0, "pending_review": False,
        "use_researcher": settings.use_researcher,
        "deep_research": settings.deep_research,
        "autonomous": autonomous,
        "humanize": settings.humanize if humanize is None else humanize,
        "use_images": settings.use_images,
        "use_embeddings": settings.use_embeddings,
        "article_cohesion": settings.article_cohesion,
        "table_read": settings.table_read,
        "divergent_drafts": settings.divergent_drafts,
        "min_insight": settings.min_insight,
        "escalate_below_confidence": 0.0 if autonomous else settings.escalate_below_confidence,
        "escalate_on_contradiction": False,
    }
    brain.write_json(paths.run_state, state)
    return article_id


def _run_article(cfg, paths: ArticlePaths, state, outline, *, force, log, ask=None):
    if state.get("pending_review"):
        log(f"[!] Section {state['current_section']} awaits review. "
            f"Run: review --chapter {state['current_section']} --instruction \"...\"")
        return state

    prefetch: dict[int, object] = {}
    pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="unit-prefetch")
    try:
        while state["phase"] != "done":
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
                outcome = _process_article_section(cfg, paths, outline, state, n, log,
                                                   prefetched=prefetch.pop(n, None), ask=ask)
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
    log(f"[OK] Article '{paths.article_id}' complete. Manuscript: {paths.manuscript}")
    _summary = llm.usage_summary()
    if _summary:
        log("   " + _summary)
    return state


def _section_fetch(cfg, paths: ArticlePaths, outline, state, n, log) -> dict:
    """Network-bound inputs for section n (research, images, skills) - independent of
    any section's prose, so _run_article prefetches it for section n+1 (see
    _chapter_fetch)."""
    from types import SimpleNamespace
    section = outline.sections[n - 1]

    def _do_research():
        if not state.get("use_researcher"):
            return ("", [])
        from . import search as search_mod
        base_query = section.search_query or f"{outline.title} {section.heading}"
        if state.get("deep_research"):
            from . import deep_research as dr
            docs = _deep_docs(
                cfg, f"{outline.title} ({outline.angle})",
                f"{section.heading}. {section.purpose}", base_query, log=log)
            brief = nodes.deep_research_article(cfg, outline, section,
                                                dr.format_documents(docs) or None)
            # Real fetched sources are more reliable than LLM-copied URLs; prefer them.
            sources = [S.Source(title=d.title, url=d.url) for d in docs] or list(brief.sources)
            prefix = ("## Research brief\n" + "\n".join([
                "### Facts", *(f"- {f}" for f in brief.facts),
                "### Style cues", *(f"- {s}" for s in brief.style_cues),
                "### Sources", *(f"- [{s.title}]({s.url})" for s in sources),
            ]) + "\n\n")
            return (prefix, sources)
        results = search_mod.web_search(base_query, max_results=5)
        web_results = search_mod.format_results(results)
        if results:
            log(f"   fetched {len(results)} web result(s) for: {base_query[:60]}")
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
                             prefetched=None, ask=None) -> str:
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
    context_prefix, sources = out.get("research") or ("", [])
    images: list[str] | None = out.get("images")

    # Prior section summaries
    article_context = _assemble_article_context(paths, n)
    full_context = (context_prefix + article_context).strip() or None

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
    voice = brain.voice_exemplars(paths.uid)
    crit: S.Critique | None = None
    draft = ""
    best: tuple[str, S.Critique] | None = None
    approved_attempt = -1

    def _write(notes, base, temperature=None):
        return nodes.write_article_section(
            cfg, outline, section, fix_notes=notes, context=full_context,
            skills=skill_bodies, images=images, base_draft=base,
            requirements=requirements, thesis=thesis_md, voice=voice,
            length_note=_length_note(0, target), temperature=temperature)

    def _critique(d):
        return nodes.critique_article_section(
            cfg, outline, section, d, context=full_context, watch_list=watch,
            requirements=requirements, thesis=thesis_md, research_on=research_on,
            length_note=_length_note(len(d.split()), target))

    n_div = max(1, int(state.get("divergent_drafts", 1) or 1))
    log(f"\n== Section {n}: {section.heading} ==")
    for attempt in range(max_rev + 1):
        if attempt == 0 and n_div > 1 and not base_draft:
            # Divergent first drafts: sample at varied temperatures in parallel, critique
            # each, refine the winner. Selection for strength, not convergence to safety.
            temps = _DIVERGENT_TEMPS[:n_div]
            log(f"   drafting {len(temps)} variants (temps {', '.join(map(str, temps))})...")
            drafts = concurrency.gather(
                {f"v{i}": (lambda t=t, fn=fix_notes: _write(fn, None, t))
                 for i, t in enumerate(temps)},
                strict=True)
            log("   critiquing variants...")
            crits = concurrency.gather(
                {k: (lambda d=d: _critique(d)) for k, d in drafts.items()}, strict=True)
            picker_ask = None if state.get("autonomous") else ask
            draft, crit = _pick_variant(drafts, crits, picker_ask, log)
            log(f"   picked variant ({sum(1 for c in crits.values() if c.verdict == 'approve')}"
                f"/{len(temps)} approved)")
        else:
            log(f"   writing ({'draft' if attempt == 0 else f'revision {attempt}'})...")
            draft = _write(fix_notes, base_draft)
            log("   critiquing...")
            crit = _critique(draft)
        glimpse = _draft_glimpse(draft)
        if glimpse:
            log(f'   · opens: "{glimpse}"')
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
        if low_insight and crit.verdict == "approve":
            log(f"   insight {crit.insight}/5 below bar {min_insight} -> sharpening")
            fix_notes = (fix_notes + "\n\n" if fix_notes else "") + _insight_note(crit, min_insight)
        base_draft = draft

    assert crit is not None and best is not None
    if approved_attempt >= 0 or state.get("autonomous"):
        if approved_attempt < 0:
            draft, crit = best
            log(f"   autonomous: committing best draft "
                f"(blocking={len(crit.blocking)}, confidence={crit.confidence:.2f})")
        first_pass = approved_attempt == 0 and instruction is None
        state.setdefault("insights", []).append(crit.insight)   # quality history for the summary card
        _commit_section(cfg, paths, section, n, draft, skill_names, sources, first_pass,
                        log, humanize=bool(state.get("humanize")))
        paths.section_draft(n).unlink(missing_ok=True)
        return "commit"
    _escalate(paths, n, crit, draft)
    return "escalate"


def _commit_section(cfg, paths: ArticlePaths, section, n, draft, skill_names, sources,
                    first_pass, log, *, humanize: bool = False) -> None:
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
        tasks["humanized"] = lambda: humanizer.humanize(cfg, draft)
    out = concurrency.gather(tasks, strict=True)

    brain.write_text(paths.section(n), out.get("humanized") or draft)
    brain.write_text(paths.section_summary(n), out["summary"])

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
    raw_sources = brain.read_json(paths.sources_json) or []
    seen_urls: set = set()
    unique: list = []
    for s in raw_sources:
        url = s.get("url", "") if isinstance(s, dict) else getattr(s, "url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique.append(s if isinstance(s, dict) else s.model_dump())

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
            edited = nodes.cohesion_edit(cfg, outline, body)
        except Exception:  # noqa: BLE001 - cohesion is best-effort polish
            edited = ""
        if (edited
                and len(edited.split()) >= 0.6 * len(body.split())
                and edited.count("## ") >= body.count("## ") * 0.8):
            body = edited
        else:
            log("   cohesion edit rejected by guard - keeping original sections")

    # Build references section
    refs_md = ""
    if not unique and _CITE.search(body):
        # In-text [n] markers with no registry entries = the writer cited from memory.
        log("   [!] citations present but NO verified sources captured - they are "
            "model-generated and unverifiable. Enable the researcher "
            "(/set use_researcher true) for grounded citations.")
    if not unique and extracted_refs:
        lines = ["## References", ""] + [f"{i}. {t}" for i, t in enumerate(extracted_refs, 1)]
        refs_md = "\n".join(lines)
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
    total_words = len(body.split())
    read_time = max(1, round(total_words / 200))
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

    # Table read: a cold read of the WHOLE piece as a skeptical target-audience reader.
    # Catches boredom curves and trust breaks no per-section critic can see. Report-only,
    # best-effort - it informs the human (and `revise`), it never rewrites anything.
    if state.get("table_read") and body.strip():
        log("   table read (skeptical reader pass)...")
        try:
            report = nodes.table_read(cfg, outline, body)
            brain.write_text(paths.root / "table_read.md", report)
            log("   [table-read] report -> table_read.md "
                "(act on it with: revise --chapter N --instruction \"...\")")
        except Exception as e:  # noqa: BLE001 - a missing report must not fail production
            log(f"   [table-read] skipped ({type(e).__name__})")


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
    out = nodes.learn(cfg, article_as_plan, instructions, "\n".join(findings), existing,
                      praised=_praised_passages(uid))
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
    export.markdown_to_html(md, out, title=title, base_dir=root)
    log(f"[OK] HTML -> {out}")
    return out


def export_docx(uid: str, book_id: str, *, log=print):
    from . import export
    root, manuscript, title = _export_paths_and_title(uid, book_id)
    md = brain.read_text(manuscript)
    if not md:
        raise FileNotFoundError(f"No manuscript for '{book_id}'. Run it first.")
    out = root / "manuscript.docx"
    export.markdown_to_docx(md, out, title=title, base_dir=root)
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
