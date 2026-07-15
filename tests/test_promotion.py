"""The promotion layer (plan §24): SEO signals pack + deterministic on-page audit,
platform repurposing, and the SEO/OG tags in the HTML export. Offline (fake mode)."""
import dataclasses

import pytest

from writingagent import brain, orchestrator, seo
from writingagent import schemas as S
from writingagent.brain import ArticlePaths
from writingagent.config import load_config, load_settings


@pytest.fixture
def fake_llm(monkeypatch):
    monkeypatch.setenv("WRITINGAGENT_FAKE", "1")


def _silent(*_a, **_k):
    pass


def _angle():
    return S.ArticleAngle(title="Ang", angle="a", audience="eng", hook="h")


def _pack(**over):
    base = dict(primary="voice latency", secondary=["voice ai", "streaming stt"],
                meta_description="How to get voice AI under 100ms: streaming STT, "
                                 "fast LLM inference, and overlapped TTS, with real numbers.",
                hashtags_x=["VoiceAI"], hashtags_linkedin=["VoiceAI", "LatencyEngineering"])
    base.update(over)
    return S.KeywordPack(**base)


_GOOD_MD = (
    "# Voice Latency: The 100ms Problem\n\n"
    + "Voice latency is the gap users feel. " * 4 + "\n\n"
    + "## Why voice latency matters\n\n" + ("Concrete words about budgets. " * 40) + "\n\n"
    + "## Streaming beats batching\n\n" + ("Short sentences carry facts. " * 40) + "\n\n"
    + "## References\n\n"
      "1. [A](https://a.example/x)\n2. [B](https://b.example/y)\n3. [C](https://c.example/z)\n"
)


# ── Rejected/dropped artifacts (figures) ─────────────────────────────────────────
def test_reconcile_embeds_missing_diagram_and_logs_rejects(tmp_brain):
    from writingagent.orchestrator import common
    paths = ArticlePaths("figs", "u")
    paths.ensure()
    draft = "## Section\n\nBody with no figure.\n"
    images = [
        "![A generated diagram](images/section_01_diagram.svg)\n\n*Figure 1.1*",
        "![A stock photo](images/wikimedia_cat.jpg)",
    ]
    out = common.reconcile_unit_images(paths, 1, "sec01", draft, images, lambda *a: None)
    # the generated diagram the writer omitted is embedded deterministically
    assert "section_01_diagram.svg" in out
    # the non-generated suggested image the writer skipped is recorded for review
    rej = common.read_rejected(paths)
    assert any(r["kind"] == "image" and "wikimedia_cat.jpg" in r["ref"] for r in rej)
    # an already-embedded image is left alone (no duplicate, no reject)
    draft2 = out
    out2 = common.reconcile_unit_images(paths, 1, "sec01", draft2, images, lambda *a: None)
    assert out2.count("section_01_diagram.svg") == 1


# ── Deterministic audit ─────────────────────────────────────────────────────────
def test_validate_passes_a_well_formed_piece():
    score, checks = seo.validate(_GOOD_MD, _pack())
    by = {c.name: c for c in checks}
    assert by["title"].status == "pass"
    assert by["keyword-in-title"].status == "pass"
    assert by["keyword-early"].status == "pass"
    assert by["keyword-in-headings"].status == "pass"
    assert by["outbound-links"].status == "pass"
    assert by["heading-hierarchy"].status == "pass"
    assert score >= 70


def test_validate_flags_missing_signals():
    md = "# Short\n\nA tiny piece with no links.\n\n#### Skipped level\n\nBody.\n"
    score, checks = seo.validate(md, _pack(primary="quantum basket weaving",
                                           meta_description=""))
    by = {c.name: c for c in checks}
    assert by["keyword-in-title"].status == "fail"       # primary nowhere in the title
    assert by["meta-description"].status == "warn"
    assert by["word-count"].status == "warn"
    assert by["outbound-links"].status == "warn"
    assert by["heading-hierarchy"].status == "warn"      # H1 -> H4 skip
    assert score < 70


def test_validate_never_raises_on_empty():
    score, checks = seo.validate("", _pack())
    assert isinstance(score, int) and checks


def test_fallback_pack_from_title():
    pack = seo._fallback_pack("How Stoicism Applies To Modern Burnout")
    assert pack.primary and "stoicism" in pack.primary
    assert pack.hashtags_x


def test_render_report_contains_score_checks_and_signals():
    score, checks = seo.validate(_GOOD_MD, _pack())
    out = seo.render_report("T", score, checks, _pack(), feel="FEEL-METRICS")
    assert f"## Score: {score}/100" in out
    assert "#VoiceAI" in out and "FEEL-METRICS" in out


# ── End-to-end (fake mode): seo + promote over a finished article ───────────────
def _finished_article(tmp_brain, fake_llm):
    cfg = load_config()
    settings = dataclasses.replace(load_settings(), divergent_drafts=1)
    aid = orchestrator.start_article(cfg, settings, "u", "abstract", _angle(),
                                     "promo1", 1, 1, autonomous=True)
    orchestrator.run(cfg, "u", aid, log=_silent)
    return cfg, aid


def test_optimize_manuscript_rewrites_title_to_carry_keyword(tmp_brain, fake_llm, monkeypatch):
    from writingagent import schemas as S
    from writingagent import seo
    pack = _pack(primary="vector database indexing")
    md = "# A Totally Unrelated Heading About Cats\n\nBody.\n"
    # fake-mode returns a schema instance with placeholder headlines (no keyword), so stub
    # the model to return a keyword-bearing candidate to exercise the splice deterministically
    monkeypatch.setattr(seo, "complete_structured",
                        lambda *a, **k: S.HeadlineVariants(headlines=[
                            "Vector Database Indexing: A Practical Guide"]))
    out, changes = seo.optimize_manuscript(load_config(), md, pack)
    assert changes and out.startswith("# Vector Database Indexing")
    # idempotent: a title already carrying the keyword and within length is left alone
    out2, changes2 = seo.optimize_manuscript(load_config(), out, pack)
    assert changes2 == []


def test_seo_keyword_threads_into_intake(tmp_brain, fake_llm):
    import dataclasses
    cfg = load_config()
    settings = dataclasses.replace(load_settings(), divergent_drafts=1, seo_keyword="voice ai latency")
    aid = orchestrator.start_article(cfg, settings, "u", "abstract", _angle(),
                                     "seokw", 1, 1, autonomous=True)
    intake = brain.read_text(ArticlePaths(aid, "u").root / "intake.md") or ""
    assert "voice ai latency" in intake and "SEO" in intake


def test_build_seo_report_writes_report_and_keywords(tmp_brain, fake_llm):
    cfg, aid = _finished_article(tmp_brain, fake_llm)
    out = orchestrator.build_seo_report(cfg, "u", aid, log=_silent)
    assert out.exists() and "## Score:" in brain.read_text(out)
    saved = brain.read_json(ArticlePaths(aid, "u").root / "keywords.json")
    assert saved and saved.get("primary")


def test_build_promo_pack_writes_formats_and_headlines(tmp_brain, fake_llm):
    cfg, aid = _finished_article(tmp_brain, fake_llm)
    promo = orchestrator.build_promo_pack(cfg, "u", aid, log=_silent)
    assert (promo / "x-thread.md").exists()
    assert (promo / "linkedin.md").exists()
    assert (promo / "newsletter-teaser.md").exists()
    assert (promo / "tldr.md").exists()
    assert (promo / "headlines.md").exists()


def test_build_promo_pack_respects_format_filter(tmp_brain, fake_llm):
    cfg, aid = _finished_article(tmp_brain, fake_llm)
    promo = orchestrator.build_promo_pack(cfg, "u", aid, formats=["linkedin"], log=_silent)
    assert (promo / "linkedin.md").exists()
    assert not (promo / "x-thread.md").exists()


def test_build_restyle_writes_variant_and_validates_inputs(tmp_brain, fake_llm, monkeypatch):
    from writingagent import promote
    cfg, aid = _finished_article(tmp_brain, fake_llm)
    # fake mode returns short placeholder text (guard would trip), so stub restyle to a
    # full-length re-voice to exercise the write path
    monkeypatch.setattr(promote, "restyle",
                        lambda *a, **k: "# Retitled\n\n" + ("Revoiced prose. " * 200))
    out = orchestrator.build_restyle(cfg, "u", aid, register="literary-fiction",
                                     persona="wry-skeptic", log=_silent)
    assert out and out.exists() and "literary-fiction-wry-skeptic" in out.name
    assert "Revoiced prose." in brain.read_text(out)
    # unknown values are ignored; with nothing valid left it refuses
    import pytest as _pt
    with _pt.raises(ValueError):
        orchestrator.build_restyle(cfg, "u", aid, register="bogus", persona="nope", log=_silent)


# ── HTML export meta tags ────────────────────────────────────────────────────────
def test_html_export_carries_seo_and_og_tags(tmp_brain, fake_llm):
    cfg, aid = _finished_article(tmp_brain, fake_llm)
    orchestrator.build_seo_report(cfg, "u", aid, log=_silent)     # writes keywords.json
    out = orchestrator.export_html("u", aid, log=_silent)
    html = out.read_text(encoding="utf-8")
    assert '<meta name="description"' in html
    assert '<meta property="og:title"' in html
    assert '<meta name="twitter:card"' in html


def test_html_export_unchanged_without_pack(tmp_brain, fake_llm):
    from writingagent.export import markdown_to_html
    out = markdown_to_html("# T\n\nBody.", tmp_brain / "x.html", title="T")
    html = out.read_text(encoding="utf-8")
    assert "og:title" not in html                     # no pack -> no extra tags
    assert "<title>T</title>" in html
