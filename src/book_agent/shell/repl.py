"""The REPL core: input routing, slash dispatch, the prompt-toolkit session, run_shell."""
from __future__ import annotations

import contextlib
import io
import re
import shlex

from .. import brain, ui
from .. import skills as skills_mod
from ..config import ModelConfig, Settings, save_settings
from ..ui import DIM, ERR, GOLD, GOLD_HI, INK, ON_CLR, PARCH, RULE
from ._const import (
    _CODE_BLOCK_RE,
    _EXIT,
    _FLEURON,
    _MODE_ALIASES,
    _NIB,
    _NODES,
    _SLASH_WORDS,
    _STRONG_SLASH,
)
from .branding import _banner, _make_console, _out, _section, _welcome
from .chat import _chat_respond, _compact_history, _show_post_hint
from .commands import (
    _cmd_auto,
    _cmd_dashboard,
    _cmd_model,
    _cmd_path,
    _cmd_praise,
    _cmd_provider,
    _cmd_set,
    _print_skill,
    _print_skills,
    _set_theme,
    _use_project,
)
from .dashboard import _cmd_run_rich
from .help import _slash_help, _toggle_grid

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
    '_prompt_state',
    '_handle_slash',
    '_SLASH_COMPLETIONS',
    '_make_pt_session',
    'run_shell',
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
        _out(console, f"[{ERR}]error:[/] {type(e).__name__}: {e}")


# ── Rich progress wrapper for `run` ──────────────────────────────────────────


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


# ── Main slash dispatcher ─────────────────────────────────────────────────────

def _handle_slash(line: str, console, cfg: ModelConfig, settings: Settings, state: dict) -> bool:
    parts = shlex.split(line)
    name = parts[0].lstrip("/").lower()
    rest = parts[1:]
    uid = state["uid"]
    if name in _EXIT:
        return False
    if name in ("help", "h", "?"):
        _slash_help(console, settings, rest)
    elif name in ("features", "toggle"):
        _toggle_grid(console, settings)
    elif name in ("clear", "cls"):
        if console:
            console.clear()
    elif name in ("model", "models"):
        _cmd_model(console, cfg, rest)
    elif name in ("provider", "providers"):
        _cmd_provider(console, settings, rest)
    elif name in ("path", "paths"):
        _cmd_path(console, settings, state, rest)
    elif name == "set":
        _cmd_set(console, settings, rest)
    elif name == "skills":
        _print_skills(console, uid)
    elif name == "skill":
        _print_skill(console, uid, rest)
    elif name in ("seed-skills", "seed"):
        _out(console, f"seeded {skills_mod.seed_builtin(uid)} new skill(s)")
    elif name in ("books", "list"):
        projects = brain.list_projects(uid)
        lines = [f"{p[0]}  [{p[1]}]" for p in projects]
        _out(console, "\n".join(lines) or "[dim](no projects yet)[/]")
    elif name == "use":
        if rest:
            _use_project(console, uid, " ".join(rest), state)
        else:
            _out(console, f"active book -> [{GOLD}]{state['book'] or '(none)'}[/]")
    elif name == "user":
        if rest:
            if not brain.is_safe_id(rest[0]):
                _out(console, f"[{ERR}]invalid user id '{rest[0]}'[/] (letters, digits, - . _)")
            else:
                state["uid"] = rest[0]
                skills_mod.seed_builtin(rest[0])
        _out(console, f"user -> [{GOLD}]{state['uid']}[/]")
    elif name == "config":
        _out(console, brain.read_text(brain._ROOT / "config" / "models.yaml") or "")
        _out(console, brain.read_text(brain._ROOT / "config" / "settings.yaml") or "")
    elif name == "update":
        msg = " ".join(rest).strip() if rest else ""
        if not msg:
            msg = (console.input(f"  [{INK}]describe your changes or what to review:[/] ")
                   if console else input("  describe your changes: ")).strip()
        if msg:
            # Read the active project's current state as context
            active = state.get("book")
            ctx_lines = []
            if active:
                from ..brain import ArticlePaths, BookPaths
                art = ArticlePaths(active, state["uid"])
                if art.run_state.exists():
                    st = brain.read_json(art.run_state) or {}
                    ctx_lines.append(f"Active project: {active} [article] - phase: {st.get('phase')}, "
                                     f"sections committed: {st.get('committed')}/{st.get('num_sections')}")
                    ms = brain.read_text(art.manuscript)
                    if ms:
                        ctx_lines.append(f"Manuscript excerpt (last 800 chars):\n{ms[-800:]}")
                else:
                    bk = BookPaths(active, state["uid"])
                    st = brain.read_json(bk.run_state) or {}
                    ctx_lines.append(f"Active project: {active} [book] - phase: {st.get('phase')}, "
                                     f"chapters committed: {st.get('committed')}/{st.get('num_chapters')}")
            update_msg = (
                "[UPDATE REQUEST - the user has made changes or wants a review]\n"
                + ("\n".join(ctx_lines) + "\n\n" if ctx_lines else "")
                + f"User's update request: {msg}\n\n"
                "Review the request in the context of the project above. "
                "If they want a manuscript change, suggest the specific edit or run the relevant command. "
                "If they want a direction change, ask one clarifying question. "
                "Keep your response concise and action-focused."
            )
            _chat_respond(update_msg, console, cfg, settings, state)
    elif name == "retry":
        last = state.get("last_chat")
        if last:
            hist = state.get("chat_history", [])
            if len(hist) >= 2 and hist[-2].get("content") == last:
                del hist[-2:]
            _chat_respond(last, console, cfg, settings, state)
        else:
            _out(console, "[dim](nothing to retry - send a chat message first)[/]")
    elif name == "reset":
        state["chat_history"] = []
        state["last_chat"] = None
        _out(console, f"[{GOLD}]context cleared[/] [dim]- assistant memory reset[/]")
    elif name == "compact":
        hist = state.get("chat_history", [])
        if not hist:
            _out(console, "[dim](no conversation history to compact)[/]")
        else:
            _out(console, "[dim]compacting...[/]")
            state["chat_history"] = _compact_history(hist, cfg)
            turns_before = len(hist) // 2
            _out(console, f"[{GOLD}]compacted[/] [dim]{turns_before} turn(s) -> 1 summary[/]")
    elif name in ("auto", "autonomous", "manual"):
        _cmd_auto(console, settings, state, name, rest)
    elif name == "praise":
        _cmd_praise(console, state, rest)
    elif name == "mode":
        if not rest:
            _out(console, f"mode: [{GOLD}]{settings.mode}[/] [dim](book | article)[/]")
        else:
            m, _c = ui.smart_match(rest[0], ("book", "article"), aliases=_MODE_ALIASES)
            if m:
                settings.mode = m
                save_settings(settings)
                _out(console, f"mode -> [{GOLD}]{m}[/] [dim](saved - next `new` will use this mode)[/]")
            else:
                _out(console, f"[{ERR}]unknown mode '{rest[0]}'[/] - valid: book  article")
    elif name == "dashboard":
        _cmd_dashboard(console, uid, rest)
    elif name in ("theme", "themes"):
        if not rest:
            _section(console, "THEMES") if console else None
            for tname, t in ui.THEMES.items():
                mark = "●" if tname == ui.current_theme else "○"
                swatch = "".join(f"[{c}]█[/]" for c in t["STOPS"])
                _out(console, f"  [{t['GOLD']}]{mark} {tname:<13}[/] {swatch}  [dim]{t['DESC']}[/]")
            _out(console, "  [dim]switch: /theme <name>[/]")
        else:
            tname, cands = ui.smart_match(rest[0], ui.THEMES)
            if tname:
                _set_theme(tname, console, settings)
            elif cands:
                _out(console, f"[{ERR}]'{rest[0]}' matches several:[/] [dim]{' · '.join(cands)}[/]")
            else:
                names = " · ".join(ui.THEMES)
                _out(console, f"[{ERR}]unknown theme '{rest[0]}'[/] [dim]- themes: {names}[/]")
    else:
        sug = ui.did_you_mean(name, [s[0] for s in _SLASH_COMPLETIONS])
        hint = f"did you mean /{sug}?" if sug else "try /help"
        _out(console, f"[{ERR}]unknown slash command:[/] /{name}  [dim]({hint})[/]")
    return True


# ── prompt_toolkit autocomplete + status toolbar ──────────────────────────────

# Flat list of (slash-name, description) for the completion dropdown
_SLASH_COMPLETIONS = [
    ("help",        "show all commands + slash commands"),
    ("features",    "interactive feature-toggle grid (space toggles · ↵ saves)"),
    ("model",       "show / set model routing"),
    ("provider",    "list / switch the model host (openrouter, deepseek, ollama, ...)"),
    ("set",         "change a setting  e.g. /set use_researcher true"),
    ("skills",      "list craft skills"),
    ("skill",       "show one skill by name"),
    ("seed-skills", "install built-in craft skills"),
    ("use",         "set active book / article"),
    ("path",        "where finished writing is saved - default + per-project"),
    ("books",       "list all projects"),
    ("user",        "switch user"),
    ("config",      "show model + settings config"),
    ("update",      "describe changes - AI reviews and suggests next steps"),
    ("retry",       "resend last chat message"),
    ("auto",        "autonomous vs manual run mode  on | off"),
    ("praise",      "mark a chapter/section as great writing"),
    ("mode",        "show / set mode  book | article"),
    ("theme",       "list / switch color theme"),
    ("dashboard",   "telemetry: calls · tokens · cost · errors"),
    ("reset",       "clear chat memory"),
    ("compact",     "compress chat memory to one summary"),
    ("clear",       "clear screen"),
    ("exit",        "quit"),
]


def _make_pt_session(known_commands: set, state: dict, cfg: ModelConfig, settings: Settings):
    """Build a prompt_toolkit PromptSession with slash-autocomplete + bottom toolbar.

    Returns (session, patch_stdout) or (None, None) if prompt_toolkit isn't available.
    """
    try:
        import dataclasses

        from prompt_toolkit import PromptSession
        from prompt_toolkit.completion import Completer, Completion
        from prompt_toolkit.history import FileHistory, InMemoryHistory
        from prompt_toolkit.patch_stdout import patch_stdout as _patch_stdout
        from prompt_toolkit.styles import Style
    except ImportError:
        return None, None

    def _comp(value, start, meta=""):
        return Completion(value, start_position=start, display=value, display_meta=meta)

    class _BWCompleter(Completer):
        def get_completions(self, document, complete_event):
            text = document.text_before_cursor
            ends_space = text.endswith(" ")
            words = text.split()
            cur = "" if ends_space else (words[-1] if words else "")

            # ── slash commands ──────────────────────────────────────────────
            if text.startswith("/"):
                if " " not in text:                              # completing the name
                    partial = text[1:].lower()
                    for name, desc in _SLASH_COMPLETIONS:
                        if name.startswith(partial):
                            yield Completion("/" + name, start_position=-len(text),
                                             display=f"/{name}", display_meta=desc)
                    return
                sub = words[0].lstrip("/").lower()
                if sub in ("use", "dashboard"):                  # → real project names
                    for pid, ptype in brain.list_projects(state["uid"]):
                        if pid.startswith(cur):
                            yield _comp(pid, -len(cur), ptype)
                elif sub in ("model", "models"):
                    from .. import providers
                    if len(words) <= (1 if ends_space else 2):       # agent | all-agents slug | list
                        for a in ["default", "list", *_NODES]:
                            if a.startswith(cur):
                                yield _comp(a, -len(cur), "browse" if a == "list" else "agent")
                        for slug in providers.model_slugs():
                            if slug.startswith(cur):
                                yield _comp(slug, -len(cur), "model")
                    else:                                            # the slug for a chosen agent
                        for slug in providers.model_slugs():
                            if slug.startswith(cur):
                                yield _comp(slug, -len(cur), "model")
                elif sub in ("provider", "providers"):
                    from .. import providers
                    for pid in providers.names():
                        if pid.startswith(cur):
                            tag = "local" if providers.REGISTRY[pid].local else "host"
                            yield _comp(pid, -len(cur), tag)
                elif sub in ("path", "paths") and len(words) <= (1 if ends_space else 2):
                    for kw in ("default", "show", "clear"):
                        if kw.startswith(cur):
                            yield _comp(kw, -len(cur), "option")
                    for pid, ptype in brain.list_projects(state["uid"]):
                        if pid.startswith(cur):
                            yield _comp(pid, -len(cur), ptype)
                elif sub == "set":
                    fields = {f.name: f for f in dataclasses.fields(settings)}
                    if len(words) <= (1 if ends_space else 2):   # the key
                        for n, f in fields.items():
                            if n.startswith(cur):
                                yield _comp(n, -len(cur), type(f.default).__name__)
                    else:                                        # values
                        key = words[1]
                        if key in fields and isinstance(fields[key].default, bool):
                            for v in ("true", "false"):
                                if v.startswith(cur):
                                    yield _comp(v, -len(cur))
                        elif key == "theme":
                            for v in ui.THEMES:
                                if v.startswith(cur):
                                    yield _comp(v, -len(cur), "theme")
                        elif key == "provider":
                            from .. import providers
                            for pid in providers.names():
                                if pid.startswith(cur):
                                    yield _comp(pid, -len(cur), "host")
                elif sub == "skill":
                    sdir = brain.skills_dir(state["uid"])
                    if sdir.exists():
                        for p in sorted(sdir.glob("*.md")):
                            if p.stem.startswith(cur):
                                yield _comp(p.stem, -len(cur), "skill")
                elif sub == "mode":
                    for v in ("book", "article"):
                        if v.startswith(cur):
                            yield _comp(v, -len(cur))
                elif sub == "auto":
                    for v in ("on", "off"):
                        if v.startswith(cur):
                            yield _comp(v, -len(cur))
                elif sub in ("theme", "themes"):
                    for v in ui.THEMES:
                        if v.startswith(cur):
                            yield _comp(v, -len(cur), "theme")
                return

            # ── book commands ────────────────────────────────────────────────
            if not words:
                return
            if len(words) == 1 and not ends_space:               # first word
                for c in sorted(known_commands):
                    if c.startswith(cur):
                        yield _comp(c, -len(cur), "command")
                return
            if words[0] == "export":                             # formats (positional) + --format
                from ..cli import _EXPORT_FORMATS
                opts = [*_EXPORT_FORMATS, "all"]
                prior = words[-1] if ends_space else (words[-2] if len(words) >= 2 else "")
                if prior == "--format":
                    for f in opts:
                        if f.startswith(cur):
                            yield _comp(f, -len(cur))
                else:
                    for f in opts:
                        if f.startswith(cur):
                            yield _comp(f, -len(cur), "format")
                    if "--format".startswith(cur) and "--format" not in words:
                        yield _comp("--format", -len(cur))

    # (No bottom toolbar: the persistent status strip read as visual noise - mode/
    # model/project state lives in the prompt prefix and the welcome footer instead.
    # A pending review still surfaces via the prompt suffix and the escalation picker.)

    _DIM_HEX = "#6b6b6b"  # prompt_toolkit needs hex; Rich's "grey42" ≈ #6b6b6b
    pt_style = Style.from_dict({
        # Completion dropdown
        "completion-menu.completion":                f"bg:#111111 fg:{GOLD}",
        "completion-menu.completion.current":        f"bg:{RULE} fg:{GOLD_HI} bold",
        "completion-menu.meta.completion":           f"bg:#111111 fg:{_DIM_HEX}",
        "completion-menu.meta.completion.current":   f"bg:{RULE} fg:{PARCH}",
        # Prompt
        "":                                          f"fg:{PARCH}",
    })

    try:                                          # persist arrow-up history across sessions
        brain.INDEX_DIR.mkdir(parents=True, exist_ok=True)
        history = FileHistory(str(brain.INDEX_DIR / "shell_history"))
    except Exception:
        history = InMemoryHistory()

    try:
        session = PromptSession(
            completer=_BWCompleter(),
            history=history,
            style=pt_style,
            complete_while_typing=True,
            mouse_support=False,
            enable_history_search=True,
        )
    except Exception:
        # Not a real interactive terminal (piped, CI, etc.) - fall back to console.input
        return None, None
    return session, _patch_stdout


# ── Shell entry point ─────────────────────────────────────────────────────────

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
    _welcome(console, cfg, settings, state["uid"])

    while True:
        slug = cfg.model_for("writer").split("/")[-1]
        book = state["book"]
        status_sfx = _prompt_state(state) if book else ""

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
            # Fix unquoted --abstract: `new --abstract some text` → single value
            argv = _normalize_argv(argv)
            # Capture argparse stderr to re-style error messages
            stderr_buf = io.StringIO()
            try:
                with contextlib.redirect_stderr(stderr_buf):
                    args, extras = parser.parse_known_args(argv)
            except SystemExit:
                err_text = stderr_buf.getvalue().strip()
                if err_text:
                    # Strip "book: error: " prefix that argparse prepends
                    msg = err_text.split(": error: ", 1)[-1] if ": error: " in err_text else err_text
                    _out(console, f"[{ERR}]error:[/] {msg}  [dim](try /help)[/]")
                continue
            if extras:
                # "run it", "read chapter 3" - a command word followed by plain
                # English. Hand the whole line to the assistant instead of
                # silently dropping the extra words and running the bare command.
                _chat_respond(line, console, cfg, settings, state)
                continue
            # Auto-pick project when none is active and the command needs one.
            # `new`/`write` CREATE a project, so they must never inherit the active id.
            creates_project = first in ("new", "write")
            if getattr(args, "book_id", None) is None:
                if first in _NEEDS_PROJECT and not state["book"]:
                    picked = _auto_or_pick_project(state["uid"], settings, console, state)
                    if not picked and first not in {"list", "new", "skills", "config"}:
                        continue
                if state["book"] and not creates_project:
                    args.book_id = state["book"]
            user = args.user if args.user != settings.default_user else state["uid"]
            projects_before = ({p[0] for p in brain.list_projects(user)}
                               if creates_project else None)
            try:
                # Special handling for destructive/interactive commands in Rich TUI
                if first == "run" and console:
                    _cmd_run_rich(args, cfg, settings, user, console)
                elif first == "delete" and console and not getattr(args, "yes", False):
                    book_id = getattr(args, "book_id", None) or state["book"] or ""
                    answer = console.input(
                        f"  [{ERR}]Delete '{book_id}' permanently?[/] [{DIM}][y/N][/] ")
                    if ui.is_affirmative(answer):
                        args.yes = True
                        commands[args.command](args, cfg, settings, user)
                        if state.get("book") == book_id:
                            state["book"] = None
                    else:
                        _out(console, "[dim]aborted[/]")
                else:
                    commands[args.command](args, cfg, settings, user)
                # After new/write, make the freshly created project active.
                if projects_before is not None:
                    fresh = [p[0] for p in brain.list_projects(user)
                             if p[0] not in projects_before]
                    if fresh:
                        state["book"] = fresh[0]
                _show_post_hint(console, state, settings)
            except KeyboardInterrupt:
                _out(console,
                     f"\n[{ERR}]interrupted[/] [dim]- state saved. Run again to resume.[/]")
            except SystemExit:
                pass
            except Exception as e:  # noqa: BLE001
                _out(console, f"[{ERR}]error:[/] {type(e).__name__}: {e}")
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
