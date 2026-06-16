"""Controller policies (plan.md §21.3.1) for both decision scopes.

A policy maps a view to the next action. Two scopes share the same three-way design
(default / llm / trace) so the learned policy (Phase 5) is a drop-in swap:

  unit scope  (decide what to do before drafting ONE unit): research / read_canon / draft
  run scope   (decide the next MACRO-action over the whole piece): draft / consolidate /
              repair / table_read / produce / learn / done

  Default*  the legacy fixed pipeline as a policy - the equivalence floor every other
            policy degrades to.
  Llm*      a ReAct-style structured call; falls back to the default on any failure or
            illegal choice.
  Trace*    conditions on the accumulated action trace (online adaptation, and the
            Phase-5 swap point for a fully-trained policy). See the class docstrings.
"""
from __future__ import annotations

from .. import llm, prompts
from . import trace
from ._schema import ControllerDecision, RunDecision

# ── Unit scope ────────────────────────────────────────────────────────────────


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
    """Trace-conditioned / learned unit policy (plan §21.11).

    Two layers, strongest first:
    1. a **learned model** (`learn.train_policy`, persisted per user) - if it has decided
       from the logged corpus that gathering does (or doesn't) lift the first-pass rate,
       follow it: gather up front when it helps, otherwise draft straight away;
    2. otherwise an **online heuristic** - if earlier units this run needed a mid-draft
       research pull to close an evidence gap, gather up front next time.
    Both only ever choose `research` when it's available and nothing has been gathered yet;
    the default (`draft`) is always the floor."""
    name = "trace"

    def __init__(self, paths):
        from . import learn
        self._learn = learn
        self.history = trace.read(paths)
        self.model = learn.load_policy(getattr(paths, "uid", "") or "")

    def decide(self, view: str, available: list[str]) -> ControllerDecision:
        can_research = "research" in available and "nothing yet" in view
        if can_research and self.model is not None:        # learned: follow the fitted model
            ctx = "article" if "'sec" in view else "book"  # unit label in the view ('sec01'/'ch01')
            verdict = self._learn.research_decision(self.model, ctx)
            if verdict is True:
                return ControllerDecision(action="research",
                                          reason=f"learned policy ({ctx}): research lifts outcome")
            if verdict is False:
                return ControllerDecision(action="draft",
                                          reason=f"learned policy ({ctx}): draft directly")
        if can_research:                                   # heuristic: adapt to evidence gaps
            gaps = sum(1 for r in self.history
                       if r.get("action") == "research"
                       and "evidence" in (r.get("reason") or "").lower())
            if gaps:
                return ControllerDecision(
                    action="research",
                    reason=f"trace: {gaps} prior evidence gap(s) -> gather up front")
        return super().decide(view, available)


def make_policy(state, cfg, paths):
    """Resolve the unit policy for this run from run-state (default unless agentic_policy
    says otherwise). cfg routes the LLM policy's model via the per-node table (plan §12.1)."""
    mode = state.get("agentic_policy", "default")
    if mode == "llm":
        node = state.get("agentic_controller_model") or "judge"
        return LlmPolicy(cfg, cfg.model_for(node))
    if mode == "trace":
        return TracePolicy(paths)
    return DefaultPolicy()


# ── Run scope ───────────────────────────────────────────────────────────────────


class DefaultRunPolicy:
    """The fixed pipeline as a macro-policy: always do exactly what the legacy loop would
    do next. This is the run-level equivalence floor (agentic+default == fixed pipeline)."""
    name = "default"

    def decide(self, view: str, legal: list[str], default: str) -> RunDecision:
        return RunDecision(action=default, reason="default policy")


class LlmRunPolicy:
    name = "llm"

    def __init__(self, cfg, model: str):
        self.cfg = cfg
        self.model = model

    def decide(self, view: str, legal: list[str], default: str) -> RunDecision:
        try:
            d = llm.complete_structured(self.model, prompts.RUN_CONTROLLER_SYS, view,
                                        RunDecision, max_tokens=400)
        except Exception:  # noqa: BLE001 - controller is advisory; never fail the run
            return RunDecision(action=default, reason="controller call failed")
        if d.action not in legal:
            return RunDecision(action=default, reason=f"illegal({d.action})->{default}")
        return d


class TraceRunPolicy(DefaultRunPolicy):
    """Trace-conditioned macro-policy (plan §21.11). It audits continuity EARLY when the
    project's history shows it's been fragile: if a past consolidate found contradictions
    and an audit is legal now (a book mid-draft), it consolidates instead of drafting on.
    Otherwise it follows the legacy default. The Phase-5 swap point for a trained policy."""
    name = "trace"

    def __init__(self, paths):
        self.history = trace.read(paths)

    def decide(self, view: str, legal: list[str], default: str) -> RunDecision:
        if "consolidate" in legal and default == "draft":
            found = sum(int(r.get("contradictions") or 0)
                        for r in self.history if r.get("action") == "consolidate")
            if found:
                return RunDecision(action="consolidate",
                                   reason=f"trace: {found} past contradiction(s) -> audit early")
        return super().decide(view, legal, default)


def make_run_policy(state, cfg, paths):
    """Resolve the macro-policy for this run (mirrors make_policy at run scope)."""
    mode = state.get("agentic_policy", "default")
    if mode == "llm":
        node = state.get("agentic_controller_model") or "judge"
        return LlmRunPolicy(cfg, cfg.model_for(node))
    if mode == "trace":
        return TraceRunPolicy(paths)
    return DefaultRunPolicy()
