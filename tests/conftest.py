import pytest

from writingagent import brain, config, llm


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path, monkeypatch):
    """EVERY test runs against the shipped dataclass defaults, never the developer's
    personal config/settings.yaml (which is gitignored, so CI already runs on defaults -
    this makes a local run match CI). Pointing _SETTINGS at a non-existent tmp file makes
    load_settings() fall back to Settings(), so a local file with e.g. agentic=true can't
    change what the suite exercises; save_settings() in a test writes to the tmp file too."""
    monkeypatch.setattr(config, "_SETTINGS", tmp_path / "settings.yaml")


@pytest.fixture(autouse=True)
def _isolated_brain(tmp_path, monkeypatch):
    """EVERY test runs against a temp brain + index. Tests that skipped the old
    opt-in fixture but exercised the real LLM call path (e.g. the retry tests)
    were appending their toy telemetry records - model "m", "401 bad key" - to
    the developer's real .index/telemetry, polluting /dashboard."""
    monkeypatch.setattr(brain, "BRAIN", tmp_path / "brain")
    monkeypatch.setattr(brain, "INDEX_DIR", tmp_path / ".index")
    # Reset the process-global LLM fallback so a prior test that configured it (via an
    # Agent run) can't leak the fallback model into a test that asserts a hard failure.
    monkeypatch.setattr(llm, "_fallback_model", "", raising=False)
    return tmp_path


@pytest.fixture
def tmp_brain(_isolated_brain):
    """Kept as the explicit opt-in name used throughout the suite."""
    return _isolated_brain
