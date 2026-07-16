"""The agentic tool registry (plan.md §21.2).

Tools wrap existing node/orchestrator functions at their CURRENT granularity. The
key invariant (plan §21.0/§21.5): ``draft`` is the unchanged write->critique->commit
episode (``_process_chapter`` / ``_process_article_section``), so the duel and
``record_chapter`` machinery is literally the same code - the controller only gains
agency *between* episodes, never inside one.

The controller's unit-phase action set is {``draft``, ``research``, ``read_canon``}.
The phase-level entries (``consolidate``/``produce``/``learn``/``done``) are reused
verbatim by the deterministic tail of the legacy loop - there is no agency to add
there - so they are catalogued here for inspection (the ``/agentic`` view and a future
learned policy) but driven by the orchestrator, not chosen by the policy.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from .. import nodes
from ._schema import ControllerDecision

# ── Static catalogue (inspection + documentation of the capability surface) ──────


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    phase: str           # "unit" | "tail"
    mutates: bool = False
    params: type | None = field(default=None)   # ControllerDecision for unit tools


CATALOG: tuple[Tool, ...] = (
    Tool("draft", "Run the full write->critique->commit episode for the current unit "
         "(the atomic, instrumented step). Terminal for this unit.",
         phase="unit", mutates=True, params=ControllerDecision),
    Tool("research", "Run a web-research pass for the current unit and fold the brief "
         "into the draft context. `query` = the search query.",
         phase="unit", params=ControllerDecision),
    Tool("read_canon", "Pull canon / prior-section summaries into the draft context. "
         "(The bound implementation currently returns the whole canon block; `query` is "
         "reserved for a future relevance-filtered slice.)",
         phase="unit", params=ControllerDecision),
    Tool("consolidate", "Cross-unit continuity audit (books).", phase="tail", mutates=True),
    Tool("produce", "Assemble front/back matter + manuscript.", phase="tail", mutates=True),
    Tool("learn", "Distill craft skills + watch-list from the finished piece.",
         phase="tail", mutates=True),
    Tool("done", "Terminal: the run is complete.", phase="tail"),
)

#: The actions the unit-phase policy may choose among.
UNIT_ACTIONS: tuple[str, ...] = tuple(t.name for t in CATALOG if t.phase == "unit")

#: OpenAI tool schemas the WRITER may call mid-draft (in-generation tool use, plan §21 Phase 3).
#: Same capabilities as the unit gathering tools, but invoked by the model *while writing* via
#: llm.complete_text_with_tools, not as a fixed pre-step. Gated by `agentic_inline_tools`.
WRITER_TOOL_SCHEMAS: tuple[dict, ...] = (
    {"type": "function", "function": {
        "name": "research",
        "description": "Search the web and return a short grounded brief (facts + style cues) "
                       "for a specific question. Use when you need a fact, statistic, name, or "
                       "date you are unsure of - never invent one.",
        "parameters": {"type": "object",
                       "properties": {"query": {"type": "string",
                                                "description": "The specific thing to look up."}},
                       "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "read_canon",
        "description": "Pull the established facts / prior-section context relevant to a query, "
                       "to stay consistent with what has already been written.",
        "parameters": {"type": "object",
                       "properties": {"query": {"type": "string",
                                                "description": "What continuity detail to check."}}}}},
    {"type": "function", "function": {
        "name": "verify_fact",
        "description": "Before asserting a specific statistic, date, quote, or attribution you are "
                       "unsure of, confirm it against fresh sources. Returns supporting material or "
                       "nothing - if nothing comes back, do NOT state the claim as fact.",
        "parameters": {"type": "object",
                       "properties": {"claim": {"type": "string",
                                                "description": "The exact claim to confirm."}},
                       "required": ["claim"]}}},
)


def catalog_summary() -> str:
    """One line per tool - for the `/agentic` view and docs."""
    return "\n".join(f"  {t.name:12s} [{t.phase}] {t.description}" for t in CATALOG)


# ── UnitOps: the bound capabilities the controller drives for one unit ───────────
# Built at the orchestrator call site (the draft closure needs orchestrator
# internals the agentic package must not import), so this stays a plain data holder.
@dataclass
class UnitOps:
    paths: object
    unit_label: str                       # "ch03" / "sec02" - trace + view label
    research_on: bool                     # is the researcher enabled this run?
    has_canon: bool                       # can read_canon return anything?
    draft: Callable[[str | None], str]    # extra_context -> "commit" | "escalate"
    research: Callable[[str], str]        # query -> brief markdown
    read_canon: Callable[[str], str]      # query -> canon/summary markdown

    def available(self) -> list[str]:
        """The legal unit actions for this run (drops research/read_canon when off)."""
        actions = ["draft"]
        if self.research_on:
            actions.append("research")
        if self.has_canon:
            actions.append("read_canon")
        return actions


# ── RunOps: the bound capabilities the RUN-phase controller drives (plan §21.3) ──
# Like UnitOps, built at the orchestrator call site (the dispatch closures need
# orchestrator internals - the store, prefetch pool, plan/outline - that this package
# must not import), so it stays a plain data holder of closures.
@dataclass
class RunOps:
    paths: object
    legal_actions: Callable[[dict], list[str]]     # state -> legal macro-actions now
    default_next: Callable[[dict], str]            # state -> what the legacy loop would do
    dispatch: Callable[..., str]                   # (action, state, log) -> "continue" | "pause"
    step_budget: Callable[[dict], int]             # state -> lifetime step cap for run_loop
    control_check: Callable[[dict], bool] | None = None   # state -> True to pause (live esc/manual)


# Run-phase actions a policy may choose among, with one-line descriptions for the
# controller prompt + the /agentic view. The legal subset per step comes from RunOps.
RUN_ACTIONS: dict[str, str] = {
    "draft": "Write the next un-written chapter/section (the full draft->critique->commit episode).",
    "reoutline": "Regenerate the plan for the not-yet-written units when the current structure isn't working.",
    "consolidate": "Audit the whole book so far for continuity contradictions (books only).",
    "repair": "Rewrite the chapters an open contradiction touches (books only).",
    "revise": "Rewrite the weakest already-committed unit to lift its quality.",
    "table_read": "Read the assembled piece cold as a skeptical target reader (a report; changes nothing).",
    "produce": "Assemble front/back matter + the final manuscript.",
    "learn": "Distill reusable craft skills + a watch-list from the finished piece.",
    "escalate": "Pause and hand control to the human when stuck or a decision genuinely needs them.",
    "done": "Finish the run.",
}

#: Optional/skippable macro-actions (vs. forward-progress ones). Dropped under budget
#: pressure (§21 self-monitoring) so a low-budget run still finishes rather than polishing.
OPTIONAL_RUN_ACTIONS: frozenset[str] = frozenset({"reoutline", "revise", "table_read"})


def _budget_line() -> str:
    """A budget-awareness line for the controller view (self-monitoring, plan §21.4/§15.1).
    Empty when no run budget is set."""
    from .. import llm
    cap = llm.run_budget()
    if not cap:
        return ""
    used = llm.current_tokens()
    left = max(0, cap - used)
    return (f"\nToken budget: {used:,}/{cap:,} used ({100 * used / cap:.0f}%); {left:,} left"
            f"{' - LOW, wrap up' if left < cap * 0.15 else ''}.")


def _score_avg(s: dict) -> float:
    """Mean of a unit's 4 rubric scores (insight/clarity/structure/evidence)."""
    return (s.get("insight", 0) + s.get("clarity", 0)
            + s.get("structure", 0) + s.get("evidence", 0)) / 4.0


def _quality_line(state: dict, unit: str) -> str:
    """A per-unit quality summary (avg score + the weakest committed unit) for the view."""
    scores = state.get("scores") or []
    if not scores:
        return ""
    avgs = [_score_avg(s) for s in scores]
    weakest = min(range(len(avgs)), key=lambda i: avgs[i])
    per = ", ".join(f"{unit}{i + 1}:{a:.1f}" for i, a in enumerate(avgs))
    return f"\nCommitted-unit quality (avg/5): {per}; weakest = {unit}{weakest + 1}."


def weakest_committed_unit(state: dict) -> int | None:
    """1-based index of the lowest-average-score committed unit, or None if none scored.
    Shared by the run view and the `revise` action so they target the same unit."""
    scores = state.get("scores") or []
    if not scores:
        return None
    return min(range(len(scores)), key=lambda i: _score_avg(scores[i])) + 1


def build_run_view(state: dict, legal: list[str]) -> str:
    """The macro-perception the run policy reasons over: progress, per-unit quality and the
    weakest unit, open contradictions, token budget, and the legal next actions (plan §21.6)."""
    is_article = state.get("mode") == "article" or "num_sections" in state
    unit = "section" if is_article else "chapter"
    cur = state.get("current_section" if is_article else "current_chapter", "?")
    tot = state.get("num_sections" if is_article else "num_chapters", "?")
    committed = state.get("committed", 0)
    contradictions = state.get("open_contradictions", 0)
    contra = f"\nOpen continuity contradictions: {contradictions}." if contradictions else ""
    opts = "\n".join(f"  - {a}: {RUN_ACTIONS.get(a, a)}" for a in legal)
    return (
        f"Directing the whole {'article' if is_article else 'book'}.\n"
        f"Phase: {state.get('phase')}. {unit.capitalize()}s committed: {committed} of {tot} "
        f"(next un-written: {cur})."
        + _quality_line(state, unit) + contra + _budget_line()
        + f"\nRun mode: {'autonomous' if state.get('autonomous') else 'manual'}.\n"
        f"Legal next actions:\n{opts}\n"
        "Pick the action that best advances a finished, coherent, well-evidenced piece. Draft "
        "remaining units before producing; reoutline or revise only when the plan/a weak unit "
        "needs it; only finish once it is assembled and learned."
    )


# ── Research tool implementations (reused by both pipelines' UnitOps) ────────────
def _brief_md(facts, style_cues, *, header: str) -> str:
    lines = [f"## {header}",
             "### Facts", *(f"- {f}" for f in (facts or [])),
             "### Style cues", *(f"- {s}" for s in (style_cues or []))]
    return "\n".join(lines)


# Run-scoped memo for on-demand research briefs. The controller / inline-tool writer can
# re-issue the SAME query within a run - across draft revisions or panel rounds - which
# otherwise repeats the web search AND the LLM synthesis. Caching the synthesized brief by
# (unit, query) removes that duplicate; the same query genuinely yields the same brief, so
# this is quality-neutral. Keyed to the current run_id so it self-clears when a new run
# begins (no cross-run leakage, no unbounded growth in a long-lived TUI).
_brief_memo: dict[tuple[str, str], str] = {}
_brief_memo_run: str | None = None


def _research_memo(unit_key: str, query: str, produce) -> str:
    """Return a cached brief for (unit_key, query) within the current run, else compute it
    via `produce()` and cache it. `produce` returns (brief_markdown, log_query)."""
    global _brief_memo_run
    from .. import llm
    rid = llm.run_id()
    if rid != _brief_memo_run:        # a new run started -> drop the prior run's briefs
        _brief_memo.clear()
        _brief_memo_run = rid
    key = (unit_key, query)
    if key in _brief_memo:
        return _brief_memo[key]
    out = produce()
    _brief_memo[key] = out
    return out


def unit_research(cfg, plan, blueprint, query: str, log) -> str:
    """On-demand book research for the current chapter (the `research` unit tool)."""
    from .. import search as search_mod
    base_query = (query or "").strip() or search_mod.build_query(plan, blueprint)
    unit_key = f"ch{getattr(blueprint, 'number', '?')}"

    def _produce() -> str:
        try:
            results = search_mod.web_search(base_query, max_results=5)
            web = search_mod.format_results(results)
        except Exception:  # noqa: BLE001 - research is best-effort enrichment, never fatal
            web = ""
        brief = nodes.research(cfg, plan, blueprint, web_results=web or None)
        log(f"   [agentic] research: {base_query[:60]}")
        return _brief_md(brief.facts, brief.style_cues, header="Controller research brief")

    return _research_memo(unit_key, base_query, _produce)


def unit_research_article(cfg, outline, section, query: str, log) -> str:
    """On-demand article research for the current section (the `research` unit tool)."""
    from .. import search as search_mod
    base_query = (query or "").strip() or (section.search_query
                                           or f"{outline.title} {section.heading}")
    unit_key = f"sec{getattr(section, 'number', '?')}"

    def _produce() -> str:
        try:
            results = search_mod.web_search(base_query, max_results=5)
            web = search_mod.format_results(results)
        except Exception:  # noqa: BLE001 - research is best-effort enrichment, never fatal
            web = ""
        brief = nodes.research_article(cfg, outline, section, web_results=web or None)
        log(f"   [agentic] research: {base_query[:60]}")
        return _brief_md(brief.facts, brief.style_cues, header="Controller research brief")

    return _research_memo(unit_key, base_query, _produce)
