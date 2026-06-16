"""Agentic controller (plan.md §21): a self-directing loop layered over the existing
durable state machine. Opt-in via ``Settings.agentic`` - the fixed pipeline stays the
default and the controller's fallback, so turning agency on cannot regress the pipeline
or the self-improving loop.

Layers (plan §21.1): the brain is the world model (unchanged); the tool registry
(``tools.py``) wraps existing node/orchestrator functions; the controller (``controller.py``
+ ``policy.py``) chooses the next action. The orchestrator seams call ``run_unit`` (via a
lazy import) only when ``state["controller"] == "agentic"``.
"""
from __future__ import annotations

from . import learn, panels, trace
from ._schema import ControllerDecision, RunDecision
from .controller import build_state_view, run_unit
from .learn import load_policy, train_policy
from .policy import (
    DefaultPolicy,
    DefaultRunPolicy,
    LlmPolicy,
    LlmRunPolicy,
    TracePolicy,
    TraceRunPolicy,
    make_policy,
    make_run_policy,
)
from .runner import run_loop
from .tools import (
    CATALOG,
    OPTIONAL_RUN_ACTIONS,
    RUN_ACTIONS,
    UNIT_ACTIONS,
    WRITER_TOOL_SCHEMAS,
    RunOps,
    UnitOps,
    build_run_view,
    catalog_summary,
    unit_research,
    unit_research_article,
    weakest_committed_unit,
)

__all__ = [
    "ControllerDecision",
    "RunDecision",
    "DefaultPolicy",
    "LlmPolicy",
    "TracePolicy",
    "DefaultRunPolicy",
    "LlmRunPolicy",
    "TraceRunPolicy",
    "make_policy",
    "make_run_policy",
    "build_state_view",
    "build_run_view",
    "run_unit",
    "run_loop",
    "UnitOps",
    "RunOps",
    "CATALOG",
    "RUN_ACTIONS",
    "OPTIONAL_RUN_ACTIONS",
    "UNIT_ACTIONS",
    "WRITER_TOOL_SCHEMAS",
    "weakest_committed_unit",
    "catalog_summary",
    "unit_research",
    "unit_research_article",
    "panels",
    "trace",
    "learn",
    "load_policy",
    "train_policy",
    "enabled",
]


def enabled(state) -> bool:
    """True when this run is driven by the agentic controller rather than the fixed loop."""
    return bool(state) and state.get("controller") == "agentic"
