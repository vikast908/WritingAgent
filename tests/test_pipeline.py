"""End-to-end orchestrator tests using fake-LLM mode (no API calls)."""
import pytest

from writingagent import brain, orchestrator
from writingagent import schemas as S
from writingagent.brain import BookPaths
from writingagent.config import load_config, load_settings


@pytest.fixture
def fake_llm(monkeypatch):
    monkeypatch.setenv("WRITINGAGENT_FAKE", "1")


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
    monkeypatch.setenv("WRITINGAGENT_FAKE_VERDICT", "revise")  # force the cap -> escalate path
    bid = orchestrator.start_book(cfg, settings, "u", "abstract", _chosen(), "esc", 1, 1)

    state = orchestrator.run(cfg, "u", bid, log=_silent)
    assert state["pending_review"] is True
    paths = BookPaths(bid, "u")
    assert paths.review_of(1).exists()
    assert paths.ch_draft(1).exists()
    assert not paths.ch(1).exists()  # not committed

    # Human answers, then it can approve -> resume to completion.
    monkeypatch.setenv("WRITINGAGENT_FAKE_VERDICT", "approve")
    orchestrator.record_instruction("u", bid, 1, "make the confrontation colder")
    state2 = orchestrator.run(cfg, "u", bid, log=_silent)
    assert state2["phase"] == "done"
    assert paths.ch(1).exists()
    assert paths.instruction_of(1).exists()


def test_low_confidence_escalates(tmp_brain, fake_llm, monkeypatch):
    cfg, settings = load_config(), load_settings()
    monkeypatch.setenv("WRITINGAGENT_FAKE_CONFIDENCE", "0.1")  # below default 0.5 threshold
    bid = orchestrator.start_book(cfg, settings, "u", "abstract", _chosen(), "lowconf", 1, 1)

    state = orchestrator.run(cfg, "u", bid, log=_silent)
    assert state["pending_review"] is True
    assert state.get("review_kind") == "chapter"
    assert BookPaths(bid, "u").review_of(1).exists()

    monkeypatch.setenv("WRITINGAGENT_FAKE_CONFIDENCE", "0.9")
    orchestrator.record_instruction("u", bid, 1, "tighten it")
    state2 = orchestrator.run(cfg, "u", bid, log=_silent)
    assert state2["phase"] == "done"


def test_consolidation_escalation_and_force(tmp_brain, fake_llm, monkeypatch):
    cfg, settings = load_config(), load_settings()
    monkeypatch.setenv("WRITINGAGENT_FAKE_CONTRADICTION", "1")  # force a contradiction
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
    monkeypatch.setenv("WRITINGAGENT_FAKE_VERDICT", "revise")    # critic never approves
    monkeypatch.setenv("WRITINGAGENT_FAKE_CONTRADICTION", "1")   # consolidation would escalate
    bid = orchestrator.start_book(cfg, settings, "u", "abstract", _chosen(), "auto", 1, 1,
                                  autonomous=True)
    state = orchestrator.run(cfg, "u", bid, log=_silent)
    assert state["phase"] == "done"                  # completed despite revise + contradiction
    assert state["pending_review"] is False
    assert BookPaths(bid, "u").ch(1).exists()        # best draft committed


def test_record_escalated_score_keeps_arrays_aligned():
    """approve_escalation commits a unit outside the attempt loop, so the per-unit
    scores/insights arrays must be appended to (via _record_escalated_score) or every
    later scores[n-1] lookup (weakest-unit revise, summary card) targets the wrong unit."""
    from writingagent.orchestrator.common import _record_escalated_score
    state = {"scores": [{"insight": 4, "clarity": 4, "structure": 4, "evidence": 4}],
             "insights": [4], "committed": 1,
             "escalated_score": {"insight": 2, "clarity": 3, "structure": 3, "evidence": 2}}
    _record_escalated_score(state)
    assert len(state["scores"]) == len(state["insights"]) == 2   # now 1:1 with committed
    assert state["scores"][1]["insight"] == 2                    # used the stashed crit
    assert state["insights"][1] == 2
    assert "escalated_score" not in state                        # consumed
    # Fallback (older paused run-state with nothing stashed): still stays aligned.
    st2 = {"scores": [], "insights": []}
    _record_escalated_score(st2)
    assert len(st2["scores"]) == len(st2["insights"]) == 1
