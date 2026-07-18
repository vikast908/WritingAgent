"""Shared TUI helpers: the theme registry + active palette, a console factory that
honors NO_COLOR / --plain, and small pure renderers (phase stepper, efficacy bar,
"did you mean", word count / reading time). Imported by both shell.py and cli.py
so the one-shot CLI and the interactive REPL render consistently.
"""
from __future__ import annotations

import difflib
import os
import re

# ── themes ────────────────────────────────────────────────────────────────────
# Every theme defines the same palette keys; apply_theme() rebinds the module-level
# constants (GOLD, INK, ...) that every renderer reads. "editorial" is the default:
# ONE warm accent used sparingly, and red/yellow/green reserved for status semantics
# (error / warning / ok) so the run dashboard stays readable at a glance. The rest
# are personality themes - kazama deliberately spends the warm band on its flame.
# The editorial defaults double as the static module bindings (linters and
# import-time from-imports see real names); apply_theme() rebinds them live.
# A theme changes EVERYTHING: the full palette, the wordmark's figlet FACE
# (FONT/WORDS/SHEAR), the gradient STOPS, the body-text tint, and the fleuron.
# Each theme owns a DIFFERENT hue family so they're distinguishable at a glance:
# editorial=ink & brass · kazama=flame · supabase=emerald · violet-bloom=purple ·
# t3-chat=pink · starry-night=indigo+gold · vercel=monochrome · fallout=CRT
# amber · mimi=rose pastels · astrovista=mars rust.
GOLD = "#c9a227"     # primary accent - commands, headings, prompt (gold)
GOLD_HI = "#e2c65a"  # lit accent - highlights (lit gold)
INK = "#b0812f"      # brass - tagline / secondary values
PARCH = "#e6ddc9"    # warm parchment - body text
DIM = "grey54"       # secondary
RULE = "#5c4a2e"     # dark brass - rules / borders
ERR = "#c23b2b"      # manuscript red - errors (semantic)
ON_CLR = "#5aa07f"   # sage green - feature on / done (semantic)
OFF_CLR = "grey50"   # feature off
FLEURON = "❧"
STOPS = ("#8f2a18", "#bf5a2e", "#d9b84a")   # wordmark gradient - oxblood → terracotta → gold
FONT = "ansi_shadow"                        # wordmark figlet face
WORDS = ("WRITING", "AGENT")                # wordmark words (case matters per face)
SHEAR = False                               # italic lean (block faces only)

THEMES: dict[str, dict] = {
    "editorial": dict(
        GOLD=GOLD, GOLD_HI=GOLD_HI, INK=INK, PARCH=PARCH,
        DIM=DIM, RULE=RULE, ERR=ERR, ON_CLR=ON_CLR,
        OFF_CLR=OFF_CLR, FLEURON=FLEURON, STOPS=STOPS,
        FONT=FONT, WORDS=WORDS, SHEAR=SHEAR,
        DESC="ink & brass - manuscript red + gold on parchment, semantic status",
    ),
    "highcontrast": dict(
        # Okabe-Ito palette - distinguishable for all common types of colour-blindness.
        # Status is NOT red/green: "on/ok" is blue, "error" is vermillion, so they never
        # collide for red-green CVD. Paired with white text for maximum contrast.
        GOLD="#0072B2", GOLD_HI="#56B4E9", INK="#E69F00", PARCH="#FFFFFF",
        DIM="#9a9a9a", RULE="#5a5a5a", ERR="#D55E00", ON_CLR="#0072B2",
        OFF_CLR="#9a9a9a", FLEURON="✒",
        STOPS=("#0072B2", "#56B4E9", "#F0E442"),
        FONT="ansi_regular", WORDS=("WRITING", "AGENT"), SHEAR=False,
        DESC="high-contrast, colourblind-safe (Okabe-Ito; blue = ok, vermillion = error)",
    ),
    "kazama": dict(
        GOLD="#ff7a18", GOLD_HI="#ffd23f", INK="#d4452f", PARCH="#e8ddd0",
        DIM="grey54", RULE="#7a1208", ERR="#ff4d3d", ON_CLR="#ffd23f",
        OFF_CLR="grey50", FLEURON="❧",
        STOPS=("#e8240c", "#ff7a18", "#ffd23f"),
        FONT="ansi_shadow", WORDS=("WRITING", "AGENT"), SHEAR=True,
        DESC="Jin Kazama - flame gradient, Tekken italic lean",
    ),
    "supabase": dict(
        GOLD="#3ecf8e", GOLD_HI="#7ce8b5", INK="#9fb8ad", PARCH="#cfe5d8",
        DIM="grey54", RULE="#1f4636", ERR="#e06c75", ON_CLR="#3ecf8e",
        OFF_CLR="grey50", FLEURON="◆",
        STOPS=("#0c7a4d", "#3ecf8e", "#7ce8b5"),
        FONT="ansi_regular", WORDS=("WRITING", "AGENT"), SHEAR=False,
        DESC="emerald on midnight - flat dashboard green",
    ),
    "violet-bloom": dict(
        GOLD="#8b5cf6", GOLD_HI="#c4b5fd", INK="#bf7fbf", PARCH="#ded5f2",
        DIM="grey54", RULE="#3b2a5e", ERR="#e06c75", ON_CLR="#6aaa5c",
        OFF_CLR="grey50", FLEURON="✿",
        STOPS=("#5b21b6", "#8b5cf6", "#c4b5fd"),
        FONT="mono12", WORDS=("Writing", "Agent"), SHEAR=False,
        DESC="violet bloom - royal purple, soft rounded face",
    ),
    "t3-chat": dict(
        GOLD="#ec4899", GOLD_HI="#f9a8d4", INK="#a78bfa", PARCH="#f2d9e5",
        DIM="grey54", RULE="#59243f", ERR="#ff6b6b", ON_CLR="#6aaa5c",
        OFF_CLR="grey50", FLEURON="♥",
        STOPS=("#9d174d", "#ec4899", "#f9a8d4"),
        FONT="smblock", WORDS=("WRITING", "AGENT"), SHEAR=False,
        DESC="t3 chat - hot pink, light bubbly face",
    ),
    "starry-night": dict(
        GOLD="#ffd86b", GOLD_HI="#ffeaa6", INK="#5b8dd9", PARCH="#cfdcf2",
        DIM="grey54", RULE="#27355c", ERR="#e06c75", ON_CLR="#6aaa5c",
        OFF_CLR="grey50", FLEURON="✶",
        STOPS=("#1e3a6e", "#5b8dd9", "#ffd86b"),
        FONT="elite", WORDS=("WRITING", "AGENT"), SHEAR=False,
        DESC="starry night - gold stars on van Gogh indigo, deco face",
    ),
    "vercel": dict(
        GOLD="#ededed", GOLD_HI="#ffffff", INK="#888888", PARCH="#c8c8c8",
        DIM="grey54", RULE="#333333", ERR="#ff4444", ON_CLR="#50e3c2",
        OFF_CLR="grey50", FLEURON="▲",
        STOPS=("#555555", "#ededed", "#ffffff"),
        FONT="smmono9", WORDS=("WRITING", "AGENT"), SHEAR=False,
        DESC="vercel - monochrome minimal, hairline face",
    ),
    # tweakcn imports (dark variants) - palettes from tweakcn.com/themes/<id>
    "fallout": dict(
        GOLD="#ffcc00", GOLD_HI="#ffe97a", INK="#00ff66", PARCH="#e0d5a0",
        DIM="grey54", RULE="#5d4a00", ERR="#ff4444", ON_CLR="#00ff66",
        OFF_CLR="grey50", FLEURON="►",
        STOPS=("#8a6d00", "#ffcc00", "#ffe97a"),
        FONT="pagga", WORDS=("WRITING", "AGENT"), SHEAR=False,
        DESC="fallout - pip-boy amber phosphor, terminal green, scanline face",
    ),
    "mimi": dict(
        GOLD="#e4a2b1", GOLD_HI="#fbe2a7", INK="#50afb6", PARCH="#f3e3ea",
        DIM="grey54", RULE="#324859", ERR="#e06c75", ON_CLR="#6aaa5c",
        OFF_CLR="grey50", FLEURON="♡",
        STOPS=("#c67b96", "#e4a2b1", "#fbe2a7"),
        FONT="double_blocky", WORDS=("WRITING", "AGENT"), SHEAR=False,
        DESC="mimi - dusky rose, cream and teal pastels, tiny playful face",
    ),
    "astrovista": dict(
        GOLD="#c14a24", GOLD_HI="#e58a5f", INK="#85a6c7", PARCH="#dfe3e8",
        DIM="grey54", RULE="#2a3656", ERR="#ef4444", ON_CLR="#6aaa5c",
        OFF_CLR="grey50", FLEURON="✧",
        STOPS=("#284167", "#c14a24", "#e58a5f"),
        FONT="delta_corps_priest_1", WORDS=("WRITING", "AGENT"), SHEAR=False,
        DESC="astrovista - mars rust over deep-space navy, sci-fi face",
    ),
}
DEFAULT_THEME = "editorial"
_PALETTE_KEYS = ("GOLD", "GOLD_HI", "INK", "PARCH", "DIM", "RULE", "ERR",
                 "ON_CLR", "OFF_CLR", "FLEURON", "STOPS", "FONT", "WORDS", "SHEAR")

current_theme = DEFAULT_THEME


def apply_theme(name: str) -> str:
    """Activate a theme by rebinding this module's palette constants.

    Unknown names fall back to the default. Returns the name actually applied.
    NOTE: shell.py from-imports these names, so after a LIVE switch it must call
    its `_sync_palette()`; at startup (cli.main applies the theme before shell is
    imported) the import picks the themed values up naturally.
    """
    global current_theme
    applied = name if name in THEMES else DEFAULT_THEME
    theme = THEMES[applied]
    globals().update({k: theme[k] for k in _PALETTE_KEYS})
    current_theme = applied
    return applied


def lerp_hex(a: str, b: str, t: float) -> str:
    """Linear blend between two #rrggbb colors, t in [0, 1]."""
    ca = [int(a.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    cb = [int(b.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    r, g, bl = (round(ca[i] + (cb[i] - ca[i]) * t) for i in range(3))
    return f"#{r:02x}{g:02x}{bl:02x}"


def flame_color(t: float, stops: tuple[str, ...] | None = None) -> str:
    """Sample the active theme's gradient: t=0 -> first stop ... t=1 -> last."""
    if stops is None:
        stops = STOPS
    t = max(0.0, min(1.0, t))
    segs = len(stops) - 1
    if segs <= 0:
        return stops[0]
    pos = t * segs
    i = min(int(pos), segs - 1)
    return lerp_hex(stops[i], stops[i + 1], pos - i)


apply_theme(DEFAULT_THEME)   # bind GOLD/INK/... at import time

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


# Slang-tolerant yes/no so confirmations accept "yeah", "yep", "sure", "nah".
_AFFIRM = frozenset({
    "y", "yes", "yeah", "yep", "yup", "ya", "yah", "yas", "sure", "ok", "okay",
    "k", "kk", "aye", "affirmative", "absolutely", "definitely", "please", "do",
    "fine", "true", "1", "on", "go",
})
_NEGATE = frozenset({
    "n", "no", "nope", "nah", "naw", "nay", "never", "negative", "dont", "stop",
    "cancel", "abort", "false", "0", "off",
})


def is_affirmative(text: str, *, default: bool = False) -> bool:
    """Whether `text` reads as yes (slang-tolerant). Empty input -> `default`,
    so a bare Enter respects the prompt's [Y/n] vs [y/N] hint."""
    t = (text or "").strip().lower().strip(".!,")
    if not t:
        return default
    if t in _AFFIRM or t.split()[0] in _AFFIRM:    # "do it", "go ahead", "yes please"
        return True
    if t in _NEGATE or t.split()[0] in _NEGATE:
        return False
    return default


def smart_match(query, options, *, aliases=None, cutoff: float = 0.6):
    """Resolve `query` to one of `options`, returning (match | None, candidates).

    Tries, in order: alias table -> exact -> unique prefix -> unique substring ->
    fuzzy. When several options tie, `match` is None and `candidates` holds them
    for the caller to offer. Lets users type a short, approximate name instead of
    the exact one. `aliases` maps a typed word to a canonical option."""
    opts = list(options)
    q = (query or "").strip().lower()
    if not q:
        return None, []
    if aliases and q in aliases:
        return aliases[q], []
    lower = {o.lower(): o for o in opts}
    if q in lower:
        return lower[q], []
    pre = [o for o in opts if o.lower().startswith(q)]
    if len(pre) == 1:
        return pre[0], []
    sub = [o for o in opts if q in o.lower()]
    if len(sub) == 1:
        return sub[0], []
    if len(pre) > 1:
        return None, pre
    if len(sub) > 1:
        return None, sub
    m = difflib.get_close_matches(q, list(lower), n=3, cutoff=cutoff)
    cands = [lower[x] for x in m]
    return (cands[0], []) if len(cands) == 1 else (None, cands)


def word_count(text: str | None) -> int:
    return len(text.split()) if text else 0


def explain_error(exc) -> str | None:
    """A friendly, recoverable one-liner for a recognised failure, or None to fall back to
    the raw error. Maps the handful of failures users actually hit (bad/missing key,
    rate-limit, network blip, locked file) to a clear next step instead of a stack-trace-y
    `RuntimeError: ...`. Progress is always saved, so every hint says 'run again'."""
    s = f"{type(exc).__name__}: {exc}".lower()
    if any(k in s for k in ("401", "unauthorized", "invalid api key", "authentication", "no auth")):
        return "API key looks invalid or missing — check it in .env (or /provider to switch host)."
    if any(k in s for k in ("429", "rate limit", "rate-limit", "too many requests", "quota")):
        return "Rate-limited by the provider — wait a moment, then run again (progress is saved)."
    if any(k in s for k in ("timeout", "timed out", "connection", "network", "getaddrinfo",
                            "ssl", "temporarily unavailable", "502", "503", "connect")):
        return "Network/provider hiccup — check your connection, then run again (saved & resumable)."
    if any(k in s for k in ("permission", "another process", "being used", "in use", "locked")):
        return "A file is locked (open in another program?) — close it, then try again."
    if any(k in s for k in ("context length", "context_length", "maximum context", "context window",
                            "too many tokens", "reduce the length", "string too long")):
        return ("Prompt outgrew the model's context window — try a smaller context "
                "(`/set max_context_chars 16000`) or split into more, shorter units; progress is saved.")
    if any(k in s for k in ("budget", "max_run_tokens", "token budget")):
        return ("Run token budget reached — lift it with `/set max_run_tokens 0` (0 = unlimited), "
                "then run again (everything committed is saved).")
    return None


def trust_chip(raw: str) -> str:
    """Normalize a critic verdict line ('verdict=approve confidence=0.50 blocking=1
    insight=5') into a glanceable chip: '✓ approved · insight 5/5 · confidence ●●●○○'.

    Invariant: a blocking issue NEVER reads as a bare 'approve' - the captured
    'verdict=approve … blocking=1' looked broken, so any blocking count wins and the
    chip shows it as 'revising'. Unparseable input falls back to the raw string."""
    g = dict(re.findall(r"(\w+)=([\w.]+)", raw or ""))
    if not g:
        return (raw or "").strip()
    verdict = (g.get("verdict") or "").lower()
    try:
        blocking = int(float(g.get("blocking", 0) or 0))
    except ValueError:
        blocking = 0
    if blocking > 0 or verdict in ("revise", "reject"):
        sym, label = "↻", "revising"
    elif verdict == "approve":
        sym, label = "✓", "approved"
    else:
        sym, label = "·", (verdict or "reviewed")
    parts = [f"{sym} {label}"]
    try:
        parts.append(f"insight {int(float(g['insight']))}/5")
    except (KeyError, ValueError):
        pass
    try:
        n = max(0, min(5, round(float(g["confidence"]) * 5)))
        parts.append("confidence " + "●" * n + "○" * (5 - n))
    except (KeyError, ValueError):
        pass
    if blocking > 0:
        parts.append(f"{blocking} blocking")
    return " · ".join(parts)


def reading_time_min(words_or_text) -> int:
    """Minutes to read. Pass the manuscript TEXT (str) for an accurate prose-only
    estimate - fenced code and the references list are excluded; pass an int for a
    raw word count (legacy live estimate, may overcount code-heavy drafts)."""
    from . import polish
    if isinstance(words_or_text, str):
        return polish.read_time_min(words_or_text)
    return max(1, round((words_or_text or 0) / polish.READ_WPM))


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
