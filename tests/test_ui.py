"""Tests for the shared UI helpers and the run dashboard's log parsing."""
from __future__ import annotations

from book_agent import ui


def test_did_you_mean():
    assert ui.did_you_mean("statuss", ["status", "run", "export"]) == "status"
    assert ui.did_you_mean("xyzzy", ["status", "run"]) is None


def test_word_count_and_reading_time():
    assert ui.word_count("one two three") == 3
    assert ui.word_count("") == 0
    assert ui.word_count(None) == 0
    assert ui.reading_time_min(0) == 1          # never zero
    assert ui.reading_time_min(400) == 2


def test_phase_stepper_marks_current():
    t = ui.phase_stepper(ui.PHASES_BOOK, "production")
    plain = t.plain
    for ph in ui.PHASES_BOOK:
        assert ph in plain
    assert "● production" in plain
    # unknown phase must not raise
    ui.phase_stepper(ui.PHASES_BOOK, "nonsense")


def test_efficacy_bar_runs():
    assert ui.efficacy_bar(0.8, 0.5).plain.endswith("80%")
    assert ui.efficacy_bar(0.0, 0.0).plain.endswith("0%")


def test_plain_mode_env(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert ui.plain_mode() is True
    monkeypatch.delenv("NO_COLOR", raising=False)
    ui.set_plain(False)
    assert ui.plain_mode() is False


def test_run_dashboard_log_parsing():
    from book_agent.shell import _RunDashboard
    d = _RunDashboard("mybook", total=2, done=0)
    for msg in [
        "== Chapter 1: The Start ==",
        "   writing (draft)...",
        "   critiquing...",
        "   verdict=approve confidence=0.80 blocking=0 nits=1",
        "   humanizing...",
        "   [OK] committed chapter 1 (+ summary)",
    ]:
        d.log(msg)
    assert d.done == 1                          # advanced on commit
    assert d.unit.startswith("Chapter 1")
    d.render()                                  # builds a renderable without raising
