"""The unit-phase controller loop (plan.md §21.3).

`run_unit` is the agentic replacement for a single `_process_chapter` /
`_process_article_section` call. It runs a bounded perceive->decide->guard->act->record
loop: the policy may gather research / canon context first (the `research` / `read_canon`
tools), but every path ends in exactly ONE `draft` - the unchanged write->critique->commit
episode (plan §21.5). Agency lives between episodes, never inside one; the episode still
fires the duel and `record_chapter`, so the self-improving loop is untouched.

The fixed pipeline calls `_process_chapter` directly; this is only reached when
`state["controller"] == "agentic"`. With DefaultPolicy the loop drafts at step 0, so its
output is identical to the fixed pipeline (the Phase-1 equivalence guarantee).
"""
from __future__ import annotations

from . import trace
from ._schema import ControllerDecision
from .policy import make_policy
from .tools import UnitOps


def build_state_view(state, ops: UnitOps, gathered: int, step: int) -> str:
    """The compact perception the policy reasons over (kept small; cache-friendly)."""
    max_steps = state.get("agentic_max_unit_steps", 3)
    have = "nothing yet" if not gathered else f"{gathered} context brief(s) already gathered"
    return (
        f"Preparing to draft unit '{ops.unit_label}'.\n"
        f"Run mode: {'autonomous' if state.get('autonomous') else 'manual'}.\n"
        f"Researcher enabled: {ops.research_on}. Canon/prior-context available: {ops.has_canon}.\n"
        f"Context gathered for this unit so far: {have}.\n"
        f"This is step {step} of at most {max_steps} gathering steps before drafting.\n"
        f"Available actions: {', '.join(ops.available())}.\n"
        "Pick 'research' or 'read_canon' ONLY if it will clearly improve THIS unit and you "
        "have not already gathered enough; otherwise pick 'draft' to write it now."
    )


def _guard(decision: ControllerDecision, available: list[str], step: int,
           max_steps: int) -> ControllerDecision:
    """before_tool (plan §21.4): force the safe `draft` action when the step budget is
    spent or the policy picked something illegal for this run."""
    if step >= max_steps:
        return ControllerDecision(action="draft", reason="step budget spent -> draft")
    if decision.action not in available:
        return ControllerDecision(action="draft", reason=f"illegal({decision.action})->draft")
    return decision


def run_unit(cfg, state, *, ops: UnitOps, log) -> str:
    """Drive one unit through the agentic loop. Returns the episode outcome
    ("commit" | "escalate") - exactly what `_process_chapter` returns - so the caller's
    bookkeeping is unchanged."""
    policy = make_policy(state, cfg, ops.paths)
    available = ops.available()
    max_steps = max(0, int(state.get("agentic_max_unit_steps", 3) or 0))
    extra: list[str] = []

    for step in range(max_steps + 1):
        decision = _guard(policy.decide(build_state_view(state, ops, len(extra), step),
                                        available), available, step, max_steps)
        state["agent_steps"] = int(state.get("agent_steps", 0)) + 1
        rec = {"unit": ops.unit_label, "step": step, "policy": policy.name,
               "action": decision.action, "query": decision.query, "reason": decision.reason}
        if decision.action == "draft":
            trace.append(ops.paths, {**rec, "result": "episode"})
            return ops.draft("\n\n".join(p for p in extra if p) or None)
        if decision.action == "research":
            brief = ops.research(decision.query) or ""
            if brief:
                extra.append(brief)
            trace.append(ops.paths, {**rec, "result": f"+{len(brief)} chars"})
        elif decision.action == "read_canon":
            slice_ = ops.read_canon(decision.query) or ""
            if slice_:
                extra.append("## Canon slice\n" + slice_)
            trace.append(ops.paths, {**rec, "result": f"+{len(slice_)} chars"})

    # Unreachable with the guard above (which drafts at step == max_steps); kept as a
    # belt-and-suspenders so the function always returns an episode outcome.
    trace.append(ops.paths, {"unit": ops.unit_label, "action": "draft",
                             "reason": "forced after step budget", "result": "episode"})
    return ops.draft("\n\n".join(p for p in extra if p) or None)
