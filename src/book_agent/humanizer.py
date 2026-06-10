"""Humanizer: strip common AI-written tells while preserving meaning (and code)."""
from __future__ import annotations

import re

from . import prompts as P
from .config import ModelConfig
from .llm import _fake_mode, complete_text

# Only [ \t] around the dash - must NOT eat newlines, or an em-dash at a line end
# would merge two lines/paragraphs into one.
_DASH = re.compile(r"[ \t]*[—–][ \t]*")  # em / en dash
_QUOTES = {"“": '"', "”": '"', "‘": "'", "’": "'",
           "…": "...", " ": " "}


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


def humanize(cfg: ModelConfig, text: str) -> str:
    """LLM rewrite to remove AI tells, then a deterministic typographic safety net.

    If the rewrite call fails (network/timeout/empty), fall back to the deterministic
    pass rather than aborting the chapter right before commit.
    """
    if _fake_mode():
        return mechanical_clean(text)
    try:
        rewritten = complete_text(cfg.model_for("humanizer"), P.HUMANIZER_SYS, text,
                                  max_tokens=16000, temperature=cfg.temperature_for("humanizer"))
    except Exception:  # noqa: BLE001 - the mechanical pass is a safe fallback
        return mechanical_clean(text)
    return mechanical_clean(rewritten)
