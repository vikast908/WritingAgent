"""Tests for the quality machinery: thesis, voice exemplars, surgical humanizer,
divergent drafting, insight gate, and /praise."""
import pytest

from book_agent import brain, humanizer, nodes, orchestrator
from book_agent import schemas as S
from book_agent.brain import ArticlePaths
from book_agent.config import load_config, load_settings


@pytest.fixture
def fake_llm(monkeypatch):
    monkeypatch.setenv("BOOK_AGENT_FAKE", "1")


def _angle():
    return S.ArticleAngle(title="A", angle="technical deep-dive",
                          audience="engineers", hook="h")


def _silent(*_a, **_k):
    pass


# ── Thesis ────────────────────────────────────────────────────────────────────
def test_start_article_writes_thesis(tmp_brain, fake_llm):
    cfg, settings = load_config(), load_settings()
    aid = orchestrator.start_article(cfg, settings, "u", "topic", _angle(),
                                     "thesart", 1, 1, autonomous=True)
    paths = ArticlePaths(aid, "u")
    assert brain.read_json(paths.root / "thesis.json")
    md = brain.read_text(paths.root / "thesis.md")
    assert md and "**Claim:**" in md


def test_thesis_reaches_writer_and_critic(tmp_brain, fake_llm, monkeypatch):
    seen = {}

    def write_spy(cfg, outline, section, fix_notes=None, *, thesis=None, voice=None, **_kw):
        seen["writer_thesis"] = thesis
        return "## Section\n\nBody."

    def crit_spy(cfg, outline, section, prose, *, thesis=None, research_on=True, **_kw):
        seen["critic_thesis"] = thesis
        seen["research_on"] = research_on
        return S.Critique(verdict="approve", confidence=0.9, blocking=[], nits=[], insight=5)

    monkeypatch.setattr(nodes, "write_article_section", write_spy)
    monkeypatch.setattr(nodes, "critique_article_section", crit_spy)
    cfg, settings = load_config(), load_settings()
    settings.divergent_drafts = 1
    aid = orchestrator.start_article(cfg, settings, "u", "topic", _angle(),
                                     "thes2", 1, 1, autonomous=True)
    orchestrator.run(cfg, "u", aid, log=_silent)
    assert seen["writer_thesis"] and "**Claim:**" in seen["writer_thesis"]
    assert seen["critic_thesis"]


# ── Voice exemplars ───────────────────────────────────────────────────────────
def test_voice_exemplars_budget_and_filtering(tmp_brain):
    d = brain.voice_dir("u")
    d.mkdir(parents=True)
    (d / "a.md").write_text("# Heading skipped\n\nFirst paragraph.\n\n```\ncode skipped\n```\n\n"
                            "Second paragraph.", encoding="utf-8")
    out = brain.voice_exemplars("u")
    assert "First paragraph." in out and "Second paragraph." in out
    assert "Heading skipped" not in out and "code skipped" not in out
    # budget respected
    tiny = brain.voice_exemplars("u", max_chars=18)
    assert tiny == "First paragraph."


def test_voice_exemplars_none_when_empty(tmp_brain):
    assert brain.voice_exemplars("u") is None


def test_voice_reaches_writer(tmp_brain, fake_llm, monkeypatch):
    d = brain.voice_dir("u")
    d.mkdir(parents=True)
    (d / "v.md").write_text("Exemplar paragraph with a distinct register.", encoding="utf-8")
    seen = {}

    def write_spy(cfg, outline, section, fix_notes=None, *, voice=None, **_kw):
        seen["voice"] = voice
        return "## Section\n\nBody."
    monkeypatch.setattr(nodes, "write_article_section", write_spy)
    cfg, settings = load_config(), load_settings()
    settings.divergent_drafts = 1
    aid = orchestrator.start_article(cfg, settings, "u", "topic", _angle(),
                                     "voicea", 1, 1, autonomous=True)
    orchestrator.run(cfg, "u", aid, log=_silent)
    assert "distinct register" in (seen["voice"] or "")


# ── Surgical humanizer ────────────────────────────────────────────────────────
def test_find_tell_sentences_flags_and_skips_code():
    text = ("Plain sentence. We will delve into the details.\n\n"
            "```python\n# delve inside code is fine\n```\n\n"
            "This is a robust solution. Clean closer here.")
    flagged = humanizer.find_tell_sentences(text)
    sents = [s for _, _, s in flagged]
    assert any("delve" in s for s in sents)
    assert any("robust" in s for s in sents)
    assert not any("code" in s for s in sents)
    assert not any("Plain sentence" in s for s in sents)


def test_rewrite_ok_guards():
    old = "The system leverages caching to hit 100ms targets [2]."
    assert humanizer._rewrite_ok(old, "The system uses caching to hit 100ms targets [2].")
    # dropped citation
    assert not humanizer._rewrite_ok(old, "The system uses caching to hit 100ms targets.")
    # drifted number
    assert not humanizer._rewrite_ok(old, "The system uses caching to hit 200ms targets [2].")
    # tell still present
    assert not humanizer._rewrite_ok(old, "The system leverages caching for 100ms targets [2].")
    # absurd length
    assert not humanizer._rewrite_ok(old, "Uses caching " * 40 + "100 ms [2].")


def test_humanize_splices_only_guarded_rewrites(monkeypatch):
    monkeypatch.delenv("BOOK_AGENT_FAKE", raising=False)
    text = ("Keep this sentence. We delve into caching here.\n\n"
            "It is a robust design with 99 nodes.")

    def fake_structured(model, system, user, schema, **kw):
        return S.LineEdits(edits=[
            S.LineEdit(index=1, text="We explore caching here."),
            # index 2 drops the number 99 -> guard must reject it
            S.LineEdit(index=2, text="It is a sturdy design with many nodes."),
        ])
    monkeypatch.setattr(humanizer, "complete_structured", fake_structured)
    out = humanizer.humanize(load_config(), text)
    assert "We explore caching here." in out
    assert "Keep this sentence." in out
    assert "99 nodes" in out          # bad rewrite rejected, original kept


def test_humanize_fake_mode_is_mechanical_only(fake_llm):
    text = "We delve into things — deeply."
    out = humanizer.humanize(load_config(), text)
    assert "—" not in out             # mechanical pass ran
    assert "delve" in out             # no LLM rewrite in fake mode


def test_structural_report_metrics():
    text = ("One two three four five.\n\n" * 5) + "Alpha, beta, and gamma walked in."
    rep = humanizer.structural_report(text)
    assert "paragraph lengths" in rep
    assert "rule-of-three" in rep
    assert "specificity density" in rep


# ── Divergent drafting + insight gate ─────────────────────────────────────────
def test_divergent_drafts_writes_n_variants(tmp_brain, fake_llm, monkeypatch):
    calls = []

    def write_spy(cfg, outline, section, fix_notes=None, *, temperature=None, **_kw):
        calls.append(temperature)
        return f"## Section\n\nBody at {temperature}."
    monkeypatch.setattr(nodes, "write_article_section", write_spy)
    cfg, settings = load_config(), load_settings()
    settings.divergent_drafts = 2
    aid = orchestrator.start_article(cfg, settings, "u", "topic", _angle(),
                                     "divart", 1, 1, autonomous=True)
    orchestrator.run(cfg, "u", aid, log=_silent)
    # first attempt = 2 variants at distinct temps (fake critic approves -> no revisions)
    assert len([t for t in calls if t is not None]) == 2
    assert len(set(t for t in calls if t is not None)) == 2


def test_low_insight_triggers_sharpening_revision(tmp_brain, fake_llm, monkeypatch):
    monkeypatch.setenv("BOOK_AGENT_FAKE_INSIGHT", "2")   # below the min_insight=3 bar
    writes = []

    real_write = nodes.write_article_section

    def write_spy(*a, **kw):
        writes.append(kw.get("fix_notes"))
        return real_write(*a, **kw)
    monkeypatch.setattr(nodes, "write_article_section", write_spy)
    cfg, settings = load_config(), load_settings()
    settings.divergent_drafts = 1
    settings.min_insight = 3
    aid = orchestrator.start_article(cfg, settings, "u", "topic", _angle(),
                                     "insart", 1, 1, autonomous=True)
    state = orchestrator.run(cfg, "u", aid, log=_silent)
    assert state["phase"] == "done"   # autonomous still completes (commits best)
    # at least one revision carried the sharpening note
    assert any(n and "generic" in n for n in writes if n)


def test_crit_better_prefers_higher_insight():
    a = S.Critique(verdict="approve", confidence=0.8, blocking=[], nits=[], insight=5)
    b = S.Critique(verdict="approve", confidence=0.9, blocking=[], nits=[], insight=3)
    assert orchestrator._crit_better(a, b)       # insight beats confidence
    assert not orchestrator._crit_better(b, a)


# ── /praise ───────────────────────────────────────────────────────────────────
def test_praise_saves_section_to_voice_dir(tmp_brain, fake_llm):
    from book_agent.shell import _cmd_praise
    cfg, settings = load_config(), load_settings()
    aid = orchestrator.start_article(cfg, settings, "u", "topic", _angle(),
                                     "praiseart", 1, 1, autonomous=True)
    orchestrator.run(cfg, "u", aid, log=_silent)
    state = {"uid": "u", "book": aid}
    _cmd_praise(None, state, [])                  # no arg -> latest committed
    files = list(brain.voice_dir("u").glob("praised-*.md"))
    assert len(files) == 1
    assert orchestrator._praised_passages("u")    # learner sees it
