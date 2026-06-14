"""Interactive REPL/TUI for WRITING AGENT (run `writing-agent` / `book` / `python book.py`).

Aesthetic: themed (see ui.THEMES; /theme to switch). The default "editorial" theme is
ink & brass - one warm accent, semantic status colors, a gradient-filled wordmark,
fleuron section markers, and clean borderless command tables. Alternates: kazama
(Jin Kazama flame), shakespeare, poe, gatsby.

Lines starting with `/` are slash commands; recognised book-command words dispatch to the
one-shot CLI; anything else is routed to the built-in conversational assistant (DeepSeek Flash).
"""
from __future__ import annotations

import collections
import contextlib
import io
import os
import re
import shlex
import threading
import time

from . import __version__ as _VERSION   # single source of truth (src/book_agent/__init__.py)
from . import brain, ui
from . import skills as skills_mod
from .config import ModelConfig, Settings, save_config, save_settings
from .ui import DIM, ERR, GOLD, GOLD_HI, INK, OFF_CLR, ON_CLR, PARCH, RULE  # palette


def _sync_palette() -> None:
    """Rebind this module's palette names after a live theme switch.

    ui.apply_theme() rebinds ui's globals, but this module from-imported the
    color names at import time - those copies must be refreshed for the new
    theme to take effect without a restart. (cli.py reads `ui.X` at call time,
    so it needs no sync.)
    """
    g = globals()
    for k in ("GOLD", "GOLD_HI", "INK", "PARCH", "DIM", "RULE", "ERR",
              "ON_CLR", "OFF_CLR"):
        g[k] = getattr(ui, k)
    g["_FLEURON"] = _NIB
_NODES = ["planner", "toc", "writer", "critic", "judge", "verifier", "summarizer",
          "consolidation", "production", "learner", "researcher", "humanizer",
          "diagram", "diagram_fallback", "chat"]
_EXIT = {"exit", "quit", "q", ":q"}
# Plain-English synonyms for the two project modes (used by /mode and /set mode).
_MODE_ALIASES = {
    "essay": "article", "blog": "article", "post": "article", "piece": "article",
    "op-ed": "article", "oped": "article", "longform": "article", "long-form": "article",
    "story": "book", "novel": "book", "manuscript": "book", "nonfiction": "book",
}
_NIB = "✒"             # the brand glyph: a pen nib (matches the logo)
_FLEURON = _NIB            # used for the prompt + section/status markers
_MAX_HISTORY = 8   # max messages kept for multi-turn context (4 user + 4 assistant)

# A bare slash-command word typed WITHOUT the slash (e.g. `help`, `features`) used to
# fall through to the chat assistant - a silent dead end (and a wasted LLM call in real
# mode). These are every name `_handle_slash` understands; when one is typed plain we run
# the slash form and show a one-line hint. (`\` before any line forces chat - see run_shell.)
_SLASH_WORDS = {
    "help", "h", "?", "features", "toggle", "clear", "cls", "model", "models",
    "provider", "providers", "path", "paths", "set", "skill", "seed-skills", "seed",
    "books", "use", "user", "config", "update", "retry", "reset", "compact",
    "auto", "autonomous", "manual", "praise", "mode", "dashboard", "theme", "themes",
}
# Safe to route even WITH trailing args - a genuine writing-chat sentence rarely opens
# with these. The ambiguous English words (set/use/mode/path/auto/clear/model/update/user)
# only route when typed as a single bare token, so "use a warmer tone" still reaches chat.
_STRONG_SLASH = {
    "help", "features", "toggle", "provider", "providers", "theme", "themes",
    "dashboard", "books", "praise", "retry", "reset", "compact", "seed-skills", "seed",
}

# Slash-command manual, grouped by category (single source for /help; the
# completion dropdown derives from _SLASH_COMPLETIONS below). Each group is
# (category-header, [(usage, description), ...]); headers render dimmed.
_SLASH_HELP = [
    ("session", [
        ("/use <book> · /books", "set active book · list books"),
        ("/mode [book|article]", "show or set the project mode (default: book)"),
        ("/path [...]", "where exports are saved - default or per-project, with move"),
        ("/auto [on|off]", "autonomous (never pause) vs manual (review each unit)"),
        ("/retry", "resend the last chat message"),
        ("/reset · /compact", "clear · summarize the assistant's conversation memory"),
    ]),
    ("configuration", [
        ("/features", "interactive toggle grid - ↑↓ move · space toggle · ↵ save"),
        ("/set <key> <value>", "change one setting live (e.g. /set use_researcher true)"),
        ("/provider [<id>]", "list or switch the model host (openrouter, deepseek, openai, ollama, ...)"),
        ("/model [<agent>] <slug>", "show / set per-agent model routing (slugs for the active host)"),
        ("/theme [<name>]", "list or switch themes - palette, wordmark font, and glyphs"),
    ]),
    ("craft & skills", [
        ("/skills · /skill <name>", "list skills · show one skill"),
        ("/seed-skills", "install the built-in craft skills"),
        ("/praise [N]", "mark a committed chapter/section as great - feeds voice + learner"),
    ]),
    ("project & telemetry", [
        ("/user <id> · /config", "switch user · show config"),
        ("/update [changes]", "describe your changes - AI reviews and advises on next steps"),
        ("/dashboard [<project>]", "telemetry rollup - calls, tokens, cost, latency, errors"),
    ]),
    ("info", [
        ("/help", "this panel + the full command list"),
        ("/clear · /exit", "clear screen · quit"),
    ]),
]
_MARKUP = re.compile(r"\[/?[^\]]*\]")
# Matches fenced code blocks: ```cmd``` or ```lang\ncmd\n```. The info string
# (language tag) is only consumed when it ends in a newline - otherwise a
# single-line block like ```run``` would lose its whole content to the tag
# and the capture group would come back empty.
_CODE_BLOCK_RE = re.compile(r"```(?:[A-Za-z0-9_+-]*\n)?(.*?)```", re.DOTALL)

# ── chat system prompt ────────────────────────────────────────────────────────
_CHAT_SYSTEM = """\
You are the built-in assistant for WRITING AGENT - an autonomous book-writing studio.
Help users understand the system, figure out what to do next, and get unblocked.
The current date is injected into your session context below - always use it when the user
asks about timing, recency, or anything date-dependent (e.g. "today", "this week", "recently").

WRITING AGENT writes complete books: give it an abstract, it plans, writes, critiques,
revises, and assembles a finished manuscript (PDF or EPUB). It runs on OpenRouter + DeepSeek.

COMMANDS  (type these directly in this shell - no 'book' prefix needed):
  write --abstract "..."     One-shot: asks a few questions upfront, then autonomously
                             researches, writes, and EXPORTS a finished file. No pauses.
                             (Interactive - tell the user to type it themselves; never auto-run it.)
  new --abstract "..."       Start a new project - book (default) or article (when mode=article)
  run                        Write the book/article - drafts, critiques, humanises, commits
  status                     Where the project is (phase, chapter/section, pending reviews)
  review --chapter N \\
    --instruction "..."      Answer an escalation when the book gets stuck
  revise --chapter N \\
    --instruction "..."      Rewrite ONE committed chapter/section of a finished piece
                             (e.g. "make section 3 more technical") and re-assemble
  read [--chapter N]         Read a chapter; add --summary, --manuscript, or --v K (a version)
  versions [--chapter N]     List draft snapshots (variants, revisions, committed finals)
  brief                      Show the goal: thesis, audience, target length
  tableread [--as "..."]     Skeptical-reader pass over the finished piece (optional persona)
  eval                       Quality report: 5-dim judged rubric + deterministic metrics
  export [fmt ...]           Export: pdf · epub · html · docx · txt · md · all  (prompts if omitted)
  memory                     Inspect characters, timeline, entity graph
  skills                     List learned craft skills + efficacy
  list                       List all your books
  consolidate                Run a global contradiction / continuity check
  produce                    Re-run front/back-matter generation
  delete [--yes]             Permanently delete a book/article (asks for confirmation)

SLASH COMMANDS  (start with /):
  /set <key> <value>         Change a setting live - use_researcher, use_images,
                             use_embeddings, humanize, autonomous, num_chapters, etc.
  /model [agent] <slug>      Switch any model to any OpenRouter slug
  /use <book>                Set the active book (avoids typing --book-id every time)
  /books · /skills           List books · browse craft skills
  /retry                     Resend your last chat message
  /mode [book|article]       Show or set mode - 'book' for novels/nonfiction, 'article' for single long-form articles
  /theme [<name>]            List or switch theme (changes palette + wordmark font) - editorial (default),
                             kazama, supabase, violet-bloom, t3-chat, starry-night, vercel, fallout, mimi, astrovista
  /dashboard [<project>]     Telemetry rollup: LLM calls, tokens, cost, latency, errors - overall, or
                             per project with a per-chapter/section breakdown
  /reset                     Clear assistant memory (fresh context)
  /compact                   Summarize memory to save context space
  /help                      Show all slash commands

TYPICAL FIRST SESSION:
  1.  new --abstract "A thriller about a forger in 1920s Paris"
  2.  run
  3.  export   (pick: pdf / epub / html / docx / txt / md, or `export all`)

NATURAL LANGUAGE → COMMAND EXECUTION:
You can understand plain English and convert it into commands that run automatically.

WHEN TO EXECUTE (user wants action, not just advice):
- "continue with deathdates", "start writing", "run the book", "do it", "go ahead"
- "turn on researcher", "set chapters to 12", "use book X", "show status"
- Any request that maps to a specific command or sequence of commands

HOW TO TRIGGER EXECUTION:
Put each command on its own line as a fenced code block. The shell will run them in order.
Example - user says "continue with mybook":
```/use mybook```
```run```

Example - user says "turn on web search and start writing":
```/set use_researcher true```
```run```

CONTEXT-AWARE EXECUTION (CRITICAL):
The session context below always shows the ACTIVE PROJECT. Check it first.

  active project: (none)  →  NEVER run `run`/`status`/`read`/`export` bare.
                              Look at "all projects" in the context, pick the right one, and
                              ALWAYS emit `/use <exact-id>` BEFORE any project command.
                              Example - user says "run it" and you see project my-article:
                              ```/use my-article```
                              ```run```

  active project: my-project  →  Run commands DIRECTLY. Do NOT emit `/use` - the active
                              project is already correct, and a `/use` risks switching to the
                              wrong one. Example - user says "export to epub":
                              ```export epub```
                              Only emit `/use` when the user EXPLICITLY asks to open a DIFFERENT
                              project that appears by name in "all projects".

  NEVER invent or guess a project id. Copy it EXACTLY from "all projects" - the id only,
  WITHOUT the "(type: article)" tag. If you're unsure which project, use the active one.
  DO NOT ask "which project?" in text. Just pick the most relevant one from context and use it.
  The shell auto-routes to the right project type for the current mode.

RESOLVING AN ESCALATION (when SESSION CONTEXT shows "ESCALATION PENDING"):
A chapter/section stalled at review and the pipeline is PAUSED waiting on the user.
Do NOT just run `status` or `read` - that leaves them stuck (this is the #1 mistake).
Read the blocking issues shown in the context, then pick by the user's intent:
- They give direction OR just say "fix it"/"continue"/"keep going":
  Turn their intent + the critic's blocking issues into ONE concrete instruction:
  ```review --chapter <N> --instruction "<specific, actionable fixes>"```
  ```run```
- They want it DONE with no more review ("just finish", "finish all", "do the rest",
  "stop asking me", "the whole thing"):
  ```run --autonomous```
Use the unit number <N> straight from the SESSION CONTEXT.

AUTONOMOUS vs MANUAL RUN MODE:
- "finish all" / "do everything" / "run to the end" / "don't pause"  →  ```run --autonomous```
  (commits the best draft for every remaining unit and runs through to export, no pauses)
- "let me review each part" / "pause for me" / "go back to manual"   →  ```run --manual```

POST-COMPLETION REVISION (the project is DONE but the user wants a change):
- "make section 3 more technical", "rewrite the intro, punchier", "add benchmarks to ch 2" →
  ```revise --chapter 3 --instruction "more technical - add concrete benchmarks"```
  This rewrites just that unit and re-assembles the manuscript; suggest re-export after.

NEW TOPIC FLOW (no project yet → propose first, execute on confirmation):
When the user describes something to write (a topic, question, or idea - even when
phrased as a command, e.g. "write an article on X" or a pasted `new ... run` line):
1. PROPOSE - reply in plain text with a short abstract shown as inline code:
     I'll write: `the fastest 100ms-latency voice agents - techniques and trade-offs`
   Then ask: say "run it" / "go ahead" to start writing, or tell me what to change.
   Do NOT emit any fenced code block in this turn.
2. REFINE - if the user replies with changes or additions in plain English
   ("also cover WebRTC", "make it more technical", "add a section on costs"),
   merge them into a REVISED abstract, show it the same way, and ask again.
   Every refinement turn: updated abstract as inline code, NO fenced blocks.
3. EXECUTE - when the user confirms ("run it", "go ahead", "yes", "start", "do it"),
   emit BOTH commands as fenced blocks in ONE response:
   ```new --abstract "<final abstract>"```
   ```run```
   The shell runs them in order; the project created by `new` becomes active
   before `run` starts, so writing begins immediately.

The shell ENFORCES this flow: a ```new``` block is executed ONLY on a turn where the
user's own message was an explicit confirmation. If you emit ```new``` before the
user confirmed, the shell holds the commands un-run and asks the user to confirm -
so always PROPOSE first; skipping it just wastes a turn.

`new` COMMAND RULES:
- `new` picks an angle/direction automatically (auto-selects option 1).
  After it runs, the new project becomes active automatically - that is why
  `new` followed by `run` in the same response is safe and is THE way to
  start writing after a confirmation.
- If a project already EXISTS and is active, "run it" / "go ahead" means just ```run```.
- ALWAYS wrap the --abstract value in double quotes.
  Keep it SHORT (under 100 characters). The planner fleshes it out.
  CORRECT:   ```new --abstract "Can LLMs ever achieve AGI? 2026 analysis"```
  WRONG:     ```new --abstract Can LLMs ever achieve AGI? 2026 analysis```

ONLY USE CODE BLOCKS FOR COMMANDS YOU WANT EXECUTED.
Use plain text or inline `backticks` when explaining commands without running them.
Never show fake/simulated output - the real output will appear automatically.

When the user is just asking a question (what does X do, how do I Y):
- Answer in plain text. Do not include executable code blocks.

Answer concisely. Keep under ~200 words unless the question demands more.\
"""


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
        from . import providers
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
        from . import providers
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
    from .brain import ArticlePaths, BookPaths
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


def _command_help_rows(settings: Settings) -> list[tuple[str, str]]:
    """The project-command (name, description) rows - single source for the /help
    COMMANDS table and the /help <topic> search."""
    is_article = settings.mode == "article"
    if is_article:
        new_desc = "start an article - topic → angles → outline + sections"
    else:
        new_desc = "start a book - idea → directions → plan + TOC"
    export_desc = "pdf · epub · html · docx · txt · md · all  (prompts if omitted)"
    rows = [
        ("write --abstract \"...\"", "★ ask a few questions upfront, then autonomously "
                                     "research → write → export a finished file"),
        ("new --abstract \"...\"", new_desc + "  (then `run`)"),
        ("run", "write it - draft · critique · humanise · commit per section" if is_article
                else "write it - draft · critique · humanise · commit per chapter"),
        ("status · review", "where the project stands · answer escalations"),
        ("revise --chapter N ...", "rewrite one committed section/chapter to your instruction"),
        ("brief · versions · eval", "the goal · draft history · quality scorecard"),
        ("evidence", "thesis + sources ranked by influence → evidence_report.md (shareable proof)"),
        ("tableread [--as \"...\"]", "skeptical-reader report on the finished piece"),
        ("read", "section (--chapter N) · --summary · --manuscript" if is_article
                 else "chapter (--chapter N) · --summary · --manuscript"),
        ("export [fmt ... | all]", export_desc),
        ("memory · skills · list", "canon & timeline · craft skills · all projects"),
        ("delete [--yes]", "permanently delete a project"),
        ("/mode book", "switch to book mode (chapters, novel/nonfiction)") if is_article
        else ("/mode article", "switch to article mode (single long-form piece)"),
    ]
    return rows


def _commands_table(console, settings: Settings) -> None:
    """The full project-command list (lives under /help; was the welcome screen)."""
    rows = _command_help_rows(settings)
    if not console:
        for a, b in rows:
            print(f"  {_MARKUP.sub('', a):<28} {_MARKUP.sub('', b)}")
        return
    _section(console, "COMMANDS")
    _cmd_table(console, rows)


def _features_table(console, settings: Settings) -> None:
    """Feature toggles with live state (lives under /features; was the welcome screen)."""
    is_article = settings.mode == "article"
    rows = [
        _feat_row("humanize   ", settings.humanize,
                  "strip AI tells from prose (em-dashes, AI phrasing)"),
        _feat_row("researcher ", settings.use_researcher,
                  "web search per section - real facts + inline citations" if is_article
                  else "DuckDuckGo web search per chapter - grounds facts"),
        _feat_row("deep search", settings.deep_research,
                  "multi-query fan-out + full-page fetch + cross-source synthesis "
                  "(needs researcher)"),
        _feat_row("embeddings ", settings.use_embeddings,
                  "semantic skill retrieval (all-MiniLM-L6-v2, local)"),
        _feat_row("images     ", settings.use_images,
                  "Wikimedia Commons images for illustrated/technical content"),
        _feat_row("cohesion   ", settings.article_cohesion,
                  "whole-article smoothing pass before References (articles)"),
        _feat_row("tournament ", settings.tournament_judge,
                  "pick the best divergent draft side-by-side (best-of-N judge)"),
        _feat_row("verify     ", settings.verify_claims,
                  "check each cited claim vs its source (blocks under deep research)"),
        _feat_row("table read ", settings.table_read,
                  "skeptical whole-piece reader pass (articles)"),
        _feat_row("reader-loop", settings.table_read_revise,
                  "autonomous: apply the reader's top fix as one revision"),
        ("", ""),
        ("quality knobs",
         f"divergent_drafts={settings.divergent_drafts}, min_insight={settings.min_insight}/5"),
        ("/set <key> true/false", "toggle any feature above and save instantly"),
    ]
    if not console:
        for a, b in rows:
            print(f"  {_MARKUP.sub('', a):<28} {_MARKUP.sub('', b)}")
        return
    _section(console, "FEATURES")
    _cmd_table(console, rows)


# Live-toggleable feature booleans for the interactive /features grid. Mirrors
# the static table above; (settings attribute, label, one-line description).
_FEATURE_KEYS = [
    ("humanize",          "humanize",    "strip AI tells from prose (em-dashes, AI phrasing)"),
    ("use_researcher",    "researcher",  "web search per unit - real facts + inline citations"),
    ("deep_research",     "deep search", "multi-query fan-out + full-page fetch (needs researcher)"),
    ("use_embeddings",    "embeddings",  "semantic skill retrieval (all-MiniLM-L6-v2, local)"),
    ("use_images",        "images",      "Wikimedia Commons images for illustrated content"),
    ("article_cohesion",  "cohesion",    "whole-article smoothing pass before References"),
    ("tournament_judge",  "tournament",  "best-of-N judge: pick the strongest divergent draft"),
    ("verify_claims",     "verify",      "check each cited claim against its source"),
    ("table_read",        "table read",  "skeptical whole-piece reader pass (articles)"),
    ("table_read_revise", "reader-loop", "autonomous: apply the reader's top fix as one revision"),
]


def _toggle_grid(console, settings: Settings) -> bool:
    """Interactive feature-toggle grid: ↑↓ move · space toggle · ↵ save · esc cancel.

    Flips boolean settings in one keyboard-driven view instead of one /set at a
    time. Edits apply and persist only on ↵ (esc discards). Returns True if
    anything was saved. Falls back to the static /features table (returns False)
    when there's no interactive TTY or prompt_toolkit is unavailable - so it
    degrades cleanly under pipes, CI, and dumb terminals.
    """
    import sys as _sys
    try:
        if not _sys.stdin.isatty():
            raise RuntimeError("no tty")
        from prompt_toolkit.application import Application
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import Layout, Window
        from prompt_toolkit.layout.controls import FormattedTextControl
        from prompt_toolkit.styles import Style
    except Exception:
        _features_table(console, settings)
        return False

    rows = [{"key": k, "label": lbl, "desc": d, "on": bool(getattr(settings, k, False))}
            for k, lbl, d in _FEATURE_KEYS]
    sel = {"i": 0}
    _OFF = "#6b6b6b"   # pt needs hex; ui.OFF_CLR/DIM are Rich names ("grey50"/"grey42")

    def render():
        frags = [("class:title", f" {_NIB}  FEATURES"),
                 ("class:hint", "    space toggle · ↑↓ move · ↵ save · esc cancel"),
                 ("", "\n\n")]
        for i, r in enumerate(rows):
            cur = i == sel["i"]
            frags.append(("class:ptr", "  › " if cur else "    "))
            frags.append(("class:on" if r["on"] else "class:off",
                          "● " if r["on"] else "○ "))
            frags.append(("class:cur" if cur else "class:lbl", f"{r['label']:<12}"))
            frags.append(("class:desc", f"  {r['desc']}"))
            if i < len(rows) - 1:
                frags.append(("", "\n"))
        return frags

    kb = KeyBindings()

    @kb.add("up")
    @kb.add("c-p")
    def _(_e):
        sel["i"] = (sel["i"] - 1) % len(rows)

    @kb.add("down")
    @kb.add("c-n")
    def _(_e):
        sel["i"] = (sel["i"] + 1) % len(rows)

    @kb.add("space")
    def _(_e):
        rows[sel["i"]]["on"] = not rows[sel["i"]]["on"]

    @kb.add("enter")
    def _(e):
        e.app.exit(result=True)

    @kb.add("escape")
    @kb.add("c-c")
    @kb.add("q")
    def _(e):
        e.app.exit(result=False)

    control = FormattedTextControl(render, focusable=True, show_cursor=False)
    layout = Layout(Window(control, height=len(rows) + 2))
    style = Style.from_dict({
        "title": f"bold {GOLD}",
        "hint":  _OFF,
        "ptr":   GOLD_HI,
        "on":    ON_CLR if str(ON_CLR).startswith("#") else "#6aaa5c",
        "off":   _OFF,
        "lbl":   PARCH,
        "cur":   f"bold {GOLD_HI}",
        "desc":  _OFF,
    })
    try:
        saved = Application(layout=layout, key_bindings=kb, style=style,
                            full_screen=False, mouse_support=False).run()
    except Exception:
        _features_table(console, settings)
        return False

    if not saved:
        _out(console, "[dim]features unchanged[/]")
        return False
    changed = []
    for r in rows:
        if bool(getattr(settings, r["key"], False)) != r["on"]:
            setattr(settings, r["key"], r["on"])
            changed.append((r["label"].strip(), r["on"]))
    if not changed:
        _out(console, "[dim]features unchanged[/]")
        return False
    save_settings(settings)
    parts = " · ".join(f"[{ON_CLR if on else OFF_CLR}]{lbl} {'on' if on else 'off'}[/]"
                       for lbl, on in changed)
    _out(console, f"[{GOLD}]saved[/]  {parts}")
    return True


def _slash_help(console, settings: Settings | None = None, topic_args=None) -> None:
    topic = " ".join(topic_args or []).strip().lower().lstrip("/")
    if topic:
        _slash_help_topic(console, settings, topic)
        return
    if not console:
        for cat, group in _SLASH_HELP:
            print(f"\n  {cat}")
            for name, desc in group:
                print(f"    {name:<26} {desc}")
        return
    from rich.text import Text
    if settings is not None:
        _commands_table(console, settings)
    _section(console, "SLASH COMMANDS")
    for cat, group in _SLASH_HELP:
        console.print(Text(f"  {cat}", style=DIM))
        _cmd_table(console, group)
    console.print(Text(f"  agents: {', '.join(_NODES)}", style=DIM))
    console.print(Text("  focused help:  /help <topic>   (e.g. /help export, /help model)", style=DIM))


def _slash_help_topic(console, settings: Settings | None, topic: str) -> None:
    """Progressive disclosure: `/help <topic>` shows only the command + slash entries
    whose name or description matches, instead of the whole manual."""
    cmd_rows = _command_help_rows(settings) if settings is not None else []
    slash_rows = [row for _cat, grp in _SLASH_HELP for row in grp]
    matches = [(n, d) for (n, d) in (cmd_rows + slash_rows)
               if topic in _MARKUP.sub("", n).lower() or topic in _MARKUP.sub("", d).lower()]
    if not matches:
        _out(console, f"[dim]no help entry matches “{topic}”.  /help lists everything.[/]")
        return
    if console:
        _section(console, f"HELP · {topic}")
        _cmd_table(console, matches)
    else:
        for n, d in matches:
            print(f"  {_MARKUP.sub('', n):<28} {_MARKUP.sub('', d)}")


# ── Slash handlers ────────────────────────────────────────────────────────────

def _model_catalog(console) -> None:
    """Browse popular models (`/model list`). Any slug works; this is just discovery."""
    from . import providers
    if console:
        _section(console, "POPULAR MODELS")
        rows = [(fam if i == 0 else "", s)               # family shown once; one slug per line
                for fam, slugs in providers.POPULAR_MODELS
                for i, s in enumerate(slugs)]
        _cmd_table(console, rows)
        _out(console, "  [dim]OpenRouter slugs (the default host) - set with /model <agent> <slug> "
                      "or /model <slug> for all. Full list: openrouter.ai/models · other hosts: /provider[/]")
    else:
        for fam, slugs in providers.POPULAR_MODELS:
            print(f"  {fam}: {', '.join(slugs)}")


def _cmd_model(console, cfg: ModelConfig, rest: list[str]) -> None:
    if rest and rest[0].lower() in ("list", "catalog", "popular", "browse"):
        _model_catalog(console)
        return
    if not rest:
        rows = [("default", cfg.default)] + [(n, cfg.model_for(n)) for n in _NODES]
        if console:
            _section(console, "MODELS")
            _cmd_table(console, rows)
            _out(console, "  [dim]change: /model <agent> <slug> · all: /model <slug> · "
                          "browse: /model list · other hosts: /provider[/]")
        else:
            for a, b in rows:
                print(f"  {a:<14} {b}")
        return
    if len(rest) == 1:
        cfg.set_all(rest[0])
        save_config(cfg)
        _out(console, f"all agents -> [{GOLD}]{rest[0]}[/] [dim](saved)[/]")
        return
    node, slug = rest[0], rest[1]
    match, cands = ui.smart_match(node, ["default", *_NODES])
    if not match:
        tail = f"matches: {', '.join(cands)}" if cands else f"agents: {', '.join(_NODES)}"
        _out(console, f"[{ERR}]unknown agent '{node}'[/] - {tail}")
        return
    node = match
    cfg.set_default(slug) if node == "default" else cfg.set_node(node, slug)
    save_config(cfg)
    _out(console, f"[{GOLD}]{node}[/] -> [{GOLD}]{slug}[/] [dim](saved)[/]")


def _cmd_provider(console, settings: Settings, rest: list[str]) -> None:
    """Show or switch the model host. `/provider` lists every provider with a
    key/local marker; `/provider <id>` switches, persists, and rebuilds the client."""
    from . import llm, providers
    if not rest:
        active = providers.resolve(settings.provider)
        rows = []
        for pid in providers.names():
            p = providers.REGISTRY[pid]
            if p.local:
                mark, tag = ON_CLR, "local"
            elif providers.has_credentials(p):
                mark, tag = ON_CLR, "key set"
            else:
                mark, tag = OFF_CLR, "no key"
            dot = "●" if pid == active else "○"
            rows.append((f"[{mark}]{dot} {pid:<11}[/]",
                         f"[{PARCH}]{p.name}[/]  [dim]{tag} · {p.notes}[/]"))
        if console:
            _section(console, "PROVIDERS")
            _cmd_table(console, rows)
            _out(console, "  [dim]switch: /provider <id>  ·  set the key in .env or your shell[/]")
        else:
            for a, b in rows:
                print(f"  {_MARKUP.sub('', a):<16} {_MARKUP.sub('', b)}")
        return

    p = providers.get(rest[0])                    # exact id or alias
    if not p:                                      # then a partial/typo
        match, cands = ui.smart_match(rest[0], providers.names())
        if match:
            p = providers.REGISTRY[match]
        elif cands:
            _out(console, f"[{ERR}]'{rest[0]}' matches several:[/] [dim]{', '.join(cands)}[/]")
            return
        else:
            _out(console, f"[{ERR}]unknown provider '{rest[0]}'[/] [dim](see /provider for the list)[/]")
            return
    settings.provider = p.id
    save_settings(settings)
    try:
        llm.configure_provider(p.id)
    except ValueError as e:
        _out(console, f"[{ERR}]{e}[/]")
        return
    note = ""
    if not providers.has_credentials(p):
        envs = " or ".join(p.key_env) or "(none)"
        note = f" · [{ERR}]no key yet[/][dim] - set {envs}[/]"
    elif p.id != "openrouter":
        note = " · [dim]models use this host's slugs - set them with /model[/]"
    _out(console, f"provider -> [{GOLD}]{p.id}[/] [dim]({p.name}, saved)[/]{note}")


def _norm_dir(raw: str):
    from pathlib import Path
    raw = (raw or "").strip().strip('"').strip("'")
    p = Path(raw).expanduser()
    try:
        return p.resolve()
    except (OSError, RuntimeError):
        return p


def _ensure_dir(d) -> tuple[bool, str]:
    try:
        if d.exists() and not d.is_dir():
            return False, "that path is a file, not a folder"
        d.mkdir(parents=True, exist_ok=True)
        return True, ""
    except OSError as e:
        return False, str(e)


def _print_path_status(console, settings: Settings, uid: str) -> None:
    rows = [("default", settings.export_dir.strip() or "[dim]each project's own folder[/]")]
    for pid, _ptype in brain.list_projects(uid):
        ov = brain.get_project_export_dir(uid, pid)
        if ov:
            rows.append((pid, ov))
    if console:
        _section(console, "SAVE PATHS")
        _cmd_table(console, rows)
        _out(console, "  [dim]change: /path (menu) · /path default <dir> · /path <project> <dir>[/]")
    else:
        for a, b in rows:
            print(f"  {a:<16} {_MARKUP.sub('', b)}")


def _set_default_path(console, settings: Settings, raw: str) -> None:
    d = _norm_dir(raw)
    ok, err = _ensure_dir(d)
    if not ok:
        _out(console, f"[{ERR}]can't use that folder:[/] {err}")
        return
    settings.export_dir = str(d)
    save_settings(settings)
    _out(console, f"default save path -> [{GOLD}]{d}[/] "
                  f"[dim](saved · for projects without their own path)[/]")


def _set_project_path(console, settings: Settings, uid: str, pid: str, raw: str,
                      *, ask_move: bool = True) -> None:
    d = _norm_dir(raw)
    ok, err = _ensure_dir(d)
    if not ok:
        _out(console, f"[{ERR}]can't use that folder:[/] {err}")
        return
    old = brain.resolve_export_dir(uid, pid)
    brain.set_project_export_dir(uid, pid, str(d))
    new = brain.resolve_export_dir(uid, pid)
    _out(console, f"[{GOLD}]{pid}[/] save path -> [{GOLD}]{new}[/] [dim](saved)[/]")
    existing = [f for f in brain.EXPORT_DELIVERABLES if (old / f).exists()]
    if old.resolve() == new.resolve() or not existing:
        return
    do_move = True
    if ask_move and console:
        ans = console.input(
            f"  [{INK}]move {len(existing)} existing export(s) from[/] [dim]{old}[/] "
            f"[{DIM}][Y/n][/] ")
        do_move = ui.is_affirmative(ans, default=True)
    if do_move:
        moved = brain.move_exports(old, new)
        _out(console, f"[{ON_CLR}]moved {len(moved)} file(s)[/] [dim]{', '.join(moved)}[/]")
    else:
        _out(console, "[dim]left existing exports where they are[/]")


def _cmd_path(console, settings: Settings, state: dict, rest: list[str]) -> None:
    """Choose where finished writing is saved: a global default plus per-project
    folders, with the option to move a project's existing exports to the new home."""
    uid = state["uid"]
    if rest:
        head, low = rest[0], rest[0].lower()
        if low == "show":
            _print_path_status(console, settings, uid)
        elif low == "default":
            if len(rest) >= 2:
                _set_default_path(console, settings, " ".join(rest[1:]))
            elif console:
                raw = console.input("  default save folder: ").strip()
                if raw:
                    _set_default_path(console, settings, raw)
            else:
                _out(console, "usage: /path default <dir>")
        elif low == "clear":
            if len(rest) >= 2:
                brain.set_project_export_dir(uid, rest[1], None)
                _out(console, f"cleared save path for [{GOLD}]{rest[1]}[/] [dim](back to default)[/]")
            else:
                settings.export_dir = ""
                save_settings(settings)
                _out(console, "cleared default save path [dim](exports go to each project's folder)[/]")
        else:                                         # head is (or should be) a project id
            pid, cands = brain.resolve_project(uid, head)
            if not pid:
                if cands:
                    _out(console, f"[{ERR}]'{head}' matches several:[/] [dim]{', '.join(cands)}"
                                  f" - be more specific[/]")
                else:
                    sug = ui.did_you_mean(head, [p[0] for p in brain.list_projects(uid)])
                    hint = f"did you mean '{sug}'?" if sug else "see /path show"
                    _out(console, f"[{ERR}]no project '{head}'[/] [dim]({hint})[/]")
            elif len(rest) >= 2:
                _set_project_path(console, settings, uid, pid, " ".join(rest[1:]))
            elif console:
                raw = console.input(f"  save folder for '{pid}': ").strip()
                if raw:
                    _set_project_path(console, settings, uid, pid, raw)
            else:
                _out(console, f"usage: /path {pid} <dir>")
        return

    # No args -> the interactive menu (default vs. a project, then move-or-not).
    _print_path_status(console, settings, uid)
    if not console:
        _out(console, "usage: /path default <dir> | /path <project> <dir> | /path show")
        return
    console.print()
    console.print(f"  [{GOLD}][1][/] set the [bold]default[/] save path  "
                  f"[dim]- all projects without their own[/]")
    console.print(f"  [{GOLD}][2][/] set a path for [bold]one project[/]  "
                  f"[dim]- and optionally move its exports[/]")
    choice = console.input(f"  [{INK}]choose[/] [dim][1/2, enter to cancel][/] ").strip()
    if choice == "1":
        raw = console.input("  default save folder: ").strip()
        if raw:
            _set_default_path(console, settings, raw)
    elif choice == "2":
        projects = brain.list_projects(uid)
        if not projects:
            _out(console, "[dim](no projects yet - create one first)[/]")
            return
        console.print()
        for i, (pid, ptype) in enumerate(projects, 1):
            ov = brain.get_project_export_dir(uid, pid)
            tag = f"  [dim]-> {ov}[/]" if ov else ""
            console.print(f"  [{GOLD}][{i}][/] {pid} [dim][{ptype}][/]{tag}")
        sel = console.input(f"  [{INK}]project number[/] [dim][enter to cancel][/] ").strip()
        if not sel.isdigit() or not (1 <= int(sel) <= len(projects)):
            _out(console, "[dim]cancelled[/]")
            return
        pid = projects[int(sel) - 1][0]
        raw = console.input(f"  save folder for '{pid}': ").strip()
        if raw:
            _set_project_path(console, settings, uid, pid, raw)
    else:
        _out(console, "[dim]cancelled[/]")


def _use_project(console, uid: str, query: str, state: dict) -> None:
    """Set the active project from a name, an excerpt, or a typo - presenting a
    numbered picker when several match (see brain.resolve_project)."""
    resolved, cands = brain.resolve_project(uid, query)
    if resolved:
        state["book"] = resolved
        _out(console, f"active book -> [{GOLD}]{resolved}[/]")
        return
    if cands:
        if console:
            _out(console, f"[dim]{len(cands)} projects match '{query}':[/]")
            for i, c in enumerate(cands, 1):
                console.print(f"  [{GOLD}][{i}][/] {c}")
            sel = console.input(f"  [{INK}]pick a number[/] [dim][enter to cancel][/] ").strip()
            if sel.isdigit() and 1 <= int(sel) <= len(cands):
                state["book"] = cands[int(sel) - 1]
                _out(console, f"active book -> [{GOLD}]{state['book']}[/]")
            else:
                _out(console, "[dim]cancelled[/]")
        else:
            _out(console, "matches: " + ", ".join(cands))
        return
    valid = [p[0] for p in brain.list_projects(uid)]
    sug = ui.did_you_mean(query, valid)
    tail = (f"did you mean '{sug}'?" if sug
            else "available: " + (", ".join(sorted(valid)) or "(none yet)"))
    _out(console, f"[{ERR}]no project matching '{query}'[/] [dim]{tail}[/]")


def _cmd_dashboard(console, uid: str, rest: list[str]) -> None:
    """/dashboard [project] - telemetry rollup: calls, tokens, cost, latency, errors."""
    from . import telemetry
    project = " ".join(rest) if rest else None
    if project and project not in {p[0] for p in brain.list_projects(uid)}:
        project, cands = brain.resolve_project(uid, project)
        if not project:
            tail = (f"matches: {', '.join(cands)}" if cands else "see /books")
            _out(console, f"[{ERR}]no project '{' '.join(rest)}'[/] [dim]({tail})[/]")
            return
    s = telemetry.summarize(project)
    t = s["totals"]
    scope = project or "all projects"
    if not t["calls"]:
        _out(console, f"[dim](no telemetry yet for {scope} - records are written per "
                      "LLM call to .index/telemetry/)[/]")
        return

    cost_part = f"   ·   ${t['cost']:.4f}" if t["cost"] > 0 else ""
    err_clr = ERR if t["errors"] else DIM
    if not console:
        print(f"dashboard: {scope}")
        print(f"  {t['calls']} calls   {t['tokens']:,} tokens{cost_part}   "
              f"~{t['avg_latency_ms']} ms/call   {t['errors']} errors")
        for model, calls, toks, cost in s["by_model"]:
            print(f"  {model:<38} {calls:>5} calls  {toks:>10,} tok  ${cost:.4f}")
        return

    from rich.table import Table
    from rich.text import Text
    _section(console, f"DASHBOARD  ·  {scope}")
    head = Text("  ")
    head.append(f"{t['calls']:,} calls", style=PARCH)
    head.append(f"   ·   {t['tokens']:,} tokens", style=PARCH)
    if t["cost"] > 0:
        head.append(f"   ·   ${t['cost']:.4f}", style=f"bold {GOLD}")
    head.append(f"   ·   ~{t['avg_latency_ms']:,} ms/call", style=DIM)
    head.append(f"   ·   {t['errors']} errors", style=err_clr)
    console.print(head)

    bm = Table(box=None, show_header=True, header_style=DIM, padding=(0, 3, 0, 2))
    bm.add_column("model", style=f"bold {GOLD}", no_wrap=True)
    bm.add_column("calls", justify="right", style=PARCH)
    bm.add_column("tokens", justify="right", style=PARCH)
    bm.add_column("cost", justify="right", style=PARCH)
    for model, calls, toks, cost in s["by_model"]:
        bm.add_row(model, f"{calls:,}", f"{toks:,}", f"${cost:.4f}" if cost else "-")
    console.print(bm)

    if project:
        bu = Table(box=None, show_header=True, header_style=DIM, padding=(0, 3, 0, 2))
        bu.add_column("unit", style=INK, no_wrap=True)
        bu.add_column("calls", justify="right", style=PARCH)
        bu.add_column("tokens", justify="right", style=PARCH)
        bu.add_column("cost", justify="right", style=PARCH)
        for unit, calls, toks, cost in s["by_unit"]:
            bu.add_row(unit, f"{calls:,}", f"{toks:,}", f"${cost:.4f}" if cost else "-")
        console.print(bu)
    else:
        rr = Table(box=None, show_header=True, header_style=DIM, padding=(0, 3, 0, 2))
        rr.add_column("run", style=DIM, no_wrap=True)
        rr.add_column("project", style=INK)
        rr.add_column("calls", justify="right", style=PARCH)
        rr.add_column("tokens", justify="right", style=PARCH)
        rr.add_column("cost", justify="right", style=PARCH)
        for run_id, proj, calls, toks, cost in s["runs"][-6:]:
            rr.add_row(run_id, proj, f"{calls:,}", f"{toks:,}",
                       f"${cost:.4f}" if cost else "-")
        console.print(rr)
        console.print(Text("  /dashboard <project> for the per-chapter/section breakdown",
                           style=DIM))


def _set_theme(name: str, console, settings: Settings) -> None:
    """Apply + persist a theme; shared by /theme and /set theme."""
    settings.theme = name
    save_settings(settings)
    ui.apply_theme(name)
    _sync_palette()
    _out(console, f"theme -> [{ui.GOLD}]{name}[/] [dim](saved - the prompt/completion "
                  f"styles refresh on next launch)[/]")


def _cmd_set(console, settings: Settings, rest: list[str]) -> None:
    import dataclasses
    if len(rest) < 2:
        fields = "  ".join(f.name for f in dataclasses.fields(settings))
        _out(console, f"usage: /set <key> <value>\nkeys: [dim]{fields}[/]")
        return
    key, raw = rest[0], rest[1]
    field_map = {f.name: f for f in dataclasses.fields(settings)}
    if key not in field_map:                       # resolve a partial/typo to a real key
        match, cands = ui.smart_match(key, list(field_map))
        if match:
            key = match
        elif cands:
            _out(console, f"[{ERR}]'{rest[0]}' matches several:[/] [dim]{', '.join(cands)}[/]")
            return
        else:
            valid = "  ".join(sorted(field_map))
            _out(console, f"[{ERR}]unknown setting '{rest[0]}'[/]\nvalid keys: [dim]{valid}[/]")
            return
    if key == "theme":   # needs the apply/sync side-effect, not just the setattr
        tname, _c = ui.smart_match(raw, ui.THEMES)
        if tname:
            _set_theme(tname, console, settings)
        else:
            _out(console, f"[{ERR}]unknown theme '{raw}'[/] [dim]- themes: "
                          f"{' · '.join(ui.THEMES)}[/]")
        return
    if key == "provider":   # needs the client rebuild, not just the setattr
        _cmd_provider(console, settings, [raw])
        return
    default = field_map[key].default
    try:
        if isinstance(default, bool):
            truthy, falsy = {"true", "1", "yes", "on"}, {"false", "0", "no", "off"}
            tok = raw.lower()
            if tok not in truthy | falsy:
                _out(console, f"[{ERR}]'{raw}' isn't a boolean[/] - use true/false "
                              f"[dim](got treated as false otherwise)[/]")
                return
            val = tok in truthy
        elif isinstance(default, int):
            val = int(raw)
        elif isinstance(default, float):
            val = float(raw)
        else:
            val = raw
        setattr(settings, key, val)
        save_settings(settings)
        _out(console, f"[{GOLD}]{key}[/] -> [{GOLD}]{val}[/] [dim](saved)[/]")
    except (ValueError, TypeError) as e:
        _out(console, f"[{ERR}]invalid value for '{key}': {e}[/]")


_AUTO_ON = {"on", "true", "1", "yes", "auto", "autonomous"}
_AUTO_OFF = {"off", "false", "0", "no", "manual", "human"}


def _cmd_auto(console, settings: Settings, state: dict, name: str, rest: list[str]) -> None:
    """Toggle autonomous (never-pause) vs manual (human-in-the-loop) run mode.

    Saves the default for new projects AND applies to the active project's
    run_state - so `/auto on` over a stalled section clears its review and the
    next `run` finishes the piece without pausing.
    """
    from . import orchestrator
    if name == "manual":
        want = False
    elif name == "autonomous":
        want = True
    elif rest:
        tok = rest[0].lower()
        if tok in _AUTO_ON:
            want = True
        elif tok in _AUTO_OFF:
            want = False
        else:
            _out(console, f"[{ERR}]usage:[/] /auto [on|off]  "
                          f"[dim](on = autonomous · off = manual)[/]")
            return
    else:
        cur = "autonomous" if settings.autonomous else "manual"
        _out(console, f"mode: [{GOLD}]{cur}[/] [dim](autonomous = never pause · "
                      f"manual = review each unit · switch with /auto on|off)[/]")
        return

    settings.autonomous = want
    save_settings(settings)
    label = "autonomous" if want else "manual"
    note = ""
    active = state.get("book")
    if active:
        st = orchestrator.apply_autonomous(state["uid"], active, want, settings)
        if st is not None:
            if want:
                note = f" · {active} won't pause - type `run` to finish it"
            else:
                note = f" · {active} will pause for review each unit"
    _out(console, f"mode -> [{GOLD}]{label}[/] [dim](saved{note})[/]")


def _cmd_praise(console, state: dict, rest: list[str]) -> None:
    """/praise [N] - mark a committed chapter/section as great writing.

    Saves it under the user's voice/ dir, where it feeds BOTH loops: future writer
    calls receive it as a register exemplar, and the learner distills what made it
    work (positive signal, not just failure patterns).
    """
    from .brain import ArticlePaths, BookPaths
    book = state.get("book")
    if not book:
        _out(console, f"[{ERR}]No active project.[/] Use `/use <project>` first.")
        return
    uid = state["uid"]
    art = ArticlePaths(book, uid)
    is_article = art.run_state.exists()
    st = brain.read_json(art.run_state if is_article else BookPaths(book, uid).run_state) or {}
    committed = int(st.get("committed", 0) or 0)
    try:
        n = int(rest[0]) if rest else committed
    except ValueError:
        _out(console, f"[{ERR}]usage:[/] /praise [chapter-or-section number]")
        return
    if n < 1:
        _out(console, "[dim](nothing committed yet - praise after a chapter/section lands)[/]")
        return
    unit = "section" if is_article else "chapter"
    text = brain.read_text(art.section(n) if is_article else BookPaths(book, uid).ch(n))
    if not text and is_article:
        # Finished articles clean up per-section files after the learn phase -
        # recover the section from the assembled manuscript instead.
        ms = brain.read_text(art.manuscript) or ""
        bodies = []
        for part in ms.split("\n\n---\n\n"):
            part = re.sub(r"^(?:-{3,}\s*)+", "", part.strip()).strip()  # doubled '---' seps
            if part.startswith("## ") and not part.startswith("## References"):
                bodies.append(part)
        if 1 <= n <= len(bodies):
            text = bodies[n - 1]
    if not text:
        _out(console, f"[{ERR}]no committed {unit} {n}[/] [dim](committed: {committed})[/]")
        return
    dest = brain.voice_dir(uid) / f"praised-{book}-{unit}{n:02d}.md"
    brain.write_text(dest, text)
    _out(console, f"[{GOLD}]praised[/] {unit} {n} of {book} [dim]-> {dest.name}; future drafts "
                  f"imitate its register and the learner distills why it works[/]")


def _print_skills(console, uid: str) -> None:
    rows = skills_mod.list_skills(uid)
    if not rows:
        _out(console, "[dim](no skills yet - try /seed-skills)[/]")
        return
    if console:
        from rich.table import Table
        _section(console, "SKILLS")
        t = Table(box=None, show_header=True, header_style=DIM, padding=(0, 3, 0, 1))
        t.add_column("skill", style=f"bold {GOLD}", no_wrap=True)
        t.add_column("status", style=PARCH)
        t.add_column("used", justify="right", style=DIM)
        t.add_column("efficacy  (vs baseline)", style=PARCH)
        for r in rows:
            t.add_row(r["name"], r["status"], str(r["applied"]),
                      ui.efficacy_bar(r["p_skill"], r["p_base"]))
        console.print(t)
    else:
        for r in rows:
            print(f"  {r['name']:<34} {r['status']:<10} applied={r['applied']} p={r['p_skill']}")


def _print_skill(console, uid: str, rest: list[str]) -> None:
    if not rest:
        _out(console, "usage: /skill <name>")
        return
    sdir = brain.skills_dir(uid)
    query = brain.slugify(" ".join(rest))
    text = brain.read_text(sdir / f"{query}.md")
    if not text and sdir.exists():                 # fuzzy: let users name a skill loosely
        names = [p.stem for p in sdir.glob("*.md")]
        match, cands = ui.smart_match(query, names)
        if match:
            text = brain.read_text(sdir / f"{match}.md")
        elif cands:
            _out(console, f"[dim]several skills match: {', '.join(cands)}[/]")
            return
    _out(console, text if text else f"[dim](no skill '{' '.join(rest)}')[/]")


# ── NL → command execution helpers ───────────────────────────────────────────

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

def _reduced_motion() -> bool:
    """Honor a reduced-motion preference: no spinner/cycling dots, just static stages
    + the elapsed clock. Set by BOOK_AGENT_REDUCED_MOTION or the a11y line-mode."""
    return bool(os.getenv("BOOK_AGENT_REDUCED_MOTION") or os.getenv("BOOK_AGENT_A11Y"))


def _a11y() -> bool:
    """Accessible line-mode (BOOK_AGENT_A11Y): no in-place Live redraw - screen readers
    can't follow a region that rewrites itself - just append one full status line per
    event. The same pipeline runs; only the rendering changes."""
    return bool(os.getenv("BOOK_AGENT_A11Y"))


class _RunControls:
    """Thread-safe flags the key-listener sets and the orchestrator reads at unit
    boundaries (duck-typed by orchestrator._apply_run_control). Bool reads/writes are
    atomic under the GIL, so no lock is needed."""

    def __init__(self):
        self.pause = False
        self._manual = False

    def request_pause(self) -> None:
        self.pause = True

    def request_manual(self) -> None:
        self._manual = True

    def take_manual(self) -> bool:
        """One-shot: True once after request_manual(), then resets."""
        if self._manual:
            self._manual = False
            return True
        return False


class _KeyListener:
    """Background single-key reader for live run controls (esc/p pause · m manual).

    A daemon thread reads one keypress at a time and forwards it to `on_key`. Activates
    ONLY when `enabled` and stdin is a real TTY, so pytest, pipes, and a11y mode are
    untouched (the run then behaves exactly as before). Cross-platform: msvcrt on
    Windows, termios cbreak + select on POSIX. Any failure disables itself silently -
    Ctrl-C still pauses. Deliberately used only for AUTONOMOUS runs, where the pipeline
    never prompts for input (so it can't fight console.input over the terminal)."""

    def __init__(self, on_key, *, enabled: bool):
        self._on_key = on_key
        self._stop = threading.Event()
        self._thread = None
        import sys as _sys
        self.active = bool(enabled)
        try:
            if enabled and _sys.stdin and _sys.stdin.isatty():
                self._thread = threading.Thread(target=self._run, daemon=True)
        except Exception:  # noqa: BLE001 - no stdin / not a tty
            self._thread = None
        self.active = self._thread is not None

    def __enter__(self):
        if self._thread is not None:
            self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=0.6)   # let POSIX restore termios before we return
        return False

    def _run(self):
        try:
            if os.name == "nt":
                self._run_windows()
            else:
                self._run_posix()
        except Exception:  # noqa: BLE001 - never let a read error crash the run
            pass

    def _run_windows(self):
        import msvcrt
        while not self._stop.is_set():
            if msvcrt.kbhit():
                try:
                    self._on_key(msvcrt.getwch())
                except Exception:  # noqa: BLE001
                    pass
            else:
                self._stop.wait(0.05)

    def _run_posix(self):
        import select
        import sys as _sys
        import termios
        import tty
        fd = _sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            while not self._stop.is_set():
                r, _, _ = select.select([_sys.stdin], [], [], 0.1)
                if r:
                    try:
                        self._on_key(_sys.stdin.read(1))
                    except Exception:  # noqa: BLE001
                        pass
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


class _RunDashboard:
    """Live, multi-line view for `run`: header (elapsed + live tokens), a chapter
    progress bar, the current unit + stage, and a short scroll of recent events.

    The dashboard object itself is handed to rich.Live (it renders via
    __rich_console__), so the auto-refresh thread re-renders it ~8x/s - the
    elapsed clock ticks and active stages animate even when the pipeline is deep
    inside one long LLM call and no log event arrives for minutes."""

    _SPIN = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"   # braille spinner, same family as console.status "dots"

    def __init__(self, book_id: str, total: int, done: int, brief: str = ""):
        self.book_id = book_id
        self.total = max(total, 1)
        self.done = done
        self.brief = brief      # the thesis claim / premise - the goal, always visible
        self.unit = ""
        self.stage = "starting…"
        self.verdict = ""
        self.events: collections.deque = collections.deque(maxlen=7)
        self.start = time.time()
        # Soft-ETA: bank each stage's duration so a repeat of the same stage can show a
        # rolling-median "~Ns". Change counters feed the summary's "self-edits" line.
        self._stage_t0 = time.monotonic()
        self._durs: dict[str, list[float]] = {}
        self.n_revised = 0
        self.n_humanized = 0
        self.n_research = 0
        self.note = ""              # transient status set by the key-listener thread
        self.live_controls = False  # True when esc/m keys are wired (autonomous + TTY)

    def _elapsed(self) -> str:
        s = int(time.time() - self.start)
        return f"{s // 60:02d}:{s % 60:02d}"

    @staticmethod
    def _norm(stage: str) -> str:
        return stage.rstrip("…. ").strip().lower()

    def _enter_stage(self, name: str) -> None:
        """Switch the active stage, banking the previous stage's elapsed time so the
        soft ETA (rolling median) can show how long this kind of step usually takes."""
        if self._norm(name) != self._norm(self.stage):
            prev, dt = self._norm(self.stage), time.monotonic() - self._stage_t0
            if prev and 0.2 < dt < 3600:
                self._durs.setdefault(prev, []).append(dt)
            self._stage_t0 = time.monotonic()
        self.stage = name

    def _eta(self) -> str:
        ds = sorted(self._durs.get(self._norm(self.stage), []))
        return f" · ~{int(ds[len(ds) // 2])}s" if ds else ""

    def _stage_label(self) -> str:
        """Active stages (ending in …) get a spinner + cycling dots so a long model
        call visibly works instead of looking hung, plus a soft ETA once we've timed
        that stage before. Reduced-motion drops the animation, keeps the meaning."""
        if not self.stage.endswith("…"):
            return self.stage
        base = self.stage[:-1]
        if _reduced_motion():
            return f"{base}…{self._eta()}"
        now = time.monotonic()
        spin = self._SPIN[int(now * 8) % len(self._SPIN)]
        dots = "." * (1 + int(now * 2.5) % 3)
        return f"{spin} {base}{dots}{self._eta()}"

    def __rich_console__(self, console, options):
        yield self.render()

    def render(self):
        from rich.console import Group
        from rich.text import Text

        from . import llm
        head = Text()
        head.append(f"{_FLEURON} {self.book_id}", style=f"bold {GOLD}")
        toks = f"{llm.current_tokens():,}"
        if llm.run_budget():
            toks += f" / {llm.run_budget():,}"
        cost = llm.current_cost()
        cost_sfx = f" · ${cost:.4f}" if cost > 0 else ""
        head.append(f"     {self._elapsed()} elapsed · {toks} tokens{cost_sfx}",
                    style=DIM)
        rows_brief = []
        if self.brief:
            brief = Text("  ")
            brief.append("goal ", style=DIM)
            brief.append(self.brief[:96], style=f"italic {INK}")
            rows_brief.append(brief)
        w = 24
        filled = min(w, round(self.done / self.total * w))
        bar = Text()
        bar.append("█" * filled, style=ON_CLR)
        bar.append("░" * (w - filled), style=DIM)
        bar.append(f"  {self.done}/{self.total}", style=PARCH)
        stage = Text("  ")
        if self.unit:
            stage.append(self.unit + "  ", style=PARCH)
        stage.append("· " + self._stage_label(), style=f"italic {INK}")
        if self.verdict:
            stage.append("   " + self.verdict, style=DIM)
        hint = ("  esc pause · m manual · Ctrl-C stop now" if self.live_controls
                else "  Ctrl-C pauses · progress is saved & resumable")
        rows = [head, *rows_brief, bar, stage, Text(hint, style=DIM)]
        if self.note:
            rows.append(Text(f"  {self.note}", style=f"bold {GOLD}"))
        if self.events:
            rows.append(Text("─" * 48, style=RULE))
            rows.extend(self.events)
        return Group(*rows)

    def log(self, msg: str) -> None:
        from rich.text import Text
        c = msg.strip()
        if not c:
            return
        if c.startswith("== Chapter") or c.startswith("== Section"):
            self.unit = c.strip("= ")
            self._enter_stage("drafting…")
            self.verdict = ""
        elif c.startswith("writing"):
            if "revision" in c:
                self._enter_stage("revising…")
                self.n_revised += 1
            else:
                self._enter_stage("drafting…")
        elif c.startswith("critiquing"):
            self._enter_stage("critiquing…")
        elif c.startswith("verdict="):
            self._enter_stage("reviewed")
            self.verdict = ui.trust_chip(c)   # normalized chip, never a contradiction
        elif c.startswith("humanizing"):
            self._enter_stage("humanising…")
            self.n_humanized += 1
        elif c.startswith("fetched") or c.startswith("generated SVG"):
            self._enter_stage("researching…")
            self.n_research += 1
            self.events.append(Text(f"  · {c}", style=DIM))
        elif "[OK] committed" in c:
            self.done += 1
            self._enter_stage("committed")
            self.events.append(Text(f"  ✓ {c[5:]}", style=ON_CLR))
        elif c.startswith("[!]"):
            self.events.append(Text(f"  {c}", style=f"bold {ERR}"))
        elif c.startswith("[OK]"):
            self.events.append(Text(f"  {c}", style=f"bold {ON_CLR}"))
        else:  # [i] / [usage] / [consolidate] / [production] / [learn] / [resume] / etc.
            self.events.append(Text(f"  {c}", style=DIM))


def _ring() -> None:
    """Terminal bell - a long run finished or needs the human; they may be elsewhere."""
    print("\a", end="", flush=True)


def _summary_card(console, dash, state: dict, uid: str, book_id: str) -> None:
    """Post-run card: the 'was it worth it' screen a finished run deserves."""
    from rich.panel import Panel
    from rich.text import Text

    from . import llm
    from .brain import ArticlePaths, BookPaths
    console.print()   # settle: the Live's last frame has no trailing newline, so the
    #                   summary Panel border would otherwise glue onto the last log line
    is_article = state.get("mode") == "article"
    paths = ArticlePaths(book_id, uid) if is_article else BookPaths(book_id, uid)
    words = len((brain.read_text(paths.manuscript) or "").split())
    insights = [i for i in (state.get("insights") or []) if isinstance(i, int)]
    units = state.get("num_sections" if is_article else "num_chapters", "?")
    toks, cost = llm.current_tokens(), llm.current_cost()

    body = Text()
    body.append(f"{units} {'sections' if is_article else 'chapters'}", style=PARCH)
    body.append(f"   ·   {words:,} words", style=PARCH)
    body.append(f"   ·   {dash._elapsed()} elapsed\n", style=DIM)
    body.append(f"{toks:,} tokens", style=DIM)
    if cost > 0:
        body.append(f"   ·   ${cost:.4f}", style=f"bold {GOLD}")
    if insights:
        avg = sum(insights) / len(insights)
        clr = ON_CLR if avg >= 4 else (PARCH if avg >= 3 else ERR)
        body.append(f"   ·   insight {avg:.1f}/5", style=f"bold {clr}")
    scores = [s for s in (state.get("scores") or []) if isinstance(s, dict)]
    if scores:
        body.append("\n")
        for dim in ("clarity", "structure", "evidence"):
            vals = [s.get(dim) for s in scores if isinstance(s.get(dim), int)]
            if vals:
                avg = sum(vals) / len(vals)
                clr = ON_CLR if avg >= 4 else (PARCH if avg >= 3 else ERR)
                body.append(f"{dim} ", style=DIM)
                body.append(f"{avg:.1f}", style=clr)
                body.append("   ", style=DIM)
        body.append("\nfull report:  eval   ·   reader pass:  tableread [--as \"persona\"]",
                    style=DIM)
    # What the AI changed on its own - so self-edits are observable, not invisible.
    chg = []
    if getattr(dash, "n_revised", 0):
        chg.append(f"{dash.n_revised} revision pass{'es' if dash.n_revised != 1 else ''}")
    if getattr(dash, "n_humanized", 0):
        chg.append(f"humanized {dash.n_humanized} unit{'s' if dash.n_humanized != 1 else ''}")
    if chg:
        body.append("\nself-edits:  " + " · ".join(chg), style=DIM)
    if is_article and (paths.root / "table_read.md").exists():
        body.append("\n📋 table read ready - a skeptical reader's report: ", style=PARCH)
        body.append("read it, then  revise --chapter N --instruction \"...\"", style=f"bold {GOLD}")
    body.append("\nnext:  export   (pdf · epub · html · docx · txt · md)", style=DIM)
    console.print(Panel(body, title=f"[{ON_CLR}]✓ complete[/]  [{GOLD}]{book_id}[/]",
                        title_align="left", border_style=ON_CLR, padding=(1, 2)))


def _paused_card(console, book_id: str) -> None:
    """A run ended without finishing and without a unit escalation - i.e. the budget
    cap or an interrupt paused it. Make that a clear, recoverable moment instead of a
    silent stop: say why, confirm nothing is lost, and give the resume + alternatives."""
    from rich.panel import Panel
    from rich.text import Text

    from . import llm
    console.print()
    tok, cap = llm.current_tokens(), llm.run_budget()
    body = Text()
    if cap and tok >= cap:
        body.append(f"token budget reached — {tok:,} / {cap:,}.\n", style=f"bold {ERR}")
        body.append("Everything committed so far is saved.\n\n", style=DIM)
        body.append("lift the cap:  /set max_run_tokens 0", style=f"bold {GOLD}")
        body.append("   then  run        ", style=DIM)
        body.append("(0 = unlimited)\n", style=DIM)
        body.append("fresh budget:  run", style=f"bold {GOLD}")
        body.append("                       ship now:  export", style=DIM)
        title, border = f"[{ERR}]⏸ paused — budget cap[/]", ERR
    else:
        body.append("run paused — progress is saved and fully resumable.\n\n", style=DIM)
        body.append("resume:  run", style=f"bold {GOLD}")
        body.append("        check state:  status        ship what exists:  export", style=DIM)
        title, border = f"[{GOLD}]⏸ paused[/]", GOLD
    console.print(Panel(body, title=title, title_align="left", border_style=border, padding=(1, 2)))


def _escalation_picker(console, cfg, uid: str, book_id: str, state: dict) -> str:
    """Interactive resolution of a stalled chapter/section - one keypress instead of
    a two-flag command. Returns 'rerun' (resume the pipeline) or 'stop'."""
    from rich.markdown import Markdown

    from . import orchestrator
    from .brain import ArticlePaths, BookPaths
    from .config import load_settings as _load_settings
    is_article = state.get("mode") == "article"
    unit = "section" if is_article else "chapter"
    n = state.get("current_section" if is_article else "current_chapter")
    paths = ArticlePaths(book_id, uid) if is_article else BookPaths(book_id, uid)
    review_md = brain.read_text(paths.review_of(n)) or "(no review file found)"

    _section(console, f"REVIEW NEEDED  ·  {unit} {n}")
    console.print(Markdown(review_md))
    while True:
        console.print()
        ans = console.input(
            f"  [{GOLD}][f][/]ix automatically · [{GOLD}][i][/]nstruct in your words · "
            f"[{GOLD}][a][/]pprove as-is · [{GOLD}][g][/]o autonomous & finish · "
            f"[{GOLD}][r][/]ead draft · [{GOLD}][s][/]top  > ").strip().lower()
        if ans == "f":
            orchestrator.record_instruction(
                uid, book_id, n,
                "Fix every blocking issue exactly as the critic's 'fix' lines suggest:\n\n"
                + review_md)
            _out(console, "[dim]critique recorded as the instruction - resuming...[/]")
            return "rerun"
        if ans == "i":
            text = console.input("  your instruction: ").strip()
            if text:
                orchestrator.record_instruction(uid, book_id, n, text)
                return "rerun"
            _out(console, "[dim](empty - pick again)[/]")
            continue
        if ans == "a":
            done = orchestrator.approve_escalation(
                cfg, uid, book_id, log=lambda m: _out(console, f"[dim]{m}[/]"))
            if done is not None:
                return "rerun"
            _out(console, f"[{ERR}]nothing to approve (draft missing)[/]")
            continue
        if ans == "g":
            orchestrator.apply_autonomous(uid, book_id, True, _load_settings())
            _out(console, "[dim]autonomous on - finishing the rest without pauses[/]")
            return "rerun"
        if ans == "r":
            draft = brain.read_text(
                paths.section_draft(n) if is_article else paths.ch_draft(n)) or "(draft missing)"
            with console.pager(styles=True):
                console.print(Markdown(draft))
            continue
        return "stop"


def run_with_dashboard(cfg, uid: str, book_id: str, console, *, force: bool = False,
                       autonomous: bool | None = None) -> None:
    """Drive orchestrator.run for one project under a live Rich dashboard.

    Shared by the shell's `run` command and the one-shot `write` flow so both show the
    same live progress view. `autonomous` (when not None) flips the project's run mode
    as it resumes. Interactive extras (TTY only): manual divergent-variant picking via
    an ask callback, an escalation picker when a unit stalls, a bell + summary card at
    the end.
    """
    import sys as _sys

    from rich.live import Live

    from . import brain as _brain
    from . import orchestrator
    from .brain import ArticlePaths, BookPaths

    interactive = bool(console) and _sys.stdin.isatty()
    while True:
        brief = ""
        try:
            art = ArticlePaths(book_id, uid)
            st = (_brain.read_json(art.run_state) if art.run_state.exists()
                  else _brain.read_json(BookPaths(book_id, uid).run_state)) or {}
            total = (max(st.get("num_sections", 1), 1) if st.get("mode") == "article"
                     else max(st.get("num_chapters", 1), 1))
            done_so_far = st.get("committed", 0)
            # Goal line: the thesis claim (articles) or premise (books), always visible.
            if art.run_state.exists():
                t = _brain.read_text(art.root / "thesis.md") or ""
                claim = next((ln for ln in t.splitlines() if ln.startswith("**Claim:**")), "")
                brief = claim.replace("**Claim:**", "").strip()
            else:
                plan = _brain.read_json(BookPaths(book_id, uid).root / "plan.json") or {}
                brief = (plan.get("premise") or "").strip()
        except Exception:
            total, done_so_far = 1, 0

        dash = _RunDashboard(book_id, total, done_so_far, brief=brief)
        controls = _RunControls()
        # Live keys only for an AUTONOMOUS run on a real TTY: that's the long hands-off
        # case worth interrupting, and it never prompts mid-run (so the key-listener
        # can't fight console.input over the terminal). Manual runs already pause per unit.
        auto_mode = autonomous if autonomous is not None else bool(st.get("autonomous"))
        use_keys = bool(console) and not _a11y() and interactive and auto_mode
        dash.live_controls = use_keys

        def _on_key(ch, controls=controls, dash=dash) -> None:   # bind: defined in a loop
            c = (ch or "").lower()
            if ch == "\x1b" or c == "p":
                controls.request_pause()
                dash.note = "⏸ pausing after this unit finishes — Ctrl-C to stop now"
            elif c == "m":
                controls.request_manual()
                dash.note = "✎ manual review from the next unit"

        if _a11y():
            # Accessible line-mode: append one plain status line per event (no Live
            # redraw). dash still tracks counters/elapsed for the summary card.
            if brief:
                console.print(f"  goal: {brief[:96]}")

            def _log(msg: str, dash=dash) -> None:   # bind: defined in a loop
                dash.log(msg)
                m = msg.strip()
                if m:
                    console.print(f"  {m}")

            def _ask(prompt: str) -> str:
                return console.input(f"\n{prompt}")

            state = orchestrator.run(cfg, uid, book_id, force=force, autonomous=autonomous,
                                     log=_log, ask=_ask if interactive else None, control=controls)
        else:
            # The dash object (not a snapshot) is the renderable: Live's auto-refresh
            # re-renders it 8x/s, so the clock + stage spinner animate between events.
            # The key-listener (autonomous + TTY only) feeds esc/m into `controls`, which
            # the orchestrator honors at the next unit boundary.
            with _KeyListener(_on_key, enabled=use_keys), \
                 Live(dash, console=console, refresh_per_second=8,
                      transient=False, vertical_overflow="visible") as live:
                def _log(msg: str, dash=dash) -> None:   # bind: defined in a loop
                    dash.log(msg)   # auto-refresh picks the mutation up within ~125ms

                def _ask(prompt: str) -> str:
                    # Pause the live render, take input, resume - prompting inside a Live
                    # frame corrupts the display otherwise.
                    live.stop()
                    try:
                        return console.input(f"\n{prompt}")
                    finally:
                        console.print()
                        live.start(refresh=True)

                state = orchestrator.run(cfg, uid, book_id, force=force, autonomous=autonomous,
                                         log=_log, ask=_ask if interactive else None,
                                         control=controls)
        force, autonomous = False, None   # one-shot flags; later passes resume plainly

        if state.get("phase") == "done":
            if console:
                _ring()
                _summary_card(console, dash, state, uid, book_id)
            return
        if (interactive and state.get("pending_review")
                and state.get("review_kind") in ("chapter", "section")):
            _ring()
            if _escalation_picker(console, cfg, uid, book_id, state) == "rerun":
                continue
        elif console and not state.get("pending_review"):
            # Not done, not a unit escalation → paused (budget cap / interrupt). Make it
            # a clear recovery moment rather than a silent return to the prompt.
            _paused_card(console, book_id)
        return


def _cmd_run_rich(args, cfg, settings, uid: str, console) -> None:
    """Run the pipeline with a live Rich dashboard."""
    # book_id is resolved by callers (_auto_or_pick_project in the shell loop or _execute_cmd)
    book_id = getattr(args, "book_id", None)
    if not book_id:
        _out(console, f"[{ERR}]No active project.[/]  Run `/use <name>` or just type `run` from the shell.")
        return
    run_with_dashboard(cfg, uid, book_id, console, force=getattr(args, "force", False),
                       autonomous=getattr(args, "autonomous", None))


# ── Conversational assistant ──────────────────────────────────────────────────

def _build_chat_system(settings: Settings, state: dict) -> str:
    import datetime
    uid = state["uid"]
    projects = brain.list_projects(uid)
    active = state.get("book")
    features_on = ", ".join(k for k, v in [
        ("humanize", settings.humanize),
        ("researcher", settings.use_researcher),
        ("deep-research", settings.deep_research),
        ("embeddings", settings.use_embeddings),
        ("images", settings.use_images),
        ("tournament-judge", settings.tournament_judge),
        ("verify-claims", settings.verify_claims),
    ] if v) or "none"
    active_line = (
        f"ACTIVE PROJECT: {active}  ← safe to run/status/read/export"
        if active else
        "ACTIVE PROJECT: (none set)  ← DO NOT execute run/status/read without /use <project> first"
    )
    today = datetime.date.today().strftime("%Y-%m-%d")
    # One per line, id clearly separated from its (type) tag - the model must copy
    # the id ONLY (it used to paste "id[article]" straight into commands).
    all_proj = ("\n" + "\n".join(f"    - {p[0]}   (type: {p[1]})" for p in projects)
                if projects else "(none yet)")
    run_mode = ("autonomous (never pauses for review)" if settings.autonomous
                else "manual (pauses for review at each unit)")
    ctx = (
        "\n\nCURRENT SESSION CONTEXT:"
        f"\n  date: {today}"
        f"\n  {active_line}"
        f"\n  all projects: {all_proj}"
        f"\n  mode: {settings.mode}"
        f"\n  run mode: {run_mode}"
        f"\n  features on: {features_on}"
        f"\n  user: {uid}"
    )
    # If the active project is paused at a chapter/section escalation, surface the
    # unit number + the critic's blocking issues so the assistant can resolve it
    # (emit `review --chapter N --instruction ...` or `run --autonomous`) instead of
    # looping on status/read.
    if active:
        from .brain import ArticlePaths, BookPaths
        ap = ArticlePaths(active, uid)
        paths = ap if ap.run_state.exists() else BookPaths(active, uid)
        st = brain.read_json(paths.run_state) or {}
        if st.get("pending_review") and st.get("review_kind") in ("chapter", "section"):
            unit_key = "current_section" if st.get("mode") == "article" else "current_chapter"
            unit_n = st.get(unit_key)
            review_md = (brain.read_text(paths.review_of(unit_n)) or "").strip()
            ctx += (
                f"\n\n⚠ ESCALATION PENDING: unit {unit_n} stalled at review and is waiting for the user."
                f"\n  Resolve it this turn - emit `review --chapter {unit_n} --instruction \"...\"` then `run`,"
                f"\n  or `run --autonomous` if the user wants it finished without more review."
            )
            if review_md:
                ctx += f"\n  Critic's blocking issues:\n{review_md[:900]}"
    # Tell the AI about article mode + how to handle project selection
    if settings.mode == "article":
        ctx += (
            "\n\nMODE: ARTICLE - important rules:"
            "\n  • `new` creates an ARTICLE, not a book. Say 'article topic', never 'Book abstract'."
            "\n  • When user asks to write/run/continue something, check ACTIVE PROJECT above."
            "\n  • If ACTIVE PROJECT is set → just run: ```run```"
            "\n  • If ACTIVE PROJECT is (none) and there are projects listed above:"
            "\n    ALWAYS execute `/use <exact-id>` first, then ```run```."
            "\n    Pick the most recently created article project."
            "\n  • If user asks to write a BOOK while in article mode, say:"
            "\n    'You are in article mode. Type `/mode book` to switch, or I can write an article instead.'"
        )
    elif not active:
        # Book mode, no active project - instruct AI to set one
        mode_filter = "book"
        matching = [p[0] for p in projects if p[1] == mode_filter]
        if matching:
            ctx += (
                f"\n\nNo active project. To help the user, use:"
                f"\n  ```/use {matching[-1]}```"
                f"\n  then suggest `run` or `status`."
            )
    return _CHAT_SYSTEM + ctx


def _next_hint(state: dict, settings=None) -> str:
    """One-liner prompt of the most useful next action given current state."""
    from .brain import ArticlePaths, BookPaths
    projects = brain.list_projects(state["uid"])
    active = state.get("book")
    if not projects:
        mode = settings.mode if settings else "book"
        noun = "topic" if mode == "article" else "idea"
        return f'next:  new --abstract "your {noun}"'
    if active:
        art = ArticlePaths(active, state["uid"])
        if art.run_state.exists():
            st = brain.read_json(art.run_state) or {}
        else:
            st = brain.read_json(BookPaths(active, state["uid"]).run_state) or {}
        mode = st.get("mode", "book")
        if st.get("pending_review"):
            key = "current_section" if mode == "article" else "current_chapter"
            return f'next:  review --chapter {st.get(key, "")} --instruction "..."'
        if st.get("phase") == "done":
            return "next:  export  (pdf · epub · html · docx · txt · md)"
        return "next:  run   (or: status  read  /help)"
    # No active project - show actual names
    mode_filter = "article" if (settings.mode if settings else "book") == "article" else "book"
    matching = [p[0] for p in projects if p[1] == mode_filter]
    candidates = matching or [p[0] for p in projects]
    if len(candidates) == 1:
        return f"next:  /use {candidates[0]}   then  run"
    return "next:  type  run  - it will ask you which project"


def _show_post_hint(console, state: dict, settings=None) -> None:
    """Print a dim next-step hint after any book command completes."""
    hint = _next_hint(state, settings)
    if console:
        from rich.rule import Rule
        from rich.text import Text
        console.print(Rule(Text(f"  {_FLEURON}  {hint}", style=DIM), style=RULE))
    else:
        print(f"\n  {hint}")


def _compact_history(history: list, cfg: ModelConfig) -> list:
    """Summarize chat history to a single system message using the chat model."""
    if not history:
        return []
    from .llm import complete_text
    model = cfg.model_for("chat")
    transcript = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in history)
    summary = complete_text(
        model,
        "You are a concise summarizer.",
        ("Summarize this WRITING AGENT assistant conversation in 3-4 sentences. "
         "Capture: what book(s) were discussed, what was done or decided, "
         "and the current state so the assistant can continue helpfully.\n\n"
         + transcript),
        max_tokens=200,
        temperature=0.0,
    )
    return [{"role": "system", "content": f"[Compacted prior context] {summary}"}]


def _trim_history(history: list, user_msg: dict, asst_msg: dict) -> None:
    """Append a turn and keep at most _MAX_HISTORY messages total."""
    history.append(user_msg)
    history.append(asst_msg)
    if len(history) > _MAX_HISTORY:
        del history[:len(history) - _MAX_HISTORY]


def _chat_respond(message: str, console, cfg: ModelConfig, settings: Settings, state: dict) -> None:
    """Route unrecognised input to the chat model with streaming + spinner UX."""
    from .llm import stream_text

    system = _build_chat_system(settings, state)
    model = cfg.model_for("chat")
    model_slug = model.split("/")[-1]
    fake = os.getenv("BOOK_AGENT_FAKE", "").lower() in ("1", "true", "yes")
    history: list[dict] = state.setdefault("chat_history", [])

    # ── Plain-text (no Rich) - stream chunks directly ─────────────────────────
    if not console:
        print(f"\nyou > {message}")
        print(f"[{model_slug}]", end=" ", flush=True)
        if fake:
            resp = "I'm WRITING AGENT. Try: `new --abstract \"your idea\"` then `run`."
            print(f"\n{resp}\n")
            state["last_chat"] = message
            _trim_history(history, {"role": "user", "content": message},
                          {"role": "assistant", "content": resp})
            return
        try:
            chunks: list[str] = []
            for chunk in stream_text(model, system, message,
                                     history=history, max_tokens=400, temperature=0.7):
                print(chunk, end="", flush=True)
                chunks.append(chunk)
            full = "".join(chunks)
            print(f"\n\n{_next_hint(state, settings)}\n")
            state["last_chat"] = message
            _trim_history(history, {"role": "user", "content": message},
                          {"role": "assistant", "content": full})
        except KeyboardInterrupt:
            print("\n(cancelled)\n")  # stop this response, stay in the shell
        except Exception as e:  # noqa: BLE001
            print(f"\n(unavailable: {e}) - try /help\n")
        return

    # ── Rich TUI - spinner → streaming → Markdown render ─────────────────────
    from rich.markdown import Markdown
    from rich.rule import Rule
    from rich.text import Text

    # 1. Acknowledge immediately - separator + echo user message
    console.print(Rule(style=RULE))
    console.print(Text(f"  you  ›  {message}", style=f"italic {INK}"))

    if fake:
        response = (
            "I'm **WRITING AGENT** - your autonomous book-writing studio.\n\n"
            "**Get started:**  `new --abstract \"your idea\"`  →  `run`  →  `export --format epub`\n\n"
            "Type `/help` for all commands, or just describe what you want to write."
        )
        console.print(Rule(style=RULE))
        console.print(Markdown(response))
        console.print(Rule(Text(f"  {_FLEURON}  {_next_hint(state, settings)}", style=DIM), style=RULE))
        state["last_chat"] = message
        _trim_history(history, {"role": "user", "content": message},
                      {"role": "assistant", "content": response})
        return

    # 2. Spinner until the first token arrives, then Live Markdown streaming
    from rich.live import Live
    from rich.padding import Padding

    chunks: list[str] = []
    error: str = ""
    cancelled = False
    try:
        gen = stream_text(model, system, message,
                          history=history, max_tokens=400, temperature=0.7)

        with console.status(
            f"[dim]✦ {model_slug}[/dim]",
            spinner="dots",
            spinner_style=f"bold {GOLD}",
        ):
            for chunk in gen:
                chunks.append(chunk)
                break  # first chunk received - drop spinner

        # 3. Stream a TRANSIENT, in-place tail preview while tokens arrive; the
        #    complete reply is rendered once, below, after the loop.
        #
        #    Why not Live-update a growing Markdown block: once the reply is taller
        #    than the terminal, a non-transient Live with vertical_overflow="visible"
        #    can't overwrite the previous frame, so it re-emits the WHOLE block on
        #    every refresh - stacking many identical copies in the scrollback (the
        #    "I see 5 duplicates" bug). A transient + cropped plain-text tail is
        #    bounded to the viewport, updates in place, and is erased on exit, so the
        #    single final print is the only thing left on screen.
        console.print(Rule(style=RULE))
        if chunks:
            max_rows = max(6, (console.size.height or 24) - 4)
            with Live(console=console, refresh_per_second=12, transient=True,
                      vertical_overflow="crop") as live:
                for chunk in gen:
                    chunks.append(chunk)
                    tail = "".join(chunks).splitlines()[-max_rows:]
                    live.update(Padding(Text("\n".join(tail) + " ▌", style=PARCH),
                                        pad=(0, 2)))

    except KeyboardInterrupt:
        cancelled = True  # stop streaming, keep partial text, stay in the shell
        console.print(Text("  (cancelled)", style=DIM))
    except Exception as e:  # noqa: BLE001
        error = f"(assistant unavailable: {e}) - type /help to see all commands"

    # The only thing committed to the scrollback: the complete reply, formatted
    # once. (The streaming preview above was transient, so there's nothing to
    # duplicate.) On cancel we still render whatever partial text we collected.
    # An error renders in the error style, clearly apart from assistant prose.
    full = "".join(chunks)
    if full:
        console.print(Padding(Markdown(full), pad=(0, 2)))
    if error:
        console.print(Text(f"  {error}", style=ERR))

    # 4. Save history (not on error - a half-streamed reply would mislead the model)
    if full and not error:
        state["last_chat"] = message
        _trim_history(history, {"role": "user", "content": message},
                      {"role": "assistant", "content": full})

    # 6. Execute any commands the model included in code blocks
    #    (skip when cancelled or errored - a half-streamed response may carry a
    #    partial command)
    cmds = (_commands_in_response(full, state.get("_known_commands", set()))
            if full and not cancelled and not error else [])
    # Hard gate: creating a project from chat needs the user's explicit go-ahead.
    # If the model jumped straight to `new` on a turn where the user didn't confirm,
    # hold the WHOLE batch (a trailing `run` would otherwise hit the previously
    # active project) and ask. The note appended to history tells the model its
    # commands did not run, so it re-emits them once the user confirms.
    if cmds and any(c.split()[0] == "new" for c in cmds) and not _is_confirmation(message):
        console.print(Rule(Text(f"  {_FLEURON}  proposed - not run yet", style=f"bold {GOLD}"), style=RULE))
        for cmd_line in cmds:
            console.print(Text(f"  $ {cmd_line}", style=f"dim {GOLD}"))
        console.print(Text('  say "go ahead" to start writing, or tell me what to change', style=DIM))
        if history and history[-1]["role"] == "assistant":
            history[-1]["content"] += (
                "\n\n[shell: the commands above were NOT executed - the shell is waiting "
                "for the user's explicit go-ahead. Re-emit them when the user confirms.]"
            )
        cmds = []
    if cmds:
        console.print(Rule(Text(f"  {_FLEURON}  running", style=f"bold {GOLD}"), style=RULE))
        for cmd_line in cmds:
            console.print(Text(f"  $ {cmd_line}", style=f"dim {GOLD}"))
            _execute_cmd(cmd_line, console, cfg, settings, state)

    # 7. Actionable hint footer
    console.print(Rule(Text(f"  {_FLEURON}  {_next_hint(state, settings)}", style=DIM), style=RULE))


# ── Prompt state indicator ────────────────────────────────────────────────────


def _prompt_state(state: dict) -> str:
    """Return a short Rich-markup suffix for the shell prompt."""
    book = state.get("book")
    if not book:
        return ""
    try:
        from .brain import ArticlePaths, BookPaths
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
                from .brain import ArticlePaths, BookPaths
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
                    from . import providers
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
                    from . import providers
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
                            from . import providers
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
                from .cli import _EXPORT_FORMATS
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
                    from .brain import BookPaths
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
