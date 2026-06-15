"""Single source of truth for the anti-slop lexicon (plan: anti-slop).

The writer's constraint block (`prompts.NO_SLOP`) is GENERATED from these lists, so the
banned-word rules the writer sees and this canonical data can never silently drift. The
deterministic humanizer (`humanizer._TELL_RE`) keeps its own morphologically-tuned regex
(it must match inflections like delve/delves/delving precisely), but a test
(`test_quality`) cross-checks it against this lexicon so a term added here that the
humanizer misses - or a TECHNICAL_EXCEPTION it wrongly strips - fails CI.

TECHNICAL_EXCEPTIONS read as slop in marketing copy but are often the *precise* term in
technical prose ("performance optimization", "navigate a tree"), so they are NEITHER
hard-banned in the prompt NOR stripped by the humanizer - the LLM judge decides in context.
This resolves the old contradiction where NO_SLOP banned "optimize" while the humanizer
deliberately allowed it.
"""
from __future__ import annotations

# Verb -> plain replacement. The metaphorical-only verbs ("optimize", "navigate") are
# deliberately NOT here - see TECHNICAL_EXCEPTIONS.
BANNED_VERBS: dict[str, str] = {
    "delve": "explore", "leverage": "use", "utilize": "use", "facilitate": "help",
    "foster": "encourage", "bolster": "strengthen", "underscore": "highlight",
    "unveil": "reveal", "streamline": "simplify", "endeavour": "try",
    "ascertain": "find out", "elucidate": "explain", "enhance": "improve",
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
