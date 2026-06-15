"""Controller policies (plan.md §21.3.1).

A policy maps the current unit view to the next action. Three implementations share
one interface so the learned policy (Phase 5) is a drop-in swap:

  DefaultPolicy  the legacy fixed pipeline as a policy - always `draft` immediately.
                 Every other policy degrades to this; it is also the guarantee that an
                 agentic run with the default policy matches the legacy pipeline exactly.
  LlmPolicy      a ReAct-style controller: one structured call picks the next action,
                 falling back to `draft` on any failure or illegal choice.
  TracePolicy    Phase-5 seam: a trained policy slots in here; for now it loads the
                 action trace and delegates to the default decision.
"""
from __future__ import annotations

from .. import llm, prompts
from . import trace
from ._schema import ControllerDecision


class DefaultPolicy:
    name = "default"

    def decide(self, view: str, available: list[str]) -> ControllerDecision:
        return ControllerDecision(action="draft", reason="default policy")


class LlmPolicy:
    name = "llm"

    def __init__(self, cfg, model: str):
        self.cfg = cfg
        self.model = model

    def decide(self, view: str, available: list[str]) -> ControllerDecision:
        try:
            d = llm.complete_structured(self.model, prompts.CONTROLLER_SYS, view,
                                        ControllerDecision, max_tokens=400)
        except Exception:  # noqa: BLE001 - controller is advisory; never fail the run
            return ControllerDecision(action="draft", reason="controller call failed")
        if d.action not in available:   # illegal for this run -> safe fallback (plan §21.4)
            return ControllerDecision(action="draft", reason=f"illegal({d.action})->draft")
        return d


class TracePolicy(DefaultPolicy):
    """Phase-5 swap point (plan §21.11). A learned policy conditions its decision on the
    accumulated action trace; until one is trained this loads the trace (so the seam is
    real and exercised) and falls back to the default `draft` decision."""
    name = "trace"

    def __init__(self, paths):
        self.history = trace.read(paths)

    def decide(self, view: str, available: list[str]) -> ControllerDecision:
        # A trained policy would condition on self.history here; the floor stays `draft`.
        return super().decide(view, available)


def make_policy(state, cfg, paths):
    """Resolve the policy for this run from run-state (default unless agentic_policy says
    otherwise). cfg routes the LLM policy's model via the per-node table (plan §12.1)."""
    mode = state.get("agentic_policy", "default")
    if mode == "llm":
        node = state.get("agentic_controller_model") or "judge"
        return LlmPolicy(cfg, cfg.model_for(node))
    if mode == "trace":
        return TracePolicy(paths)
    return DefaultPolicy()
