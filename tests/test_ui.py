"""Tests for the shared UI helpers and the run dashboard's log parsing."""
from __future__ import annotations

from writingagent import ui


def test_did_you_mean():
    assert ui.did_you_mean("statuss", ["status", "run", "export"]) == "status"
    assert ui.did_you_mean("xyzzy", ["status", "run"]) is None


def test_trust_chip_normalizes_verdict():
    # Invariant: a blocking issue NEVER reads as a bare 'approve' (the captured bug).
    blocked = ui.trust_chip("verdict=approve confidence=0.50 blocking=1 insight=5")
    assert "approved" not in blocked and "revising" in blocked and "1 blocking" in blocked
    assert "insight 5/5" in blocked and "●" in blocked   # 0.50 -> ●●●○○ (3 dots)
    clean = ui.trust_chip("verdict=approve confidence=0.9 blocking=0 insight=4")
    assert clean.startswith("✓ approved") and "blocking" not in clean
    assert ui.trust_chip("garbage") == "garbage"          # unparseable -> raw passthrough


def test_prose_reading_time_excludes_code_and_refs():
    from writingagent import polish
    md = ("Prose one two three four five.\n\n"
          "```python\n" + "x = 1\n" * 50 + "```\n\n"
          "More prose words here.\n\n"
          "## References\n\n1. **20** · 2024 · [a](u)\n2. **10** · 2023 · [b](v)\n")
    assert polish.prose_word_count(md) < len(md.split())   # code + refs dropped
    assert polish.prose_word_count(md) == len("Prose one two three four five. More prose words here.".split())
    assert polish.read_time_min(md) >= 1
    # ui.reading_time_min accepts text (prose) or an int (legacy)
    assert ui.reading_time_min(md) == polish.read_time_min(md)
    assert ui.reading_time_min(450) >= 1


def test_input_disambiguation_word_sets():
    """Bare slash-words must be catchable; ambiguous English words must NOT auto-route
    when followed by chat text (only as a single bare token)."""
    from writingagent import shell
    assert {"help", "features", "theme", "provider"} <= shell._SLASH_WORDS
    # ambiguous words are present (single-token routing) but excluded from STRONG (args case)
    for w in ("set", "use", "model", "mode", "path", "auto", "clear"):
        assert w in shell._SLASH_WORDS and w not in shell._STRONG_SLASH
    assert {"help", "features", "provider", "theme"} <= shell._STRONG_SLASH


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
    from writingagent.shell import _RunDashboard
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

    from writingagent.shell import _RunDashboard
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
    monkeypatch.delenv("WRITINGAGENT_FAKE", raising=False)
    from writingagent import shell
    from writingagent.config import load_config, load_settings
    console = _record_console()
    shell._welcome(console, load_config(), load_settings(), "u")
    assert len(console.file.getvalue().splitlines()) <= 14


def test_welcome_warns_on_fake_mode(tmp_brain, monkeypatch):
    """A leftover WRITINGAGENT_FAKE otherwise silently cans every model call."""
    monkeypatch.setenv("WRITINGAGENT_FAKE", "1")
    from writingagent import shell
    from writingagent.config import load_config, load_settings
    console = _record_console()
    shell._welcome(console, load_config(), load_settings(), "u")
    assert "FAKE MODE" in console.file.getvalue()


def test_features_and_commands_tables_render(tmp_brain):
    """/features and /help content moved out of the welcome - they must still render."""
    from writingagent import shell
    from writingagent.config import load_settings
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
    from writingagent import shell
    from writingagent.config import load_settings
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


def test_slash_help_topic_filters(tmp_brain):
    from writingagent import shell
    from writingagent.config import load_settings
    console = _record_console()
    shell._slash_help(console, load_settings(), ["export"])
    out = console.file.getvalue()
    assert "HELP" in out and "export" in out and "epub" in out
    console = _record_console()
    shell._slash_help(console, load_settings(), ["zzznope"])
    assert "no help entry" in console.file.getvalue()


def test_stack_label_reflects_provider_and_model(tmp_brain):
    from writingagent import shell
    from writingagent.config import Settings, load_config
    cfg = load_config()
    label = shell._stack_label(cfg, Settings(provider="openrouter"))
    assert "OpenRouter" in label and "deepseek-v4-pro" in label and "v" in label
    assert "DeepSeek" in shell._stack_label(cfg, Settings(provider="deepseek"))


def test_key_warning_surfaces_missing_key(tmp_brain, monkeypatch):
    from writingagent import shell
    from writingagent.config import Settings
    monkeypatch.delenv("WRITINGAGENT_FAKE", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    assert shell._provider_needs_key(Settings(provider="deepseek")) is True
    assert "DEEPSEEK_API_KEY" in shell._key_warning(Settings(provider="deepseek"))
    # local providers never need a key; fake mode suppresses the warning entirely
    assert shell._provider_needs_key(Settings(provider="ollama")) is False
    monkeypatch.setenv("WRITINGAGENT_FAKE", "1")
    assert shell._provider_needs_key(Settings(provider="deepseek")) is False


def test_export_failed_messages(capsys):
    from writingagent.cli import _export_failed
    _export_failed(None, "pdf", PermissionError("file in use"))
    out = capsys.readouterr().out
    assert "pdf" in out and ("locked" in out or "close" in out)
    _export_failed(None, "epub", ModuleNotFoundError("No module named 'ebooklib'"))
    assert "pip install ebooklib" in capsys.readouterr().out


def test_reduced_motion_label(monkeypatch):
    from writingagent.shell import _RunDashboard
    monkeypatch.setenv("WRITINGAGENT_REDUCED_MOTION", "1")
    d = _RunDashboard("b", total=1, done=0)
    d.stage = "critiquing…"
    label = d._stage_label()
    assert "critiquing" in label and "⠋" not in label and "⠹" not in label   # no spinner


def test_paused_card_renders(tmp_brain):
    from writingagent import shell
    console = _record_console()
    shell._paused_card(console, "mybook")          # no budget set -> generic paused card
    assert "paused" in console.file.getvalue().lower()


def test_narrow_banner_drops_figlet():
    import io

    from rich.console import Console

    from writingagent import shell
    from writingagent.config import Settings, load_config
    console = Console(file=io.StringIO(), force_terminal=True, width=40)
    shell._banner(console, load_config(), Settings())
    out = console.file.getvalue()
    assert "WRITING AGENT" in out                   # one-line wordmark, not the figlet block


def test_run_controls_flags():
    from writingagent.shell import _RunControls
    c = _RunControls()
    assert c.pause is False and c.take_manual() is False
    c.request_pause()
    assert c.pause is True
    c.request_manual()
    assert c.take_manual() is True and c.take_manual() is False   # one-shot


def test_key_listener_no_ops_without_tty():
    """Under pytest stdin isn't a TTY, so the listener must stay inactive (no thread) -
    this is what keeps the run behaving identically in tests / pipes / a11y."""
    from writingagent.shell import _KeyListener
    sink = []
    with _KeyListener(sink.append, enabled=False) as kl:
        assert kl.active is False
    with _KeyListener(sink.append, enabled=True) as kl:
        assert kl.active is False          # enabled, but no TTY -> still inactive


def test_apply_run_control_pause_and_manual(tmp_path):
    from types import SimpleNamespace

    from writingagent import orchestrator
    paths = SimpleNamespace(run_state=tmp_path / "rs.json")
    logs: list[str] = []
    assert orchestrator._apply_run_control(None, {}, paths, logs.append) is False

    class _Pause:
        pause = True
        def take_manual(self):
            return False
    assert orchestrator._apply_run_control(_Pause(), {"autonomous": True}, paths, logs.append) is True

    class _Manual:
        pause = False
        def take_manual(self):
            return True
    st = {"autonomous": True}
    assert orchestrator._apply_run_control(_Manual(), st, paths, logs.append) is False
    assert st["autonomous"] is False                      # flipped to manual
    assert "escalate_below_confidence" in st              # thresholds restored


def test_feature_keys_match_settings_and_table(tmp_brain):
    """Every grid toggle maps to a real bool setting, and the no-TTY path falls
    back to the static table (returns False, never opens an app under pytest)."""
    from writingagent import shell
    from writingagent.config import Settings, load_settings
    s = Settings()
    for key, _label, _desc in shell._FEATURE_KEYS:
        assert isinstance(getattr(s, key), bool), f"{key} is not a bool setting"
    console = _record_console()
    # pytest has no interactive stdin -> _toggle_grid degrades to the table.
    assert shell._toggle_grid(console, load_settings()) is False
    assert "humanize" in console.file.getvalue()


# ── First-run key wizard + /setkey (onboarding friction fixes) ───────────────────
class _FakeConsole:
    """A console that records prints and replays scripted answers to input()."""
    def __init__(self, answers):
        self._answers = list(answers)
        self.out = []

    def print(self, *a, **_k):
        self.out.append(" ".join(str(x) for x in a))

    def input(self, prompt=""):
        self.print(prompt)
        if self._answers:
            return self._answers.pop(0)
        raise EOFError


def test_write_env_key_creates_then_updates_in_place(tmp_path, monkeypatch):
    import os

    from writingagent import brain, shell
    monkeypatch.setattr(brain, "_ROOT", tmp_path)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    shell._write_env_key("OPENROUTER_API_KEY", "sk-aaa")
    assert os.environ["OPENROUTER_API_KEY"] == "sk-aaa"          # applied live, no restart
    assert (tmp_path / ".env").read_text(encoding="utf-8").strip() == "OPENROUTER_API_KEY=sk-aaa"
    shell._write_env_key("OPENROUTER_API_KEY", "sk-bbb")
    txt = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "sk-bbb" in txt and "sk-aaa" not in txt              # updated, not appended
    assert txt.count("OPENROUTER_API_KEY=") == 1


def test_write_env_key_readonly_location_sets_live_without_crashing(tmp_path, monkeypatch):
    """On a pip/npm-installed copy brain._ROOT is read-only. The key must still apply to
    THIS session (the live os.environ set comes first) and the write must degrade to None,
    never raise - a crash here would hit the first-run wizard at startup."""
    import os

    from writingagent import brain, shell
    monkeypatch.setattr(brain, "_ROOT", tmp_path)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    def _boom(*_a, **_k):
        raise PermissionError("read-only")
    monkeypatch.setattr(type(tmp_path / ".env"), "write_text", _boom)
    result = shell._write_env_key("OPENROUTER_API_KEY", "sk-live")
    assert result is None                                   # persistence failed, gracefully
    assert os.environ["OPENROUTER_API_KEY"] == "sk-live"    # but the session works


def test_first_run_setup_enter_picks_free_preview(monkeypatch):
    import sys
    import types

    from writingagent import shell
    from writingagent.config import Settings
    monkeypatch.delenv("WRITINGAGENT_FAKE", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(sys, "stdin", types.SimpleNamespace(isatty=lambda: True))
    console = _FakeConsole([""])                                # just press Enter
    shell._first_run_setup(console, Settings(provider="deepseek"))
    import os
    assert os.environ.get("WRITINGAGENT_FAKE") == "1"          # free preview on, no restart
    assert any("free preview" in o for o in console.out)


def test_first_run_setup_paste_key(tmp_path, monkeypatch):
    import sys
    import types

    from writingagent import brain, shell
    from writingagent.config import Settings
    monkeypatch.setattr(brain, "_ROOT", tmp_path)
    monkeypatch.delenv("WRITINGAGENT_FAKE", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(sys, "stdin", types.SimpleNamespace(isatty=lambda: True))
    console = _FakeConsole(["1", "sk-zzz"])                     # paste a key
    shell._first_run_setup(console, Settings(provider="deepseek"))
    import os
    assert os.environ["DEEPSEEK_API_KEY"] == "sk-zzz"
    assert (tmp_path / ".env").read_text(encoding="utf-8").strip().endswith("sk-zzz")


def test_first_run_setup_noop_when_key_present(monkeypatch):
    import sys
    import types

    from writingagent import shell
    from writingagent.config import Settings
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-present")
    monkeypatch.setattr(sys, "stdin", types.SimpleNamespace(isatty=lambda: True))
    console = _FakeConsole(["1", "x"])
    shell._first_run_setup(console, Settings(provider="deepseek"))
    assert console.out == []                                    # nothing shown - key already set


def test_cmd_setkey_saves_key_and_clears_fake(tmp_path, monkeypatch):
    import os

    from writingagent import brain
    from writingagent.config import Settings
    from writingagent.shell.commands import _cmd_setkey
    monkeypatch.setattr(brain, "_ROOT", tmp_path)
    monkeypatch.setenv("WRITINGAGENT_FAKE", "1")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    _cmd_setkey(_FakeConsole([]), Settings(provider="deepseek"), ["sk-direct"])
    assert os.environ["DEEPSEEK_API_KEY"] == "sk-direct"
    assert "WRITINGAGENT_FAKE" not in os.environ                # a real key turns real runs on
    assert (tmp_path / ".env").read_text(encoding="utf-8").strip().endswith("sk-direct")
