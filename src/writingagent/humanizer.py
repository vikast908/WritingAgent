"""Humanizer: strip AI-written tells while preserving meaning (and code).

Surgical, not wholesale: tells are DETECTED deterministically (lexicon + patterns),
only the flagged sentences are sent for rewrite, and every rewrite is guarded
(citations, numbers, length) before it is spliced back. The approved prose is never
re-generated end-to-end, so a Flash-model paraphrase can't drift facts or regress
the whole chapter toward that model's mean style.

Also home to structural_report(): deterministic style metrics (paragraph uniformity,
rule-of-three density, specificity) fed to the critic as computed evidence.
"""
from __future__ import annotations

import re
from functools import cache

from . import prompts as P
from . import registers, slop
from . import schemas as S
from .config import ModelConfig
from .llm import _fake_mode, complete_structured

# Only [ \t] around the dash - must NOT eat newlines, or an em-dash at a line end
# would merge two lines/paragraphs into one.
_DASH = re.compile(r"[ \t]*[—–][ \t]*")  # em / en dash
_QUOTES = {"“": '"', "”": '"', "‘": "'", "’": "'",
           "…": "...", " ": " "}


def _clean_segment(s: str, allow_em_dash: bool = False) -> str:
    for k, v in _QUOTES.items():
        s = s.replace(k, v)
    if not allow_em_dash:
        s = _DASH.sub(" - ", s)
    return re.sub(r"[ \t]{2,}", " ", s)


def mechanical_clean(text: str, allow_em_dash: bool = False) -> str:
    """Deterministic typographic de-AI pass. Leaves fenced code blocks (```) untouched.

    Tracks fences line-by-line so an unbalanced/odd number of ``` markers can't shift
    the parity and either mangle code or skip prose (the old naive split did both).
    `allow_em_dash` (set for fiction/poetry/essay registers) keeps em-dashes, which are
    voice there, not a tell.
    """
    out: list[str] = []
    in_fence = False
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append(line)
        else:
            out.append(line if in_fence else _clean_segment(line, allow_em_dash))
    return "".join(out)


# ── Tell detection (the NO_SLOP lexicon, as code instead of prompt hope) ──────
# The pattern is GENERATED from slop.py (the single source the writer prompt is also
# generated from), so adding a banned word there updates this stripper too - no parallel
# hand-maintained regex to drift. The morphological rules (verb inflections, apostrophe
# tolerance, the "in today's [anything]" wildcard) live in slop.tell_pattern().
# slop.TECHNICAL_EXCEPTIONS ("optimize", "navigate") are absent by construction: in
# technical prose they are often the precise term - the LLM judge decides.
_TELL_RE = re.compile(slop.tell_pattern(), re.IGNORECASE)


@cache
def _tell_re(register: str | None):
    """Register-aware tell matcher (cached). None -> the default _TELL_RE, so existing
    callers are unchanged; a register drops the words it permits (a novel's em-dash and
    'realm', an academic paper's 'moreover') so the stripper won't mangle them."""
    if register is None:
        return _TELL_RE
    return re.compile(slop.tell_pattern(register), re.IGNORECASE)

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
# Inline citation markers, including the [N1] synthesis form (mirror polish._INLINE_CITE);
# a plain \[\d+\] guard was blind to [N12] and let a rewrite silently strip the marker.
_CITE_MARKS = re.compile(r"\[N?\d+\]")
_NUMBERS = re.compile(r"\d+(?:\.\d+)?")


def _prose_spans(text: str) -> list[tuple[int, int]]:
    """(start, end) character spans of text OUTSIDE fenced code blocks."""
    spans: list[tuple[int, int]] = []
    pos = 0
    in_fence = False
    for line in text.splitlines(keepends=True):
        end = pos + len(line)
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        elif not in_fence:
            spans.append((pos, end))
        pos = end
    return spans


def find_tell_sentences(text: str, cap: int = 40,
                        register: str | None = None) -> list[tuple[int, int, str]]:
    """Sentences outside code fences that contain a detected tell.

    Returns (start, end, sentence) spans into `text`, at most `cap` of them
    (caps the rewrite-call size; later runs catch the rest). `register` tunes which
    words count as tells (a novel keeps its em-dash and 'realm').
    """
    tre = _tell_re(register)
    flagged: list[tuple[int, int, str]] = []
    for s_start, s_end in _prose_spans(text):
        segment = text[s_start:s_end]
        pos = 0
        for sent in _SENT_SPLIT.split(segment):
            if not sent:
                continue
            idx = segment.index(sent, pos)   # always advances - duplicates can't re-match
            pos = idx + len(sent)
            if tre.search(sent):
                start = s_start + idx
                clean = sent.rstrip("\n")   # span must match the stored text exactly,
                flagged.append((start, start + len(clean), clean))  # or splicing eats the newline
                if len(flagged) >= cap:
                    return flagged
    return flagged


def _rewrite_ok(old: str, new: str, tre=None) -> bool:
    """Guard one rewrite: meaning-bearing tokens must survive, length must be sane.

    - inline citation markers [n] preserved exactly (same multiset)
    - all numbers preserved (same multiset - a paraphrase must not drift "100ms")
    - length within 0.4-2.5x of the original
    - the tell is actually gone (otherwise splicing is pointless churn)

    `tre` is the tell matcher (defaults to the register-neutral _TELL_RE).
    """
    tre = tre or _TELL_RE
    if not new or not new.strip():
        return False
    if sorted(_CITE_MARKS.findall(old)) != sorted(_CITE_MARKS.findall(new)):
        return False
    if sorted(_NUMBERS.findall(old)) != sorted(_NUMBERS.findall(new)):
        return False
    ratio = len(new) / max(len(old), 1)
    if not (0.4 <= ratio <= 2.5):
        return False
    return not tre.search(new)


def humanize(cfg: ModelConfig, text: str, register: str | None = None) -> str:
    """Surgical de-tell pass: detect → rewrite only flagged sentences → guard → splice.

    The committed draft is the source of truth; this can only swap individual
    sentences whose rewrites pass the guard. Any failure (network, parse, guard)
    leaves the original sentence in place, and the deterministic typographic pass
    always runs last. `register` tailors the tell set and keeps em-dashes where the
    register treats them as voice (fiction/poetry/essay).
    """
    allow_em = registers.get(register).allow_em_dash
    if _fake_mode():
        return mechanical_clean(text, allow_em)
    flagged = find_tell_sentences(text, register=register)
    if not flagged:
        return mechanical_clean(text, allow_em)

    numbered = "\n".join(f"[{i + 1}] {sent}" for i, (_, _, sent) in enumerate(flagged))
    try:
        out = complete_structured(
            cfg.model_for("humanizer"), P.humanizer_surgical_sys(register),
            "Rewrite each flagged sentence minimally:\n\n" + numbered,
            S.LineEdits, max_tokens=8000,
            temperature=cfg.temperature_for("humanizer"))
        rewrites = {e.index: e.text.strip() for e in out.edits}
    except Exception:  # noqa: BLE001 - the mechanical pass is a safe fallback
        return mechanical_clean(text, allow_em)

    # Splice from the end so earlier spans stay valid.
    tre = _tell_re(register)
    result = text
    for i in range(len(flagged) - 1, -1, -1):
        start, end, old = flagged[i]
        new = rewrites.get(i + 1)
        if new and _rewrite_ok(old, new, tre):
            result = result[:start] + new + result[end:]
    return mechanical_clean(result, allow_em)


# ── Deterministic style metrics (computed evidence for the critic) ────────────
def structural_report(text: str, register: str | None = None) -> str:
    """Compact, computed style metrics: structural tells a lexicon can't catch.

    Delegates to craft.report, which selects the metric set from the writing register
    (registers.py). `register=None` reproduces the historical nonfiction metrics
    (paragraph-length uniformity, rule-of-three density, wrap-up closers, specificity
    density) plus the universal additions (sentence rhythm, passive, adverbs, reading
    level, clichés, opening line). Fiction/poetry/screenplay swap in filter-verbs,
    dialogue ratio, said-bookisms, POV/tense, and sensory density.
    """
    from . import craft
    return craft.report(text, register)
