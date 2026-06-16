"""Generalized surgical craft passes (plan §22, Tier 2).

The humanizer proved the pattern, and this generalizes it: detect a craft defect
deterministically, send ONLY the flagged sentences to the model for a minimal rewrite,
guard each rewrite (citations + numbers preserved, length sane, the defect actually
reduced, no new slop introduced), and splice. The approved draft is never regenerated
end-to-end, so a Flash-model micro-edit cannot drift facts or regress the whole unit.

Two passes today:
- show_dont_tell: filter verbs ('she saw', 'he felt') and told emotion ('she was afraid')
  → the concrete image/action that earns it. The single biggest lever for believable
  fiction, and the backbone of the "emotions" work (see docs/proposal-personas-emotions).
- de_passive: passive voice → active where active reads better.

Which passes run is chosen by the writing register (registers.py): fiction-shaped registers
get show-don't-tell; prose registers get de-passive. In fake/offline mode every pass is a
no-op (no model call), so tests and key-less runs are unaffected.
"""
from __future__ import annotations

import re

from . import craft, humanizer, registers
from . import prompts as P
from . import schemas as S
from .config import ModelConfig
from .llm import _fake_mode, complete_structured

# Told emotion: a copula/transition verb followed by a named feeling - the classic "tell".
_TOLD_EMOTION = re.compile(
    r"\b(?:was|were|felt|feels|looked|seemed|grew|became|is|are)\s+"
    r"(?:very |so |quite |really |rather |a bit )?"
    r"(?:afraid|scared|angry|furious|mad|sad|happy|glad|joyful|nervous|anxious|excited|"
    r"terrified|relieved|embarrassed|ashamed|proud|confused|surprised|worried|calm|"
    r"frightened|delighted|miserable|lonely|content|annoyed|frustrated)\b",
    re.IGNORECASE)
# Show-don't-tell targets either a filter verb or a told emotion.
_TELLING_RE = re.compile(f"(?:{craft._FILTER_RE.pattern})|(?:{_TOLD_EMOTION.pattern})", re.IGNORECASE)


def _find(text: str, pattern: re.Pattern, cap: int = 30) -> list[tuple[int, int, str]]:
    """Sentences outside code fences matching `pattern`, as (start, end, sentence) spans."""
    out: list[tuple[int, int, str]] = []
    for s_start, s_end in humanizer._prose_spans(text):
        segment = text[s_start:s_end]
        pos = 0
        for sent in humanizer._SENT_SPLIT.split(segment):
            if not sent:
                continue
            idx = segment.index(sent, pos)
            pos = idx + len(sent)
            if pattern.search(sent):
                start = s_start + idx
                clean = sent.rstrip("\n")
                out.append((start, start + len(clean), clean))
                if len(out) >= cap:
                    return out
    return out


def _guard(old: str, new: str, defect_re: re.Pattern, *, max_ratio: float = 3.0) -> bool:
    """Accept a rewrite only if it preserves meaning-bearing tokens and actually helps.

    - inline [n] citations preserved exactly (same multiset)
    - all numbers preserved (same multiset)
    - length within 0.4-max_ratio x (show-don't-tell may lengthen, so the cap is generous)
    - the targeted defect count strictly decreases (otherwise it's pointless churn)
    - no NEW anti-slop tell is introduced by the rewrite
    """
    if not new or not new.strip():
        return False
    if sorted(humanizer._CITE_MARKS.findall(old)) != sorted(humanizer._CITE_MARKS.findall(new)):
        return False
    if sorted(humanizer._NUMBERS.findall(old)) != sorted(humanizer._NUMBERS.findall(new)):
        return False
    ratio = len(new) / max(len(old), 1)
    if not (0.4 <= ratio <= max_ratio):
        return False
    if len(defect_re.findall(new)) >= len(defect_re.findall(old)):
        return False
    return not humanizer._TELL_RE.search(new)


def _run(cfg: ModelConfig, text: str, flagged, system: str, defect_re: re.Pattern,
         *, max_ratio: float = 3.0) -> str:
    if not flagged:
        return text
    numbered = "\n".join(f"[{i + 1}] {sent}" for i, (_, _, sent) in enumerate(flagged))
    try:
        out = complete_structured(
            cfg.model_for("humanizer"), system,
            "Rewrite each flagged sentence:\n\n" + numbered, S.LineEdits, max_tokens=8000,
            temperature=cfg.temperature_for("humanizer"))
        rewrites = {e.index: e.text.strip() for e in out.edits}
    except Exception:  # noqa: BLE001 - leave the prose untouched on any failure
        return text
    result = text
    for i in range(len(flagged) - 1, -1, -1):   # splice from the end so spans stay valid
        start, end, old = flagged[i]
        new = rewrites.get(i + 1)
        if new and _guard(old, new, defect_re, max_ratio=max_ratio):
            result = result[:start] + new + result[end:]
    return result


def show_dont_tell(cfg: ModelConfig, text: str) -> str:
    """Replace filter verbs and told emotion with the concrete image/action (fiction)."""
    if _fake_mode():
        return text
    return _run(cfg, text, _find(text, _TELLING_RE), P.SHOW_DONT_TELL_SYS, _TELLING_RE)


def de_passive(cfg: ModelConfig, text: str) -> str:
    """Rewrite passive sentences active where active reads better."""
    if _fake_mode():
        return text
    return _run(cfg, text, _find(text, craft._PARTICIPLE), P.DE_PASSIVE_SYS,
                craft._PARTICIPLE, max_ratio=2.5)


def apply(cfg: ModelConfig, text: str, register: str | None = None) -> str:
    """Run the register-appropriate surgical passes on an approved draft.

    Fiction-shaped registers (those that track filter verbs / sensory density) get
    show-don't-tell; prose registers get de-passive. Poetry and screenplay are skipped
    (fragments and present-tense action make both detectors noisy). No-op in fake mode.
    """
    if _fake_mode():
        return text
    reg = registers.get(register)
    out = text
    if "filter_words" in reg.metrics or "concrete_sensory" in reg.metrics:
        out = show_dont_tell(cfg, out)
    if reg.name not in ("poetry", "screenplay"):
        out = de_passive(cfg, out)
    return out
