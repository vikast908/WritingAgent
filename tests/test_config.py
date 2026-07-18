"""Settings range validation (C-007): a typo in settings.yaml must clamp to sane bounds,
not produce baffling runtime behavior (an unreachable insight gate, a broken loop range)."""
from writingagent.config import ModelConfig, Settings, _clamp_settings, load_config


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


def test_default_user_heals_from_corruption():
    """A default_user corrupted to a non-safe value (e.g. YAML-parsed as an int, or an
    unsafe string) heals to 'default' instead of crashing everything that uses the uid."""
    from writingagent import brain
    assert brain.is_safe_id(1234) is False          # robust to a non-str, no TypeError
    s = Settings()
    s.default_user = 1234                            # simulate the corrupted-int case
    assert _clamp_settings(s).default_user == "default"
    assert _clamp_settings(Settings(default_user="bad id!")).default_user == "default"
    assert _clamp_settings(Settings(default_user="vikas")).default_user == "vikas"


def test_clamp_image_source_is_a_validated_ordered_list():
    # unknown tokens dropped, order + case normalized, valid ones kept
    assert _clamp_settings(Settings(image_source="PIXABAY, wikimedia, junk")).image_source == "pixabay,wikimedia"
    # nothing valid -> the keyless default
    assert _clamp_settings(Settings(image_source="zzz")).image_source == "openverse,wikimedia"
    # the shipped default is itself valid and untouched
    assert _clamp_settings(Settings()).image_source == "openverse,wikimedia"


def test_clamp_leaves_valid_settings_untouched():
    s = _clamp_settings(Settings(min_insight=3, max_revisions=2, divergent_drafts=2,
                                 escalate_below_confidence=0.5, mode="book",
                                 agentic_policy="llm"))
    assert (s.min_insight, s.max_revisions, s.divergent_drafts, s.escalate_below_confidence,
            s.mode, s.agentic_policy) == (3, 2, 2, 0.5, "book", "llm")


# ── A-024: repetition penalties ─────────────────────────────────────────────────
def test_penalty_getters_clamp_to_openai_range():
    c = ModelConfig({"frequency_penalty": {"writer": 0.3, "x": 9},
                     "presence_penalty": {"writer": -5}})
    assert c.frequency_penalty_for("writer") == 0.3
    assert c.frequency_penalty_for("x") == 2.0        # clamped to the [-2, 2] max
    assert c.presence_penalty_for("writer") == -2.0   # clamped to the min
    assert c.frequency_penalty_for("missing") is None
    assert c.presence_penalty_for("missing") is None


def test_penalties_round_trip_through_to_dict():
    c = ModelConfig({"frequency_penalty": {"writer": 0.3}, "presence_penalty": {"writer": 0.1}})
    d = c.to_dict()
    assert d["frequency_penalty"] == {"writer": 0.3}
    assert d["presence_penalty"] == {"writer": 0.1}


def test_shipped_writer_penalty_and_deterministic_temps():
    # The shipped models.yaml must keep the writer's anti-repetition penalty and the
    # analytical nodes deterministic (A-022/A-024).
    c = load_config()
    assert c.frequency_penalty_for("writer") and c.frequency_penalty_for("writer") > 0
    assert c.temperature_for("consolidation") == 0.0
    assert c.temperature_for("summarizer") == 0.0
    lt = c.temperature_for("learner")
    assert lt is not None and lt <= 0.5


# ── Cost modes (budget profile, plan §19) ─────────────────────────────────────
def test_cost_mode_budget_pins_lean_and_routes_flash():
    from writingagent.config import apply_cost_mode
    cfg = ModelConfig({"default": "pro-model", "fallback": "flash-model",
                       "nodes": {"critic": "pro-model", "writer": "pro-model"}})
    s = Settings(cost_mode="budget", divergent_drafts=2, max_revisions=2,
                 table_read=True, max_run_tokens=0, max_context_chars=24000)
    cfg2, s2, notes = apply_cost_mode(cfg, s)
    assert s2.divergent_drafts == 1 and s2.max_revisions == 1
    assert s2.table_read is False and s2.table_read_revise is False
    assert s2.max_context_chars == 12_000
    for node in ("critic", "judge", "verifier", "consolidation", "diagram"):
        assert cfg2.model_for(node) == "flash-model"
    assert cfg2.model_for("writer") == "pro-model"      # prose quality stays on pro
    # the caller's objects are never mutated
    assert cfg.model_for("critic") == "pro-model" and s.divergent_drafts == 2
    assert notes


def test_cost_mode_standard_is_noop():
    from writingagent.config import apply_cost_mode
    cfg, s = ModelConfig({}), Settings()
    cfg2, s2, notes = apply_cost_mode(cfg, s)
    assert cfg2 is cfg and s2 is s and notes == []


def test_cost_mode_budget_engages_prompt_cache_for_deepseek_default():
    """Budget mode auto-pins the DeepSeek upstream so the prompt cache engages (prompt
    tokens are the majority of spend; unpinned they largely miss the cache)."""
    from writingagent.config import apply_cost_mode
    cfg = ModelConfig({"default": "deepseek/deepseek-v4-pro",
                       "fallback": "deepseek/deepseek-v4-flash"})
    _, s2, notes = apply_cost_mode(cfg, Settings(cost_mode="budget"))
    assert s2.openrouter_providers == "DeepSeek"
    assert any("cache-pin" in n for n in notes)


def test_cost_mode_cache_pin_respects_user_value_and_non_deepseek_default():
    from writingagent.config import apply_cost_mode
    # a user's explicit pin is never overridden
    _, s2, _ = apply_cost_mode(ModelConfig({"default": "deepseek/deepseek-v4-pro"}),
                               Settings(cost_mode="budget", openrouter_providers="Together"))
    assert s2.openrouter_providers == "Together"
    # a non-DeepSeek default stays unpinned (the pin is DeepSeek-cache specific)
    _, s3, _ = apply_cost_mode(ModelConfig({"default": "openai/gpt-5"}),
                               Settings(cost_mode="budget"))
    assert s3.openrouter_providers == ""


def test_cost_mode_budget_never_loosens_a_leaner_user_value():
    from writingagent.config import apply_cost_mode
    s = Settings(cost_mode="budget", divergent_drafts=1, max_revisions=0,
                 table_read=False, max_context_chars=8000)
    _, s2, _ = apply_cost_mode(ModelConfig({}), s)
    assert s2.max_context_chars == 8000
    assert s2.divergent_drafts == 1 and s2.max_revisions == 0


def test_budget_scales_with_units_and_respects_explicit_cap():
    from writingagent.config import BUDGET_OVERHEAD_TOKENS, budget_for_units
    # budget mode with no explicit cap: scales by unit count so a full piece finishes
    s = Settings(cost_mode="budget", max_run_tokens=0, budget_tokens_per_unit=20_000)
    assert budget_for_units(s, 3) == BUDGET_OVERHEAD_TOKENS + 3 * 20_000
    assert budget_for_units(s, 6) == BUDGET_OVERHEAD_TOKENS + 6 * 20_000
    # an explicit max_run_tokens is a hard ceiling that always wins
    s2 = Settings(cost_mode="budget", max_run_tokens=90_000)
    assert budget_for_units(s2, 6) == 90_000
    # standard mode, no cap -> unlimited (historical behavior)
    assert budget_for_units(Settings(cost_mode="standard", max_run_tokens=0), 6) == 0


def test_cost_mode_clamped_to_known_values():
    assert _clamp_settings(Settings(cost_mode="bogus")).cost_mode == "standard"
    assert _clamp_settings(Settings(cost_mode="budget")).cost_mode == "budget"


# ── "random" voice fields resolve to a concrete pick at creation ────────────────
def test_random_survives_clamp_and_resolves_to_concrete():
    from writingagent import registers
    from writingagent.config import _clamp_settings, resolve_random
    # "random" passes validation (not cleared to "")
    s = _clamp_settings(Settings(persona="random", emotion="random", register="random",
                                 field="random", citation_style="random"))
    assert s.persona == "random" and s.emotion == "random" and s.register == "random"
    assert s.field == "random" and s.citation_style == "random"
    # resolve_random turns each into a real member of its set
    r = resolve_random(s)
    assert r.register in registers.names() and r.register != "random"
    assert r.persona != "random" and r.emotion != "random"
    assert r.field != "random" and r.citation_style in (
        "influence", "numeric", "apa", "mla", "chicago", "ap")
    # a non-random value is left untouched; the caller's object is not mutated
    assert resolve_random(Settings(persona="wry-skeptic")).persona == "wry-skeptic"
    assert s.persona == "random"
