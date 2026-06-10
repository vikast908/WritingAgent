"""Article-pipeline tests (fake-LLM mode, no network) + the cmd_read article fix.

The book pipeline is covered in test_pipeline.py; the article pipeline (added later)
had no dedicated tests. These exercise start_article -> run -> done, manuscript +
references assembly, source de-duplication, and project-type-aware path resolution.
"""
import pytest

from book_agent import brain, orchestrator
from book_agent import schemas as S
from book_agent.brain import ArticlePaths, BookPaths
from book_agent.config import load_config, load_settings


@pytest.fixture
def fake_llm(monkeypatch):
    monkeypatch.setenv("BOOK_AGENT_FAKE", "1")


def _angle():
    return S.ArticleAngle(title="A", angle="technical deep-dive",
                          audience="engineers", hook="h")


def _silent(*_a, **_k):
    pass


def test_article_end_to_end_completes(tmp_brain, fake_llm):
    cfg, settings = load_config(), load_settings()
    aid = orchestrator.start_article(cfg, settings, "u", "topic", _angle(),
                                     "myart", 1, 1, autonomous=True)
    state = orchestrator.run(cfg, "u", aid, log=_silent)

    assert state["phase"] == "done"
    assert state["mode"] == "article"
    paths = ArticlePaths(aid, "u")
    assert paths.manuscript.exists()
    ms = brain.read_text(paths.manuscript)
    assert ms and "# " in ms                       # has a title header
    # Intermediate section files are cleaned up after assembly.
    assert not list(paths.root.glob("section_*.md"))
    # Learner produced at least one skill for the user.
    assert list(brain.skills_dir("u").glob("*.md"))


def test_article_escalation_then_resume(tmp_brain, fake_llm, monkeypatch):
    cfg, settings = load_config(), load_settings()
    monkeypatch.setenv("BOOK_AGENT_FAKE_VERDICT", "revise")  # never approves -> cap -> escalate
    aid = orchestrator.start_article(cfg, settings, "u", "topic", _angle(),
                                     "esc", 1, 1)  # not autonomous
    state = orchestrator.run(cfg, "u", aid, log=_silent)
    assert state["pending_review"] is True
    paths = ArticlePaths(aid, "u")
    assert paths.review_of(1).exists()
    assert not paths.section(1).exists()            # not committed

    monkeypatch.setenv("BOOK_AGENT_FAKE_VERDICT", "approve")
    orchestrator.record_instruction("u", aid, 1, "tighten the intro")
    state2 = orchestrator.run(cfg, "u", aid, log=_silent)
    assert state2["phase"] == "done"
    assert paths.instruction_of(1).exists()


def test_article_references_dedup_by_url(tmp_brain, fake_llm):
    """_produce_article must de-duplicate sources by URL when building References."""
    cfg, settings = load_config(), load_settings()
    aid = orchestrator.start_article(cfg, settings, "u", "topic", _angle(),
                                     "refs", 1, 1, autonomous=True)
    paths = ArticlePaths(aid, "u")
    # Seed duplicate sources (same URL twice, one unique) before production runs.
    brain.write_json(paths.sources_json, [
        {"title": "One", "url": "https://x.org/a", "date": "2024"},
        {"title": "One again", "url": "https://x.org/a", "date": "2024"},
        {"title": "Two", "url": "https://y.org/b", "date": ""},
    ])
    # Re-run from the produce phase by forcing state; simplest is to drive production directly.
    outline = S.ArticleOutline(**brain.read_json(paths.outline_json))
    state = brain.read_json(paths.run_state)
    # Provide one committed section so production has content to assemble.
    brain.write_text(paths.section(1), "## Body\n\nSome text.")
    orchestrator._produce_article(cfg, paths, outline, state, log=_silent)

    ms = brain.read_text(paths.manuscript)
    assert ms.count("https://x.org/a") == 1         # duplicate URL collapsed
    assert "https://y.org/b" in ms


def test_article_learner_receives_critic_findings(tmp_brain, fake_llm, monkeypatch):
    """eval_*.json files must survive until the learn phase reads them (they used to
    be deleted by production's cleanup, silently starving the article learner)."""
    from book_agent import nodes
    seen = {}
    real_learn = nodes.learn

    def spy(cfg, plan, instructions, critic_findings, existing):
        seen["findings"] = critic_findings
        return real_learn(cfg, plan, instructions, critic_findings, existing)
    monkeypatch.setattr(nodes, "learn", spy)

    cfg, settings = load_config(), load_settings()
    aid = orchestrator.start_article(cfg, settings, "u", "topic", _angle(),
                                     "learnart", 1, 1, autonomous=True)
    state = orchestrator.run(cfg, "u", aid, log=_silent)
    assert state["phase"] == "done"
    # Fake critiques carry one blocking issue each -> findings must be non-empty.
    assert seen["findings"].strip()
    # Cleanup still happens - just after learn, not before.
    assert not list(ArticlePaths(aid, "u").root.glob("eval_*.json"))


def test_produce_guard_preserves_manuscript(tmp_brain, fake_llm):
    """Re-entering produce after cleanup (crash window) must not overwrite the
    assembled manuscript with an empty one."""
    cfg, settings = load_config(), load_settings()
    aid = orchestrator.start_article(cfg, settings, "u", "topic", _angle(),
                                     "guard", 1, 1, autonomous=True)
    paths = ArticlePaths(aid, "u")
    brain.write_text(paths.manuscript, "# Real manuscript\n\nfull body text")
    outline = S.ArticleOutline(**brain.read_json(paths.outline_json))
    state = brain.read_json(paths.run_state)
    # No section_*.md files on disk - the guard must keep the manuscript intact.
    orchestrator._produce_article(cfg, paths, outline, state, log=_silent)
    assert "full body text" in brain.read_text(paths.manuscript)


def test_register_sources_and_renumber_citations():
    registry = [{"title": "Existing", "url": "https://a.org/1"}]
    sources = [S.Source(title="New", url="https://b.org/2"),      # local [1] -> global 2
               S.Source(title="Existing", url="https://a.org/1"),  # local [2] -> global 1
               S.Source(title="No URL", url="")]                   # unmapped
    mapping = orchestrator._register_sources(registry, sources)
    assert mapping == {1: 2, 2: 1}
    assert [s["url"] for s in registry] == ["https://a.org/1", "https://b.org/2"]

    text = "Fact [1] and fact [2], unknown [9], a [link](https://x) and [3](y)."
    out = orchestrator._renumber_citations(text, mapping)
    assert "Fact [2] and fact [1]" in out                # swapped without collision
    assert "[9]" in out                                  # unmapped citation untouched
    assert "[link](https://x)" in out and "[3](y)" in out  # markdown links untouched


def test_commit_section_writes_real_summary_and_registry(tmp_brain, fake_llm):
    cfg, settings = load_config(), load_settings()
    aid = orchestrator.start_article(cfg, settings, "u", "topic", _angle(),
                                     "commitsec", 1, 1, autonomous=True)
    paths = ArticlePaths(aid, "u")
    outline = S.ArticleOutline(**brain.read_json(paths.outline_json))
    section = outline.sections[0]
    sources = [S.Source(title="Src", url="https://s.org/x")]
    orchestrator._commit_section(cfg, paths, section, 1, "## Heading\n\nBody [1].",
                                 [], sources, True, _silent, humanize=False)
    assert (brain.read_json(paths.sources_json) or [])[0]["url"] == "https://s.org/x"
    # A real (LLM) summary is written - not the draft's first 800 chars.
    assert brain.read_text(paths.section_summary(1)).strip()


# ── cmd_read article fix (Item 1) ───────────────────────────────────────────────
def test_paths_for_resolves_article_vs_book(tmp_brain, fake_llm):
    from book_agent import cli
    cfg, settings = load_config(), load_settings()
    aid = orchestrator.start_article(cfg, settings, "u", "topic", _angle(),
                                     "art1", 1, 1, autonomous=True)
    orchestrator.run(cfg, "u", aid, log=_silent)

    p = cli._paths_for("u", aid)
    assert isinstance(p, ArticlePaths)
    # The manuscript path lives under articles/, and exists after a run.
    assert "articles" in str(p.manuscript).replace("\\", "/")
    assert p.manuscript.exists()


def test_paths_for_defaults_to_book(tmp_brain):
    from book_agent import cli
    # No project on disk -> BookPaths (the historical default).
    p = cli._paths_for("u", "nonexistent")
    assert isinstance(p, BookPaths)
