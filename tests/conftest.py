import pytest

from writingagent import brain


@pytest.fixture(autouse=True)
def _isolated_brain(tmp_path, monkeypatch):
    """EVERY test runs against a temp brain + index. Tests that skipped the old
    opt-in fixture but exercised the real LLM call path (e.g. the retry tests)
    were appending their toy telemetry records - model "m", "401 bad key" - to
    the developer's real .index/telemetry, polluting /dashboard."""
    monkeypatch.setattr(brain, "BRAIN", tmp_path / "brain")
    monkeypatch.setattr(brain, "INDEX_DIR", tmp_path / ".index")
    return tmp_path


@pytest.fixture
def tmp_brain(_isolated_brain):
    """Kept as the explicit opt-in name used throughout the suite."""
    return _isolated_brain
