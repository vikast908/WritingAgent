"""Smart, forgiving input across the TUI: fuzzy project lookup (excerpts/typos),
slang-tolerant yes/no, and the generic option matcher used by /theme /mode /model
/set /provider. The system should understand intent, not demand exact strings."""
from writingagent import brain, ui

_SLUGS = [
    "from-idea-to-sub-100ms-voicebot-a-step-by-step-technical-blueprint",
    "under-the-hood-engineering-multi-agent-orchestration-for-sub-100ms-response-times",
    "real-time-voice-ai-from-zero-to-100ms-a-practical-build-guide",
]


def _seed(uid="u"):
    for slug in _SLUGS:
        d = brain.user_dir(uid) / "articles" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / "run_state.json").write_text('{"mode":"article"}', encoding="utf-8")


def test_resolve_project_excerpt_typo_and_case(tmp_brain):
    _seed()
    for query, expect in [
        ("voicebot", "blueprint"),       # excerpt -> the one project with that word
        ("voicebott", "blueprint"),      # one-char typo still lands
        ("VoiceBot", "blueprint"),       # case-insensitive
        ("orchestration", "under-the-hood"),
        ("multi-agent", "under-the-hood"),
        ("practical build guide", "real-time"),
        ("voice ai", "real-time"),
    ]:
        resolved, cands = brain.resolve_project("u", query)
        assert resolved and expect in resolved, (query, resolved, cands)


def test_resolve_project_ambiguous_returns_options(tmp_brain):
    _seed()
    resolved, cands = brain.resolve_project("u", "100ms")   # all three mention 100ms
    assert resolved is None and len(cands) == 3


def test_resolve_project_no_match(tmp_brain):
    _seed()
    assert brain.resolve_project("u", "quantum computing") == (None, [])


def test_resolve_project_exact_id_wins(tmp_brain):
    _seed()
    resolved, cands = brain.resolve_project("u", _SLUGS[0])
    assert resolved == _SLUGS[0] and cands == []


def test_chat_use_guardrail_ignores_junk_keeps_active(tmp_brain):
    """A chat-emitted /use to a hallucinated id (or with an [article] tag) must
    never clobber the correct active project - it only switches on a strong match."""
    from writingagent import shell
    _seed()
    active, other = _SLUGS[0], _SLUGS[1]
    hallucinated = "totally-made-up-voice-thing-from-zero-to-100ms-guide"
    # junk id: active stays put (this was the reported bug)
    st = {"uid": "u", "book": other}
    shell._chat_use_project(f"/use {hallucinated}[article]", None, st)
    assert st["book"] == other
    # exact id (even with the display tag) switches
    st = {"uid": "u", "book": other}
    shell._chat_use_project(f"/use {active}[article]", None, st)
    assert st["book"] == active
    # a strong excerpt switches; a bare /use is a no-op
    st = {"uid": "u", "book": other}
    shell._chat_use_project("/use voicebot", None, st)
    assert st["book"] == active
    shell._chat_use_project("/use", None, st)
    assert st["book"] == active


def test_is_affirmative_slang_and_defaults():
    for yes in ("y", "yes", "yeah", "yep", "yup", "sure", "ok", "okay",
                "do it", "go ahead", "absolutely", "YES!"):
        assert ui.is_affirmative(yes), yes
    for no in ("n", "no", "nope", "nah", "naw", "cancel", "stop", "abort"):
        assert not ui.is_affirmative(no), no
    # empty respects the prompt's default ([Y/n] vs [y/N])
    assert ui.is_affirmative("", default=True) is True
    assert ui.is_affirmative("", default=False) is False
    # unknown falls back to the default, never a crash
    assert ui.is_affirmative("maybe", default=True) is True
    assert ui.is_affirmative("maybe", default=False) is False


def test_smart_match_prefix_substring_alias_and_fuzzy():
    opts = ["editorial", "kazama", "supabase", "violet-bloom", "fallout"]
    assert ui.smart_match("edit", opts)[0] == "editorial"        # unique prefix
    assert ui.smart_match("bloom", opts)[0] == "violet-bloom"    # unique substring
    assert ui.smart_match("falout", opts)[0] == "fallout"        # fuzzy typo
    assert ui.smart_match("editorial", opts)[0] == "editorial"   # exact
    # alias table
    assert ui.smart_match("essay", ("book", "article"),
                          aliases={"essay": "article"})[0] == "article"
    # ambiguous -> no match, candidates offered
    m, cands = ui.smart_match("a", ["alpha", "alistair", "beta"])
    assert m is None and set(cands) == {"alpha", "alistair"}
    # nothing close
    assert ui.smart_match("zzzz", opts) == (None, [])
