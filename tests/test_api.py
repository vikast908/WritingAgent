"""Offline tests for the stable public API (book_agent.api).

All runs use BOOK_AGENT_FAKE so no network/API key is needed; the autouse
`_isolated_brain` fixture (conftest) redirects storage to a temp dir. Articles
with a single section are used for the full create -> run -> export path because
they finish fast and deterministically offline (mirrors test_write_flow.py).
"""
import pytest

import book_agent
from book_agent import Agent, Approach, ProjectNotFound, Status, write


@pytest.fixture
def fake_llm(monkeypatch):
    monkeypatch.setenv("BOOK_AGENT_FAKE", "1")


@pytest.fixture
def agent(fake_llm):
    # 1-section articles, one revision: the smallest finished piece offline.
    return Agent(user="u", mode="article", num_sections=1, max_revisions=1, autonomous=True)


# ── package surface ───────────────────────────────────────────────────────────
def test_lazy_exports_and_version():
    assert isinstance(book_agent.__version__, str)
    # Lazy PEP 562 resolution works for the public names...
    assert book_agent.Agent is Agent
    assert callable(book_agent.write)
    assert "pdf" in book_agent.EXPORT_FORMATS
    # ...and unknown attributes still raise.
    with pytest.raises(AttributeError):
        _ = book_agent.NoSuchThing


# ── planning ──────────────────────────────────────────────────────────────────
def test_plan_returns_indexed_approaches(agent):
    approaches = agent.plan("how DNS works", mode="article")
    assert approaches and all(isinstance(a, Approach) for a in approaches)
    assert [a.index for a in approaches] == list(range(1, len(approaches) + 1))
    assert approaches[0].title and approaches[0].raw is not None


def test_bad_mode_rejected(agent):
    with pytest.raises(ValueError):
        agent.plan("x", mode="poem")


# ── create + run (full pipeline, offline) ─────────────────────────────────────
def test_create_run_status_and_read(agent):
    project = agent.create("how DNS resolution works", requirements="Audience: beginners.")
    assert project.mode == "article"
    status = project.run(progress=lambda _m: None)
    assert isinstance(status, Status)
    assert status.done and status.phase == "done"
    assert status.mode == "article" and status.total_units == 1
    # The manuscript is assembled and readable through the handle.
    assert project.manuscript_path.exists()
    assert project.word_count() > 0
    assert project.read(manuscript=True).strip()


def test_requirements_dict_persisted(agent):
    project = agent.create("topic", requirements={"length": "900 words", "tone": "wry"})
    intake = (project.root / "intake.md").read_text(encoding="utf-8")
    assert "length" in intake and "900 words" in intake


def test_create_with_explicit_approach_object(agent):
    approaches = agent.plan("caching strategies", mode="article")
    project = agent.create("caching strategies", approach=approaches[-1])
    # The chosen angle is persisted to the project's outline/angle on disk.
    assert project.status().mode == "article"


def test_create_with_int_approach_out_of_range(agent):
    from book_agent.api import BookAgentError
    with pytest.raises(BookAgentError):
        agent.create("x", approach=99)


# ── one-shot write ────────────────────────────────────────────────────────────
def test_write_one_shot_exports(fake_llm):
    # md export is dependency-free; force a 1-section article for speed.
    result = write("how TLS handshakes work", user="u", mode="article",
                   units=1, max_revisions=1, export="md")
    assert result.project_id and result.mode == "article"
    assert result.export_path is not None and result.export_path.exists()
    assert result.export_format == "md"
    assert result.word_count > 0
    assert result.status.done


def test_write_without_export_skips_file(fake_llm):
    result = write("how OAuth works", user="u", mode="article",
                   units=1, max_revisions=1, export=None)
    assert result.export_path is None
    assert result.manuscript_path.exists()


# ── open / projects / not-found ───────────────────────────────────────────────
def test_open_and_projects_roundtrip(agent):
    project = agent.create("a topic about queues")
    pid = project.id
    again = agent.open(pid)
    assert again.id == pid and again.mode == "article"
    assert pid in {p.id for p in agent.projects()}


def test_open_missing_raises(agent):
    with pytest.raises(ProjectNotFound):
        agent.open("does-not-exist")


# ── export validation ─────────────────────────────────────────────────────────
def test_export_unknown_format_rejected(agent):
    project = agent.create("topic for bad export")
    project.run(progress=lambda _m: None)
    from book_agent.api import BookAgentError
    with pytest.raises(BookAgentError):
        project.export("rtf")


# ── settings overrides are validated ──────────────────────────────────────────
def test_unknown_settings_override_rejected(fake_llm):
    with pytest.raises(TypeError):
        Agent(user="u", not_a_setting=True)


def test_delete_removes_project(agent):
    project = agent.create("ephemeral topic")
    pid = project.id
    assert pid in {p.id for p in agent.projects()}
    project.delete()
    assert pid not in {p.id for p in agent.projects()}
