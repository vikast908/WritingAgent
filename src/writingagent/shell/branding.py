"""Banner, wordmark, flame rule, palette sync, the welcome screen, and the borderless
table/section rendering primitives."""
from __future__ import annotations

import os
from pathlib import Path

from .. import __version__ as _VERSION
from .. import brain, ui
from ..config import ModelConfig, Settings
from ..ui import DIM, ERR, GOLD, GOLD_HI, INK, OFF_CLR, ON_CLR, PARCH, RULE
from ._const import _FLEURON, _MARKUP, _NIB

__all__ = [
    '_sync_palette',
    '_make_console',
    '_out',
    '_trim_blank_edges',
    '_shear',
    '_WORDMARK_FACES',
    '_wordmark',
    '_SHADOW_CHARS',
    '_flame_text',
    '_flame_rule',
    '_active_provider',
    '_stack_label',
    '_provider_needs_key',
    '_key_warning',
    '_banner',
    '_section',
    '_cmd_table',
    '_feat_row',
    '_book_status_rows',
    '_welcome',
    '_write_env_key',
    '_first_run_setup',
    'SIGNUP_URLS',
]

#: Where a writer gets an API key, per provider id - shown in the first-run wizard.
SIGNUP_URLS = {
    "openrouter": "https://openrouter.ai/keys",
    "openai": "https://platform.openai.com/api-keys",
    "anthropic": "https://console.anthropic.com/settings/keys",
    "deepseek": "https://platform.deepseek.com/api_keys",
    "google": "https://aistudio.google.com/app/apikey",
    "xai": "https://console.x.ai",
    "groq": "https://console.groq.com/keys",
    "mistral": "https://console.mistral.ai/api-keys",
    "perplexity": "https://www.perplexity.ai/settings/api",
}

#: The providers offered in the first-run picker (order = how they're listed). A curated,
#: no-default menu so a new writer chooses a host instead of inheriting one.
_FIRST_RUN_CHOICES = ("openrouter", "openai", "anthropic", "deepseek", "google")


def _sync_palette() -> None:
    """Rebind the palette names after a live theme switch.

    ui.apply_theme() rebinds ui's globals, but the shell submodules from-imported the
    color names at import time - those copies must be refreshed for the new theme to
    take effect without a restart. Since the shell package is split into seams that each
    hold a copy (plus the facade, which callers/tests read as `shell.X`), refresh them
    all. (cli.py reads `ui.X` at call time, so it needs no sync.)
    """
    import sys

    from . import chat, commands, dashboard, repl
    from . import help as _help
    names = ("GOLD", "GOLD_HI", "INK", "PARCH", "DIM", "RULE", "ERR", "ON_CLR", "OFF_CLR")
    targets = [sys.modules[__name__], chat, commands, dashboard, repl, _help,
               sys.modules.get(__package__)]
    for mod in targets:
        if mod is None:
            continue
        g = vars(mod)
        for k in names:
            if k in g:
                g[k] = getattr(ui, k)


def _make_console():
    return ui.make_console()   # honors NO_COLOR / --plain


def _out(console, text: str) -> None:
    if console:
        console.print(text)
    else:
        print(_MARKUP.sub("", text))


def _trim_blank_edges(lines: list[str]) -> list[str]:
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def _shear(lines: list[str], step: int = 1) -> list[str]:
    """Italicize a figlet block: indent upper rows so the letters lean right,
    like the slanted Tekken wordmark."""
    n = len(lines)
    return [(" " * ((n - 1 - i) * step)) + ln for i, ln in enumerate(lines)]


# Generic wordmark fallbacks: (figlet font, top word, bottom word, shear). Tried
# when the active theme's own face (ui.FONT) is unavailable in this pyfiglet
# build; plain text is the last resort so the banner never crashes.
_WORDMARK_FACES = (
    ("ansi_shadow", "WRITING", "AGENT", False),
    ("ansi_regular", "WRITING", "AGENT", False),
    ("mono9", "Writing", "Agent", False),
    ("slant", "WRITING", "AGENT", False),
    ("small", "WRITING", "AGENT", False),
    ("standard", "WRITING", "AGENT", False),
)


def _wordmark() -> list[str]:
    """Wordmark as a list of lines, one word stacked over the other.

    The figlet FACE is part of the theme (ui.FONT/WORDS/SHEAR) - switching the
    theme changes the typography, not just the colors. Falls back through the
    generic solid faces if the theme's face is missing from this pyfiglet build.
    """
    theme_face = (ui.FONT, ui.WORDS[0], ui.WORDS[1], ui.SHEAR)
    try:
        import pyfiglet
        for font, top_word, bot_word, shear in (theme_face, *_WORDMARK_FACES):
            try:
                top = pyfiglet.figlet_format(top_word, font=font)
                bot = pyfiglet.figlet_format(bot_word, font=font)
            except Exception:
                continue
            top_l = _trim_blank_edges(top.split("\n"))
            bot_l = _trim_blank_edges(bot.split("\n"))
            if shear:   # Tekken-style italic lean (block faces only)
                top_l, bot_l = _shear(top_l), _shear(bot_l)
            lines = top_l + [""] + bot_l
            if lines and max((len(ln) for ln in lines), default=0) <= 80:
                return lines
    except Exception:
        pass
    return ["W R I T I N G", "A G E N T"]


# Box-drawing shadow chars in the ansi_shadow fallback font - rendered as the
# wordmark's dark outline (the theme's RULE color), not part of the gradient fill.
_SHADOW_CHARS = set("╔╗╚╝═║")


def _flame_text(lines: list[str], *, bold: bool = True):
    """Render lines with a per-character diagonal gradient in the active theme.

    Two layers: the solid letter strokes sweep the theme's gradient stops from
    the top-left to the bottom-right (vertical-weighted so each letterform reads
    as one piece), while any shadow characters become a dark outline that gives
    the mark its depth.
    """
    from rich.text import Text
    n_rows = max(len(lines) - 1, 1)
    width = max((len(ln) for ln in lines), default=1)
    weight = "bold " if bold else ""
    t = Text()
    for i, ln in enumerate(lines):
        for j, ch in enumerate(ln):
            if ch == " ":
                t.append(ch)
            elif ch in _SHADOW_CHARS:
                t.append(ch, style=RULE)
            else:
                frac = 0.72 * (i / n_rows) + 0.28 * (j / max(width - 1, 1))
                t.append(ch, style=f"{weight}{ui.flame_color(frac)}")
        t.append("\n")
    return t


def _flame_rule(console):
    """A horizontal rule with a mirrored flame gradient: red edges burning to a
    yellow-hot core. Frames the masthead."""
    from rich.text import Text
    width = console.size.width or 80
    t = Text()
    for j in range(width):
        frac = j / max(width - 1, 1)
        t.append("━", style=ui.flame_color(1 - abs(2 * frac - 1)))
    return t


def _active_provider(settings: Settings | None):
    """The active Provider object, or None. NB: providers.resolve() returns a canonical
    id (a str), not a Provider - REGISTRY maps that id to the object."""
    if settings is None:
        return None
    try:
        from .. import providers
        return providers.REGISTRY.get(providers.resolve(settings.provider))
    except Exception:  # noqa: BLE001 - cosmetic only
        return None


def _stack_label(cfg: ModelConfig | None, settings: Settings | None) -> str:
    """The masthead's `provider · model · vX` line, reflecting what's ACTUALLY in use
    (not a hardcoded 'OpenRouter · DeepSeek'). Defensive: never breaks the banner."""
    p = _active_provider(settings)
    prov = p.name if p is not None else "OpenRouter"
    model = "DeepSeek"
    if cfg is not None:
        try:
            model = cfg.model_for("writer").split("/")[-1]   # drop the host prefix
        except Exception:  # noqa: BLE001
            pass
    return f"{prov} · {model} · v{_VERSION}"


def _provider_needs_key(settings: Settings | None) -> bool:
    """True when the active (non-local) provider has no API key set - so we can warn at
    launch instead of letting the first real call fail with a cryptic auth error."""
    if os.getenv("WRITINGAGENT_FAKE"):
        return False
    p = _active_provider(settings)
    if p is None:
        return False
    try:
        from .. import providers
        return not getattr(p, "local", False) and not providers.has_credentials(p)
    except Exception:  # noqa: BLE001 - cosmetic only
        return False


def _key_warning(settings: Settings | None) -> str:
    """The provider-specific 'set your key' line, or '' when credentials are present."""
    p = _active_provider(settings)
    if p is None or not _provider_needs_key(settings):
        return ""
    env = (p.key_env[0] if getattr(p, "key_env", None) else "the API key")
    return (f"⚠ no API key yet for {p.name} — run /setkey to add one, or set {env} in .env")


def _write_env_key(env_name: str, value: str) -> Path | None:
    """Apply ``ENV_NAME=value`` live in this process (always) and persist it to the agent
    home's ``.env`` (the same file the CLI auto-loads on startup) when it is writable.

    The live set comes FIRST so the key works this session even if persistence fails
    (locked-down home dir, etc.). Returns the .env path on success, or ``None`` when it
    couldn't be written (the caller tells the user it's session-only)."""
    os.environ[env_name] = value                       # session-live first - never lost
    env_path = brain.HOME / ".env"
    line = f"{env_name}={value}"
    try:
        try:
            existing = env_path.read_text(encoding="utf-8").splitlines()
        except (FileNotFoundError, OSError):
            existing = []
        for i, ln in enumerate(existing):
            if ln.strip().startswith(f"{env_name}="):
                existing[i] = line
                break
        else:
            existing.append(line)
        env_path.write_text("\n".join(existing).strip("\n") + "\n", encoding="utf-8")
        return env_path
    except OSError:                                    # read-only location, etc. - session-only
        return None


def _apply_provider(settings, pid: str) -> None:
    """Persist a provider choice to settings.yaml and activate it live. Best-effort - a
    read-only install still gets the live switch even if the save can't be written."""
    from .. import llm
    try:
        from ..config import save_settings
        settings.provider = pid
        save_settings(settings)
    except Exception:  # noqa: BLE001 - read-only location; the live switch below still applies
        pass
    try:
        llm.configure_provider(pid)
    except Exception:  # noqa: BLE001 - cosmetic; the first real call will re-report a bad choice
        pass


def _first_run_setup(console, settings) -> None:
    """A one-time, friendly setup shown only at an interactive prompt when the active host has
    no key. There is NO blessed provider: if a key for some host is already in the environment
    we offer to use it; otherwise the writer PICKS a host (then pastes its key, saved to .env +
    applied live), or tries the whole flow free ($0 placeholder output), or skips. No-op when
    not a TTY, already in fake mode, or a key for the active provider exists."""
    import sys
    if not console or os.getenv("WRITINGAGENT_FAKE") or not _provider_needs_key(settings):
        return
    if not getattr(sys.stdin, "isatty", lambda: False)():
        return
    from rich.text import Text

    from .. import providers
    _section(console, "WELCOME  ·  LET'S GET YOU WRITING")

    def _ask(prompt: str) -> str | None:
        try:
            return console.input(prompt).strip().lower()
        except (EOFError, KeyboardInterrupt):
            console.print()
            return None

    def _go_free() -> None:
        os.environ["WRITINGAGENT_FAKE"] = "1"
        _out(console, f"[bold {GOLD}]✓ free preview on[/] [dim]— the whole flow, placeholder "
                      "output, $0. Add a key later with /setkey for real runs.[/]")

    # 1) A key is already set for some host? Offer it - never assume OpenRouter.
    active = providers.resolve(settings.provider)
    usable = [p for p in providers.configured() if p.id != active]
    if usable:
        console.print(Text(f"  Found a key for: {', '.join(p.name for p in usable)}. "
                           "Use one for real runs?", style=PARCH))
        rows = [(str(i + 1), f"Write with {p.name}") for i, p in enumerate(usable)]
        rows += [("f", "Try it free instead ($0, placeholder)"), ("s", "Not now")]
        _cmd_table(console, rows)
        choice = _ask(f"  [{GOLD}]choice[/] [dim][1 = {usable[0].name}]:[/] ")
        if choice is None or choice in ("s", "skip", "n", "no"):
            return
        if choice in ("f", "free"):
            return _go_free()
        idx = int(choice) - 1 if (choice.isdigit() and 0 < int(choice) <= len(usable)) else 0
        cp = usable[idx]
        _apply_provider(settings, cp.id)
        _out(console, f"[bold {ON_CLR}]✓ using {cp.name}[/] [dim]— real runs on (saved). "
                      "Set per-node models with /model.[/]")
        return

    # 2) No key anywhere - let them CHOOSE a host, then paste its key.
    console.print(Text("  No API key yet — pick a host to write with "
                       "(any of these, or run free; change it anytime with /provider):", style=PARCH))
    choices = [providers.REGISTRY[c] for c in _FIRST_RUN_CHOICES if c in providers.REGISTRY]
    rows = [(str(i + 1), f"{p.name}  [dim]· {p.notes}[/]") for i, p in enumerate(choices)]
    rows += [("Enter", "Try it free now  ·  the whole flow, placeholder output, $0"),
             ("s", "Skip — I'll add a key later with /setkey")]
    _cmd_table(console, rows)
    choice = _ask(f"  [{GOLD}]choice[/] [dim][Enter = try free]:[/] ")
    if choice is None:
        return
    if choice in ("s", "skip"):
        _out(console, "[dim]ok — real runs need a key; pick a host with /provider then /setkey[/]")
        return
    if not (choice.isdigit() and 0 < int(choice) <= len(choices)):
        return _go_free()
    cp = choices[int(choice) - 1]
    _apply_provider(settings, cp.id)                 # so /setkey + real calls target the chosen host
    env = cp.key_env[0] if cp.key_env else "the API key"
    url = SIGNUP_URLS.get(cp.id, "")
    if url:
        console.print(Text(f"  Get a {cp.name} key at {url}", style=DIM))
    key = _ask(f"  paste your {cp.name} key ([dim]{env}[/]) [dim](Enter to skip for now):[/] ")
    if key:
        path = _write_env_key(env, key)
        os.environ.pop("WRITINGAGENT_FAKE", None)    # a real key means real runs
        if path:
            _out(console, f"[bold {ON_CLR}]✓ {cp.name} key saved[/] [dim]→ {path}  ·  real runs on[/]")
        else:
            _out(console, f"[bold {ON_CLR}]✓ key set for this session[/] [dim]— couldn't write .env "
                          f"(read-only?); set {env} in your shell to keep it[/]")
    else:
        _out(console, f"[dim]{cp.name} selected (saved) — add its key anytime with /setkey[/]")


def _banner(console, cfg: ModelConfig | None = None, settings: Settings | None = None) -> None:
    lines = _wordmark()
    if not console:
        print("\n".join(lines))
        print("an autonomous writing studio - books, articles & more")
        return
    from rich.padding import Padding
    from rich.text import Text
    pad = (0, 0, 0, 2)   # left-aligned with a 2-col indent
    # Narrow terminal: the figlet masthead would wrap into noise - drop to a one-line
    # wordmark so the banner still reads (and the wordmark stays on screen).
    warn = _key_warning(settings)
    if (console.size.width or 80) < 60:
        console.print()
        console.print(Padding(Text(f"{_NIB} WRITING AGENT", style=f"bold {GOLD}"), pad))
        console.print(Padding(Text(_stack_label(cfg, settings), style=DIM), pad))
        if warn:
            console.print(Padding(Text(warn, style=f"bold {ERR}"), pad))
        console.print()
        return
    console.print()
    console.print(_flame_rule(console))
    console.print()
    console.print(Padding(_flame_text(lines), pad))
    console.print(Padding(Text("an autonomous writing studio - books, articles & more",
                               style=f"italic {INK}"), pad))
    console.print(Padding(Text(_stack_label(cfg, settings), style=DIM), pad))
    if warn:
        console.print(Padding(Text(warn, style=f"bold {ERR}"), pad))
    console.print()
    console.print(_flame_rule(console))


def _section(console, title: str) -> None:
    from rich.rule import Rule
    from rich.text import Text
    label = Text(f" {_FLEURON}  ", style=GOLD_HI)      # yellow flame-tip fleuron
    label.append(f"{title} ", style=f"bold {GOLD}")    # blazing-orange title
    console.print(Rule(label, style=RULE, align="left"))


def _cmd_table(console, rows: list[tuple[str, str]]) -> None:
    from rich.table import Table
    t = Table(box=None, show_header=False, padding=(0, 4, 0, 3))
    t.add_column(style=f"bold {GOLD}", no_wrap=True)
    t.add_column(style=PARCH)
    for a, b in rows:
        t.add_row(a, b)
    console.print(t)


def _feat_row(label: str, enabled: bool, desc: str) -> tuple[str, str]:
    """Return a (indicator, description) row for the features table."""
    indicator = f"[bold {ON_CLR}]● on [/]  {label}" if enabled else f"[{OFF_CLR}]○ off[/]  {label}"
    return (indicator, desc)


def _book_status_rows(uid: str, projects: list[tuple[str, str]]) -> list[tuple[str, str]]:
    from ..brain import ArticlePaths, BookPaths
    rows = []
    for project_id, ptype in projects[:8]:
        try:
            if ptype == "article":
                paths = ArticlePaths(project_id, uid)
                st = brain.read_json(paths.run_state) or {}
                phase = st.get("phase", "-")
                ch = st.get("current_section", "?")
                total = st.get("num_sections", "?")
                label = f"[dim]article[/]  {phase}  sec {ch}/{total}"
            else:
                paths = BookPaths(project_id, uid)
                st = brain.read_json(paths.run_state) or {}
                phase = st.get("phase", "-")
                ch = st.get("current_chapter", "?")
                total = st.get("num_chapters", "?")
                label = f"{phase}  ch {ch}/{total}"
            pending = "  [bold]⚠ review needed[/]" if st.get("pending_review") else ""
            rows.append((project_id, f"{label}{pending}"))
        except Exception:
            rows.append((project_id, "-"))
    if len(projects) > 8:
        rows.append(("", f"[dim]… +{len(projects) - 8} more (see /books)[/]"))
    return rows


# A rotating writing epigraph for the welcome - public-domain voices only (consistent with the
# personas' no-living-author rule). Kept short so it never wraps; chosen by the date so it's
# stable within a day, varied across days.
_EPIGRAPHS = [
    ("Easy reading is damn hard writing.", "Nathaniel Hawthorne"),
    ("Omit needless words.", "William Strunk Jr."),
    ("Vigorous writing is concise.", "William Strunk Jr."),
    ("The pen is the tongue of the mind.", "Cervantes"),
    ("The secret of being a bore is to tell everything.", "Voltaire"),
    ("What is written without effort is read without pleasure.", "Samuel Johnson"),
    ("Substitute 'damn' for every 'very'; your editor will delete it.", "Mark Twain"),
]


def _epigraph() -> tuple[str, str]:
    import datetime
    return _EPIGRAPHS[datetime.date.today().toordinal() % len(_EPIGRAPHS)]


def _welcome(console, cfg: ModelConfig, settings: Settings, uid: str) -> None:
    sdir = brain.skills_dir(uid)
    skl = sorted(p.stem for p in sdir.glob("*.md")) if sdir.exists() else []
    projects = brain.list_projects(uid)
    mode = settings.mode
    is_article = mode == "article"
    # Loud guard: a leftover test env var otherwise makes every model call return
    # canned text with zero indication why (chat replies with the same boilerplate,
    # runs "succeed" with placeholder prose).
    fake = os.getenv("WRITINGAGENT_FAKE", "").lower() in ("1", "true", "yes")
    fake_msg = ("⚠ FAKE MODE — placeholder output, no real AI calls ($0). Add a key with "
                "/setkey for real runs (or unset WRITINGAGENT_FAKE).")

    if not console:
        if fake:
            print(fake_msg)
        print("commands: new run status review read export memory consolidate produce list")
        print("slash:    /help /model /set /skills /use /auto /config /clear /exit")
        print(f"mode:     {mode}   run: {'autonomous' if settings.autonomous else 'manual'}"
              f"   agentic: {'on' if settings.agentic else 'off'}")
        print(f"models:   pro={cfg.model_for('writer')}  flash={cfg.model_for('critic')}")
        proj_str = ", ".join(f"{p[0]}[{p[1]}]" for p in projects) or "(none)"
        print(f"skills: {len(skl)}   projects: {proj_str}   user: {uid}")
        if not projects:
            print('\nGet started:  new --abstract "your idea"  then  run')
        return

    from rich.text import Text

    # Compact by design: the wordmark must still be on screen when the prompt
    # appears (the old screen was ~45 lines and scrolled the banner away on a
    # standard 30-row terminal). Full lists live behind /help and /features.
    if fake:
        console.print(Text(f"  {fake_msg}", style=f"bold {ERR}"))

    # A single warm line: a rotating writing epigraph, prefixed with a greeting for a
    # returning writer. One line by design (see the compactness note above).
    quote, who = _epigraph()
    lead = "Welcome back.  " if projects else ""
    console.print(Text(f"  {lead}“{quote}”  — {who}", style=f"italic {DIM}"))

    # ── No API key yet: point at the one command that fixes it (the wizard ran first). ─
    if _provider_needs_key(settings):
        p = _active_provider(settings)
        env = (p.key_env[0] if p and getattr(p, "key_env", None) else "the API key")
        _section(console, "ADD YOUR KEY")
        _cmd_table(console, [
            ("/setkey", f"paste your {env} once — saved to .env, real runs turn on"),
        ])

    # ── Start here ──────────────────────────────────────────────────────────────
    _section(console, "START")
    unit = "section" if is_article else "chapter"
    start_rows = [
        ("write --abstract \"...\"", "★ one command — answer a few questions, then it researches, "
                                     "writes & self-edits the whole piece (press m to pause & steer)"),
    ]
    if not projects:
        example = ("How Python async/await actually works" if is_article
                   else "A thriller set on Mars in 2089")
        start_rows.append(("try it", f'write --abstract "{example}"'))
        start_rows.append(("step by step", "[dim]new → run → export · see /help[/]"))
    else:
        start_rows.append(("new --abstract \"...\"", f"step-by-step — outline → `run` (write · "
                                                     f"critique · humanise per {unit}) → `export`"))
    _cmd_table(console, start_rows)

    # ── Projects ──────────────────────────────────────────────────────────────
    if projects:
        _section(console, "YOUR PROJECTS")
        _cmd_table(console, _book_status_rows(uid, projects))

    # ── Footer ────────────────────────────────────────────────────────────────
    console.print()
    foot = Text("  ")
    foot.append("mode ", style=DIM)
    foot.append(mode, style=f"bold {GOLD}" if is_article else INK)
    foot.append("   run ", style=DIM)
    foot.append("autonomous" if settings.autonomous else "manual",
                style=f"bold {GOLD}" if settings.autonomous else INK)
    foot.append("   pro ", style=DIM)
    foot.append(cfg.model_for("writer").split("/")[-1], style=INK)
    foot.append("   agentic ", style=DIM)
    agentic_on = bool(settings.agentic)
    foot.append("on" if agentic_on else "off",
                style=f"bold {GOLD}" if agentic_on else INK)
    foot.append("   theme ", style=DIM)
    foot.append(ui.current_theme, style=INK)
    n_proj = len(projects)
    foot.append(f"   {len(skl)} skills   {n_proj} project{'s' if n_proj != 1 else ''}   {uid}",
                style=DIM)
    console.print(foot)
    feats = [("humanize", settings.humanize), ("researcher", settings.use_researcher),
             ("deep search", settings.deep_research), ("embeddings", settings.use_embeddings),
             ("images", settings.use_images), ("cohesion", settings.article_cohesion)]
    on = " · ".join(k for k, v in feats if v) or "none"
    off = " · ".join(k for k, v in feats if not v) or "none"
    console.print(Text(f"  features on: {on}   off: {off}", style=DIM))
    console.print(Text(
        "  /help all commands · /features toggles · /agentic on|off · /theme looks · or just chat in plain English",
        style=DIM,
    ))
