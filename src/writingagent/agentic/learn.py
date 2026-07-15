"""Learned policy π distilled from the action trace (plan.md §21.11).

This is the Phase-5 endgame in its honest, runnable form: a policy *trained from logged
experience* rather than a hardcoded heuristic. `train_policy` fits a small model over the
accumulated `agent_trace.jsonl` corpus across the user's projects - off-policy value
estimation, the contextual-bandit form of "learn from your own traces". The model answers
one question the controller faces every unit: **does gathering context before drafting
actually improve the outcome?** It joins each unit's gather decisions (research/read_canon)
to that unit's labelled outcome (`first_pass`, written to the trace at commit) and compares
the first-pass rate with vs. without gathering.

Safety (invariant §21.0 #3): the model is **not** auto-promoted. It is consulted only by
`TracePolicy`/`TraceRunPolicy`, which a user opts into (`agentic_policy="trace"`); the fixed
pipeline stays the default and the fallback. Training is deterministic and idempotent (it
re-reads the whole corpus), so it never double-counts.
"""
from __future__ import annotations

from .. import brain
from . import trace

# Enough labelled units in EACH arm before we trust the comparison (small-sample guard,
# same spirit as the skills efficacy gate's MIN_DUELS). Two noisy means at n=3 flip on
# noise; 10 per arm is the floor at which the comparison starts to mean anything.
# Tunable; on thin data the policy correctly defers to the heuristic.
_MIN_PER_ARM = 10


def _policy_path(uid: str):
    return brain.user_dir(uid) / "agent_policy.json"


def load_policy(uid: str) -> dict | None:
    """The distilled model for this user, or None if never trained / insufficient data."""
    try:
        return brain.read_json(_policy_path(uid))
    except Exception:  # noqa: BLE001 - a missing/corrupt model just means "no learned policy"
        return None


def _collect_units(uid: str) -> dict:
    """Join trace decisions to outcomes across all the user's projects:
    {(project, unit): {"ctx": "book"|"article", "gathered": bool,
                       "first_pass": bool | None, "insight": int | None}}."""
    from ..brain import ArticlePaths, BookPaths
    units: dict = {}
    for pid, ptype in brain.list_projects(uid):
        ctx = "article" if ptype == "article" else "book"
        paths = ArticlePaths(pid, uid) if ptype == "article" else BookPaths(pid, uid)
        for r in trace.read(paths):
            unit = r.get("unit")
            if not unit:
                continue
            d = units.setdefault((pid, unit),
                                 {"ctx": ctx, "gathered": False, "first_pass": None, "insight": None})
            if r.get("action") in ("research", "read_canon"):
                # Confound guard: the mid-loop RESCUE research (reason "evidence gap")
                # only fires AFTER a failed critique, when first_pass is already False
                # by construction - counting it as "gathered" poisons that arm with
                # guaranteed failures and the policy would "learn" that research hurts.
                # Only pre-draft gathering (the controller's actual choice) counts.
                if r.get("reason") != "evidence gap":
                    d["gathered"] = True
            if r.get("scope") == "unit-outcome" and r.get("first_pass") is not None:
                d["first_pass"] = bool(r.get("first_pass"))
                d["insight"] = r.get("insight")
    return units


def _reward(d: dict) -> float:
    """Composite reward for one unit: first-pass (did it commit without revision) blended with
    the critic's insight score (1-5, normalized). Richer than first-pass alone (§21 #6)."""
    fp = 1.0 if d.get("first_pass") else 0.0
    ins = d.get("insight")
    if isinstance(ins, (int, float)):
        return 0.6 * fp + 0.4 * (max(1.0, min(5.0, float(ins))) - 1) / 4.0
    return fp


def _fit(rows: list[dict]) -> dict | None:
    """Compare mean reward with vs. without gathering over labelled units. None if either
    arm is below the small-sample floor."""
    g = [d for d in rows if d["first_pass"] is not None and d["gathered"]]
    nd = [d for d in rows if d["first_pass"] is not None and not d["gathered"]]
    if len(g) < _MIN_PER_ARM or len(nd) < _MIN_PER_ARM:
        return None
    rg = sum(_reward(d) for d in g) / len(g)
    rd = sum(_reward(d) for d in nd) / len(nd)
    return {"n_gathered": len(g), "n_direct": len(nd),
            "reward_gathered": round(rg, 3), "reward_direct": round(rd, 3),
            "research_helps": rg > rd}


def train_policy(uid: str) -> dict | None:
    """Fit + persist the learned policy from the trace corpus (context-conditioned on book vs.
    article, with a global fallback; composite first-pass+insight reward). Returns the model, or
    None (and writes nothing) when no arm has enough labelled data."""
    units = list(_collect_units(uid).values())
    model: dict = {}
    glob = _fit(units)
    if glob:
        model["global"] = glob
    by_ctx = {}
    for ctx in ("book", "article"):
        fit = _fit([d for d in units if d.get("ctx") == ctx])
        if fit:
            by_ctx[ctx] = fit
    if by_ctx:
        model["by_context"] = by_ctx
    if not model:
        return None                                  # undecided -> fall back to the heuristic
    brain.write_json(_policy_path(uid), model)
    return model


def research_decision(model: dict | None, ctx: str | None) -> bool | None:
    """The learned verdict for whether to gather before drafting in this context: the
    context-specific model when it has data, else the global one, else None (undecided)."""
    if not model:
        return None
    entry = (model.get("by_context", {}) or {}).get(ctx) or model.get("global")
    return entry.get("research_helps") if entry else None
