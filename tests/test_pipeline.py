"""End-to-end orchestrator tests using fake-LLM mode (no API calls)."""
import pytest

from book_agent import brain, orchestrator
from book_agent import schemas as S
from book_agent.brain import BookPaths
from book_agent.config import load_config, load_settings


@pytest.fixture
def fake_llm(monkeypatch):
    monkeypatch.setenv("BOOK_AGENT_FAKE", "1")


def _chosen():
    return S.Direction(title="Dir", premise="p", tone="dark", themes=["fog"],
                       hook="h", why_it_works="w")


def _silent(*_a, **_k):
    pass


def test_end_to_end_completes(tmp_brain, fake_llm):
    cfg, settings = load_config(), load_settings()
    bid = orchestrator.start_book(cfg, settings, "u", "abstract", _chosen(), "mybook", 1, 1)
    state = orchestrator.run(cfg, "u", bid, log=_silent)

    assert state["phase"] == "done"
    paths = BookPaths(bid, "u")
    assert paths.ch(1).exists()
    assert paths.ch_summary(1).exists()
    assert paths.manuscript.exists()
    assert (paths.consolidation / "final.md").exists()
    assert "character" in orchestrator.memory_summary("u", bid).lower()
    # learner produced at least one skill
    assert list(brain.skills_dir("u").glob("*.md"))


def test_escalation_review_resume(tmp_brain, fake_llm, monkeypatch):
    cfg, settings = load_config(), load_settings()
    monkeypatch.setenv("BOOK_AGENT_FAKE_VERDICT", "revise")  # force the cap -> escalate path
    bid = orchestrator.start_book(cfg, settings, "u", "abstract", _chosen(), "esc", 1, 1)

    state = orchestrator.run(cfg, "u", bid, log=_silent)
    assert state["pending_review"] is True
    paths = BookPaths(bid, "u")
    assert paths.review_of(1).exists()
    assert paths.ch_draft(1).exists()
    assert not paths.ch(1).exists()  # not committed

    # Human answers, then it can approve -> resume to completion.
    monkeypatch.setenv("BOOK_AGENT_FAKE_VERDICT", "approve")
    orchestrator.record_instruction("u", bid, 1, "make the confrontation colder")
    state2 = orchestrator.run(cfg, "u", bid, log=_silent)
    assert state2["phase"] == "done"
    assert paths.ch(1).exists()
    assert paths.instruction_of(1).exists()


def test_low_confidence_escalates(tmp_brain, fake_llm, monkeypatch):
    cfg, settings = load_config(), load_settings()
    monkeypatch.setenv("BOOK_AGENT_FAKE_CONFIDENCE", "0.1")  # below default 0.5 threshold
    bid = orchestrator.start_book(cfg, settings, "u", "abstract", _chosen(), "lowconf", 1, 1)

    state = orchestrator.run(cfg, "u", bid, log=_silent)
    assert state["pending_review"] is True
    assert state.get("review_kind") == "chapter"
    assert BookPaths(bid, "u").review_of(1).exists()

    monkeypatch.setenv("BOOK_AGENT_FAKE_CONFIDENCE", "0.9")
    orchestrator.record_instruction("u", bid, 1, "tighten it")
    state2 = orchestrator.run(cfg, "u", bid, log=_silent)
    assert state2["phase"] == "done"


def test_consolidation_escalation_and_force(tmp_brain, fake_llm, monkeypatch):
    cfg, settings = load_config(), load_settings()
    monkeypatch.setenv("BOOK_AGENT_FAKE_CONTRADICTION", "1")  # force a contradiction
    bid = orchestrator.start_book(cfg, settings, "u", "abstract", _chosen(), "consesc", 1, 1)

    state = orchestrator.run(cfg, "u", bid, log=_silent)
    assert state["pending_review"] is True
    assert state.get("review_kind") == "consolidation"
    assert (BookPaths(bid, "u").reviews / "consolidation-final.md").exists()

    # A plain run stays blocked; --force proceeds to completion.
    blocked = orchestrator.run(cfg, "u", bid, log=_silent)
    assert blocked["pending_review"] is True
    done = orchestrator.run(cfg, "u", bid, force=True, log=_silent)
    assert done["phase"] == "done"


def test_autonomous_never_pauses(tmp_brain, fake_llm, monkeypatch):
    cfg, settings = load_config(), load_settings()
    monkeypatch.setenv("BOOK_AGENT_FAKE_VERDICT", "revise")    # critic never approves
    monkeypatch.setenv("BOOK_AGENT_FAKE_CONTRADICTION", "1")   # consolidation would escalate
    bid = orchestrator.start_book(cfg, settings, "u", "abstract", _chosen(), "auto", 1, 1,
                                  autonomous=True)
    state = orchestrator.run(cfg, "u", bid, log=_silent)
    assert state["phase"] == "done"                  # completed despite revise + contradiction
    assert state["pending_review"] is False
    assert BookPaths(bid, "u").ch(1).exists()        # best draft committed
