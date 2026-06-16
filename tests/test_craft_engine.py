"""Tests for the register/genre craft engine (plan §22): register profiles, register-aware
anti-slop, genre-aware craft metrics, few-shot exemplars, surgical passes, field templates,
citation styles, and the voice-drift detector. All deterministic - no LLM calls."""
import re

from writingagent import (
    brain,
    craft,
    exemplars,
    fields,
    humanizer,
    polish,
    prompts,
    registers,
    slop,
    surgery,
)
from writingagent.config import Settings, _clamp_settings


# ── Registers + register-aware anti-slop ──────────────────────────────────────
def test_default_render_constraints_byte_identical():
    # The historical default and the explicit `nonfiction` profile must agree, and neither
    # may have changed (the single-source round-trip test guards the rest).
    assert slop.render_constraints() == slop.render_constraints("nonfiction")
    assert slop.tell_pattern() == slop.tell_pattern("nonfiction")
    assert "NO EM-DASHES" in slop.render_constraints()
    assert "RESEARCHER VOICE" in slop.render_constraints()


def test_fiction_register_relaxes_em_dash_and_terms():
    c = slop.render_constraints("literary-fiction")
    assert "NO EM-DASHES" not in c                 # em-dash is voice in fiction
    assert "NARRATIVE VOICE" in c
    tre = re.compile(slop.tell_pattern("literary-fiction"), re.I)
    assert not tre.search("She stepped into the digital realm.")   # 'realm' allowed
    assert tre.search("We delve into it.")                         # 'delve' still banned everywhere


def test_academic_keeps_connectives_and_requires_hedging():
    c = slop.render_constraints("academic")
    assert "KEEP HEDGING" in c
    tre = re.compile(slop.tell_pattern("academic"), re.I)
    assert not tre.search("Moreover, the results held.")           # connective allowed
    assert "moreover" not in c.lower() or "BANNED TRANSITIONS" not in c.split("moreover")[0][-40:]


def test_copywriting_allows_enthusiasm_and_intensifiers():
    c = slop.render_constraints("copywriting")
    assert "SYNTHETIC ENTHUSIASM" not in c
    assert "BANNED INTENSIFIERS" not in c          # intensifiers permitted -> line dropped


def test_register_inference_from_genre():
    assert registers.infer("epic fantasy novel", "book") == "genre-fiction"
    assert registers.infer("a quiet literary novel", "book") == "literary-fiction"
    assert registers.infer("API documentation", "article") == "technical"
    assert registers.infer("peer-reviewed journal paper", "article") == "academic"
    assert registers.infer("breaking news report", "article") == "journalism"
    assert registers.infer("", "article") == "nonfiction"          # default


def test_register_get_is_total_and_safe():
    assert registers.get(None).name == "nonfiction"
    assert registers.get("does-not-exist").name == "nonfiction"
    assert registers.get("LITERARY_FICTION").name == "literary-fiction"   # normalized


def test_every_register_renders_without_error():
    for name in registers.names():
        assert slop.render_constraints(name)
        assert re.compile(slop.tell_pattern(name), re.I) is not None


# ── Gold corpus ───────────────────────────────────────────────────────────────
def test_gold_exemplars_ship_for_every_register_with_gold():
    for name in registers.names():
        if registers.get(name).gold:
            assert registers.gold_exemplars(name), f"missing/empty gold for {name}"


def test_gold_exemplars_loads_and_skips_headings():
    out = registers.gold_exemplars("nonfiction")
    assert out and not out.startswith("#")
    assert "Gold exemplar" not in out                 # the heading line is skipped
    assert len(out) <= 1200                            # default budget respected


def test_style_exemplars_falls_back_to_gold(tmp_brain):
    # No user voice dir -> the register's gold corpus is the default anchor.
    assert brain.voice_exemplars("u") is None
    assert brain.style_exemplars("u", "literary-fiction")


# ── Genre-aware craft metrics ─────────────────────────────────────────────────
def test_structural_report_default_keeps_historical_metrics():
    text = ("One two three four five.\n\n" * 5) + "Alpha, beta, and gamma walked in."
    rep = humanizer.structural_report(text)
    assert "paragraph lengths" in rep
    assert "rule-of-three" in rep
    assert "specificity density" in rep


def test_fiction_metrics_swap_in_dialogue_and_filters():
    prose = ('"Run," she said. He felt afraid and saw the door.\n\n'
             "The cold rain hit the metal roof. She felt nothing.")
    rep = craft.report(prose, "literary-fiction")
    assert "filter-verb density" in rep
    assert "dialogue" in rep
    assert "specificity density" not in rep        # nonfiction-only metric not applied


def test_opening_and_closing_flags():
    text = ("In this chapter we explore widgets. Widgets are common. They work well. "
            "In conclusion, widgets matter.")
    rep = craft.report(text, "nonfiction")
    assert "opening/closing" in rep


def test_reading_grade_and_cliche_metrics():
    text = ("At the end of the day, the cat sat on the mat. The dog ran in the yard. "
            "A bird flew over the tall green tree by the old stone wall near the lake.")
    rep = craft.report(text, "nonfiction")
    assert "reading level" in rep
    assert "clichés detected" in rep              # "at the end of the day"


# ── Few-shot exemplars ────────────────────────────────────────────────────────
def test_humanizer_fewshot_and_critic_anchors_present():
    assert "BEFORE:" in exemplars.humanizer_fewshot()
    anchors = exemplars.critic_anchors()
    assert "SCORE ANCHORS" in anchors
    for dim in ("insight", "clarity", "structure", "evidence"):
        assert dim in anchors


# ── Prompt builders ───────────────────────────────────────────────────────────
def test_prompt_builders_default_unchanged_and_register_aware():
    assert prompts.writer_sys() == prompts.WRITER_SYS
    assert prompts.article_writer_sys() == prompts.ARTICLE_WRITER_SYS
    fic = prompts.writer_sys("literary-fiction")
    assert fic != prompts.WRITER_SYS and "NARRATIVE VOICE" in fic
    crit = prompts.critic_sys("literary-fiction")
    assert "SCORE ANCHORS" in crit and "em-dashes are voice" in crit


# ── Surgical passes ───────────────────────────────────────────────────────────
def test_telling_detector_flags_filter_and_told_emotion():
    flagged = surgery._find(
        "She felt a chill. The cake was baked. He was afraid of the dark.", surgery._TELLING_RE)
    sents = [s for *_, s in flagged]
    assert any("felt a chill" in s for s in sents)
    assert any("afraid" in s for s in sents)
    assert not any("cake" in s for s in sents)     # 'baked' is not a tell


def test_surgery_guard_rejects_drift_and_requires_progress():
    old = "She felt afraid as she saw the 3 guards [1]."
    # good: fewer tells, citation + number preserved
    assert surgery._guard(old, "Her hands shook as the 3 guards stepped in [1].", surgery._TELLING_RE)
    # drops citation
    assert not surgery._guard(old, "Her hands shook as the 3 guards stepped in.", surgery._TELLING_RE)
    # drifts the number
    assert not surgery._guard(old, "Her hands shook as the 4 guards stepped in [1].", surgery._TELLING_RE)
    # no progress (still has a filter verb + told emotion, same count)
    assert not surgery._guard(old, "She felt afraid as she saw the 3 guards arrive [1].",
                              surgery._TELLING_RE)


def test_surgery_apply_noop_in_fake_mode(monkeypatch):
    monkeypatch.setenv("WRITINGAGENT_FAKE", "1")
    text = "She felt afraid. He saw the door."
    assert surgery.apply(None, text, "literary-fiction") == text


# ── Field templates ───────────────────────────────────────────────────────────
def test_field_resolve_maps_register_to_structure():
    assert "inverted pyramid" in fields.resolve("journalism").lower()
    assert "imrad" in fields.resolve("academic").lower()
    assert "bluf" in fields.resolve("business").lower()
    assert fields.resolve("nonfiction", "imrad").lower().count("imrad")    # explicit field wins
    assert fields.resolve("poetry") == ""          # no default structure


# ── Citation styles ───────────────────────────────────────────────────────────
def _scored():
    sources = [{"title": "NIST Guide", "url": "https://nist.gov/x", "date": "2023"},
               {"title": "Blog Post", "url": "https://example.com/y", "date": ""}]
    return polish.score_sources(sources, "A cited claim [1] and another [1].", "guide claim")


def test_citation_styles_render_and_none_is_empty():
    scored = _scored()
    assert "Ranked by influence" in polish.build_references(scored, style="influence")
    assert "APA-style" in polish.build_references(scored, drop_noise=False, style="apa")
    assert "MLA-style" in polish.build_references(scored, drop_noise=False, style="mla")
    num = polish.build_references(scored, drop_noise=False, style="numeric")
    assert num.startswith("## References\n") and "**" not in num   # no influence score column
    assert polish.build_references(scored, style="none") == ""


# ── Voice drift ───────────────────────────────────────────────────────────────
def test_voice_drift_flags_outlier_chapter():
    norm = "the cat sat on the mat and it was warm and she was there with them all day "
    chapters = [(f"ch{i}", norm * 20) for i in range(4)]
    chapters.append(("ch_alien", "zxqv blorp fnord wibble grok " * 40))
    drift = polish.voice_drift(chapters)
    assert drift and drift[0][0] == "ch_alien"


def test_voice_drift_clean_book_is_empty():
    norm = "the cat sat on the mat and it was warm and she was there with them all day "
    chapters = [(f"ch{i}", norm * 20) for i in range(5)]
    assert polish.voice_drift(chapters) == []


def test_cohesion_report_mentions_voice_drift():
    norm = "the cat sat on the mat and it was warm and she was there with them all day "
    chapters = [(f"ch{i}", norm * 20) for i in range(4)]
    chapters.append(("ch_alien", "zxqv blorp fnord wibble grok " * 40))
    rep = polish.cohesion_report(chapters)
    assert "Voice drift" in rep


# ── Config wiring ─────────────────────────────────────────────────────────────
def test_settings_clamp_validates_register_field_style():
    s = _clamp_settings(Settings(register="LITERARY_FICTION", field="imrad",
                                 citation_style="APA"))
    assert s.register == "literary-fiction" and s.field == "imrad" and s.citation_style == "apa"
    bad = _clamp_settings(Settings(register="nope", field="nope", citation_style="nope"))
    assert bad.register == "" and bad.field == "" and bad.citation_style == ""
