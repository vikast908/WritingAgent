"""The REPL core: input routing, slash dispatch, the prompt-toolkit session, run_shell."""
from __future__ import annotations

import shlex

from .. import brain
from .. import skills as skills_mod
from ..config import ModelConfig, Settings
from ..ui import ERR, GOLD, INK, ON_CLR
from ._const import (
    _EXIT,
    _FLEURON,
    _NIB,
    _SLASH_WORDS,
    _STRONG_SLASH,
)
from .branding import _banner, _first_run_setup, _make_console, _out, _welcome
from .chat import _chat_respond, _show_post_hint
from .dispatch import _dispatch_command
from .session import _make_pt_session
from .slash import _handle_slash

__all__ = [
    '_prompt_state',
    'run_shell',
]


def _prompt_state(state: dict) -> str:
    """Return a short Rich-markup suffix for the shell prompt."""
    book = state.get("book")
    if not book:
        return ""
    try:
        from ..brain import ArticlePaths, BookPaths
        art = ArticlePaths(book, state["uid"])
        if art.run_state.exists():
            st = brain.read_json(art.run_state) or {}
            mode_sfx = f" [{INK}]article[/]"
        else:
            st = brain.read_json(BookPaths(book, state["uid"]).run_state) or {}
            mode_sfx = ""
        if st.get("pending_review"):
            return f"{mode_sfx} [bold {ERR}]![/]"
        if st.get("phase") == "done":
            return f"{mode_sfx} [{ON_CLR}]✓[/]"
        return mode_sfx
    except Exception:
        pass
    return ""

def run_shell(parser, commands, cfg: ModelConfig, settings: Settings) -> None:
    known_commands: set[str] = set(commands.keys())
    state: dict = {
        "uid": settings.default_user,
        "book": None,
        "chat_history": [],       # multi-turn context (last _MAX_HISTORY messages)
        "last_chat": None,        # most recent user chat message, for /retry
        "_parser": parser,        # for NL→command execution from chat
        "_commands": commands,
        "_known_commands": known_commands,
    }
    skills_mod.seed_builtin(state["uid"])
    console = _make_console()
    pt_session, patch_stdout = _make_pt_session(known_commands, state, cfg, settings)

    _banner(console, cfg, settings)
    _first_run_setup(console, settings)   # offer key / free-mode before the welcome reflects it
    _welcome(console, cfg, settings, state["uid"])

    while True:
        slug = cfg.model_for("writer").split("/")[-1]
        book = state["book"]

        # Build prompt string
        global_mode = settings.mode   # "book" or "article" - the NEW-project default
        if pt_session:
            # prompt_toolkit renders ANSI - use plain text with a trailing space
            book_part = f" · {book}" if book else ""
            sfx_plain = ""
            if book:
                try:
                    from ..brain import BookPaths
                    st = brain.read_json(BookPaths(book, state["uid"]).run_state) or {}
                    if st.get("pending_review"):
                        sfx_plain = " !"
                    elif st.get("phase") == "done":
                        sfx_plain = " done"
                    elif st.get("mode") == "article":
                        sfx_plain = " [article]"
                except Exception:
                    pass
            elif global_mode == "article":
                sfx_plain = " [article]"  # no active book - show global mode
            prompt_plain = f"\n{_NIB} {slug}{book_part}{sfx_plain} "
        elif console:
            status_sfx = _prompt_state(state) if book else ""
            mode_tag = f" [{INK}]article[/]" if not book and global_mode == "article" else ""
            prompt_plain = (f"\n[{GOLD}]{_FLEURON}[/] "
                            f"[dim]{slug}{(' · ' + book) if book else ''}[/]"
                            f"{status_sfx}{mode_tag} ")
        else:
            prompt_plain = "\n> "

        try:
            if pt_session:
                if console:
                    console.file.flush()
                with patch_stdout(raw=True):
                    line = pt_session.prompt(prompt_plain).strip()
            else:
                line = (console.input(prompt_plain) if console else input(prompt_plain)).strip()
        except (EOFError, KeyboardInterrupt):
            # Ctrl+C / Ctrl+D at the idle prompt QUIT the app (like every shell). A ^C
            # DURING a run pauses the pipeline instead - that's caught deeper (dispatch/
            # dashboard), not here.
            break
        if not line:
            continue
        if line in _EXIT:
            break

        # ── Escape hatch: `\` forces the rest to the chat assistant ─────────────
        # (so a sentence opening with a command word can still be chatted).
        if line.startswith("\\"):
            _chat_respond(line[1:].lstrip(), console, cfg, settings, state)
            continue

        # ── Slash command ──────────────────────────────────────────────────────
        if line.startswith("/"):
            if not _handle_slash(line, console, cfg, settings, state):
                break
            continue

        # ── Parse as a book command if the first word is recognised ───────────
        try:
            argv = shlex.split(line)
        except ValueError:
            # shlex failed (backslash at end, unmatched quote, etc.) - treat as chat
            argv = []

        first = argv[0] if argv else ""
        if first in known_commands:
            _dispatch_command(
                argv, console, cfg, settings, state, interactive=True, line=line,
                on_extras=lambda ln: _chat_respond(ln, console, cfg, settings, state),
                on_done=lambda: _show_post_hint(console, state, settings),
            )
            continue

        # ── Reserved command word typed without its slash → run it, don't chat it ─
        fl = first.lower()
        if fl in _SLASH_WORDS and (len(argv) == 1 or fl in _STRONG_SLASH):
            _out(console, f"[dim]‹{first}› is a slash command — running /{fl}.  "
                          f"(meant to chat? prefix the line with \\)[/]")
            if not _handle_slash("/" + line, console, cfg, settings, state):
                break
            continue

        # ── Everything else → conversational assistant ────────────────────────
        _chat_respond(line, console, cfg, settings, state)

    _out(console, f"[dim]{_FLEURON} closed.[/]")
