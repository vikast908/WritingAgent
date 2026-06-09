import pytest

from book_agent import brain


@pytest.fixture
def tmp_brain(tmp_path, monkeypatch):
    """Redirect the brain + derived index into a temp dir for isolation."""
    monkeypatch.setattr(brain, "BRAIN", tmp_path / "brain")
    monkeypatch.setattr(brain, "INDEX_DIR", tmp_path / ".index")
    return tmp_path
