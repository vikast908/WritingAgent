"""Deterministic, genre-aware craft metrics (plan §22).

Computed evidence for the critic - never verdicts. These run with no model call, so they
hold the quality line on a *basic* model exactly as well as on a strong one: a regex does
not care how clever the writer is. `structural_report` (humanizer.py) delegates here and
selects the metric set from the writing register (registers.py), so a novel is measured for
filter-verbs and dialogue while a whitepaper is measured for specificity density.

Each metric returns one short line of evidence (or None when there isn't enough text to
judge). The phrasing names the failure mode and the rough threshold, so the critic - even a
weak one - has a concrete anchor instead of an abstract instruction.
"""
from __future__ import annotations

import re

from . import registers

# ── shared text prep ──────────────────────────────────────────────────────────────
_CODE_FENCE = re.compile(r"(?ms)^```.*?^```")
_IMG_LINE = re.compile(r"(?m)^!\[[^\]]*\]\([^)]*\).*$")
_HEADING = re.compile(r"(?m)^#{1,6}[ \t].*$")
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
_NUMBERS = re.compile(r"\d+(?:\.\d+)?")
_WORD = re.compile(r"[A-Za-z']+")
_TRIAD = re.compile(r"\b\w+, \w+, and \w+\b")
_WRAPUP = re.compile(
    r"^(?:in short|ultimately|overall|in the end|in other words|simply put|the bottom line)\b",
    re.IGNORECASE)


def _prose(text: str) -> str:
    """Strip fenced code, headings, and image lines so metrics see only prose."""
    t = _CODE_FENCE.sub(" ", text or "")
    t = _HEADING.sub(" ", t)
    return _IMG_LINE.sub(" ", t)


def _paragraphs(prose: str) -> list[list[str]]:
    return [p.split() for p in re.split(r"\n\s*\n", prose)
            if p.strip() and not p.strip().startswith("#")]


def _sentences(prose: str) -> list[str]:
    flat = re.sub(r"\s+", " ", prose).strip()
    return [s.strip() for s in _SENT_SPLIT.split(flat) if s.strip()]


def _count_syllables(word: str) -> int:
    """Cheap English syllable estimate (vowel groups, minus a silent terminal 'e')."""
    w = word.lower()
    groups = re.findall(r"[aeiouy]+", w)
    n = len(groups)
    if w.endswith("e") and not w.endswith(("le", "ie")) and n > 1:
        n -= 1
    return max(1, n)


# ── metrics (each: prose-derived inputs -> one evidence line or None) ───────────────
class _Ctx:
    """Pre-computed views of the draft shared by all metrics (compute once)."""

    def __init__(self, text: str):
        self.prose = _prose(text)
        self.paras = _paragraphs(self.prose)
        self.sents = _sentences(self.prose)
        self.words = [w for w in _WORD.findall(self.prose)]
        self.n_words = max(len(self.words), 1)
        self.lower = self.prose.lower()


def _m_paragraph_uniformity(c: _Ctx) -> str | None:
    if len(c.paras) < 4:
        return None
    lens = [len(p) for p in c.paras]
    mean = sum(lens) / len(lens)
    var = sum((x - mean) ** 2 for x in lens) / len(lens)
    cv = (var ** 0.5) / mean if mean else 0
    return (f"- paragraph lengths: {len(c.paras)} paragraphs, mean {mean:.0f} words, "
            f"variation {cv:.2f} (under 0.30 reads machine-uniform)")


def _m_rule_of_three(c: _Ctx) -> str | None:
    triads = len(_TRIAD.findall(c.prose))
    return (f"- rule-of-three constructions: {triads} per {c.n_words} words "
            f"({'heavy' if triads > c.n_words / 250 else 'ok'})")


def _m_wrapups(c: _Ctx) -> str | None:
    wrapups = sum(1 for p in re.split(r"\n\s*\n", c.prose)
                  if p.strip() and _WRAPUP.match(p.strip().splitlines()[-1].strip()))
    if not wrapups:
        return None
    return f"- {wrapups} paragraph(s) close with a summarizing wrap-up opener"


def _m_specificity(c: _Ctx) -> str | None:
    numbers = len(_NUMBERS.findall(c.prose))
    proper = len(re.findall(r"(?<![.!?]\s)(?<!^)\b[A-Z][a-z]{2,}", c.prose))
    specificity = (numbers + proper) / c.n_words * 100
    return (f"- specificity density: {specificity:.1f} concrete tokens "
            f"(numbers + proper nouns) per 100 words "
            f"({'low - prose may be generic' if specificity < 2.0 else 'ok'})")


def _m_sentence_variance(c: _Ctx) -> str | None:
    if len(c.sents) < 5:
        return None
    lens = [len(s.split()) for s in c.sents]
    mean = sum(lens) / len(lens)
    var = sum((x - mean) ** 2 for x in lens) / len(lens)
    cv = (var ** 0.5) / mean if mean else 0
    openers = [s.split()[0].lower() for s in c.sents if s.split()]
    run = best = 1
    for i in range(1, len(openers)):
        run = run + 1 if openers[i] == openers[i - 1] else 1
        best = max(best, run)
    flag = "monotone - vary length and sentence openings" if cv < 0.35 or best >= 3 else "ok"
    return (f"- sentence rhythm: {len(lens)} sentences, mean {mean:.0f} words, variation "
            f"{cv:.2f}, longest run of identical opening word {best} ({flag})")


_BE = r"(?:am|is|are|was|were|be|been|being|got|gets|get)"
_PARTICIPLE = re.compile(
    rf"\b{_BE}\s+(?:\w+ly\s+)?(?:\w+ed|written|done|made|given|taken|seen|known|held|built|"
    r"shown|brought|found|told|kept|sent|set|put|begun|driven|drawn|born|caught|chosen)\b",
    re.IGNORECASE)


def _m_passive(c: _Ctx) -> str | None:
    if len(c.sents) < 4:
        return None
    hits = len(_PARTICIPLE.findall(c.prose))
    ratio = hits / len(c.sents)
    return (f"- passive-voice (heuristic): ~{hits} in {len(c.sents)} sentences "
            f"({ratio * 100:.0f}%{'; high - prefer active' if ratio > 0.25 else ''})")


_ADVERB_OK = frozenset("only family reply apply ally fully early holy italy ugly lonely "
                       "likely daily supply july imply rely".split())


def _m_adverbs(c: _Ctx) -> str | None:
    advs = [w for w in c.words if w.lower().endswith("ly") and w.lower() not in _ADVERB_OK
            and len(w) > 3]
    per100 = len(advs) / c.n_words * 100
    return (f"- -ly adverb density: {per100:.1f} per 100 words "
            f"({'high - let stronger verbs carry it' if per100 > 4.0 else 'ok'})")


def _m_reading_grade(c: _Ctx) -> str | None:
    if len(c.sents) < 3 or c.n_words < 30:
        return None
    syll = sum(_count_syllables(w) for w in c.words)
    grade = 0.39 * (c.n_words / len(c.sents)) + 11.8 * (syll / c.n_words) - 15.59
    grade = max(0.0, grade)
    return f"- reading level: ~grade {grade:.0f} (Flesch-Kincaid)"


_CLICHES = (
    "at the end of the day", "think outside the box", "low-hanging fruit", "move the needle",
    "tip of the iceberg", "needle in a haystack", "calm before the storm", "time will tell",
    "few and far between", "last but not least", "when all is said and done", "in this day and age",
    "only time will tell", "the fact of the matter", "raining cats and dogs", "cut to the chase",
    "back to square one", "a perfect storm", "at a crossroads", "light at the end of the tunnel",
)


def _m_cliche(c: _Ctx) -> str | None:
    from . import emotions  # emotion clichés ('her heart raced') are the anti-symptom-dict deny-list
    hits = [p for p in _CLICHES if p in c.lower]
    hits += [p for p in emotions.avoid_phrases() if p in c.lower]
    if not hits:
        return None
    return f"- clichés detected ({len(hits)}): " + "; ".join(hits[:5])


_FILTER_VERBS = (
    "saw", "see", "sees", "heard", "hear", "hears", "felt", "feel", "feels", "noticed",
    "notice", "realized", "realize", "wondered", "wonder", "watched", "watch", "seemed",
    "seem", "seems", "looked", "knew", "thought", "decided", "remembered", "wished",
)
_FILTER_RE = re.compile(r"\b(?:" + "|".join(_FILTER_VERBS) + r")\b", re.IGNORECASE)


def _m_filter_words(c: _Ctx) -> str | None:
    hits = len(_FILTER_RE.findall(c.prose))
    per100 = hits / c.n_words * 100
    return (f"- filter-verb density: {hits} ({per100:.1f}/100 words) - 'she saw', 'he felt', "
            f"'it seemed'{'; high - render the thing directly, drop the filter' if per100 > 1.2 else ''}")


def _m_dialogue(c: _Ctx) -> str | None:
    blocks = [p.strip() for p in re.split(r"\n\s*\n", c.prose) if p.strip()]
    if not blocks:
        return None
    dlg = sum(1 for b in blocks if b[:1] in ('"', "“", "'", "‘", "—"))
    pct = dlg / len(blocks) * 100
    return f"- dialogue: {dlg}/{len(blocks)} paragraphs open in speech ({pct:.0f}%)"


_SAID_BOOKISMS = (
    "exclaimed", "retorted", "declared", "interjected", "opined", "gushed", "quipped",
    "snarled", "hissed", "breathed", "chuckled", "grinned", "smiled", "laughed", "barked",
    "growled", "purred", "pleaded", "snapped", "boomed", "stammered",
)
_BOOKISM_RE = re.compile(r"\b(?:" + "|".join(_SAID_BOOKISMS) + r")\b", re.IGNORECASE)


def _m_said_bookisms(c: _Ctx) -> str | None:
    hits = _BOOKISM_RE.findall(c.prose)
    if not hits:
        return None
    uniq = sorted({h.lower() for h in hits})
    return (f"- said-bookisms ({len(hits)}): {', '.join(uniq[:6])} - 'said'/'asked' "
            "usually disappear better than fancy tags")


def _m_pov_tense(c: _Ctx) -> str | None:
    low = c.lower
    first = len(re.findall(r"\b(?:i|me|my|mine|we|us|our)\b", low))
    second = len(re.findall(r"\b(?:you|your|yours)\b", low))
    third = len(re.findall(r"\b(?:he|she|they|him|her|them|his|hers|their)\b", low))
    pov = max((first, "first"), (second, "second"), (third, "third"))[1]
    past = len(re.findall(r"\b(?:was|were|had|said|went|came|knew|saw|took|felt)\b", low))
    present = len(re.findall(r"\b(?:is|are|says|goes|comes|knows|sees|takes|feels|walks)\b", low))
    if past + present < 4:
        return None
    mix = min(past, present) / (past + present)
    tnote = "mixed past/present - check tense consistency" if mix > 0.35 else "consistent"
    return f"- POV appears {pov}-person; tense {tnote} (past {past}/present {present})"


_SENSORY = (
    "light", "dark", "bright", "shadow", "red", "blue", "green", "gold", "loud", "quiet",
    "silence", "echo", "whisper", "scream", "cold", "warm", "hot", "rough", "smooth", "sharp",
    "soft", "wet", "dry", "smell", "scent", "reek", "sweet", "bitter", "sour", "salt", "taste",
    "touch", "skin", "hand", "rain", "wind", "smoke", "dust", "blood", "metal", "stone",
)
_SENSORY_RE = re.compile(r"\b(?:" + "|".join(_SENSORY) + r")\w*\b", re.IGNORECASE)


def _m_concrete_sensory(c: _Ctx) -> str | None:
    hits = len(_SENSORY_RE.findall(c.prose))
    per100 = hits / c.n_words * 100
    return (f"- sensory-word density: {per100:.1f} per 100 words "
            f"({'low - the prose may be telling, not showing' if per100 < 1.5 else 'ok'})")


_WEAK_OPENERS = re.compile(
    r"^\s*(?:in this (?:chapter|section|article|piece|essay)|this (?:chapter|section|article) "
    r"(?:will|covers|discusses|explores)|in (?:today's|the modern|the current))",
    re.IGNORECASE)


_FORMULAIC_CLOSE = re.compile(
    r"^(?:in conclusion|to sum up|to summarize|to summarise|in summary|all in all|"
    r"all things considered|at the end of the day|in the end|ultimately|overall)\b",
    re.IGNORECASE)


def _m_opening(c: _Ctx) -> str | None:
    """Judge the two most important sentences: the first (earns the read) and the last
    (the button). Flags throat-clearing/definitional openers and formulaic clinchers."""
    if not c.sents:
        return None
    first = c.sents[0]
    notes = []
    if _WEAK_OPENERS.match(first):
        notes.append("opening: meta/throat-clearing first line")
    if re.match(r"^\s*\w+ (?:is|are|was|were) (?:a|an|the) ", first, re.IGNORECASE):
        notes.append("opening: starts on a dictionary definition")
    if len(first.split()) > 45:
        notes.append("opening: first sentence very long")
    if len(c.sents) >= 3:
        last = c.sents[-1]
        if _FORMULAIC_CLOSE.match(last):
            notes.append("closing: formulaic wrap-up ('in conclusion'/'ultimately')")
    if not notes:
        return None
    return ("- opening/closing: " + "; ".join(notes)
            + " - the first and last sentences carry the most weight")


_METRICS = {
    "paragraph_uniformity": _m_paragraph_uniformity,
    "rule_of_three": _m_rule_of_three,
    "wrapups": _m_wrapups,
    "specificity": _m_specificity,
    "sentence_variance": _m_sentence_variance,
    "passive": _m_passive,
    "adverbs": _m_adverbs,
    "reading_grade": _m_reading_grade,
    "cliche": _m_cliche,
    "filter_words": _m_filter_words,
    "dialogue": _m_dialogue,
    "said_bookisms": _m_said_bookisms,
    "pov_tense": _m_pov_tense,
    "concrete_sensory": _m_concrete_sensory,
    "opening": _m_opening,
}


def report(text: str, register: str | None = None) -> str:
    """Compute the register's craft metrics for a draft and return them as evidence lines.

    `register=None` uses the default (`nonfiction`) metric set, which reproduces the
    historical structural_report lines (paragraph uniformity, rule-of-three, wrap-ups,
    specificity) plus the new universal ones."""
    reg = registers.get(register)
    c = _Ctx(text)
    lines = []
    for key in reg.metrics:
        fn = _METRICS.get(key)
        if fn is None:
            continue
        line = fn(c)
        if line:
            lines.append(line)
    if reg.reading_grade and "reading_grade" in reg.metrics:
        lo, hi = reg.reading_grade
        lines.append(f"  (target reading level for this register: grade {lo}-{hi})")
    return "\n".join(lines)
