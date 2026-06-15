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


# ── Research tool implementations (reused by both pipelines' UnitOps) ────────────
def _brief_md(facts, style_cues, *, header: str) -> str:
    lines = [f"## {header}",
             "### Facts", *(f"- {f}" for f in (facts or [])),
             "### Style cues", *(f"- {s}" for s in (style_cues or []))]
    return "\n".join(lines)


def unit_research(cfg, plan, blueprint, query: str, log) -> str:
    """On-demand book research for the current chapter (the `research` unit tool)."""
    from .. import search as search_mod
    base_query = (query or "").strip() or search_mod.build_query(plan, blueprint)
    try:
        results = search_mod.web_search(base_query, max_results=5)
        web = search_mod.format_results(results)
    except Exception:  # noqa: BLE001 - research is best-effort enrichment, never fatal
        web = ""
    brief = nodes.research(cfg, plan, blueprint, web_results=web or None)
    log(f"   [agentic] research: {base_query[:60]}")
    return _brief_md(brief.facts, brief.style_cues, header="Controller research brief")


def unit_research_article(cfg, outline, section, query: str, log) -> str:
    """On-demand article research for the current section (the `research` unit tool)."""
    from .. import search as search_mod
    base_query = (query or "").strip() or (section.search_query
                                           or f"{outline.title} {section.heading}")
    try:
        results = search_mod.web_search(base_query, max_results=5)
        web = search_mod.format_results(results)
    except Exception:  # noqa: BLE001 - research is best-effort enrichment, never fatal
        web = ""
    brief = nodes.research_article(cfg, outline, section, web_results=web or None)
    log(f"   [agentic] research: {base_query[:60]}")
    return _brief_md(brief.facts, brief.style_cues, header="Controller research brief")
