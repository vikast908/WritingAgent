"""The run-phase controller loop (plan.md §21.3, the macro level).

`run_loop` is the agentic replacement for the orchestrator's hardcoded
`while state["phase"] != "done"` machine. Instead of a fixed
chapters→consolidate→produce→learn order, a `RunPolicy` *chooses* the next macro-action
each step (draft the next unit, audit/repair continuity, read the piece cold, assemble,
learn, finish) from the legal set for the current state.

The safety model mirrors the unit controller:
- `DefaultRunPolicy` returns exactly what the legacy loop would do next (`RunOps.default_next`),
  so an agentic run with the default policy is byte-identical to the fixed pipeline - the
  run-level equivalence guarantee.
- the guard forces a legal action (the default) whenever the policy picks something illegal
  or the per-run step budget is spent, so the run always terminates and never corrupts state.
- `RunOps.dispatch` performs the action by calling the SAME orchestrator helpers the legacy
  loop calls (so episodes, duels, and the learning index are untouched - invariants §21.0).

`RunOps.dispatch` returns "continue" to keep looping or "pause" to return control to the
human (an escalation or a budget pause), exactly like the legacy loop's early returns.
"""
from __future__ import annotations

from . import trace
from ._schema import RunDecision
from .tools import OPTIONAL_RUN_ACTIONS, build_run_view


def _budget_pressured() -> bool:
    """True when the run has spent most of its token budget - the agent should stop
    polishing and finish (self-monitoring, plan §21.4/§15.1). False when no budget is set."""
    from .. import llm
    cap = llm.run_budget()
    return bool(cap) and llm.current_tokens() >= cap * 0.85


def _legal_now(run_ops, state) -> list[str]:
    """The legal actions, with optional/polish actions dropped under budget pressure so a
    low-budget run converges on a finished piece instead of reoutlining/revising forever."""
    legal = run_ops.legal_actions(state)
    if _budget_pressured():
        progress = [a for a in legal if a not in OPTIONAL_RUN_ACTIONS]
        return progress or legal     # never empty the set
    return legal


def _run_guard(decision: RunDecision, legal: list[str], default: str) -> RunDecision:
    """Force a legal macro-action: an illegal/empty pick collapses to the legacy default
    (the fixed pipeline is always the floor)."""
    if decision.action not in legal:
        return RunDecision(action=default, reason=f"illegal({decision.action})->{default}")
    return decision


def run_loop(cfg, state, *, run_ops, log) -> dict:
    """Drive the whole run via a RunPolicy. Returns the final (or paused) state - exactly
    what the legacy `run()` / `_run_article` returns, so the caller's contract is unchanged."""
    from .policy import make_run_policy
    policy = make_run_policy(state, cfg, run_ops.paths)
    # A generous lifetime cap so a misbehaving policy can't spin forever; the real bound is
    # that every legal action makes monotonic progress (draft advances, produce/learn are
    # one-shot) and the token budget (§15.1). Sized to units + the fixed tail with slack.
    max_steps = run_ops.step_budget(state)

    for _ in range(max_steps):
        if state.get("phase") == "done":
            break
        if run_ops.control_check and run_ops.control_check(state):
            return state                                   # live pause / switch-to-manual
        legal = _legal_now(run_ops, state)
        if not legal:
            break
        default = run_ops.default_next(state)
        decision = _run_guard(policy.decide(build_run_view(state, legal), legal, default),
                              legal, default)
        state["agent_steps"] = int(state.get("agent_steps", 0)) + 1
        trace.append(run_ops.paths, {"scope": "run", "phase": state.get("phase"),
                                     "policy": policy.name, "action": decision.action,
                                     "reason": decision.reason})
        if run_ops.dispatch(decision.action, state, log) == "pause":
            return state
    return state
