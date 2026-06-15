"""Smoke tests for the zero-install web demo (web/app.py).

The demo imports gradio lazily (only inside build_ui), so its runtime helpers and the
streaming generate() run here without gradio installed - exactly how the package treats
its other optional extras."""
import importlib.util
from pathlib import Path

import pytest

_APP = Path(__file__).resolve().parent.parent / "web" / "app.py"


def _load_app():
    spec = importlib.util.spec_from_file_location("wa_web_app", _APP)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def app(monkeypatch):
    # Snapshot the env vars the demo mutates so a run can't leak into other tests.
    for var in ("WRITINGAGENT_FAKE", "WRITINGAGENT_PROVIDER", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    return _load_app()


def test_configure_runtime_free_preview_forces_fake(app, monkeypatch):
    assert app.configure_runtime(False, "OpenRouter", "") == ""
    import os
    assert os.environ.get("WRITINGAGENT_FAKE") == "1"


def test_configure_runtime_real_run_needs_key(app):
    with pytest.raises(ValueError):
        app.configure_runtime(True, "OpenRouter", "   ")


def test_configure_runtime_real_run_installs_key(app):
    import os
    pid = app.configure_runtime(True, "OpenRouter", "sk-test-123")
    assert pid == "openrouter"
    assert os.environ["OPENROUTER_API_KEY"] == "sk-test-123"
    assert os.environ["WRITINGAGENT_PROVIDER"] == "openrouter"
    assert "WRITINGAGENT_FAKE" not in os.environ


def test_generate_blank_topic_short_circuits(app):
    out = list(app.generate("", "article", 1, "OpenRouter", "", False))
    assert out and "topic" in out[-1][0].lower()


def test_generate_free_preview_runs_pipeline(app):
    # Full offline run (fake mode) of a 1-section article: streams progress, then yields a
    # non-empty manuscript and a downloadable .md path.
    final = None
    for item in app.generate("How vector databases work", "article", 1, "OpenRouter", "", False):
        final = item
    log, manuscript, evidence, download = final
    assert "Done" in log
    assert manuscript.strip()                      # the assembled (placeholder) piece
    assert isinstance(evidence, str) and evidence  # evidence tab has content/explanation
    assert download and str(download).endswith(".md")
