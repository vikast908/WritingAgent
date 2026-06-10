"""Shared TUI helpers: the editorial palette, a console factory that honors
NO_COLOR / --plain, and small pure renderers (phase stepper, efficacy bar,
"did you mean", word count / reading time). Imported by both shell.py and cli.py
so the one-shot CLI and the interactive REPL render consistently.
"""
from __future__ import annotations

import difflib
import os

# ── palette: ink & gilt (editorial) ──────────────────────────────────────────
GOLD = "#ff6719"     # brand orange — wordmark + accents
GOLD_HI = "#ff8c4b"  # lit orange — gradient top
INK = "#7c9cbf"      # slate ink-blue — tagline / values
PARCH = "#d9cfb8"    # parchment — body text
DIM = "grey42"       # secondary
RULE = "#8c3a10"     # dim burnt-orange — rules
ERR = "#a8533a"      # burgundy — errors
ON_CLR = "#6aaa5c"   # muted green — feature on / done
OFF_CLR = "grey50"   # feature off
FLEURON = "❧"

_FORCE_PLAIN = False


def set_plain(on: bool) -> None:
    """Force monochrome output (set from --plain); NO_COLOR env is also honored."""
    global _FORCE_PLAIN
    _FORCE_PLAIN = on


def plain_mode() -> bool:
    return _FORCE_PLAIN or bool(os.getenv("NO_COLOR"))


def make_console():
    try:
        from rich.console import Console
        return Console(no_color=plain_mode())
    except ImportError:
        return None


def did_you_mean(word: str, options, cutoff: float = 0.6) -> str | None:
    m = difflib.get_close_matches(word, list(options), n=1, cutoff=cutoff)
    return m[0] if m else None


def word_count(text: str | None) -> int:
    return len(text.split()) if text else 0


def reading_time_min(words: int) -> int:
    return max(1, round(words / 200))


# Phase pipelines for the status stepper.
PHASES_BOOK = ["chapters", "consolidate", "production", "learn", "done"]
PHASES_ARTICLE = ["sections", "produce", "learn", "done"]


def phase_stepper(phases: list[str], current: str):
    """A horizontal pipeline with the current phase lit, past dimmed-green, future dim."""
    from rich.text import Text
    try:
        cur_i = phases.index(current)
    except ValueError:
        cur_i = -1
    t = Text()
    for i, ph in enumerate(phases):
        if i < cur_i:
            t.append(f"✓ {ph}", style=ON_CLR)
        elif i == cur_i:
            t.append(f"● {ph}", style=f"bold {GOLD}")
        else:
            t.append(f"○ {ph}", style=DIM)
        if i < len(phases) - 1:
            t.append("  →  ", style=DIM)
    return t


def efficacy_bar(p_skill: float, p_base: float, width: int = 12):
    """A tiny bar comparing a skill's first-pass rate to the baseline."""
    from rich.text import Text
    filled = max(0, min(width, round(p_skill * width)))
    lift = p_skill - p_base
    color = ON_CLR if lift > 0.02 else (ERR if lift < -0.02 else DIM)
    t = Text()
    t.append("█" * filled, style=color)
    t.append("░" * (width - filled), style=DIM)
    t.append(f" {p_skill:.0%}", style=color)
    return t
