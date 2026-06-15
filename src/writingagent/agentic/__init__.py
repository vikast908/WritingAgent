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

from . import panels, trace
from ._schema import ControllerDecision
from .controller import build_state_view, run_unit
from .policy import DefaultPolicy, LlmPolicy, TracePolicy, make_policy
from .tools import (
    CATALOG,
    UNIT_ACTIONS,
    UnitOps,
    catalog_summary,
    unit_research,
    unit_research_article,
)

__all__ = [
    "ControllerDecision",
    "DefaultPolicy",
    "LlmPolicy",
    "TracePolicy",
    "make_policy",
    "build_state_view",
    "run_unit",
    "UnitOps",
    "CATALOG",
    "UNIT_ACTIONS",
    "catalog_summary",
    "unit_research",
    "unit_research_article",
    "panels",
    "trace",
    "enabled",
]


def enabled(state) -> bool:
    """True when this run is driven by the agentic controller rather than the fixed loop."""
    return bool(state) and state.get("controller") == "agentic"
