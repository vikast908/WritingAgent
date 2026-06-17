"""Tests for the agentic TUI surface: flipping an existing project's controller via
`orchestrator.apply_controller`, the `/agentic` toggle, and the `/trace` printout.

Offline (WRITINGAGENT_FAKE=1) against the autouse tmp-path brain from conftest.
"""
import io

import pytest
from rich.console import Console

from writingagent import agentic, brain, config, orchestrator
from writingagent import schemas as S
from writingagent.brain import ArticlePaths
from writingagent.config import load_config, load_settings
from writingagent.shell.commands import _cmd_agentic, _cmd_trace


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path, monkeypatch):
    """`save_settings` persists to the real repo config/settings.yaml; redirect it to a
    tmp file so toggling /agentic here never pollutes the developer's live config (and so
    one test's save can't leak into another's load_settings)."""
    monkeypatch.setattr(config, "_SETTINGS", tmp_path / "settings.yaml")


@pytest.fixture
def fake_llm(monkeypatch):
    monkeypatch.setenv("WRITINGAGENT_FAKE", "1")


def _console():
    return Console(file=io.StringIO(), force_terminal=False, width=100)


def _angle():
    return S.ArticleAngle(title="A", angle="technical deep-dive",
                          audience="engineers", hook="h")


def _silent(*_a, **_k):
    pass


def _make_article(aid: str):
    cfg, settings = load_config(), load_settings()
    return orchestrator.start_article(cfg, settings, "u", "topic", _angle(),
                                      aid, 1, 1, autonomous=True)


# ── orchestrator.apply_controller ─────────────────────────────────────────────
def test_apply_controller_flips_existing_project_both_ways(tmp_brain, fake_llm):
    settings = load_settings()
    aid = _make_article("ctrlflip")
    paths = ArticlePaths(aid, "u")

    # The facade re-exports apply_controller from manage.
    st = orchestrator.apply_controller("u", aid, True, settings)
    assert st is not None and st["controller"] == "agentic"
    assert st["agentic_policy"] == settings.agentic_policy
    # persisted, not just returned
    assert brain.read_json(paths.run_state)["controller"] == "agentic"

    st = orchestrator.apply_controller("u", aid, False, settings)
    assert st["controller"] == "pipeline"
    assert brain.read_json(paths.run_state)["controller"] == "pipeline"


def test_apply_controller_none_for_unknown_project(tmp_brain, fake_llm):
    assert orchestrator.apply_controller("u", "no-such-project", True,
                                         load_settings()) is None


# ── /agentic ──────────────────────────────────────────────────────────────────
def test_cmd_agentic_toggles_setting_and_live_project(tmp_brain, fake_llm):
    settings = load_settings()
    assert settings.agentic is False                       # default-off
    aid = _make_article("agtoggle")
    state = {"uid": "u", "book": aid}

    _cmd_agentic(_console(), settings, state, ["on"])
    assert settings.agentic is True
    assert brain.read_json(ArticlePaths(aid, "u").run_state)["controller"] == "agentic"

    _cmd_agentic(_console(), settings, state, ["off"])
    assert settings.agentic is False
    assert brain.read_json(ArticlePaths(aid, "u").run_state)["controller"] == "pipeline"


def test_cmd_agentic_sets_policy(tmp_brain, fake_llm):
    settings = load_settings()
    _cmd_agentic(_console(), settings, {"uid": "u", "book": None}, ["llm"])
    assert settings.agentic_policy == "llm"
    _cmd_agentic(_console(), settings, {"uid": "u", "book": None}, ["default"])
    assert settings.agentic_policy == "default"


def test_cmd_agentic_status_no_args(tmp_brain, fake_llm):
    settings = load_settings()
    console = _console()
    _cmd_agentic(console, settings, {"uid": "u", "book": None}, [])
    out = console.file.getvalue()
    assert "agentic" in out and "off" in out
    # status view must not change the setting
    assert settings.agentic is False


def test_cmd_agentic_no_project_still_saves_setting(tmp_brain, fake_llm):
    settings = load_settings()
    _cmd_agentic(_console(), settings, {"uid": "u", "book": None}, ["on"])
    assert settings.agentic is True   # saved even with no active project


def test_cmd_agentic_surfaces_learned_policy(tmp_brain, fake_llm):
    """The self-improving loop must be observable: when a learned policy exists, /agentic
    status surfaces what it concluded from the user's run traces."""
    from writingagent.agentic import learn
    model = {"by_context": {"book": {"n_gathered": 5, "n_direct": 4, "reward_gathered": 0.82,
                                     "reward_direct": 0.61, "research_helps": True}}}
    p = learn._policy_path("u")
    p.parent.mkdir(parents=True, exist_ok=True)
    brain.write_json(p, model)
    console = _console()
    _cmd_agentic(console, load_settings(), {"uid": "u", "book": None}, [])
    out = console.file.getvalue()
    assert "learned from your runs" in out
    assert "gather context first" in out          # research_helps=True -> the readable verdict


# ── /trace ────────────────────────────────────────────────────────────────────
def test_cmd_trace_prints_recorded_decisions(tmp_brain, fake_llm):
    aid = _make_article("traceart")
    paths = ArticlePaths(aid, "u")
    agentic.trace.append(paths, {
        "unit": "section 1", "step": 0, "policy": "llm", "action": "research",
        "query": "voice latency benchmarks", "reason": "thin on evidence",
        "result": "ok"})
    agentic.trace.append(paths, {
        "unit": "section 1", "step": 1, "policy": "llm", "action": "draft",
        "query": "", "reason": "enough context gathered", "result": "ok"})

    console = _console()
    _cmd_trace(console, load_settings(), {"uid": "u", "book": aid}, [])
    out = console.file.getvalue()
    assert "research" in out and "draft" in out
    assert "thin on evidence" in out
    assert "voice latency benchmarks" in out      # query surfaced


def test_cmd_trace_empty_is_friendly(tmp_brain, fake_llm):
    aid = _make_article("traceempty")
    console = _console()
    _cmd_trace(console, load_settings(), {"uid": "u", "book": aid}, [])
    assert "no agentic decisions recorded" in console.file.getvalue()


def test_cmd_trace_no_active_project(tmp_brain, fake_llm):
    console = _console()
    _cmd_trace(console, load_settings(), {"uid": "u", "book": None}, [])
    assert "No active project" in console.file.getvalue()
