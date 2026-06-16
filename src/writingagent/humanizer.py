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

from . import prompts as P
from . import schemas as S
from . import slop
from .config import ModelConfig
from .llm import _fake_mode, complete_structured

# Only [ \t] around the dash - must NOT eat newlines, or an em-dash at a line end
# would merge two lines/paragraphs into one.
_DASH = re.compile(r"[ \t]*[—–][ \t]*")  # em / en dash
_QUOTES = {"“": '"', "”": '"', "‘": "'", "’": "'",
           "…": "...", " ": " "}


def _clean_segment(s: str) -> str:
    for k, v in _QUOTES.items():
        s = s.replace(k, v)
    s = _DASH.sub(" - ", s)
    return re.sub(r"[ \t]{2,}", " ", s)


def mechanical_clean(text: str) -> str:
    """Deterministic typographic de-AI pass. Leaves fenced code blocks (```) untouched.

    Tracks fences line-by-line so an unbalanced/odd number of ``` markers can't shift
    the parity and either mangle code or skip prose (the old naive split did both).
    """
    out: list[str] = []
    in_fence = False
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append(line)
        else:
            out.append(line if in_fence else _clean_segment(line))
    return "".join(out)


# ── Tell detection (the NO_SLOP lexicon, as code instead of prompt hope) ──────
# The pattern is GENERATED from slop.py (the single source the writer prompt is also
# generated from), so adding a banned word there updates this stripper too - no parallel
# hand-maintained regex to drift. The morphological rules (verb inflections, apostrophe
# tolerance, the "in today's [anything]" wildcard) live in slop.tell_pattern().
# slop.TECHNICAL_EXCEPTIONS ("optimize", "navigate") are absent by construction: in
# technical prose they are often the precise term - the LLM judge decides.
_TELL_RE = re.compile(slop.tell_pattern(), re.IGNORECASE)

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
_CITE_MARKS = re.compile(r"\[\d+\]")
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


def find_tell_sentences(text: str, cap: int = 40) -> list[tuple[int, int, str]]:
    """Sentences outside code fences that contain a detected tell.

    Returns (start, end, sentence) spans into `text`, at most `cap` of them
    (caps the rewrite-call size; later runs catch the rest).
    """
    flagged: list[tuple[int, int, str]] = []
    for s_start, s_end in _prose_spans(text):
        segment = text[s_start:s_end]
        pos = 0
        for sent in _SENT_SPLIT.split(segment):
            if not sent:
                continue
            idx = segment.index(sent, pos)   # always advances - duplicates can't re-match
            pos = idx + len(sent)
            if _TELL_RE.search(sent):
                start = s_start + idx
                clean = sent.rstrip("\n")   # span must match the stored text exactly,
                flagged.append((start, start + len(clean), clean))  # or splicing eats the newline
                if len(flagged) >= cap:
                    return flagged
    return flagged


def _rewrite_ok(old: str, new: str) -> bool:
    """Guard one rewrite: meaning-bearing tokens must survive, length must be sane.

    - inline citation markers [n] preserved exactly (same multiset)
    - all numbers preserved (same multiset - a paraphrase must not drift "100ms")
    - length within 0.4-2.5x of the original
    - the tell is actually gone (otherwise splicing is pointless churn)
    """
    if not new or not new.strip():
        return False
    if sorted(_CITE_MARKS.findall(old)) != sorted(_CITE_MARKS.findall(new)):
        return False
    if sorted(_NUMBERS.findall(old)) != sorted(_NUMBERS.findall(new)):
        return False
    ratio = len(new) / max(len(old), 1)
    if not (0.4 <= ratio <= 2.5):
        return False
    return not _TELL_RE.search(new)


def humanize(cfg: ModelConfig, text: str) -> str:
    """Surgical de-tell pass: detect → rewrite only flagged sentences → guard → splice.

    The committed draft is the source of truth; this can only swap individual
    sentences whose rewrites pass the guard. Any failure (network, parse, guard)
    leaves the original sentence in place, and the deterministic typographic pass
    always runs last.
    """
    if _fake_mode():
        return mechanical_clean(text)
    flagged = find_tell_sentences(text)
    if not flagged:
        return mechanical_clean(text)

    numbered = "\n".join(f"[{i + 1}] {sent}" for i, (_, _, sent) in enumerate(flagged))
    try:
        out = complete_structured(
            cfg.model_for("humanizer"), P.HUMANIZER_SURGICAL_SYS,
            "Rewrite each flagged sentence minimally:\n\n" + numbered,
            S.LineEdits, max_tokens=8000,
            temperature=cfg.temperature_for("humanizer"))
        rewrites = {e.index: e.text.strip() for e in out.edits}
    except Exception:  # noqa: BLE001 - the mechanical pass is a safe fallback
        return mechanical_clean(text)

    # Splice from the end so earlier spans stay valid.
    result = text
    for i in range(len(flagged) - 1, -1, -1):
        start, end, old = flagged[i]
        new = rewrites.get(i + 1)
        if new and _rewrite_ok(old, new):
            result = result[:start] + new + result[end:]
    return mechanical_clean(result)


# ── Deterministic style metrics (computed evidence for the critic) ────────────
_TRIAD = re.compile(r"\b\w+, \w+, and \w+\b")
_WRAPUP = re.compile(
    r"^(?:in short|ultimately|overall|in the end|in other words|simply put|the bottom line)\b",
    re.IGNORECASE)


def structural_report(text: str) -> str:
    """Compact, computed style metrics: structural tells a lexicon can't catch.

    Reported to the critic as evidence (not verdicts): paragraph-length uniformity,
    rule-of-three density, wrap-up closers, and specificity density (numbers +
    mid-sentence proper nouns per 100 words - a proxy for concrete-over-abstract).
    """
    prose = "\n".join(text[a:b] for a, b in _prose_spans(text))
    paras = [p.split() for p in re.split(r"\n\s*\n", prose) if p.strip() and not p.strip().startswith("#")]
    words = [w for p in paras for w in p]
    n_words = max(len(words), 1)

    lines = []
    if len(paras) >= 4:
        lens = [len(p) for p in paras]
        mean = sum(lens) / len(lens)
        var = sum((x - mean) ** 2 for x in lens) / len(lens)
        cv = (var ** 0.5) / mean if mean else 0
        lines.append(f"- paragraph lengths: {len(paras)} paragraphs, mean {mean:.0f} words, "
                     f"variation {cv:.2f} (under 0.30 reads machine-uniform)")
    triads = len(_TRIAD.findall(prose))
    lines.append(f"- rule-of-three constructions: {triads} per {n_words} words "
                 f"({'heavy' if triads > n_words / 250 else 'ok'})")
    wrapups = sum(1 for p in re.split(r"\n\s*\n", prose)
                  if p.strip() and _WRAPUP.match(p.strip().splitlines()[-1].strip()))
    if wrapups:
        lines.append(f"- {wrapups} paragraph(s) close with a summarizing wrap-up opener")
    numbers = len(_NUMBERS.findall(prose))
    proper = len(re.findall(r"(?<![.!?]\s)(?<!^)\b[A-Z][a-z]{2,}", prose))
    specificity = (numbers + proper) / n_words * 100
    lines.append(f"- specificity density: {specificity:.1f} concrete tokens "
                 f"(numbers + proper nouns) per 100 words "
                 f"({'low - prose may be generic' if specificity < 2.0 else 'ok'})")
    return "\n".join(lines)
