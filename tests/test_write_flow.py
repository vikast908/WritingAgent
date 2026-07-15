"""Tests for the upfront-interview + autonomous `write` flow.

Covers: the interview node, the autonomous-flag fix (settings no longer shadowed),
intake/author persistence + threading into the writer, the interview helper, and the
end-to-end `write` command (interview -> autonomous run -> exported file), all offline.
"""
from types import SimpleNamespace

import pytest

from writingagent import brain, cli, nodes, orchestrator
from writingagent import schemas as S
from writingagent.brain import ArticlePaths
from writingagent.config import Settings, load_config, load_settings


@pytest.fixture
def fake_llm(monkeypatch):
    monkeypatch.setenv("WRITINGAGENT_FAKE", "1")


def _silent(*_a, **_k):
    pass


def _angle():
    return S.ArticleAngle(title="A", angle="deep-dive", audience="engineers", hook="h")


# ── interview node ────────────────────────────────────────────────────────────
def test_interview_node_returns_questions(fake_llm):
    cfg = load_config()
    out = nodes.interview(cfg, "how DNS works", mode="article")
    assert isinstance(out, S.Interview)
    assert out.questions and out.questions[0].question


# ── autonomous-flag fix ───────────────────────────────────────────────────────
def test_autonomous_value_honors_setting_when_flag_unset():
    auto = Settings(autonomous=True)
    manual = Settings(autonomous=False)
    # Flag unset (None) -> fall through to the setting (the old bug returned False here).
    assert cli._autonomous_value(SimpleNamespace(autonomous=None), auto) is True
    assert cli._autonomous_value(SimpleNamespace(autonomous=None), manual) is False
    # Explicit flag always wins over the setting.
    assert cli._autonomous_value(SimpleNamespace(autonomous=False), auto) is False
    assert cli._autonomous_value(SimpleNamespace(autonomous=True), manual) is True


# ── intake + author persistence ───────────────────────────────────────────────
def test_start_article_persists_intake_and_author(tmp_brain, fake_llm):
    cfg, settings = load_config(), load_settings()
    aid = orchestrator.start_article(
        cfg, settings, "u", "topic", _angle(), "intk", 1, 1,
        autonomous=True, intake="Keep it under 1200 words. Audience: beginners.",
        author="Jane Doe")
    paths = ArticlePaths(aid, "u")
    state = brain.read_json(paths.run_state)
    assert state["intake"].startswith("Keep it under 1200")
    assert state["author"] == "Jane Doe"
    assert "1200" in (brain.read_text(paths.root / "intake.md") or "")
    # Author recorded to the user profile so production can fill the byline.
    assert "Jane Doe" in (brain.read_text(brain.user_profile("u")) or "")


def test_article_byline_uses_recorded_author(tmp_brain, fake_llm):
    cfg, settings = load_config(), load_settings()
    aid = orchestrator.start_article(cfg, settings, "u", "topic", _angle(), "byl", 1, 1,
                                     autonomous=True, intake="x", author="Ada Lovelace")
    orchestrator.run(cfg, "u", aid, log=_silent)
    ms = brain.read_text(ArticlePaths(aid, "u").manuscript)
    assert "**By:** Ada Lovelace" in ms
    assert "[AUTHOR NAME]" not in ms


# ── intake threads into the writer prompt ─────────────────────────────────────
def test_intake_reaches_the_writer(tmp_brain, fake_llm, monkeypatch):
    captured = {}

    def spy(cfg, outline, section, fix_notes=None, *, requirements=None, **_kw):
        captured["requirements"] = requirements
        return "## Section\n\nBody text."
    monkeypatch.setattr(nodes, "write_article_section", spy)

    cfg, settings = load_config(), load_settings()
    aid = orchestrator.start_article(cfg, settings, "u", "topic", _angle(), "thread", 1, 1,
                                     autonomous=True, intake="MUST mention asyncio.")
    orchestrator.run(cfg, "u", aid, log=_silent)
    assert captured.get("requirements") and "asyncio" in captured["requirements"]


# ── interview helper ──────────────────────────────────────────────────────────
def test_conduct_interview_builds_intake_no_console(tmp_brain, fake_llm, monkeypatch):
    cfg, settings = load_config(), load_settings()
    # approach pick, then every question answered with Enter (take defaults).
    answers = iter(["", "", "", ""])
    monkeypatch.setattr("builtins.input", lambda *_a: next(answers, ""))
    chosen, intake_md, fmts, author = cli._conduct_interview(
        cfg, settings, "u", "how X works", "article", None)
    assert isinstance(chosen, S.ArticleAngle)
    assert fmts == ["docx"]                     # the article default (now a list; supports 'all')
    assert "# Author requirements" in intake_md


# ── end-to-end `write` ────────────────────────────────────────────────────────
def test_cmd_write_end_to_end_exports_file(tmp_brain, fake_llm, monkeypatch):
    cfg, settings = load_config(), load_settings()
    settings.mode = "article"
    monkeypatch.setattr(cli.interview, "_console", lambda: None)   # plain path, no Rich dashboard
    # approach pick, question(s), author, then format = md (dependency-free export)
    answers = iter(["", "", "", "md"])
    monkeypatch.setattr("builtins.input", lambda *_a: next(answers, ""))

    args = SimpleNamespace(abstract="how DNS resolution works", chapters=1,
                           max_revisions=1, book_id=None, no_humanize=False, user="u")
    cli.cmd_write(args, cfg, settings, "u")

    projects = brain.list_projects("u")
    assert projects, "write should have created a project"
    pid = projects[0][0]
    paths = ArticlePaths(pid, "u")
    assert paths.manuscript.exists()
    # The run was autonomous: it completed without pausing for review.
    assert (brain.read_json(paths.run_state) or {}).get("phase") == "done"
    # A finished file was exported.
    assert (paths.root / "manuscript_export.md").exists()
    # auto_promote (default on): the SEO audit + promo pack ran - LOCAL artifacts only.
    assert (paths.root / "seo_report.md").exists()
    assert (paths.root / "keywords.json").exists()
    assert (paths.root / "promo" / "x-thread.md").exists()
    assert (paths.root / "promo" / "linkedin.md").exists()


def test_cmd_write_skips_export_when_run_pauses(tmp_brain, fake_llm, monkeypatch):
    """A paused/escalated run must NOT fall through to export: shipping a partial
    manuscript under the paused card was the old behavior."""
    cfg, settings = load_config(), load_settings()
    settings.mode = "article"
    monkeypatch.setattr(cli.interview, "_console", lambda: None)
    answers = iter(["", "", "", "md"])
    monkeypatch.setattr("builtins.input", lambda *_a: next(answers, ""))
    monkeypatch.setattr(orchestrator, "status",
                        lambda uid, pid: {"phase": "sections", "pending_review": True})
    exported = []
    monkeypatch.setattr(cli.interview, "_run_exports",
                        lambda *a, **k: exported.append(a) or 0)

    args = SimpleNamespace(abstract="how DNS resolution works", chapters=1,
                           max_revisions=1, book_id=None, no_humanize=False, user="u")
    cli.cmd_write(args, cfg, settings, "u")
    assert not exported                      # paused -> no export attempt
