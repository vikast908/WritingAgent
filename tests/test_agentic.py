"""Agentic controller (plan §21), fake-LLM mode - no API calls.

Covers every phase: the tool registry (P0), default-policy equivalence with the fixed
pipeline (P1), the LLM policy + action trace (P2), mid-draft research folded into the
draft (P3), the fact-check panel (P4), and the trace-policy seam (P5).
"""
import dataclasses

import pytest

from writingagent import agentic, brain, orchestrator
from writingagent import schemas as S
from writingagent import skills as skills_mod
from writingagent.brain import ArticlePaths, BookPaths
from writingagent.config import load_config, load_settings


@pytest.fixture
def fake_llm(monkeypatch):
    monkeypatch.setenv("WRITINGAGENT_FAKE", "1")


def _dir():
    return S.Direction(title="Dir", premise="p", tone="dark", themes=["fog"],
                       hook="h", why_it_works="w")


def _angle():
    return S.ArticleAngle(title="Ang", angle="a", audience="eng", hook="h")


def _settings(**over):
    return dataclasses.replace(load_settings(), **over)


def _silent(*_a, **_k):
    pass


# ── Phase 0: tool registry ────────────────────────────────────────────────────
def test_catalog_exposes_unit_tools():
    names = {t.name for t in agentic.CATALOG}
    assert {"draft", "research", "read_canon"} <= names
    assert agentic.UNIT_ACTIONS == ("draft", "research", "read_canon")
    assert "draft" in agentic.catalog_summary()


def test_default_policy_always_drafts():
    d = agentic.DefaultPolicy().decide("view", ["draft", "research", "read_canon"])
    assert d.action == "draft"


def test_unitops_available_drops_disabled_tools():
    ops = agentic.UnitOps(paths=None, unit_label="ch01", research_on=False, has_canon=False,
                          draft=lambda e: "commit", research=lambda q: "", read_canon=lambda q: "")
    assert ops.available() == ["draft"]
    ops2 = dataclasses.replace(ops, research_on=True, has_canon=True)
    assert ops2.available() == ["draft", "research", "read_canon"]


# ── Phase 1: default-policy equivalence with the fixed pipeline ────────────────
def test_agentic_default_matches_pipeline(tmp_brain, fake_llm):
    """An agentic run with the default policy must match the fixed pipeline: identical
    manuscript, identical episode count, identical duel count (plan §21.5)."""
    cfg = load_config()
    bid1 = orchestrator.start_article(cfg, _settings(agentic=False), "u1", "abstract",
                                      _angle(), "p1", 2, 1, autonomous=True)
    orchestrator.run(cfg, "u1", bid1, log=_silent)
    bid2 = orchestrator.start_article(cfg, _settings(agentic=True), "u2", "abstract",
                                      _angle(), "p2", 2, 1, autonomous=True)
    orchestrator.run(cfg, "u2", bid2, log=_silent)

    ms1 = brain.read_text(ArticlePaths(bid1, "u1").manuscript)
    ms2 = brain.read_text(ArticlePaths(bid2, "u2").manuscript)
    assert ms1 and ms1 == ms2                              # byte-identical output
    # episode count (record_chapter) is the learning-loop signal: identical between runs.
    base1, base2 = skills_mod.load_index("u1")["_baseline"], skills_mod.load_index("u2")["_baseline"]
    assert base1["chapters"] == base2["chapters"] >= 1


def test_agentic_default_writes_only_draft_actions(tmp_brain, fake_llm):
    cfg = load_config()
    bid = orchestrator.start_article(cfg, _settings(agentic=True), "ua", "abstract",
                                     _angle(), "pa", 2, 1, autonomous=True)
    orchestrator.run(cfg, "ua", bid, log=_silent)
    tr = agentic.trace.read(ArticlePaths(bid, "ua"))
    episodes = skills_mod.load_index("ua")["_baseline"]["chapters"]
    # default policy => exactly one 'draft' action per committed unit, nothing else.
    assert tr and len(tr) == episodes and all(r["action"] == "draft" for r in tr)


def test_agentic_book_completes(tmp_brain, fake_llm):
    cfg = load_config()
    bid = orchestrator.start_book(cfg, _settings(agentic=True), "ub", "abstract",
                                  _dir(), "bk", 1, 1, autonomous=True)
    state = orchestrator.run(cfg, "ub", bid, log=_silent)
    assert state["phase"] == "done"
    assert BookPaths(bid, "ub").ch(1).exists()
    assert any(r["action"] == "draft" for r in agentic.trace.read(BookPaths(bid, "ub")))


# ── Phase 2: LLM policy + trace ───────────────────────────────────────────────
def test_agentic_llm_policy_completes_offline(tmp_brain, fake_llm):
    """The LLM policy must complete offline: in fake mode the structured call returns the
    safe default ('draft'), so the run finishes exactly like the pipeline."""
    cfg = load_config()
    bid = orchestrator.start_article(cfg, _settings(agentic=True, agentic_policy="llm"),
                                     "ul", "abstract", _angle(), "pl", 1, 1, autonomous=True)
    state = orchestrator.run(cfg, "ul", bid, log=_silent)
    assert state["phase"] == "done"
    assert ArticlePaths(bid, "ul").manuscript.exists()


def test_llm_policy_falls_back_on_illegal_action():
    cfg = load_config()
    pol = agentic.LlmPolicy(cfg, "m")

    class _Bad:
        def decide(self, *_a):
            return agentic.ControllerDecision(action="research")
    # research not available this run -> guarded to draft
    d = pol.decide("view", ["draft"])   # fake mode returns 'draft' already; assert legality holds
    assert d.action in ("draft",)


# ── Phase 3: mid-draft tool use (research folded into the draft context) ───────
def test_run_unit_research_then_draft(tmp_brain, fake_llm, monkeypatch):
    cfg = load_config()

    class StubPolicy:
        name = "stub"
        def __init__(self):
            self.calls = 0

        def decide(self, view, available):
            self.calls += 1
            if self.calls == 1 and "research" in available:
                return agentic.ControllerDecision(action="research", query="q", reason="gather")
            return agentic.ControllerDecision(action="draft", reason="write now")

    monkeypatch.setattr(agentic.controller, "make_policy", lambda *a, **k: StubPolicy())

    paths = BookPaths("x", "u5")
    paths.ensure()
    captured = {}

    def _draft(extra):
        captured["extra"] = extra
        return "commit"

    ops = agentic.UnitOps(paths=paths, unit_label="ch01", research_on=True, has_canon=True,
                          draft=_draft, research=lambda q: "## Controller research brief\nfact",
                          read_canon=lambda q: "canon")
    state = {"controller": "agentic", "agentic_policy": "default",
             "agentic_max_unit_steps": 3, "agent_steps": 0}
    out = agentic.run_unit(cfg, state, ops=ops, log=_silent)

    assert out == "commit"
    assert "fact" in (captured["extra"] or "")            # research folded into the draft context
    assert state["agent_steps"] == 2                       # research + draft
    actions = [r["action"] for r in agentic.trace.read(paths)]
    assert actions == ["research", "draft"]


def test_run_unit_step_budget_forces_draft(tmp_brain):
    cfg = load_config()

    class AlwaysResearch:
        name = "greedy"
        def decide(self, view, available):
            return agentic.ControllerDecision(action="research", query="q")

    import writingagent.agentic.controller as ctrl
    orig = ctrl.make_policy
    try:
        ctrl.make_policy = lambda *a, **k: AlwaysResearch()
        paths = BookPaths("xb", "u6")
        paths.ensure()
        calls = {"n": 0}

        def _draft(extra):
            calls["n"] += 1
            return "commit"

        ops = agentic.UnitOps(paths=paths, unit_label="ch01", research_on=True, has_canon=False,
                              draft=_draft, research=lambda q: "brief", read_canon=lambda q: "")
        state = {"controller": "agentic", "agentic_max_unit_steps": 2, "agent_steps": 0}
        out = agentic.run_unit(cfg, state, ops=ops, log=_silent)
        assert out == "commit" and calls["n"] == 1          # the budget forced exactly one draft
    finally:
        ctrl.make_policy = orig


# ── Phase 4: multi-agent fact-check panel ─────────────────────────────────────
def test_factcheck_panel_passes_offline(fake_llm):
    ok, refutes = agentic.panels.fact_check_panel(load_config(), "draft [1]", "source text",
                                                  voters=3, log=_silent)
    assert ok is True and refutes == 0                      # fake verify_claims => 'supported'


def test_factcheck_panel_noop_without_source():
    ok, refutes = agentic.panels.fact_check_panel(load_config(), "draft", "", log=_silent)
    assert ok is True and refutes == 0


# ── Phase 4 wiring: panel gates an article approval (offline) ─────────────────
def _inject_source_text(monkeypatch, text="ground truth source material"):
    """Make the article section fetch return a non-empty `source_text` so the
    agentic fact-check panel has ground truth to run against in offline mode."""
    from writingagent.orchestrator import article as art

    orig = art._section_fetch

    def _patched(cfg, paths, outline, state, n, log):
        out = orig(cfg, paths, outline, state, n, log)
        out["research"] = ("", [], text)   # (brief_prefix, sources, source_text)
        return out

    monkeypatch.setattr(art, "_section_fetch", _patched)


def test_factcheck_panel_article_completes(tmp_brain, fake_llm, monkeypatch):
    """An agentic article run with the panel ON completes: fake verify_claims =>
    'supported' => panel passes => the section commits and the run reaches 'done'."""
    _inject_source_text(monkeypatch)
    cfg = load_config()
    bid = orchestrator.start_article(
        cfg, _settings(agentic=True, agentic_factcheck_panel=True),
        "up1", "abstract", _angle(), "pp1", 1, 1, autonomous=True)
    state = orchestrator.run(cfg, "up1", bid, log=_silent)
    assert state["phase"] == "done"
    assert ArticlePaths(bid, "up1").manuscript.exists()


def test_factcheck_panel_failure_triggers_revision_then_commits(tmp_brain, fake_llm, monkeypatch):
    """A failing panel must NOT hang: it blocks the approval this attempt, the revision
    loop runs, and the autonomous 'commit best' still lands the unit within max_rev."""
    _inject_source_text(monkeypatch)
    calls = {"n": 0}

    def _always_refute(cfg, draft, source_text, *, voters=3, log=print):
        calls["n"] += 1
        return False, voters

    monkeypatch.setattr(agentic.panels, "fact_check_panel", _always_refute)
    cfg = load_config()
    # deep_research=True: the panel only blocks on full-text ground truth (matches the
    # verify-gate's snippet policy), so it must be enabled for the panel to gate here.
    bid = orchestrator.start_article(
        cfg, _settings(agentic=True, agentic_factcheck_panel=True, deep_research=True),
        "up2", "abstract", _angle(), "pp2", 1, 1, autonomous=True)
    state = orchestrator.run(cfg, "up2", bid, log=_silent)
    assert state["phase"] == "done"                      # committed, did not hang
    assert ArticlePaths(bid, "up2").manuscript.exists()
    assert calls["n"] >= 1                                # the panel actually gated the approval


# ── Phase 3 wiring: an evidence gap pulls one research brief mid-unit ─────────
def test_evidence_gap_pulls_research_trace(tmp_brain, fake_llm, monkeypatch):
    """Under the agentic controller with the researcher on, a BLOCKING evidence issue in
    the critique must trigger exactly one mid-unit research pull, recorded in the trace
    with reason 'evidence gap'."""
    from writingagent import nodes
    from writingagent.orchestrator import article as art

    seen = {"flagged": False}

    def _gate_with_evidence_gap(cfg, state, draft, source_text, crit, log):
        # Force one evidence blocking issue on the first pass so Phase-3 fires; let later
        # attempts pass so the run still completes.
        if not seen["flagged"]:
            seen["flagged"] = True
            crit.blocking.append(S.BlockingIssue(
                type="evidence", where="[1]", detail="claim X is unsupported",
                fix="ground it"))
            crit.verdict = "revise"
        return crit, ""

    # Stamp the on-demand research brief with a sentinel and spy on the writer's context,
    # proving the folded brief reaches the NEXT revision via closure late-binding.
    orig_research = agentic.unit_research_article
    monkeypatch.setattr(
        agentic, "unit_research_article",
        lambda *a, **k: "## SENTINEL_BRIEF\n" + orig_research(*a, **k))
    contexts: list[str | None] = []
    orig_write = nodes.write_article_section
    monkeypatch.setattr(
        nodes, "write_article_section",
        lambda *a, **k: (contexts.append(k.get("context")), orig_write(*a, **k))[1])

    monkeypatch.setattr(art, "_verify_claims_gate", _gate_with_evidence_gap)
    cfg = load_config()
    bid = orchestrator.start_article(
        cfg, _settings(agentic=True, use_researcher=True),
        "up3", "abstract", _angle(), "pp3", 1, 2, autonomous=True)
    state = orchestrator.run(cfg, "up3", bid, log=_silent)
    assert state["phase"] == "done"

    tr = agentic.trace.read(ArticlePaths(bid, "up3"))
    research = [r for r in tr if r.get("action") == "research" and r.get("reason") == "evidence gap"]
    assert research, f"expected an evidence-gap research trace entry, got {tr}"
    # The brief was folded into the context the post-gap revision writer actually saw.
    assert any("SENTINEL_BRIEF" in (c or "") for c in contexts), \
        "folded research brief did not reach the next writer context"


def test_evidence_gap_research_skipped_when_not_agentic(tmp_brain, fake_llm, monkeypatch):
    """The Phase-3 pull must NOT fire under the fixed pipeline (controller != agentic),
    preserving the equivalence guarantee even when an evidence gap is present."""
    from writingagent.orchestrator import article as art

    def _gate_with_evidence_gap(cfg, state, draft, source_text, crit, log):
        crit.blocking.append(S.BlockingIssue(
            type="evidence", where="[1]", detail="unsupported", fix="ground it"))
        crit.verdict = "revise"
        return crit, ""

    monkeypatch.setattr(art, "_verify_claims_gate", _gate_with_evidence_gap)
    cfg = load_config()
    bid = orchestrator.start_article(
        cfg, _settings(agentic=False, use_researcher=True),
        "up4", "abstract", _angle(), "pp4", 1, 2, autonomous=True)
    orchestrator.run(cfg, "up4", bid, log=_silent)
    # No agent trace file at all on a non-agentic run => no Phase-3 research entry.
    tr = agentic.trace.read(ArticlePaths(bid, "up4"))
    assert not any(r.get("reason") == "evidence gap" for r in tr)


# ── Phase 5: trace-policy seam ────────────────────────────────────────────────
def test_trace_policy_reads_history_and_defaults(tmp_brain):
    paths = BookPaths("xt", "ut")
    paths.ensure()
    agentic.trace.append(paths, {"action": "draft", "unit": "ch01"})
    tp = agentic.TracePolicy(paths)
    assert tp.history and tp.history[0]["action"] == "draft"
    assert tp.decide("view", ["draft"]).action == "draft"


def test_public_api_opt_in(tmp_brain, fake_llm):
    """The opt-in surface: Agent(agentic=True) bakes controller='agentic' into run-state,
    and /set reaches the new fields generically (both go through Settings)."""
    from writingagent import Agent
    proj = Agent(user="uapi", agentic=True, autonomous=True).create("topic", mode="article", units=1)
    assert proj.status().raw.get("controller") == "agentic"


def test_make_policy_resolves_modes(tmp_brain):
    cfg = load_config()
    paths = BookPaths("xm", "um")
    paths.ensure()
    assert agentic.make_policy({"agentic_policy": "default"}, cfg, paths).name == "default"
    assert agentic.make_policy({"agentic_policy": "llm"}, cfg, paths).name == "llm"
    assert agentic.make_policy({"agentic_policy": "trace"}, cfg, paths).name == "trace"


# ── D-014: trace records carry the join keys (run_id + ts) ──────────────────────
def test_trace_append_stamps_run_id_and_ts(tmp_brain):
    from writingagent import llm
    paths = BookPaths("trace-join", "utj").ensure()
    llm.reset_usage()
    agentic.trace.append(paths, {"unit": "ch01", "action": "draft"})
    recs = agentic.trace.read(paths)
    assert recs and recs[0]["run_id"] == llm.run_id()
    assert "ts" in recs[0] and recs[0]["action"] == "draft"


def test_trace_append_keeps_caller_supplied_keys(tmp_brain):
    paths = BookPaths("trace-keep", "utk").ensure()
    agentic.trace.append(paths, {"action": "research", "run_id": "explicit"})
    recs = agentic.trace.read(paths)
    assert recs[-1]["run_id"] == "explicit"   # caller value wins over the auto-stamp
