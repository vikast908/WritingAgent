"""Humanizer: strip common AI-written tells while preserving meaning (and code)."""
from __future__ import annotations

import re

from . import prompts as P
from .config import ModelConfig
from .llm import _fake_mode, complete_text

_DASH = re.compile(r"\s*[—–]\s*")  # em / en dash
_QUOTES = {"“": '"', "”": '"', "‘": "'", "’": "'",
           "…": "...", " ": " "}


def _clean_segment(s: str) -> str:
    for k, v in _QUOTES.items():
        s = s.replace(k, v)
    s = _DASH.sub(" - ", s)
    return re.sub(r"[ \t]{2,}", " ", s)


def mechanical_clean(text: str) -> str:
    """Deterministic typographic de-AI pass. Leaves fenced code blocks (```) untouched."""
    parts = text.split("```")
    for i in range(0, len(parts), 2):  # even segments are outside code fences
        parts[i] = _clean_segment(parts[i])
    return "```".join(parts)


def humanize(cfg: ModelConfig, text: str) -> str:
    """LLM rewrite to remove AI tells, then a deterministic typographic safety net."""
    if _fake_mode():
        return mechanical_clean(text)
    rewritten = complete_text(cfg.model_for("humanizer"), P.HUMANIZER_SYS, text,
                              max_tokens=16000, temperature=cfg.temperature_for("humanizer"))
    return mechanical_clean(rewritten)
