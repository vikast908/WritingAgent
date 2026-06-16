"""Single source of truth for the anti-slop lexicon (plan: anti-slop).

Both views of the lexicon are GENERATED from these lists, so nothing can silently drift:
- the writer's constraint block (`prompts.NO_SLOP`) via `render_constraints()`, and
- the deterministic humanizer's tell-detector (`humanizer._TELL_RE`) via `tell_pattern()` -
  the morphological matching rules (verb inflections, apostrophe tolerance, the
  "in today's [anything]" wildcard) now live here too, so adding a banned word here updates
  the stripper automatically. `test_quality` still asserts the round-trip as a guard.

TECHNICAL_EXCEPTIONS read as slop in marketing copy but are often the *precise* term in
technical prose ("performance optimization", "navigate a tree"), so they are NEITHER
hard-banned in the prompt NOR stripped by the humanizer - the LLM judge decides in context.
This resolves the old contradiction where NO_SLOP banned "optimize" while the humanizer
deliberately allowed it.
"""
from __future__ import annotations

import re

# Verb -> plain replacement. The metaphorical-only verbs ("optimize", "navigate") are
# deliberately NOT here - see TECHNICAL_EXCEPTIONS.
BANNED_VERBS: dict[str, str] = {
    "delve": "explore", "leverage": "use", "utilize": "use", "facilitate": "help",
    "foster": "encourage", "bolster": "strengthen", "underscore": "highlight",
    "unveil": "reveal", "streamline": "simplify", "endeavour": "try",
    "ascertain": "find out", "elucidate": "explain", "enhance": "improve",
    "boast": "have",
}

# Adjectives / nouns that read as filler.
BANNED_TERMS: list[str] = [
    "robust", "comprehensive", "pivotal", "crucial", "vital", "transformative",
    "cutting-edge", "groundbreaking", "innovative", "seamless", "intricate", "nuanced",
    "multifaceted", "holistic", "tapestry", "symphony", "beacon", "realm", "testament",
    "watershed", "landscape", "myriad", "plethora", "paramount",
]

BANNED_TRANSITIONS: list[str] = [
    "furthermore", "moreover", "notwithstanding", '"that being said"', '"at its core"',
    '"in essence"', '"it is worth noting that"', '"in the realm of"',
    '"in today\'s [anything]"', '"it goes without saying"', '"let\'s delve into"',
    '"this begs the question"', '"additionally" (when merely listing)',
]

BANNED_INTENSIFIERS: list[str] = [
    "absolutely", "extremely", "dramatically", "significantly", "incredibly",
    "remarkably", "truly", "fundamentally", "essentially", "undoubtedly",
]

BANNED_PHRASES: list[str] = [
    "shed light on", "pave the way for", "a myriad of", "a plethora of",
    "in the ever-evolving landscape", "serves as a testament", "left an indelible mark",
    "deeply rooted", "unwavering commitment", "stark reminder", "It's important to note",
    "When it comes to", "At the end of the day", "In today's world",
    "it's not just X, it's Y",
]

BANNED_OPENERS: list[str] = [
    "Whether you're...", "Imagine a world where...", "In conclusion...", "To sum up...",
    "All things considered...",
]

# Hard directives (not word-lists) the writer/humanizer/critic all honor. Kept here so the
# whole anti-slop contract lives in one file.
HARD_RULES: list[str] = [
    "NO EM-DASHES. Rewrite with a comma, semicolon, period, or parentheses.",
    "NO FABRICATIONS. No invented stats, quotes, attributions, dates, or case studies.",
    "NO REPEATED TALKING POINTS. Say it once; remove duplicates.",
    "NO SCARE QUOTES on ordinary words. Quotes = real attributed quotations only.",
    "NO SYNTHETIC ENTHUSIASM. No exclamation marks or cheerleading.",
    "VARY sentence length. Short sentences are powerful. Occasional long ones too.",
    "CONCRETE OVER ABSTRACT. Every vague claim needs a specific fact, name, or date.",
    "RESEARCHER VOICE: direct, grounded, specific. Delete any sentence generic enough "
    "to appear unchanged on any site. Make it specific or cut it.",
]

# Slop in marketing copy, precise in technical prose - never hard-banned, never auto-stripped.
TECHNICAL_EXCEPTIONS: frozenset[str] = frozenset({"optimize", "navigate"})


def render_constraints() -> str:
    """Build the MANDATORY-CONSTRAINTS block injected into every writer/humanizer/critic
    prompt, from the lists above (so the prompt is a derived view of this single source)."""
    verbs = ", ".join(f"{k}→{v}" for k, v in BANNED_VERBS.items())
    lines = [
        "━━ MANDATORY WRITING CONSTRAINTS - zero exceptions ━━",
        "",
        f"BANNED VERBS (use plain equivalents): {verbs}.",
        "(The metaphorical senses of 'navigate' and 'optimize' are slop; their literal / "
        "technical senses are fine - use them only when precise.)",
        "",
        "BANNED ADJECTIVES / NOUNS: " + ", ".join(BANNED_TERMS) + ".",
        "",
        "BANNED TRANSITIONS: " + ", ".join(BANNED_TRANSITIONS) + ".",
        "",
        "BANNED INTENSIFIERS: " + ", ".join(BANNED_INTENSIFIERS) + ".",
        "",
        "BANNED PHRASES: " + " · ".join(f'"{p}"' for p in BANNED_PHRASES) + ".",
        "",
        "BANNED OPENERS: " + " · ".join(f'"{o}"' for o in BANNED_OPENERS),
        "",
        *HARD_RULES,
        "━━ END CONSTRAINTS ━━",
    ]
    return "\n".join(lines)


# ── Deterministic-stripper view (humanizer._TELL_RE is compiled from this) ────────
def _verb_fragment(verb: str) -> str:
    """Regex fragment matching a banned verb and its inflections. A silent-e verb
    (delve, leverage, utilize) drops the 'e' so the stem + ``\\w*`` covers es/ed/ing
    (delve→delv\\w* matches delve/delves/delving/delved); others keep their stem."""
    stem = verb[:-1] if verb.endswith("e") else verb
    return re.escape(stem) + r"\w*"


def _phrase_fragment(text: str) -> str | None:
    """Normalize a banned phrase/transition/opener into a matchable regex fragment, or
    None to skip it. Skips entries with a parenthetical caveat ("additionally (when merely
    listing)" - the stripper can't judge the condition) or a single-letter template
    placeholder ("it's not just X, it's Y"). Otherwise: drop surrounding quotes and the
    opener ellipsis, lower-case, turn "[anything]" into a wildcard, and make apostrophes
    optional (so "it's"/"its" and curly/straight forms both match)."""
    raw = text.strip()
    if "(" in raw:                       # conditional/caveated ban - not for blind stripping
        return None
    p = raw.replace('"', "").strip().lower().rstrip(".").strip()
    if not p or re.search(r"\b[xy]\b", p):   # empty or a free-variable template -> skip
        return None
    frag = re.escape(p)
    frag = frag.replace(r"\[anything\]", r"\w+")   # "in today's [anything]" -> in today's \w+
    return frag.replace("'", "'?")                  # apostrophe-tolerant (it's / its)


def tell_pattern() -> str:
    """The full case-insensitive regex the humanizer compiles into ``_TELL_RE``.

    Word group (``\\b``-anchored): banned verbs (inflected) + adjectives/nouns (exact) +
    the single-word transitions. Phrase group (substring): the multi-word transitions,
    banned phrases, and openers, normalized by ``_phrase_fragment``. TECHNICAL_EXCEPTIONS
    are absent by construction (they're in no list)."""
    words = [_verb_fragment(v) for v in BANNED_VERBS]
    words += [re.escape(t) for t in BANNED_TERMS]
    phrase_src: list[str] = list(BANNED_PHRASES) + list(BANNED_OPENERS)
    for t in BANNED_TRANSITIONS:
        cleaned = t.strip().replace('"', "").strip()
        if "(" not in t and " " not in cleaned:     # furthermore / moreover / notwithstanding
            words.append(re.escape(cleaned))
        else:
            phrase_src.append(t)
    phrases = [f for f in (_phrase_fragment(t) for t in phrase_src) if f]
    return rf"\b(?:{'|'.join(words)})\b|(?:{'|'.join(phrases)})"
