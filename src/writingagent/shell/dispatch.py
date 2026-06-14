"""Input interpretation for the REPL + chat assistant: confirmation detection,
project auto-pick, argv normalization, executable-command extraction, and
_execute_cmd (the chat assistant's guarded command runner)."""
from __future__ import annotations

import contextlib
import io
import re
import shlex

from .. import brain
from ..config import Settings
from ..ui import DIM, ERR, GOLD, INK, explain_error
from ._const import _CODE_BLOCK_RE
from .branding import _out
from .dashboard import _cmd_run_rich
from .slash import _handle_slash

__all__ = [
    '_NEEDS_PROJECT',
    '_CHAT_BLOCKED_CMDS',
    '_CHAT_BLOCKED_SLASH',
    '_CONFIRM_FILLER',
    '_CONFIRM_VOCAB',
    '_is_confirmation',
    '_auto_or_pick_project',
    '_normalize_argv',
    '_commands_in_response',
    '_chat_use_project',
    '_execute_cmd',
]


_NEEDS_PROJECT = {"run", "status", "read", "export", "review", "revise", "memory",
                   "delete", "produce", "consolidate", "versions", "brief",
                   "tableread", "eval"}

# The chat assistant must NOT silently auto-execute destructive or
# config/tenant-changing commands - the human has to type these. (The model may
# still mention them in prose.) `delete` = data loss; `/user` switches tenant;
# `/set` can disable human-in-the-loop (autonomous) and reroute models;
# `write` runs an interactive interview + a long autonomous run - the human starts it.
_CHAT_BLOCKED_CMDS = {"delete", "write"}
_CHAT_BLOCKED_SLASH = {"user", "set"}

# A chat-emitted `new` only executes on a turn where the user's own message was an
# explicit go-ahead. The model is *instructed* to propose first and wait (NEW TOPIC
# FLOW in _CHAT_SYSTEM), but prompts are advisory - this is the hard guarantee that
# a project is never created + run without the user saying so.
_CONFIRM_FILLER = {"please", "now", "and", "then", "the", "a", "an", "that", "this"}
_CONFIRM_VOCAB = {
    "go", "ahead", "run", "it", "yes", "yeah", "yep", "y", "ok", "okay", "sure",
    "start", "do", "proceed", "begin", "write", "writing", "confirm", "confirmed",
    "approve", "approved", "lgtm", "ship", "lets", "let's", "sounds", "looks",
    "good", "fine", "great", "perfect", "works", "until", "end", "finish", "all",
    "way", "everything",
}


def _is_confirmation(message: str) -> bool:
    """True when the message is a pure go-ahead ("run it", "yes - go ahead")."""
    words = [w for w in re.findall(r"[a-z']+", message.lower()) if w not in _CONFIRM_FILLER]
    return 0 < len(words) <= 6 and all(w in _CONFIRM_VOCAB for w in words)


def _auto_or_pick_project(uid: str, settings: Settings, console, state: dict) -> str | None:
    """Return the project_id to use, auto-picking when unambiguous.

    - If state["book"] is already set → return it.
    - If mode=article, prefer article projects; mode=book, prefer book projects.
    - If exactly 1 match → auto-set state["book"] and return it.
    - If multiple → show an inline numbered picker and wait for input.
    - If none → print a helpful message and return None.
    """
    if state.get("book"):
        return state["book"]

    projects = brain.list_projects(uid)
    if not projects:
        mode = settings.mode
        noun = "article topic" if mode == "article" else "book idea"
        _out(console, f"[{ERR}]No projects yet.[/]  Start with: [bold]new --abstract \"{noun}\"[/]")
        return None

    mode_filter = "article" if settings.mode == "article" else "book"
    matching = [p for p in projects if p[1] == mode_filter]
    candidates = matching if matching else projects  # fall back to all if none match mode

    if len(candidates) == 1:
        pid = candidates[0][0]
        state["book"] = pid
        _out(console, f"[{DIM}]auto-selected → {pid}[/]")
        return pid

    # Multiple - show picker
    _out(console, f"\n  [{GOLD}]Which project?[/]")
    for i, (pid, ptype) in enumerate(candidates, 1):
        ptype_tag = f"[{INK}]{ptype}[/]"
        _out(console, f"  [{GOLD}]{i}[/]  {ptype_tag}  {pid}")
    raw = (console.input(f"\n  [{INK}]pick[/] [{DIM}][1]: [/]") if console
           else input("  pick [1]: ")).strip() or "1"
    try:
        pid = candidates[int(raw) - 1][0]
        state["book"] = pid
        return pid
    except (ValueError, IndexError):
        _out(console, f"[{ERR}]invalid choice[/]")
        return None


def _normalize_argv(argv: list[str]) -> list[str]:
    """Fix unquoted multi-word --abstract values for `new` commands.

    When the LLM generates `new --abstract can AGI ever be achieved`, shlex
    splits it into many tokens. We rejoin everything after --abstract (up to
    the next -- flag) into a single value so argparse doesn't choke.
    """
    if not argv or argv[0] != "new" or "--abstract" not in argv:
        return argv
    idx = argv.index("--abstract")
    abstract_parts: list[str] = []
    remaining: list[str] = []
    i = idx + 1
    while i < len(argv):
        if argv[i].startswith("--"):
            remaining = argv[i:]
            break
        abstract_parts.append(argv[i])
        i += 1
    if len(abstract_parts) > 1:
        return argv[:idx + 1] + [" ".join(abstract_parts)] + remaining
    return argv


def _commands_in_response(text: str, known_commands: set) -> list[str]:
    """Return single-line fenced code blocks that are executable commands or slash commands."""
    cmds = []
    for m in _CODE_BLOCK_RE.finditer(text):
        block = m.group(1).strip()
        if "\n" in block or not block:
            continue
        first = block.split()[0]
        if first.startswith("/"):
            if first.lstrip("/").lower() in _CHAT_BLOCKED_SLASH:
                continue
            cmds.append(block)
        elif first in known_commands and first not in _CHAT_BLOCKED_CMDS:
            cmds.append(block)
    return cmds


def _chat_use_project(cmd_line: str, console, state: dict) -> None:
    """Chat-safe `/use`: switch only on a STRONG match, else do nothing.

    The model sometimes invents an id or copies the '[article]' display tag; a junk
    id must never error in the user's face or clobber the already-correct active
    project. We require a high-confidence match (the model should be copying a real
    id) - a vague resemblance to a hallucinated title is ignored, active stays."""
    parts = cmd_line.split(None, 1)
    query = re.sub(r"\s*\[(?:article|book)\]\s*$", "", parts[1]).strip() if len(parts) > 1 else ""
    if not query or query == state.get("book"):
        return
    ranked = brain.match_projects(state["uid"], query)
    if ranked and (ranked[0][2] >= 0.8 or ranked[0][0].lower() == query.lower()):
        pid = ranked[0][0]
        if pid != state.get("book"):
            state["book"] = pid
            _out(console, f"[dim]active project -> {pid}[/]")
    # else: unknown/ambiguous/hallucinated id - keep the active project, stay quiet.


def _execute_cmd(cmd_line: str, console, cfg, settings, state) -> None:
    """Execute one command string emitted by the chat assistant.

    Destructive/config commands are refused here (defense in depth on top of the
    filtering in `_commands_in_response`) - the human must type those directly.
    """
    if cmd_line.startswith("/"):
        slash = cmd_line.lstrip("/").split()
        head = slash[0].lower() if slash else ""
        if head in _CHAT_BLOCKED_SLASH:
            _out(console, f"[dim](skipped /{head} - type it yourself)[/]")
            return
        if head in ("use", "open", "switch"):
            _chat_use_project(cmd_line, console, state)
            return
        _handle_slash(cmd_line, console, cfg, settings, state)
        return
    parser = state.get("_parser")
    commands = state.get("_commands")
    known = state.get("_known_commands", set())
    if not parser or not commands:
        return
    try:
        argv = shlex.split(cmd_line)
    except ValueError:
        return
    first = argv[0] if argv else ""
    if first not in known or first in _CHAT_BLOCKED_CMDS:
        if first in _CHAT_BLOCKED_CMDS:
            _out(console, f"[dim](skipped '{first}' - run it yourself to confirm)[/]")
        return

    # Fix unquoted --abstract: `new --abstract can AGI...` → single value
    argv = _normalize_argv(argv)

    # `new` is interactive (angle/direction picking) - inject --pick 1 if missing
    # so it doesn't block waiting for user input in the middle of a chat response.
    if first == "new" and "--pick" not in argv:
        argv += ["--pick", "1"]

    stderr_buf = io.StringIO()
    try:
        with contextlib.redirect_stderr(stderr_buf):
            args, _ = parser.parse_known_args(argv)
    except SystemExit:
        err_text = stderr_buf.getvalue().strip()
        if err_text:
            msg = err_text.split(": error: ", 1)[-1] if ": error: " in err_text else err_text
            _out(console, f"[{ERR}]error:[/] {msg}")
        return
    # Auto-pick project when command needs one and none is active
    if first in _NEEDS_PROJECT and getattr(args, "book_id", None) is None and not state.get("book"):
        picked = _auto_or_pick_project(state["uid"], settings, console, state)
        if not picked:
            return
    if getattr(args, "book_id", None) is None and state.get("book"):
        args.book_id = state["book"]
    user = args.user if args.user != settings.default_user else state["uid"]
    projects_before = set(p[0] for p in brain.list_projects(user)) if first == "new" else None
    try:
        if first == "run" and console:
            _cmd_run_rich(args, cfg, settings, user, console)
        else:
            commands[args.command](args, cfg, settings, user)
        # After `new` succeeds, auto-set the newly created project as active
        if first == "new" and projects_before is not None:
            new_projects = [p[0] for p in brain.list_projects(user) if p[0] not in projects_before]
            if new_projects:
                state["book"] = new_projects[0]
                _out(console, f"[dim]active project -> {new_projects[0]}[/]")
    except KeyboardInterrupt:
        _out(console, f"\n[{ERR}]interrupted[/] [dim]- state saved. Run again to resume.[/]")
    except SystemExit:
        pass
    except Exception as e:  # noqa: BLE001
        _out(console, f"[{ERR}]error:[/] {explain_error(e) or f'{type(e).__name__}: {e}'}")
