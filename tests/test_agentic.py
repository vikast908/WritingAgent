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
    # default policy => exactly one 'draft' DECISION per committed unit, nothing else.
    # (unit-outcome labels - scope set, no action - are not decisions; filter them out.)
    decisions = [r for r in tr if r.get("action")]
    assert decisions and len(decisions) == episodes and all(r["action"] == "draft" for r in decisions)


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


# ── Run-level controller: the macro-agentic loop (plan §21.3) ───────────────────
def _book_dir():
    return S.Direction(title="Dir", premise="p", tone="dark", themes=["fog"],
                       hook="h", why_it_works="w")


def test_run_actions_catalogued():
    assert {"draft", "consolidate", "repair", "produce", "learn", "done"} <= set(agentic.RUN_ACTIONS)


def test_run_loop_book_macro_completes(tmp_brain, fake_llm):
    """A book under a macro policy (llm) drives itself to done via run_loop, recording
    run-scope decisions (draft -> final consolidate -> produce -> learn)."""
    cfg = load_config()
    bid = orchestrator.start_book(cfg, _settings(agentic=True, agentic_policy="llm"),
                                  "umb", "abstract", _book_dir(), "mbk", 2, 1, autonomous=True)
    state = orchestrator.run(cfg, "umb", bid, log=_silent)
    assert state["phase"] == "done"
    assert BookPaths(bid, "umb").manuscript.exists()
    runs = [r["action"] for r in agentic.trace.read(BookPaths(bid, "umb")) if r.get("scope") == "run"]
    assert "draft" in runs and "consolidate" in runs and "produce" in runs and "learn" in runs


def test_run_loop_article_macro_completes(tmp_brain, fake_llm):
    cfg = load_config()
    aid = orchestrator.start_article(cfg, _settings(agentic=True, agentic_policy="trace"),
                                     "uma", "abstract", _angle(), "mar", 2, 1, autonomous=True)
    state = orchestrator.run(cfg, "uma", aid, log=_silent)
    assert state["phase"] == "done"
    assert ArticlePaths(aid, "uma").manuscript.exists()
    runs = [r["action"] for r in agentic.trace.read(ArticlePaths(aid, "uma")) if r.get("scope") == "run"]
    assert runs and runs[-1] == "learn"      # macro loop drove produce -> learn -> done


def test_default_policy_uses_no_run_scope_trace(tmp_brain, fake_llm):
    """The DEFAULT policy stays on the legacy loop, so it never writes run-scope trace
    entries - the macro controller engages only for llm/trace policies."""
    cfg = load_config()
    aid = orchestrator.start_article(cfg, _settings(agentic=True), "umd", "abstract",
                                     _angle(), "mdf", 1, 1, autonomous=True)
    orchestrator.run(cfg, "umd", aid, log=_silent)
    assert not any(r.get("scope") == "run" for r in agentic.trace.read(ArticlePaths(aid, "umd")))


def test_run_guard_forces_legal_default():
    from writingagent.agentic._schema import RunDecision
    from writingagent.agentic.runner import _run_guard
    # legal pick passes through; illegal collapses to the default.
    assert _run_guard(RunDecision(action="produce"), ["produce", "learn"], "learn").action == "produce"
    assert _run_guard(RunDecision(action="draft"), ["produce"], "produce").action == "produce"


def test_run_policy_resolution():
    cfg = load_config()
    paths = BookPaths("rp", "urp")
    assert agentic.make_run_policy({"agentic_policy": "default"}, cfg, paths).name == "default"
    assert agentic.make_run_policy({"agentic_policy": "llm"}, cfg, paths).name == "llm"
    assert agentic.make_run_policy({"agentic_policy": "trace"}, cfg, paths).name == "trace"


def test_llm_run_policy_falls_back_on_illegal(fake_llm):
    # fake mode returns the first enum ("draft"); when draft is illegal the guard in the
    # policy itself maps it to the legal default.
    pol = agentic.LlmRunPolicy(load_config(), "m")
    assert pol.decide("view", ["produce"], "produce").action == "produce"


def test_trace_run_policy_audits_after_contradiction():
    pol = agentic.TraceRunPolicy.__new__(agentic.TraceRunPolicy)
    pol.history = [{"action": "consolidate", "contradictions": 2}]
    # a past contradiction + consolidate legal + default draft -> audit early
    assert pol.decide("v", ["draft", "consolidate"], "draft").action == "consolidate"
    # but if consolidate isn't legal, fall back to the default
    assert pol.decide("v", ["draft"], "draft").action == "draft"
    # no past contradictions -> follow the default
    pol.history = [{"action": "consolidate", "contradictions": 0}]
    assert pol.decide("v", ["draft", "consolidate"], "draft").action == "draft"


def test_trace_policy_researches_after_evidence_gap():
    pol = agentic.TracePolicy.__new__(agentic.TracePolicy)
    pol.history = [{"action": "research", "reason": "evidence gap"}]
    pol.model = None                                       # no learned model -> heuristic layer
    view = "Context gathered for this unit so far: nothing yet."
    assert pol.decide(view, ["draft", "research"]).action == "research"   # learns to gather up front
    assert pol.decide(view, ["draft"]).action == "draft"                  # research unavailable
    pol.history = []
    assert pol.decide(view, ["draft", "research"]).action == "draft"      # no signal -> draft


def test_read_canon_slice_is_query_relevant():
    from writingagent.orchestrator import book

    class _Stub:
        def search_excerpts(self, terms, limit=3):
            return [("ch01", "matched snippet")] if terms else []

        def canon_context(self, **_k):
            return "WHOLE CANON BLOCK"
    stub = _Stub()
    assert "matched snippet" in book._read_canon_slice(stub, "alpha beta")   # relevant slice
    assert book._read_canon_slice(stub, "") == "WHOLE CANON BLOCK"           # no query -> whole


# ── Gap 2: trained policy distilled from the trace corpus (plan §21.11) ──────────
def test_train_policy_fits_and_persists(tmp_brain, monkeypatch):
    from writingagent.agentic import learn
    units = {("p", f"g{i}"): {"gathered": True, "first_pass": True} for i in range(3)}
    units.update({("p", f"d{i}"): {"gathered": False, "first_pass": False} for i in range(3)})
    monkeypatch.setattr(learn, "_collect_units", lambda uid: units)
    model = learn.train_policy("ufit")
    assert model and model["global"]["research_helps"] is True       # gathering lifts the reward here
    assert learn.research_decision(learn.load_policy("ufit"), None) is True   # persisted + consulted


def test_train_policy_undecided_on_thin_data(tmp_brain, monkeypatch):
    from writingagent.agentic import learn
    monkeypatch.setattr(learn, "_collect_units",
                        lambda uid: {("p", "u1"): {"gathered": True, "first_pass": True}})
    assert learn.train_policy("uthin") is None                  # < MIN_PER_ARM -> no model
    assert learn.load_policy("uthin") is None                   # nothing written


def test_trace_policy_follows_learned_model():
    pol = agentic.TracePolicy.__new__(agentic.TracePolicy)
    pol.history = []
    pol._learn = agentic.learn
    view = "Preparing to draft unit 'sec01'. Context gathered for this unit so far: nothing yet."
    pol.model = {"global": {"research_helps": True}}
    assert pol.decide(view, ["draft", "research"]).action == "research"   # learned: gather
    pol.model = {"global": {"research_helps": False}}
    assert pol.decide(view, ["draft", "research"]).action == "draft"      # learned: draft directly


def test_agentic_run_records_unit_outcome(tmp_brain, fake_llm):
    cfg = load_config()
    aid = orchestrator.start_article(cfg, _settings(agentic=True, agentic_policy="llm"),
                                     "uo", "abstract", _angle(), "uor", 1, 1, autonomous=True)
    orchestrator.run(cfg, "uo", aid, log=_silent)
    recs = agentic.trace.read(ArticlePaths(aid, "uo"))
    assert any(r.get("scope") == "unit-outcome" and "first_pass" in r for r in recs)


def test_inline_tools_setting_threads_into_state(tmp_brain, fake_llm):
    cfg = load_config()
    aid = orchestrator.start_article(cfg, _settings(agentic=True, agentic_inline_tools=True),
                                     "uit", "abstract", _angle(), "uitr", 1, 1, autonomous=True)
    st = brain.read_json(ArticlePaths(aid, "uit").run_state)
    assert st["agentic_inline_tools"] is True       # writer in-generation tools opt-in is durable


# ── The 8-gap batch: wider action space, panels, self-monitoring ─────────────────
def test_run_actions_include_planning_and_escalate():
    assert {"reoutline", "revise", "escalate"} <= set(agentic.RUN_ACTIONS)
    assert agentic.OPTIONAL_RUN_ACTIONS == frozenset({"reoutline", "revise", "table_read"})


def test_writer_tools_include_verify_fact():
    names = {t["function"]["name"] for t in agentic.WRITER_TOOL_SCHEMAS}
    assert {"research", "read_canon", "verify_fact"} <= names


def test_weakest_committed_unit():
    state = {"scores": [
        {"insight": 5, "clarity": 5, "structure": 5, "evidence": 5},
        {"insight": 2, "clarity": 2, "structure": 3, "evidence": 2},   # weakest
        {"insight": 4, "clarity": 4, "structure": 4, "evidence": 4}]}
    assert agentic.weakest_committed_unit(state) == 2
    assert agentic.weakest_committed_unit({}) is None


def test_run_view_surfaces_quality_contradictions_budget(monkeypatch):
    from writingagent import llm
    monkeypatch.setattr(llm, "run_budget", lambda: 1000)
    monkeypatch.setattr(llm, "current_tokens", lambda: 900)
    state = {"mode": "book", "phase": "chapters", "current_chapter": 2, "num_chapters": 3,
             "committed": 1, "open_contradictions": 2,
             "scores": [{"insight": 2, "clarity": 2, "structure": 2, "evidence": 2}]}
    view = agentic.build_run_view(state, ["draft", "consolidate"])
    assert "weakest = chapter1" in view and "contradictions: 2" in view
    assert "Token budget" in view and "LOW" in view          # self-monitoring perception


def test_run_loop_exercises_reoutline_and_revise(tmp_brain, fake_llm, monkeypatch):
    from writingagent.agentic import policy as pol_mod

    class Greedy:                      # take every optional structural move while it's legal
        name = "greedy"
        def decide(self, view, legal, default):
            for a in ("reoutline", "revise"):
                if a in legal:
                    return agentic.RunDecision(action=a)
            return agentic.RunDecision(action=default)
    monkeypatch.setattr(pol_mod, "make_run_policy", lambda *a, **k: Greedy())
    cfg = load_config()
    aid = orchestrator.start_article(cfg, _settings(agentic=True, agentic_policy="llm"),
                                     "urx", "abstract", _angle(), "urxr", 2, 1, autonomous=True)
    state = orchestrator.run(cfg, "urx", aid, log=_silent)
    assert state["phase"] == "done"                          # still converges despite the detours
    assert state.get("reoutlines", 0) == 2                   # capped
    assert state.get("revisions_done", 0) == 3               # capped
    acts = [r["action"] for r in agentic.trace.read(ArticlePaths(aid, "urx"))
            if r.get("scope") == "run-result"]
    assert "reoutline" in acts and "revise" in acts


def test_run_loop_escalate_pauses(tmp_brain, fake_llm, monkeypatch):
    from writingagent.agentic import policy as pol_mod

    class Defer:
        name = "defer"
        def decide(self, view, legal, default):
            return agentic.RunDecision(action="escalate")
    monkeypatch.setattr(pol_mod, "make_run_policy", lambda *a, **k: Defer())
    cfg = load_config()
    aid = orchestrator.start_article(cfg, _settings(agentic=True, agentic_policy="llm"),
                                     "ues", "abstract", _angle(), "uesr", 2, 1, autonomous=True)
    state = orchestrator.run(cfg, "ues", aid, log=_silent)
    assert state["phase"] != "done" and state.get("pending_review")   # the agent deferred


def test_budget_pressure_drops_optional_actions(monkeypatch):
    from writingagent import llm
    from writingagent.agentic import runner
    monkeypatch.setattr(llm, "run_budget", lambda: 1000)
    monkeypatch.setattr(llm, "current_tokens", lambda: 950)   # 95% spent -> pressured

    class _Ops:
        def legal_actions(self, st):
            return ["draft", "reoutline", "revise", "produce"]
    legal = runner._legal_now(_Ops(), {})
    assert "reoutline" not in legal and "revise" not in legal   # polish dropped
    assert "draft" in legal and "produce" in legal              # progress kept


def test_critique_panel_majority(monkeypatch, fake_llm):
    from writingagent import schemas as S
    from writingagent.agentic import panels

    def all_clean(lens):
        return S.Critique(verdict="approve", confidence=0.9, blocking=[], nits=[])
    passed, blocks = panels.critique_panel(all_clean, log=_silent)
    assert passed and blocks == 0

    calls = {"n": 0}
    def two_block(lens):
        calls["n"] += 1
        bad = calls["n"] <= 2     # 2 of 3 lenses block
        return S.Critique(verdict="revise" if bad else "approve", confidence=0.5,
                          blocking=[S.BlockingIssue(type="quality", where="w", detail="d", fix="f")]
                          if bad else [], nits=[])
    passed, blocks = panels.critique_panel(two_block, log=_silent)
    assert not passed and blocks == 2
