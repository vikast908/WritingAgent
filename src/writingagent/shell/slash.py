"""The slash-command dispatcher (/help /model /provider /theme /use /set ...)."""
from __future__ import annotations

import shlex

from .. import brain, ui
from .. import skills as skills_mod
from ..config import ModelConfig, Settings, save_settings
from ..ui import ERR, GOLD, INK
from ._const import _EXIT, _MODE_ALIASES, _SLASH_COMPLETIONS
from .branding import _out, _section
from .chat import _chat_respond, _compact_history
from .commands import (
    _cmd_agentic,
    _cmd_auto,
    _cmd_dashboard,
    _cmd_model,
    _cmd_path,
    _cmd_praise,
    _cmd_provider,
    _cmd_set,
    _cmd_setkey,
    _cmd_trace,
    _print_skill,
    _print_skills,
    _set_theme,
    _use_project,
)
from .help import _slash_help, _toggle_grid

__all__ = [
    '_handle_slash',
]


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
    elif name in ("setkey", "key", "apikey"):
        _cmd_setkey(console, settings, rest)
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
    elif name == "agentic":
        _cmd_agentic(console, settings, state, rest)
    elif name == "trace":
        _cmd_trace(console, settings, state, rest)
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
