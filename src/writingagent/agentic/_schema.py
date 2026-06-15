"""Structured decision schema for the agentic controller (plan.md §21.3.1)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ControllerDecision(BaseModel):
    """One step's choice by the agentic controller for the current unit.

    The action set is the unit-phase tool registry (see tools.py). ``"draft"`` is
    listed FIRST on purpose: fake mode (and any model that ignores the schema and
    returns the first enum) then defaults to the safe terminal action, so offline
    runs always converge. ``query`` carries the search query (``research``) or the
    canon focus (``read_canon``); it is ignored for ``draft``. ``reason`` is a
    one-line rationale recorded to the action trace.
    """

    action: Literal["draft", "research", "read_canon"]
    query: str = ""
    reason: str = ""
