"""The prompt_toolkit session: slash/command autocomplete + completion styling."""
from __future__ import annotations

from .. import brain, ui
from ..config import ModelConfig, Settings
from ..ui import GOLD, GOLD_HI, PARCH, RULE
from ._const import _NODES, _SLASH_COMPLETIONS

__all__ = [
    '_make_pt_session',
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
