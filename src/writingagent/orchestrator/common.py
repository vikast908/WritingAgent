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
    '_research_brief_prefix',
    '_svg_diagram_figure',
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
    '_escalate',
    '_record_escalated_score',
    '_writer_tool_runner',
    '_reoutline_units',
    '_revise_weakest_unit',
    '_manuscript_section_bodies',
    '_replace_manuscript_section',
    'record_rejected',
    'read_rejected',
    'reconcile_unit_images',
]


_BUDGET_PAUSE_MSG = ("[!] {err} - run paused. Raise the cap (/set max_run_tokens N, "
                     "0 = unlimited) or just run again to continue with a fresh budget.")


# ── Research-brief prefix (shared by the chapter + section fetchers) ──────────
def _research_brief_prefix(facts, style_cues, *, comparisons=None, sources=None) -> str:
    """Assemble the '## Research brief' context block prepended to the writer's input.
    Always carries Facts + Style cues; the Comparisons section is rendered when
    `comparisons` is a list (book deep research - its header stays even when empty), and
    Sources when `sources` is non-empty. Trailing '\\n\\n' separates the brief from the
    body that follows. `sources` items expose .title/.url."""
    lines = ["## Research brief",
             "### Facts", *(f"- {f}" for f in (facts or [])),
             "### Style cues", *(f"- {s}" for s in (style_cues or []))]
    if comparisons is not None:
        lines += ["### Comparisons", *(f"- {c}" for c in comparisons)]
    if sources:
        lines += ["### Sources", *(f"- [{s.title}]({s.url})" for s in sources)]
    return "\n".join(lines) + "\n\n"


def _svg_diagram_figure(cfg, *, label, context, engine, spec_path, svg_path, log) -> list[str]:
    """Generate one SVG concept diagram and return it as a one-item figure-markdown list
    (the image-fetch fallback when Wikimedia has nothing). Writes the diagram spec to
    `spec_path` (under versions/) and the rendered SVG to `svg_path` (under images/); the
    in-manuscript reference is images/<svg filename>, the convention both pipelines use."""
    svg_text = nodes.generate_svg_diagram(
        cfg, label, context, engine=engine,
        on_spec=lambda sp: brain.write_text(spec_path, sp.model_dump_json(indent=2)))
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    svg_path.write_text(svg_text, encoding="utf-8")
    log(f"   generated SVG diagram -> {svg_path.name}")
    return [f"![{label} diagram](images/{svg_path.name})\n*Figure: {label}*"]


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
        # Shuffle presentation order to break position bias (LLM judges over-pick
        # slot 1, and v0 - the most conservative temp - always sat there). The seed
        # is derived from the draft texts, so a resumed run re-judges the same order
        # and the pick stays reproducible.
        import hashlib
        import random
        seed = int.from_bytes(hashlib.sha256(
            "\x00".join(drafts[k] for k in keys).encode("utf-8")).digest()[:8], "big")
        order = list(keys)
        random.Random(seed).shuffle(order)
        labelled = {str(i + 1): drafts[k] for i, k in enumerate(order)}
        try:
            ranking = nodes.rank_variants(cfg, unit_desc, labelled, thesis)
            w = ranking.winner
            if isinstance(w, int) and 1 <= w <= len(order):
                best = order[w - 1]
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


# ── Rejected/dropped artifacts (for review, plan §26) ─────────────────────────
_IMG_MD = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")


def record_rejected(paths, entry: dict) -> None:
    """Append one dropped-artifact record to <root>/rejected.jsonl (best-effort).
    Surfaced in the dashboard's Rejected view so nothing is silently discarded."""
    try:
        import datetime
        import json
        rec = {"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
               **entry}
        with open(paths.root / "rejected.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001 - review breadcrumb must never break a run
        pass


def read_rejected(paths) -> list[dict]:
    import json
    p = paths.root / "rejected.jsonl"
    if not p.exists():
        return []
    out: list[dict] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def reconcile_unit_images(paths, unit_no: int, unit_tag: str, draft: str,
                          images, log) -> str:
    """Make generated figures reliable. Images are handed to the writer as *suggestions*
    ('embed where relevant'), so placement depends on the model - which is why generated
    diagrams got orphaned on disk (paid for, never shown). Here we deterministically
    embed a generated section diagram the writer omitted, and record any still-unused
    suggested image to rejected.jsonl for review. Returns the (possibly augmented) draft."""
    if not images:
        return draft
    for md in images:
        m = _IMG_MD.search(md or "")
        if not m:
            continue
        ref = m.group(1)
        fname = ref.rsplit("/", 1)[-1]
        if fname in draft:
            continue  # the writer placed it
        if "_diagram.svg" in fname:   # a generated figure -> guarantee it appears
            draft = draft.rstrip() + "\n\n" + md.strip() + "\n"
            log(f"   [figure] embedded generated diagram the writer left out ({fname})")
        else:                          # a suggested (e.g. Wikimedia) image the writer skipped
            record_rejected(paths, {"unit": unit_tag, "kind": "image", "ref": ref,
                                    "reason": "suggested but not placed by the writer"})
    return draft


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
        "image_source": getattr(settings, "image_source", "wikimedia"),
        "image_model": getattr(settings, "image_model", "") or "",
        "image_provider": getattr(settings, "image_provider", "") or "",
        "diagram_engine": settings.diagram_engine,
        "use_embeddings": settings.use_embeddings,
        "divergent_drafts": settings.divergent_drafts,
        "tournament_judge": settings.tournament_judge,
        "min_insight": settings.min_insight,
        "max_context_chars": settings.max_context_chars,
        "skill_duels": settings.skill_duels,
        "watch_blocking": settings.watch_blocking,
        "verify_excerpt_chars": getattr(settings, "verify_excerpt_chars", 6000),
        "seo_keyword": (getattr(settings, "seo_keyword", "") or "").strip(),
        "book_cohesion": settings.book_cohesion,
        # Register craft layer (plan §22): surgical show-don't-tell / de-passive toggle.
        # `register`/`field`/`citation_style` are set per-mode (book/article) at creation.
        "craft_passes": getattr(settings, "craft_passes", True),
        # Compositor manner layers (plan §23): a selected persona voice + a per-run emotional
        # target. Both optional; the compositor drops a persona that doesn't fit the register.
        "persona": getattr(settings, "persona", "") or "",
        "emotion": getattr(settings, "emotion", "") or "",
        # Agentic controller (plan §21): baked at creation like every other toggle. The
        # default ("pipeline") drives the unchanged fixed loop; "agentic" routes each unit
        # through agentic.run_unit. The real bounds are the per-unit agentic_max_unit_steps
        # cap and the token budget; agent_steps is a recorded per-decision counter (telemetry).
        "controller": "agentic" if settings.agentic else "pipeline",
        "agentic_policy": settings.agentic_policy,
        "agentic_controller_model": settings.agentic_controller_model,
        "agentic_max_unit_steps": settings.agentic_max_unit_steps,
        "agentic_factcheck_panel": settings.agentic_factcheck_panel,
        "agentic_inline_tools": settings.agentic_inline_tools,
        "agentic_critique_panel": settings.agentic_critique_panel,
        "agent_steps": 0,
        # Autonomous runs never pause on low confidence.
        "escalate_below_confidence": 0.0 if autonomous else settings.escalate_below_confidence,
    }


def _load(uid: str, book_id: str):
    paths = BookPaths(book_id, uid)
    state = brain.read_json(paths.run_state)
    if state is None:
        raise FileNotFoundError(f"No run_state for book '{book_id}'. Run `new` first.")
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
                           skeletons, log, duel=None):
    """Attempt-0 divergent drafting, shared by chapters and sections: draft n_div
    variants at varied temperatures in parallel, critique each, and let a side-by-side
    judge pick the winner (selection for strength over convergence). With skeletons=True
    (article opt-in) the variants are short and only the winner is expanded to full
    length, so discarded drafts cost ~a third the tokens. `write`/`critique` are the
    unit's own node closures. Returns (draft, crit, judge_note)."""
    temps = _DIVERGENT_TEMPS[:n_div]
    label_kind = "skeleton" if skeletons else "variant"
    # Ablation duel (opt-in): draft one EXTRA variant with the `duel` skill held out, at v0's
    # temperature, so the only difference is that one skill. The critic's verdict on v0 vs the
    # ablated twin (_crit_better) is the skill's causal lift - a real counterfactual. Adding a
    # variant rather than reusing a slot keeps every real contender, so publication quality is
    # not sacrificed; the cost is one extra draft, only on units with an undecided skill.
    # Skipped in skeleton mode (a one-third draft carries too little signal).
    duel_on = bool(duel) and not skeletons and len(temps) >= 1
    tasks = {f"v{i}": (lambda t=t, fn=fix_notes: write(fn, None, t, skeleton=skeletons))
             for i, t in enumerate(temps)}
    labels = {f"v{i}": f"{label_kind} temp={t}" for i, t in enumerate(temps)}
    if duel_on:
        tasks["ablated"] = (lambda fn=fix_notes: write(fn, None, temps[0], skills=duel["ablated"]))
        labels["ablated"] = f"ablated:{duel['name']} temp={temps[0]}"
    log(f"   drafting {len(tasks)} variants (temps {', '.join(map(str, temps))}"
        f"{'; +1 ablation probe' if duel_on else ''})...")
    drafts = concurrency.gather(tasks, strict=True)
    log("   critiquing variants...")
    crits = concurrency.gather(
        {k: (lambda d=d: critique(d)) for k, d in drafts.items()}, strict=True)
    for k, d in drafts.items():
        _save_version(paths, unit_tag, d, label=labels.get(k, label_kind))
    if duel_on:
        won = _crit_better(crits["v0"], crits["ablated"])
        skills_mod.record_duel(paths.uid, duel["name"], won)
        log(f"   [duel] skill '{duel['name']}' -> {'kept lift (won)' if won else 'no lift (lost)'}")
    picker_ask = None if autonomous else ask
    draft, crit, judge_note, pref = _pick_variant(
        cfg, unit_desc, thesis_brief, drafts, crits, picker_ask, log, use_judge=use_judge)
    if pref:
        _record_preference(paths, pref)
    log(f"   picked variant ({sum(1 for c in crits.values() if c.verdict == 'approve')}"
        f"/{len(crits)} approved)")
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


# Watch-list memory bound: newest items first, oldest dropped past the cap (tunable).
_WATCH_LIST_CAP = 40


def _watch_key(line: str) -> str:
    """Dedupe key for one '- pattern - why' watch line: the pattern half, case-folded."""
    return line[2:].split(" - ")[0].strip().lower()


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
    # MERGE with the existing watch-list instead of overwriting it: the watch-list is
    # cross-run memory of failure patterns, and a fresh run used to erase every earlier
    # project's lessons (a memory lifetime of exactly one piece). Newest first, deduped
    # on the pattern, capped so it can't grow without bound.
    new_items = [f"- {w.pattern} - {w.why}" for w in out.watch_items]
    old_items = [ln.strip() for ln in (brain.read_text(brain.watch_list(uid)) or "").splitlines()
                 if ln.strip().startswith("- ")]
    merged = list(new_items)
    seen = {_watch_key(ln) for ln in new_items}
    for ln in old_items:
        key = _watch_key(ln)
        if key not in seen:
            seen.add(key)
            merged.append(ln)
    watch = ["# Avoid list (watch-list)", ""] + merged[:_WATCH_LIST_CAP]
    brain.write_text(brain.watch_list(uid), "\n".join(watch))
    statuses = skills_mod.reconcile(uid)
    distilled = skills_mod.distill(uid) if load_settings().skill_distill else []
    log(f"   [learn] +{len(out.skills)} skills, {len(out.watch_items)} watch items; "
        f"reconciled {len(statuses)} skills"
        + (f", distilled {len(distilled)} duplicate(s)" if distilled else ""))
    _train_agentic_policy(paths, log)


def _train_agentic_policy(paths, log) -> None:
    """Distill/refresh the learned controller policy from the action trace (plan §21.11),
    compounding run-over-run. Only fires when this project has a trace (agentic runs); a
    thin/undecided corpus writes nothing. Best-effort - never breaks the learn phase."""
    from .. import agentic
    try:
        if not agentic.trace.trace_path(paths).exists():
            return
        if agentic.train_policy(paths.uid):
            log("   [agentic] learned policy refreshed from the action trace")
    except Exception:  # noqa: BLE001 - policy training must never break a run
        pass


def _escalate(paths, n, crit: S.Critique, draft: str, *, state=None,
              unit: str = "chapter") -> None:
    brain.write_text(paths.ch_draft(n), draft)
    lines = [
        f"# Review needed - {unit} {n}", "",
        f"- verdict: {crit.verdict}", f"- confidence: {crit.confidence:.2f}", "",
        "## Blocking",
        *(f"- [{b.type}] {b.where}: {b.detail}\n  fix: {b.fix}" for b in crit.blocking),
        "", "## Nits", *(f"- {x}" for x in crit.nits), "",
        "## Your directed instructions",
        # The --chapter flag is universal (it addresses the Nth section too); the command is
        # `review`/`run`, not the obsolete `book <subcmd>` prefix - and the unit word tracks
        # the pipeline so an article never tells the user to review a "chapter".
        f'_Run: review --chapter {n} --instruction "..." - then run to resume._',
    ]
    brain.write_text(paths.review_of(n), "\n".join(lines))
    brain.append_text(paths.revision_log, f"## {unit.capitalize()} {n} ESCALATED ({crit.verdict})")
    # Persist the blocking critique's scores so an approve-as-is (approve_escalation) can keep
    # the per-unit scores/insights arrays 1:1 with `committed` - otherwise they desync and
    # every later scores[n-1] lookup (weakest-unit revise, summary card) targets the wrong unit.
    if state is not None:
        state["escalated_score"] = {"insight": crit.insight, "clarity": crit.clarity,
                                    "structure": crit.structure, "evidence": crit.evidence}


def _record_escalated_score(state) -> None:
    """Append the escalating critique's scores (stashed by _escalate) to the per-unit
    scores/insights arrays, keeping them aligned with `committed` after an approve-as-is.
    Falls back to a neutral score if none was stashed (older paused run-states)."""
    sc = state.pop("escalated_score", None) or {"insight": 3, "clarity": 3,
                                                "structure": 3, "evidence": 3}
    state.setdefault("insights", []).append(sc.get("insight", 3))
    state.setdefault("scores", []).append(sc)


# ── Shared agentic run-op bodies (identical logic for book chapters + article sections) ──────
# The book and article macro-controllers (`_book_run_ops`/`_article_run_ops`) each expose the
# same `revise` / `reoutline` / in-generation-tool-use actions; only the unit vocabulary (chapter
# vs section), the path methods, and the per-unit process/plan functions differ. These helpers
# hold the one copy of the logic; each pipeline passes in its vocabulary + callables. Behavior is
# byte-identical to the old inline closures. (`draft` is intentionally NOT shared: its phase
# transitions and has_canon rules genuinely differ between the two pipelines.)

def _writer_tool_runner(state, *, research, read_canon):
    """(tools, runner) for the writer's in-generation tool use (plan §21 Phase 3), shared by
    chapters + sections. `research(query)` and `read_canon(query)` are the unit-specific
    implementations; `research` (and `verify_fact`) are gated on `use_researcher`."""
    from .. import agentic
    research_on = bool(state.get("use_researcher"))

    def runner(name, args):
        a = args or {}
        if name == "research" and research_on:
            return research(a.get("query", ""))
        if name == "verify_fact" and research_on:
            return research(f"verify: {a.get('claim', '')}")
        if name == "read_canon":
            return read_canon(a.get("query", ""))
        return ""
    return agentic.WRITER_TOOL_SCHEMAS, runner


def _reoutline_units(state, paths, *, unit_word, current_key, count_key, units,
                     build_fresh, persist, log) -> str:
    """Regenerate the not-yet-written units' plan - committed units and the total count are
    preserved (§21 #2/#4). `build_fresh(count)` returns a fresh list of units; `units` is the
    live list spliced in place; `persist()` writes the plan to disk."""
    from .. import agentic
    n = state[current_key]                              # first un-written unit (1-based)
    count = state[count_key]
    fresh = build_fresh(count)
    for i in range(n - 1, min(len(units), len(fresh))):
        u = fresh[i]
        u.number = i + 1                                # keep numbering stable
        units[i] = u
    persist()
    state["reoutlines"] = state.get("reoutlines", 0) + 1
    brain.write_json(paths.run_state, state)
    agentic.trace.append(paths, {"scope": "run-result", "action": "reoutline", "from_unit": n})
    log(f"   [agentic] reoutlined {unit_word}s {n}..{count}")
    return "continue"


def _revise_weakest_unit(state, paths, *, unit_prefix, unit_word,
                         committed_path, draft_path, process, log) -> str:
    """Rewrite the weakest committed unit to lift its score (§21 #3). `committed_path(n)` /
    `draft_path(n)` are the unit's on-disk paths and `process(n)` re-runs its
    write->critique->commit episode with a targeted instruction (canon re-extraction is
    idempotent, so this is safe). Rolls back to the committed text if the re-process does not
    approve, and realigns the per-unit scores/insights arrays so they stay 1:1 with `committed`."""
    from .. import agentic
    n = agentic.weakest_committed_unit(state)
    if not n or n > state.get("committed", 0):
        return "continue"
    sc = (state.get("scores") or [{}])[n - 1]
    dim = min(("insight", "clarity", "structure", "evidence"), key=lambda k: sc.get(k, 5))
    brain.write_text(paths.instruction_of(n),
                     f"Strengthen the {dim} of this {unit_word} - it scored lowest there. "
                     "Keep everything that already works; change only what lifts it.")
    committed_text = brain.read_text(committed_path(n)) or ""
    brain.write_text(draft_path(n), committed_text)     # revise from the committed text
    committed_path(n).unlink(missing_ok=True)           # clear the resume guard -> re-draft
    result = None
    try:
        result = process(n)
    finally:
        # A revise must never LOSE a committed unit: if the re-process escalated (or raised) it
        # wrote only the draft, yet state still counts n committed and assembly would silently
        # drop it - restore the original.
        if result != "commit" and not committed_path(n).exists():
            brain.write_text(committed_path(n), committed_text)
    draft_path(n).unlink(missing_ok=True)
    paths.instruction_of(n).unlink(missing_ok=True)
    unit = f"{unit_prefix}{n:02d}"
    if result != "commit":
        state["revisions_done"] = state.get("revisions_done", 0) + 1
        brain.write_json(paths.run_state, state)
        agentic.trace.append(paths, {"scope": "run-result", "action": "revise",
                                     "unit": unit, "dim": dim, "result": "rolled_back"})
        log(f"   [agentic] revise of {unit_word} {n} did not approve - kept the committed version")
        return "continue"
    # _finalize_unit appended a fresh score/insight; move it onto unit n so the per-unit arrays
    # stay aligned with committed units (n stays committed, count unchanged).
    for key in ("scores", "insights"):
        arr = state.get(key) or []
        if len(arr) > state.get("committed", 0):
            arr[n - 1] = arr.pop()
    state["revisions_done"] = state.get("revisions_done", 0) + 1
    brain.write_json(paths.run_state, state)
    agentic.trace.append(paths, {"scope": "run-result", "action": "revise", "unit": unit, "dim": dim})
    log(f"   [agentic] revised {unit_word} {n} (weakest: {dim})")
    return "continue"


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
