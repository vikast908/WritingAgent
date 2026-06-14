"""Interactive REPL/TUI for WRITING AGENT (run `writing-agent` / `book` / `python book.py`).

Aesthetic: themed (see ui.THEMES; /theme to switch). The default "editorial" theme is
ink & brass - one warm accent, semantic status colors, a gradient-filled wordmark,
fleuron section markers, and clean borderless command tables. Alternates: kazama
(Jin Kazama flame), shakespeare, poe, gatsby.

Lines starting with `/` are slash commands; recognised book-command words dispatch to the
one-shot CLI; anything else is routed to the built-in conversational assistant (DeepSeek Flash).
"""
from __future__ import annotations

from ..ui import (  # noqa: F401 - re-exported as shell.X; refreshed live by _sync_palette
    DIM,
    ERR,
    GOLD,
    GOLD_HI,
    INK,
    OFF_CLR,
    ON_CLR,
    PARCH,
    RULE,
)
from ._const import *  # noqa: F401,F403
from .branding import *  # noqa: F401,F403
from .chat import *  # noqa: F401,F403
from .commands import *  # noqa: F401,F403
from .dashboard import *  # noqa: F401,F403
from .dispatch import *  # noqa: F401,F403
from .help import *  # noqa: F401,F403
from .repl import *  # noqa: F401,F403
from .session import *  # noqa: F401,F403
from .slash import *  # noqa: F401,F403
