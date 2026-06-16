"""Tests for the compositor manner layers (plan §23): personas, emotions, and the
voice-layer precedence/conflict resolution. All deterministic - no LLM calls."""
from writingagent import brain, compositor, craft, emotions, personas
from writingagent.config import Settings, _clamp_settings


# ── Personas ──────────────────────────────────────────────────────────────────
def test_persona_registry_and_resolution():
    assert "wry-skeptic" in personas.names()
    assert personas.get("WRY_SKEPTIC").name == "wry-skeptic"     # normalized
    assert personas.get("nope") is None
    assert personas.get(None) is None


def test_persona_register_compatibility():
    # lyrical-maximalist fits fiction, not business
    assert personas.compatible("lyrical-maximalist", "literary-fiction")
    assert not personas.compatible("lyrical-maximalist", "business")
    # deadpan-technical fits technical, not fiction
    assert personas.compatible("deadpan-technical", "technical")
    assert not personas.compatible("deadpan-technical", "literary-fiction")


def test_persona_block_includes_signature_and_exemplar():
    blk = personas.block("hard-boiled-minimalist", "genre-fiction")
    assert blk and "PERSONA" in blk and "MANNER ONLY" in blk
    # the exemplar prose ships and is included
    assert len(blk) > 400
    # incompatible -> None
    assert personas.block("hard-boiled-minimalist", "academic") is None


def test_every_persona_ships_a_loadable_exemplar():
    for name in personas.names():
        p = personas.get(name)
        reg = p.registers[0] if p.registers else "nonfiction"
        assert personas.block(name, reg), f"persona {name} has no loadable exemplar"


def test_no_living_author_personas():
    # Sanity guard for the legal/quality boundary: only archetypes + public-domain manner.
    assert all(personas.get(n).kind in ("archetype", "author") for n in personas.names())
    banned = {"hemingway", "rowling", "king", "gaiman", "atwood"}
    assert not (banned & set(personas.names()))


# ── Emotions (anti-cliché, not a symptom dictionary) ────────────────────────────
def test_emotion_resolution_with_aliases():
    assert emotions.get("fear") is emotions.get("dread")          # alias
    assert emotions.get("a creeping sense of dread")["cue"]       # substring
    assert emotions.get("nope") is None
    assert emotions.cue("grief")


def test_emotion_avoid_phrases_feed_cliche_detector():
    assert "heart raced" in emotions.avoid_phrases("fear")
    assert "heart raced" in emotions.avoid_phrases()              # union default
    # the craft cliché metric now flags the emotion cliché
    rep = craft.report("Her heart raced and her palms grew sweaty as the door opened slowly.",
                       "genre-fiction")
    assert "clichés detected" in rep and "heart raced" in rep


# ── Compositor voice layer ──────────────────────────────────────────────────────
def test_compositor_uses_compatible_persona(tmp_brain):
    out = compositor.voice("u", "literary-fiction", "lyrical-maximalist")
    assert out and "PERSONA" in out


def test_compositor_drops_incompatible_persona_and_logs(tmp_brain):
    logs = []
    out = compositor.voice("u", "literary-fiction", "deadpan-technical", log=logs.append)
    assert "PERSONA" not in (out or "")               # persona dropped (register wins)
    assert out                                        # fell back to the register gold
    assert any("does not fit" in m for m in logs)


def test_compositor_user_voice_precedence_over_gold(tmp_brain):
    d = brain.voice_dir("u")
    d.mkdir(parents=True)
    (d / "v.md").write_text("My own distinct authorial register here.", encoding="utf-8")
    out = compositor.voice("u", "nonfiction", None)
    assert "distinct authorial register" in out


def test_compositor_appends_emotion_cue(tmp_brain):
    out = compositor.voice("u", "nonfiction", None, "fear")
    assert "EMOTIONAL TARGET" in out


def test_compositor_returns_none_when_nothing_resolves(tmp_brain, monkeypatch):
    # No persona, no user voice, a register with no gold, no emotion -> None.
    monkeypatch.setattr("writingagent.registers.gold_exemplars", lambda *a, **k: None)
    assert compositor.voice("u", "nonfiction", None, None) is None


# ── Config wiring ─────────────────────────────────────────────────────────────
def test_settings_clamp_validates_persona_and_emotion():
    s = _clamp_settings(Settings(persona="WRY_SKEPTIC", emotion="dread"))
    assert s.persona == "wry-skeptic" and s.emotion == "dread"
    bad = _clamp_settings(Settings(persona="nope", emotion="nope"))
    assert bad.persona == "" and bad.emotion == ""
