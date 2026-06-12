"""Tests for the TUI/UX batch: approve-as-is, post-completion revise, variant
picking, insight tracking, and the table read."""
import pytest

from book_agent import brain, nodes, orchestrator
from book_agent import schemas as S
from book_agent.brain import ArticlePaths
from book_agent.config import load_config, load_settings


@pytest.fixture
def fake_llm(monkeypatch):
    monkeypatch.setenv("BOOK_AGENT_FAKE", "1")


def _angle():
    return S.ArticleAngle(title="A", angle="technical deep-dive",
                          audience="engineers", hook="h")


def _silent(*_a, **_k):
    pass


def _crit(verdict="approve", insight=4, blocking=0):
    issues = [S.BlockingIssue(type="style", where="p1", detail="d", fix="f")] * blocking
    return S.Critique(verdict=verdict, confidence=0.9, blocking=issues, nits=[],
                      insight=insight)


# ── approve_escalation ────────────────────────────────────────────────────────
def test_approve_escalation_commits_stalled_section(tmp_brain, fake_llm, monkeypatch):
    monkeypatch.setenv("BOOK_AGENT_FAKE_VERDICT", "escalate")
    cfg, settings = load_config(), load_settings()
    aid = orchestrator.start_article(cfg, settings, "u", "topic", _angle(),
                                     "appr", 2, 1, autonomous=False)
    state = orchestrator.run(cfg, "u", aid, log=_silent)
    assert state["pending_review"] and state["review_kind"] == "section"

    out = orchestrator.approve_escalation(cfg, "u", aid, log=_silent)
    assert out is not None
    assert out["pending_review"] is False
    assert out["committed"] == 1 and out["current_section"] == 2
    assert brain.read_text(ArticlePaths(aid, "u").section(1))   # committed file exists

    monkeypatch.delenv("BOOK_AGENT_FAKE_VERDICT", raising=False)
    final = orchestrator.run(cfg, "u", aid, log=_silent)        # resumes and finishes
    assert final["phase"] == "done"
    assert final["committed"] == 1   # fake outline always has 1 section


def test_approve_escalation_none_when_nothing_pending(tmp_brain, fake_llm):
    cfg, settings = load_config(), load_settings()
    aid = orchestrator.start_article(cfg, settings, "u", "topic", _angle(),
                                     "apprnone", 1, 1, autonomous=True)
    orchestrator.run(cfg, "u", aid, log=_silent)
    assert orchestrator.approve_escalation(cfg, "u", aid, log=_silent) is None


# ── manuscript section helpers ────────────────────────────────────────────────
_MS = ("# Title\n\n*sub*\n\n---\n\n\n---\n\n## First\n\nBody one.\n\n---\n\n"
       "## Second\n\nBody two.\n\n---\n\n## References\n\n1. [x](y)\n")


def test_manuscript_section_bodies():
    bodies = orchestrator._manuscript_section_bodies(_MS)
    assert len(bodies) == 2
    assert bodies[0].startswith("## First") and bodies[1].startswith("## Second")


def test_replace_manuscript_section():
    out = orchestrator._replace_manuscript_section(_MS, 1, "## Second\n\nNew body.")
    assert "New body." in out and "Body two." not in out
    assert "Body one." in out and "## References" in out
    assert orchestrator._replace_manuscript_section(_MS, 9, "x") is None


# ── revise_unit ───────────────────────────────────────────────────────────────
def test_revise_unit_patches_finished_manuscript(tmp_brain, fake_llm, monkeypatch):
    cfg, settings = load_config(), load_settings()
    aid = orchestrator.start_article(cfg, settings, "u", "topic", _angle(),
                                     "revart", 1, 1, autonomous=True)
    orchestrator.run(cfg, "u", aid, log=_silent)
    paths = ArticlePaths(aid, "u")
    assert brain.read_text(paths.manuscript)

    def write_spy(cfg, outline, section, fix_notes=None, **_kw):
        assert "punchier" in (fix_notes or "")
        return "## Revised Heading\n\nDistinctive revised body."
    monkeypatch.setattr(nodes, "write_article_section", write_spy)
    monkeypatch.setattr(nodes, "critique_article_section",
                        lambda *a, **k: _crit())
    orchestrator.revise_unit(cfg, "u", aid, 1, "punchier intro", log=_silent)
    ms = brain.read_text(paths.manuscript)
    assert "Distinctive revised body." in ms
    assert "## References" in ms          # rest of the manuscript survived


def test_revise_unit_out_of_range(tmp_brain, fake_llm):
    cfg, settings = load_config(), load_settings()
    aid = orchestrator.start_article(cfg, settings, "u", "topic", _angle(),
                                     "revrange", 1, 1, autonomous=True)
    orchestrator.run(cfg, "u", aid, log=_silent)
    with pytest.raises(ValueError):
        orchestrator.revise_unit(cfg, "u", aid, 7, "x", log=_silent)


# ── variant picking ───────────────────────────────────────────────────────────
def test_pick_variant_human_choice_and_default():
    drafts = {"v0": "## A\n\nAlpha body.", "v1": "## B\n\nBeta body."}
    crits = {"v0": _crit(insight=5), "v1": _crit(insight=2)}
    # human picks 2 despite the critic preferring v0
    d, c = orchestrator._pick_variant(drafts, crits, lambda _p: "2", _silent)
    assert d == drafts["v1"]
    # Enter (empty) → critic's pick
    d, c = orchestrator._pick_variant(drafts, crits, lambda _p: "", _silent)
    assert d == drafts["v0"]
    # no ask → critic's pick
    d, c = orchestrator._pick_variant(drafts, crits, None, _silent)
    assert d == drafts["v0"]


def test_ask_reaches_variant_picker_in_manual_run(tmp_brain, fake_llm):
    cfg, settings = load_config(), load_settings()
    settings.divergent_drafts = 2
    asked = {}

    def ask(prompt):
        asked["prompt"] = prompt
        return ""   # accept critic's pick
    aid = orchestrator.start_article(cfg, settings, "u", "topic", _angle(),
                                     "askart", 1, 1, autonomous=False)
    orchestrator.run(cfg, "u", aid, log=_silent, ask=ask)
    assert "Variant drafts ready" in asked.get("prompt", "")


# ── insights + table read ─────────────────────────────────────────────────────
def test_insights_tracked_and_table_read_written(tmp_brain, fake_llm):
    cfg, settings = load_config(), load_settings()
    aid = orchestrator.start_article(cfg, settings, "u", "topic", _angle(),
                                     "insux", 2, 1, autonomous=True)
    state = orchestrator.run(cfg, "u", aid, log=_silent)
    assert state["phase"] == "done"
    # one insight per committed section (the fake outline always has 1 section)
    assert state.get("insights") == [5]
    assert (ArticlePaths(aid, "u").root / "table_read.md").exists()
