"""Settings range validation (C-007): a typo in settings.yaml must clamp to sane bounds,
not produce baffling runtime behavior (an unreachable insight gate, a broken loop range)."""
from writingagent.config import Settings, _clamp_settings


def test_clamp_brings_out_of_range_into_bounds():
    s = _clamp_settings(Settings(
        min_insight=99, max_revisions=-1, divergent_drafts=0, num_chapters=0,
        num_sections=0, consolidate_every=0, escalate_below_confidence=5.0,
        request_timeout=-1, max_run_tokens=-5, max_context_chars=-10,
        agentic_max_unit_steps=-2))
    assert s.min_insight == 5                      # clamped into 0..5
    assert s.max_revisions == 0                    # >= 0
    assert s.divergent_drafts == 1                 # >= 1
    assert s.num_chapters == 1 and s.num_sections == 1 and s.consolidate_every == 1
    assert s.escalate_below_confidence == 1.0      # clamped into 0..1
    assert s.request_timeout == 60.0               # positive default restored
    assert s.max_run_tokens == 0 and s.max_context_chars == 0 and s.agentic_max_unit_steps == 0


def test_clamp_normalizes_enums():
    s = _clamp_settings(Settings(mode="novella", agentic_policy="psychic"))
    assert s.mode == "article" and s.agentic_policy == "default"


def test_clamp_leaves_valid_settings_untouched():
    s = _clamp_settings(Settings(min_insight=3, max_revisions=2, divergent_drafts=2,
                                 escalate_below_confidence=0.5, mode="book",
                                 agentic_policy="llm"))
    assert (s.min_insight, s.max_revisions, s.divergent_drafts, s.escalate_below_confidence,
            s.mode, s.agentic_policy) == (3, 2, 2, 0.5, "book", "llm")
