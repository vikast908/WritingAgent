"""Banner, wordmark, flame rule, palette sync, the welcome screen, and the borderless
table/section rendering primitives."""
from __future__ import annotations

import os

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
]


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
    if os.getenv("BOOK_AGENT_FAKE"):
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
    return (f"⚠ no API key for {p.name} — set {env} in .env or your shell, "
            f"or /provider to switch host")


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


def _welcome(console, cfg: ModelConfig, settings: Settings, uid: str) -> None:
    sdir = brain.skills_dir(uid)
    skl = sorted(p.stem for p in sdir.glob("*.md")) if sdir.exists() else []
    projects = brain.list_projects(uid)
    mode = settings.mode
    is_article = mode == "article"
    # Loud guard: a leftover test env var otherwise makes every model call return
    # canned text with zero indication why (chat replies with the same boilerplate,
    # runs "succeed" with placeholder prose).
    fake = os.getenv("BOOK_AGENT_FAKE", "").lower() in ("1", "true", "yes")
    fake_msg = ("⚠ FAKE MODE is on (BOOK_AGENT_FAKE env var) - no real AI calls; chat and runs "
                "return canned text. Fix: Remove-Item Env:BOOK_AGENT_FAKE  then restart.")

    if not console:
        if fake:
            print(fake_msg)
        print("commands: new run status review read export memory consolidate produce list")
        print("slash:    /help /model /set /skills /use /auto /config /clear /exit")
        print(f"mode:     {mode}   run: {'autonomous' if settings.autonomous else 'manual'}")
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

    # ── First run with no API key: don't suggest a command that will just fail. ─
    if _provider_needs_key(settings):
        p = _active_provider(settings)
        env = (p.key_env[0] if p and getattr(p, "key_env", None) else "the API key")
        _section(console, "FIRST RUN  ·  NO API KEY YET")
        _cmd_table(console, [
            ("real runs", f"set [bold]{env}[/] in a .env file  (or [bold]/provider[/] to switch host)"),
            ("try it free now", "restart with [bold]BOOK_AGENT_FAKE=1[/] — the whole flow, "
                                "placeholder output, $0"),
        ])

    # ── Start here ────────────────────────────────────────────────────────────
    _section(console, "START")
    unit = "section" if is_article else "chapter"
    start_rows = [
        ("write --abstract \"...\"", "★ one command - a few questions upfront, then it "
                                     "researches, writes, and exports the finished file"),
        ("new --abstract \"...\"", f"step-by-step - outline → `run` (write · critique · "
                                   f"humanise per {unit}) → `export`"),
    ]
    if not projects:
        example = ("How Python async/await actually works" if is_article
                   else "A thriller set on Mars in 2089")
        start_rows.append(("try it", f'write --abstract "{example}"'))
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
    foot.append("   flash ", style=DIM)
    foot.append(cfg.model_for("critic").split("/")[-1], style=INK)
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
        "  /help all commands · /features toggles · /theme looks · or just chat in plain English",
        style=DIM,
    ))
