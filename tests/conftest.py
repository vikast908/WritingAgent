import pytest

from writingagent import brain, llm


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
