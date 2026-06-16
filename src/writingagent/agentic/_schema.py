"""Structured decision schema for the agentic controller (plan.md §21.3.1)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ControllerDecision(BaseModel):
    """One step's choice by the UNIT-phase controller (prepare-then-draft one unit).

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


class RunDecision(BaseModel):
    """One step's choice by the RUN-phase controller (which macro-action next over the
    whole piece): draft the next unit, audit/repair continuity, read the piece cold,
    assemble it, learn from it, or finish.

    ``"draft"`` is FIRST so fake mode / a schema-ignoring model defaults to making
    forward progress (the guard then maps it to the legal default when drafting is done,
    so offline runs always converge). ``reason`` is recorded to the action trace.
    """

    action: Literal["draft", "reoutline", "revise", "consolidate", "repair",
                    "table_read", "produce", "learn", "escalate", "done"]
    reason: str = ""
