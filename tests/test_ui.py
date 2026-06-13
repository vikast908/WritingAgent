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


def test_run_dashboard_stage_animates(monkeypatch):
    """Active stages (…) must visibly move between log events: Live re-renders the
    dash object, and the label changes frame-to-frame. Terminal stages stay static."""
    import time as _time

    from book_agent.shell import _RunDashboard
    d = _RunDashboard("b", total=1, done=0)
    d.stage = "critiquing…"
    monkeypatch.setattr(_time, "monotonic", lambda: 0.0)
    first = d._stage_label()
    monkeypatch.setattr(_time, "monotonic", lambda: 0.5)
    second = d._stage_label()
    assert first != second                      # spinner/dots advanced
    assert "critiquing" in first
    d.stage = "committed"
    assert d._stage_label() == "committed"      # no spinner on settled stages
    # The dash itself is a Rich renderable (handed to Live directly).
    _record_console().print(d)


def _record_console():
    import io

    from rich.console import Console
    return Console(file=io.StringIO(), force_terminal=True, width=110)


def test_welcome_is_compact(tmp_brain, monkeypatch):
    """The welcome must leave the banner on screen: banner (~21 rows) + welcome must
    fit a standard 35-row terminal. The 45-line welcome was the regression this guards."""
    monkeypatch.delenv("BOOK_AGENT_FAKE", raising=False)
    from book_agent import shell
    from book_agent.config import load_config, load_settings
    console = _record_console()
    shell._welcome(console, load_config(), load_settings(), "u")
    assert len(console.file.getvalue().splitlines()) <= 14


def test_welcome_warns_on_fake_mode(tmp_brain, monkeypatch):
    """A leftover BOOK_AGENT_FAKE otherwise silently cans every model call."""
    monkeypatch.setenv("BOOK_AGENT_FAKE", "1")
    from book_agent import shell
    from book_agent.config import load_config, load_settings
    console = _record_console()
    shell._welcome(console, load_config(), load_settings(), "u")
    assert "FAKE MODE" in console.file.getvalue()


def test_features_and_commands_tables_render(tmp_brain):
    """/features and /help content moved out of the welcome - they must still render."""
    from book_agent import shell
    from book_agent.config import load_settings
    settings = load_settings()
    console = _record_console()
    shell._features_table(console, settings)
    out = console.file.getvalue()
    assert "humanize" in out and "/set" in out
    console = _record_console()
    shell._commands_table(console, settings)
    assert "write --abstract" in console.file.getvalue()


def test_slash_help_is_grouped_by_category(tmp_brain):
    """/help groups commands under dimmed category headers (the registry is
    category-keyed, not a flat list)."""
    from book_agent import shell
    from book_agent.config import load_settings
    # Structure: [(category, [(usage, desc), ...]), ...]
    cats = [c for c, _ in shell._SLASH_HELP]
    assert "configuration" in cats and "session" in cats
    for _cat, group in shell._SLASH_HELP:
        for row in group:
            assert len(row) == 2 and row[0].startswith("/")
    console = _record_console()
    shell._slash_help(console, load_settings())
    out = console.file.getvalue()
    assert "configuration" in out and "/features" in out and "/theme" in out


def test_feature_keys_match_settings_and_table(tmp_brain):
    """Every grid toggle maps to a real bool setting, and the no-TTY path falls
    back to the static table (returns False, never opens an app under pytest)."""
    from book_agent import shell
    from book_agent.config import Settings, load_settings
    s = Settings()
    for key, _label, _desc in shell._FEATURE_KEYS:
        assert isinstance(getattr(s, key), bool), f"{key} is not a bool setting"
    console = _record_console()
    # pytest has no interactive stdin -> _toggle_grid degrades to the table.
    assert shell._toggle_grid(console, load_settings()) is False
    assert "humanize" in console.file.getvalue()
