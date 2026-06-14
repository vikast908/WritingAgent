"""Shared orchestrator leaf helpers, used by both the book and article pipelines.

Research/query building, divergent-draft selection (`_pick_variant`,
`_divergent_first_draft`), claim verification, citation/reference utilities, author
preferences, run-state scaffolding (`_base_run_state`, `_apply_run_control`,
`_mark_escalated`, `_log_run_complete`) and the shared learner tail. The package
facade (`__init__`) re-exports everything here, so `orchestrator.X` keeps resolving.
"""
from __future__ import annotations

import re

from .. import brain, concurrency, llm, nodes, render
from .. import schemas as S
from .. import skills as skills_mod
from ..brain import BookPaths
from ..config import load_settings

__all__ = [
    '_BUDGET_PAUSE_MSG',
    '_research_queries',
    '_deep_docs',
    '_merge_fix_notes',
    '_crit_better',
    '_DIVERGENT_TEMPS',
    '_save_version',
    '_draft_glimpse',
    '_pick_variant',
    '_insight_note',
    '_verify_claims_gate',
    '_pref_log',
    '_record_preference',
    '_read_preferences',
    '_length_note',
    '_NONFICTION_RE',
    '_CITE',
    '_register_sources',
    '_renumber_citations',
    '_SECTION_PREFIX',
    '_REF_BLOCK',
    '_REF_ENTRY',
    '_strip_section_prefix',
    '_consolidate_section_refs',
    '_with_intake',
    '_record_author',
    '_base_run_state',
    '_load',
    '_apply_run_control',
    '_mark_escalated',
    '_log_run_complete',
    '_divergent_first_draft',
    '_finalize_unit',
    '_praised_passages',
    '_run_learner',
]


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
    from .. import deep_research as dr
    from .. import search as search_mod
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


def _save_version(paths, unit_tag: str, text: str, label: str = "") -> int:
    """Append a draft snapshot under <project>/versions/ - git-for-writing.

    Every generated draft (divergent variant, revision, committed final, revise
    output) gets the next number for its unit. Survives article cleanup (which only
    sweeps the project root), so `versions` / `read --v` work after completion.
    """
    d = paths.root / "versions"
    k = len(list(d.glob(f"{unit_tag}.v*.md"))) + 1 if d.exists() else 1
    header = f"<!-- v{k}{' · ' + label if label else ''} -->\n"
    brain.write_text(d / f"{unit_tag}.v{k:02d}.md", header + text)
    return k


def _draft_glimpse(draft: str) -> str:
    """First prose line of a draft, for the dashboard - what is it actually writing?"""
    return next((ln.strip() for ln in draft.splitlines()
                 if ln.strip() and not ln.lstrip().startswith(("#", "!", "```"))), "")[:76]


def _pick_variant(cfg, unit_desc, thesis, drafts: dict, crits: dict, ask, log,
                  *, use_judge: bool = True) -> tuple[str, S.Critique, str, str]:
    """Choose among divergent drafts and return (draft, critique, refine_note, pref).

    A dedicated judge reads all drafts SIDE BY SIDE (more reliable than comparing each
    draft's jittery absolute self-score via `_crit_better`); the scalar comparison is
    kept as the fallback when the judge is off or errors. `refine_note` is the winner's
    biggest remaining flaw (from the judge), fed into the refinement pass; `pref` is a
    preference breadcrumb for the learner (what won and why - plan §8). In manual
    interactive runs (ask provided) the human gets the final say; Enter = the pick."""
    keys = list(drafts)
    scalar_best = keys[0]
    for k in keys:
        if _crit_better(crits[k], crits[scalar_best]):
            scalar_best = k
    best = scalar_best
    note = pref = ""
    if use_judge and len(keys) > 1:
        labelled = {str(i + 1): drafts[k] for i, k in enumerate(keys)}
        try:
            ranking = nodes.rank_variants(cfg, unit_desc, labelled, thesis)
            w = ranking.winner
            if isinstance(w, int) and 1 <= w <= len(keys):
                best = keys[w - 1]
                note = (ranking.winner_weakness or "").strip()
                log(f"   judge picked variant {w}/{len(keys)}"
                    + (f" - {ranking.reason[:80]}" if ranking.reason else ""))
                pref = (f"## Tournament ({unit_desc})\n"
                        f"Chosen draft won over {len(keys) - 1} other(s). "
                        f"Why it won: {ranking.reason}. "
                        f"Remaining weakness: {ranking.winner_weakness}\n"
                        f'Winning opener: "{_draft_glimpse(drafts[best])}"')
        except Exception:  # noqa: BLE001 - the judge is an upgrade over scalar, never fatal
            log("   judge unavailable - falling back to critic's scalar pick")
    if ask is None:
        return drafts[best], crits[best], note, pref
    lines = []
    for i, k in enumerate(keys, 1):
        c = crits[k]
        star = "  ← pick" if k == best else ""
        lines.append(f"  [{i}] {c.verdict} · insight {c.insight}/5 · "
                     f"{len(c.blocking)} blocking{star}\n"
                     f'      "{_draft_glimpse(drafts[k])}"')
    try:
        choice = ask("Variant drafts ready:\n" + "\n".join(lines)
                     + f"\npick [1-{len(keys)}, Enter = recommended]: ")
        idx = int(str(choice).strip()) - 1
        if 0 <= idx < len(keys):
            best = keys[idx]
            note = pref = ""   # human override: don't impose the judge's note/preference
            log(f"   human picked variant {idx + 1}")
    except (ValueError, TypeError):
        pass   # Enter / noise → recommended pick
    return drafts[best], crits[best], note, pref


def _insight_note(crit: S.Critique, bar: int) -> str:
    """Revision note for a draft that is correct but generic."""
    return (f"The draft is publishable-correct but generic (insight {crit.insight}/5; "
            f"the bar is {bar}). Sharpen the argument: lead with the contestable claim, "
            "replace each generic statement with a specific fact, example, or number, "
            "and cut every sentence that could appear unchanged in another piece on "
            "this topic.")


# ── Claim verification gate (evidence as fact, plan §15.4) ────────────────────
def _verify_claims_gate(cfg, state, draft: str, source_text: str, crit: S.Critique,
                        log) -> tuple[S.Critique, str]:
    """Check each [N]-cited specific claim against its source. No-ops when verification
    is off, there is no source material, or the draft has no citations. Severity is
    gated on the strength of the ground truth (plan §15.6):

    - **deep research** (full page text) - an unsupported claim is strong evidence of
      fabrication: append to `crit.blocking`, downgrade `approve`->`revise`, and return a
      revision note so the writer fixes it.
    - **shallow research** (snippets only) - the source is too thin to confidently fail a
      claim (it may be true but simply absent from the snippet): surface as `crit.nits`
      and never block, so a default-on setting can't tank a good draft on weak evidence."""
    if not state.get("verify_claims") or not source_text or not _CITE.search(draft):
        return crit, ""
    try:
        audit = nodes.verify_claims(cfg, draft, source_text)
    except Exception:  # noqa: BLE001 - a verification guard must never fail a run
        return crit, ""
    bad = [c for c in audit.checks if c.supported == "unsupported"]
    if not bad:
        return crit, ""
    if not state.get("deep_research"):   # thin snippets -> advisory only, never blocking
        for c in bad:
            crit.nits.append(f"unsupported by cited source [{c.source}]: {c.claim}"
                             + (f" ({c.note})" if c.note else ""))
        log(f"   claim check: {len(bad)} cited claim(s) unsupported by snippet "
            "(flagged as nits; enable deep_research to enforce)")
        return crit, ""
    for c in bad:
        crit.blocking.append(S.BlockingIssue(
            type="evidence", where=f"[{c.source}]",
            detail=f"Cited claim not supported by source [{c.source}]: {c.claim}",
            fix=c.note or "Cite a source that supports it, soften to what the source says, or cut it."))
    if crit.verdict == "approve":
        crit.verdict = "revise"
    log(f"   claim check: {len(bad)} cited claim(s) unsupported by full-text source -> revise")
    note = ("Some cited claims are NOT supported by the sources they cite. Fix each - cite a "
            "source that backs it, soften it to what the source actually says, or cut it:\n"
            + "\n".join(f'- "{c.claim}" [{c.source}]'
                        + (f" ({c.note})" if c.note else "") for c in bad))
    return crit, note


# ── Preference signals for the learner (compounding, plan §8) ─────────────────
def _pref_log(paths):
    return paths.root / "learning_signals.md"


def _record_preference(paths, entry: str) -> None:
    """Append a model-judged preference signal (a tournament outcome or a revision that
    fixed a flaw) for the learner to distill into skills. Secondary signal: candidate
    skills only, never auto-promoted to user scope (plan §8 - same gate as critic findings)."""
    try:
        brain.append_text(_pref_log(paths), entry)
    except Exception:  # noqa: BLE001 - a learning breadcrumb must never break a run
        pass


def _read_preferences(paths) -> str:
    return (brain.read_text(_pref_log(paths)) or "").strip()


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
def _base_run_state(uid, abstract, *, intake, author, max_revisions, autonomous, humanize,
                    settings) -> dict:
    """Run-state keys shared by every project (book + article). Callers spread this and add
    the mode-specific keys (the id, phase, unit counter, and any per-mode quality flags)."""
    return {
        "uid": uid, "abstract": abstract,
        "intake": intake or "", "author": author or "",
        "max_revisions": max_revisions, "committed": 0, "pending_review": False,
        "use_researcher": settings.use_researcher,
        "deep_research": settings.deep_research,
        "autonomous": autonomous,
        "humanize": settings.humanize if humanize is None else humanize,
        "use_images": settings.use_images,
        "diagram_engine": settings.diagram_engine,
        "use_embeddings": settings.use_embeddings,
        "divergent_drafts": settings.divergent_drafts,
        "tournament_judge": settings.tournament_judge,
        "min_insight": settings.min_insight,
        # Autonomous runs never pause on low confidence.
        "escalate_below_confidence": 0.0 if autonomous else settings.escalate_below_confidence,
    }


def _load(uid: str, book_id: str):
    paths = BookPaths(book_id, uid)
    state = brain.read_json(paths.run_state)
    if state is None:
        raise FileNotFoundError(f"No run_state for book '{book_id}'. Run `book new` first.")
    plan = S.BookPlan(**brain.read_json(paths.root / "plan.json"))
    toc = S.TOC(**brain.read_json(paths.root / "toc.json"))
    return paths, state, plan, toc


# ── Main driver ──────────────────────────────────────────────────────────────
def _apply_run_control(control, state, paths, log) -> bool:
    """Honor live run controls at a unit boundary (the only safe point - a model call
    can't be interrupted mid-token). Returns True if the run should pause now (the caller
    returns the already-durable state). No-op when control is None, so every existing
    caller and test is unaffected. `control` is duck-typed (shell._RunControls)."""
    if control is None:
        return False
    if control.take_manual():
        s = load_settings()
        state["autonomous"] = False
        state["escalate_below_confidence"] = s.escalate_below_confidence
        state["escalate_on_contradiction"] = s.escalate_on_contradiction
        brain.write_json(paths.run_state, state)
        log("[i] manual review enabled for the remaining units.")
    if control.pause:
        log("[i] paused on request - resumable. Run again to continue.")
        return True
    return False


def _mark_escalated(state, paths, kind: str, msg: str, log) -> None:
    """Record a unit escalation in the durable run_state and tell the author how to
    resolve it. Shared by the book and article run loops; the caller returns `state`
    afterwards (the run pauses here until the review is answered)."""
    state["pending_review"] = True
    state["review_kind"] = kind
    brain.write_json(paths.run_state, state)
    log(msg)


def _log_run_complete(label: str, name: str, manuscript, log) -> None:
    """Shared run-completion footer: the done line + the per-run token/cost usage
    summary (book and article print these identically)."""
    log(f"[OK] {label} '{name}' complete. Manuscript: {manuscript}")
    summary = llm.usage_summary()
    if summary:
        log("   " + summary)


def _divergent_first_draft(cfg, paths, *, unit_tag, unit_desc, n_div, fix_notes,
                           write, critique, thesis_brief, ask, autonomous, use_judge,
                           skeletons, log):
    """Attempt-0 divergent drafting, shared by chapters and sections: draft n_div
    variants at varied temperatures in parallel, critique each, and let a side-by-side
    judge pick the winner (selection for strength over convergence). With skeletons=True
    (article opt-in) the variants are short and only the winner is expanded to full
    length, so discarded drafts cost ~a third the tokens. `write`/`critique` are the
    unit's own node closures. Returns (draft, crit, judge_note)."""
    temps = _DIVERGENT_TEMPS[:n_div]
    log(f"   drafting {len(temps)} variants (temps {', '.join(map(str, temps))})...")
    drafts = concurrency.gather(
        {f"v{i}": (lambda t=t, fn=fix_notes: write(fn, None, t, skeleton=skeletons))
         for i, t in enumerate(temps)},
        strict=True)
    log("   critiquing variants...")
    crits = concurrency.gather(
        {k: (lambda d=d: critique(d)) for k, d in drafts.items()}, strict=True)
    label_kind = "skeleton" if skeletons else "variant"
    for i, d in enumerate(drafts.values()):
        _save_version(paths, unit_tag, d, label=f"{label_kind} temp={temps[i]}")
    picker_ask = None if autonomous else ask
    draft, crit, judge_note, pref = _pick_variant(
        cfg, unit_desc, thesis_brief, drafts, crits, picker_ask, log, use_judge=use_judge)
    if pref:
        _record_preference(paths, pref)
    log(f"   picked variant ({sum(1 for c in crits.values() if c.verdict == 'approve')}"
        f"/{len(temps)} approved)")
    if skeletons:   # expand only the winning skeleton to full length (article F3)
        log("   expanding the winning skeleton to full length...")
        draft = write(((judge_note + "\n") if judge_note else "")
                      + "Expand this skeleton into the full section at the target "
                      "length - keep its structure, argument, and specifics; add the "
                      "prose, examples, and citations.", draft)
        _save_version(paths, unit_tag, draft, label="skeleton-expanded")
        crit = critique(draft)
        judge_note = ""   # consumed by the expansion
    return draft, crit, judge_note


def _finalize_unit(state, *, approved_attempt, best, draft, crit, instruction, log):
    """Post-attempt-loop bookkeeping shared by chapters and sections: in autonomous mode
    fall back to the best-judged attempt (not the last), compute first_pass, and append
    the insight/score history the summary card reads. Returns (draft, crit, first_pass)."""
    if approved_attempt < 0:
        draft, crit = best   # commit the best-judged attempt, not the last one
        log(f"   autonomous: committing best draft "
            f"(blocking={len(crit.blocking)}, confidence={crit.confidence:.2f})")
    first_pass = approved_attempt == 0 and instruction is None
    state.setdefault("insights", []).append(crit.insight)   # quality history for the summary card
    state.setdefault("scores", []).append(
        {"insight": crit.insight, "clarity": crit.clarity,
         "structure": crit.structure, "evidence": crit.evidence})
    return draft, crit, first_pass


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


def _run_learner(cfg, paths, plan, instructions: str, findings: str, *, log) -> None:
    """Shared learner tail (book + article): distill craft skills + a watch-list from a
    finished piece, write them, reconcile, log. Callers gather their own instructions /
    critic findings and build the plan object (a real BookPlan, or an article proxy)."""
    uid = paths.uid
    existing = "\n".join(p.stem for p in brain.skills_dir(uid).glob("*.md"))
    out = nodes.learn(cfg, plan, instructions, findings, existing,
                      praised=_praised_passages(uid), preferences=_read_preferences(paths))
    for prop in out.skills:
        skills_mod.write_skill(uid, prop)
    watch = ["# Avoid list (watch-list)", ""] + [f"- {w.pattern} - {w.why}" for w in out.watch_items]
    brain.write_text(brain.watch_list(uid), "\n".join(watch))
    statuses = skills_mod.reconcile(uid)
    log(f"   [learn] +{len(out.skills)} skills, {len(out.watch_items)} watch items; "
        f"reconciled {len(statuses)} skills")
