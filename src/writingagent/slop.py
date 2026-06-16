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

from . import registers

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


# ── Register-aware filtering (plan §22) ───────────────────────────────────────────
# The contract is parameterized by a writing register (registers.py): a novel keeps its
# em-dashes, an academic paper keeps 'moreover' and its hedges, ad copy keeps the
# exclamation mark. `register=None` means the historical default (the `nonfiction`
# profile reproduces it byte-for-byte, so render_constraints()/tell_pattern() are
# unchanged for every existing caller).
_CONNECTIVES = frozenset({"furthermore", "moreover", "notwithstanding", "additionally"})


def _reg(register):
    """Resolve to a Register, or None to mean 'historical default' (unfiltered)."""
    return None if register is None else registers.get(register)


def _allows(reg, word: str) -> bool:
    """True if this register explicitly permits an otherwise-banned verb/term/connective."""
    w = word.lower()
    if w in reg.allow_terms:
        return True
    if reg.allow_transitions and w in _CONNECTIVES:
        return True
    if reg.allow_intensifiers and w in {t.lower() for t in BANNED_INTENSIFIERS}:
        return True
    return False


def _hard_rules(reg) -> list[str]:
    """The hard directives for a register. For `nonfiction` this is HARD_RULES verbatim;
    other registers drop the em-dash / enthusiasm bans, swap the voice + concreteness
    lines, and (for academic) add the hedging-is-required note."""
    out: list[str] = []
    if not reg.allow_em_dash:
        out.append("NO EM-DASHES. Rewrite with a comma, semicolon, period, or parentheses.")
    out += [
        "NO FABRICATIONS. No invented stats, quotes, attributions, dates, or case studies.",
        "NO REPEATED TALKING POINTS. Say it once; remove duplicates.",
        "NO SCARE QUOTES on ordinary words. Quotes = real attributed quotations only.",
    ]
    if not reg.allow_enthusiasm:
        out.append("NO SYNTHETIC ENTHUSIASM. No exclamation marks or cheerleading.")
    out.append("VARY sentence length. Short sentences are powerful. Occasional long ones too.")
    out.append(reg.concrete_line)
    out.append(reg.voice_line)
    if reg.hedging_required:
        out.append("KEEP HEDGING where certainty is not warranted ('suggests', 'may', 'appears "
                    "to'): in this register it is epistemic honesty, not filler.")
    return out


def render_constraints(register=None) -> str:
    """Build the MANDATORY-CONSTRAINTS block injected into every writer/humanizer/critic
    prompt, from the lists above (so the prompt is a derived view of this single source).

    `register` (a name resolved via registers.get) tailors the contract to the genre;
    `None` is the historical nonfiction default and is byte-for-byte unchanged."""
    reg = _reg(register)
    if reg is None:
        verbs_items = list(BANNED_VERBS.items())
        terms, transitions, intensifiers = list(BANNED_TERMS), list(BANNED_TRANSITIONS), list(BANNED_INTENSIFIERS)
        hard = list(HARD_RULES)
    else:
        verbs_items = [(k, v) for k, v in BANNED_VERBS.items() if not _allows(reg, k)]
        terms = [t for t in BANNED_TERMS if not _allows(reg, t)]
        transitions = [t for t in BANNED_TRANSITIONS
                       if not (reg.allow_transitions and t.strip().strip('"').lower() in _CONNECTIVES)]
        intensifiers = [] if reg.allow_intensifiers else list(BANNED_INTENSIFIERS)
        hard = _hard_rules(reg)
    verbs = ", ".join(f"{k}→{v}" for k, v in verbs_items)
    lines = [
        "━━ MANDATORY WRITING CONSTRAINTS - zero exceptions ━━",
        "",
        f"BANNED VERBS (use plain equivalents): {verbs}.",
        "(The metaphorical senses of 'navigate' and 'optimize' are slop; their literal / "
        "technical senses are fine - use them only when precise.)",
        "",
    ]
    if terms:
        lines += ["BANNED ADJECTIVES / NOUNS: " + ", ".join(terms) + ".", ""]
    if transitions:
        lines += ["BANNED TRANSITIONS: " + ", ".join(transitions) + ".", ""]
    if intensifiers:
        lines += ["BANNED INTENSIFIERS: " + ", ".join(intensifiers) + ".", ""]
    lines += [
        "BANNED PHRASES: " + " · ".join(f'"{p}"' for p in BANNED_PHRASES) + ".",
        "",
        "BANNED OPENERS: " + " · ".join(f'"{o}"' for o in BANNED_OPENERS),
        "",
        *hard,
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


def tell_pattern(register=None) -> str:
    """The full case-insensitive regex the humanizer compiles into ``_TELL_RE``.

    Word group (``\\b``-anchored): banned verbs (inflected) + adjectives/nouns (exact) +
    the single-word transitions. Phrase group (substring): the multi-word transitions,
    banned phrases, and openers, normalized by ``_phrase_fragment``. TECHNICAL_EXCEPTIONS
    are absent by construction (they're in no list).

    `register` (resolved via registers.get) drops the words that register permits so the
    stripper won't mangle, e.g., a novel's 'realm' or an academic paper's 'moreover'.
    `None` is the historical default and is unchanged."""
    reg = _reg(register)
    verbs_src = [k for k in BANNED_VERBS if reg is None or not _allows(reg, k)]
    terms_src = [t for t in BANNED_TERMS if reg is None or not _allows(reg, t)]
    words = [_verb_fragment(v) for v in verbs_src]
    words += [re.escape(t) for t in terms_src]
    phrase_src: list[str] = list(BANNED_PHRASES) + list(BANNED_OPENERS)
    for t in BANNED_TRANSITIONS:
        cleaned = t.strip().replace('"', "").strip()
        if "(" not in t and " " not in cleaned:     # furthermore / moreover / notwithstanding
            if reg is not None and reg.allow_transitions and cleaned.lower() in _CONNECTIVES:
                continue                              # academic/legal keep these connectives
            words.append(re.escape(cleaned))
        else:
            phrase_src.append(t)
    phrases = [f for f in (_phrase_fragment(t) for t in phrase_src) if f]
    return rf"\b(?:{'|'.join(words)})\b|(?:{'|'.join(phrases)})"
