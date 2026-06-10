"""Interactive REPL/TUI for WRITING AGENT (run `writing-agent` / `book` / `python book.py`).

Aesthetic: editorial letterpress - an "ink & gilt" palette, a title-page masthead, fleuron
section markers, and clean borderless command tables.

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
import time

from . import brain, ui
from . import skills as skills_mod
from .config import ModelConfig, Settings, save_config, save_settings
from .ui import DIM, ERR, GOLD, GOLD_HI, INK, OFF_CLR, ON_CLR, PARCH, RULE  # palette

_VERSION = "0.1.0"
_NODES = ["planner", "toc", "writer", "critic", "summarizer", "consolidation",
          "production", "learner", "researcher", "humanizer", "chat"]
_EXIT = {"exit", "quit", "q", ":q"}
_FLEURON = ui.FLEURON
_MAX_HISTORY = 10  # max messages kept for multi-turn context (5 user + 5 assistant)

_SLASH_HELP = [
    ("/help", "this panel + the full command list"),
    ("/model", "show per-agent model routing"),
    ("/model <slug>", "route ALL agents to a model (any OpenRouter slug)"),
    ("/model <agent> <slug>", "set one agent (e.g. /model critic openai/gpt-4o)"),
    ("/set <key> <value>", "change a setting live (e.g. /set use_researcher true)"),
    ("/skills · /skill <name>", "list skills · show one skill"),
    ("/seed-skills", "install the built-in craft skills"),
    ("/use <book> · /books", "set active book · list books"),
    ("/user <id> · /config", "switch user · show config"),
    ("/update [changes]", "describe your changes - AI reviews and advises on next steps"),
    ("/retry", "resend the last chat message"),
    ("/mode [book|article]", "show or set the project mode (default: book)"),
    ("/reset", "clear the assistant's conversation memory (fresh context)"),
    ("/compact", "summarize conversation memory to save context space"),
    ("/clear · /exit", "clear screen · quit"),
]
_MARKUP = re.compile(r"\[/?[^\]]*\]")
# Matches single-line fenced code blocks: ```cmd``` or ```\ncmd\n```
_CODE_BLOCK_RE = re.compile(r"```[^\n`]*\n?(.*?)```", re.DOTALL)

# ── chat system prompt ────────────────────────────────────────────────────────
_CHAT_SYSTEM = """\
You are the built-in assistant for WRITING AGENT - an autonomous book-writing studio.
Help users understand the system, figure out what to do next, and get unblocked.
The current date is injected into your session context below - always use it when the user
asks about timing, recency, or anything date-dependent (e.g. "today", "this week", "recently").

WRITING AGENT writes complete books: give it an abstract, it plans, writes, critiques,
revises, and assembles a finished manuscript (PDF or EPUB). It runs on OpenRouter + DeepSeek.

COMMANDS  (type these directly in this shell - no 'book' prefix needed):
  new --abstract "..."       Start a new project - book (default) or article (when mode=article)
  run                        Write the book/article - drafts, critiques, humanises, commits
  status                     Where the project is (phase, chapter/section, pending reviews)
  review --chapter N \\
    --instruction "..."      Answer an escalation when the book gets stuck
  read [--chapter N]         Read a chapter; add --summary or --manuscript for those views
  export [--format <fmt>]    Export: pdf · epub · html · docx · txt · md  (prompts if omitted)
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
  /reset                     Clear assistant memory (fresh context)
  /compact                   Summarize memory to save context space
  /help                      Show all slash commands

TYPICAL FIRST SESSION:
  1.  new --abstract "A thriller about a forger in 1920s Paris"
  2.  run
  3.  export   (then pick: pdf / epub / html / docx / txt / md)

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

  active project: my-project  →  Safe to run commands directly - no /use needed.

  DO NOT ask "which project?" in text. Just pick the most recent/relevant one from context and use it.
  The shell auto-routes to the right project type for the current mode.

`new` COMMAND RULES:
- `new` picks an angle/direction automatically (auto-selects option 1).
  After it runs, the new project becomes active automatically.
- If user says "run it" / "go ahead" AFTER a new project was created:
  Just emit ```run``` - no /use needed because the project is already active.
- NEVER put `new` and `run` in the same response. Two separate turns:
  first turn: ```new --abstract "..."```  → project created + activated
  next turn (if user says "run it"): ```run```
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


def _lerp(a: str, b: str, t: float) -> str:
    ca = [int(a.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    cb = [int(b.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    r, g, bl = (round(ca[i] + (cb[i] - ca[i]) * t) for i in range(3))
    return f"#{r:02x}{g:02x}{bl:02x}"


def _trim_blank_edges(lines: list[str]) -> list[str]:
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def _wordmark() -> list[str]:
    """Wordmark as a list of lines. WRITING stacked over AGENT.

    Uses pure line-art ASCII fonts (not block/box-drawing fonts) so the letters
    render correctly in any terminal regardless of font or line spacing - block
    fonts like ANSI Shadow only tile cleanly in some terminals. Falls back to
    plain text so it never crashes on an exotic pyfiglet build.
    """
    try:
        import pyfiglet
        for font in ("slant", "small", "standard"):
            try:
                top = pyfiglet.figlet_format("WRITING", font=font)
                bot = pyfiglet.figlet_format("AGENT", font=font)
            except Exception:
                continue
            lines = (_trim_blank_edges(top.split("\n"))
                     + [""] + _trim_blank_edges(bot.split("\n")))
            if lines and max((len(ln) for ln in lines), default=0) <= 80:
                return lines
    except Exception:
        pass
    return ["W R I T I N G", "A G E N T"]


def _banner(console) -> None:
    lines = _wordmark()
    if not console:
        print("\n".join(lines))
        print("an autonomous writing studio - books, articles & more")
        return
    from rich.align import Align
    from rich.rule import Rule
    from rich.text import Text
    # Gentle per-line vertical gradient (top lit -> bottom). Coloring whole lines
    # (not each character) keeps the letters reading as one cohesive wordmark.
    n = max(len(lines) - 1, 1)
    grad = Text()
    for i, ln in enumerate(lines):
        grad.append(ln + "\n", style=f"bold {_lerp(GOLD_HI, GOLD, i / n)}")
    console.print()
    console.print(Rule(style=RULE))
    console.print()
    console.print(Align.center(grad))
    console.print(Align.center(Text("an autonomous writing studio - books, articles & more",
                                    style=f"italic {INK}")))
    console.print(Align.center(Text(f"OpenRouter · DeepSeek · v{_VERSION}", style=DIM)))
    console.print()
    console.print(Rule(style=RULE))


def _section(console, title: str) -> None:
    from rich.rule import Rule
    from rich.text import Text
    console.print(Rule(Text(f" {_FLEURON}  {title} ", style=f"bold {GOLD}"),
                       style=RULE, align="left"))


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

    if not console:
        print("commands: new run status review read export memory consolidate produce list")
        print("slash:    /help /model /set /skills /use /config /clear /exit")
        print(f"mode:     {mode}")
        print(f"models:   pro={cfg.model_for('writer')}  flash={cfg.model_for('critic')}")
        proj_str = ", ".join(f"{p[0]}[{p[1]}]" for p in projects) or "(none)"
        print(f"skills: {len(skl)}   projects: {proj_str}   user: {uid}")
        if not projects:
            print('\nGet started:  new --abstract "your idea"  then  run')
        return

    from rich.text import Text

    # ── Commands ──────────────────────────────────────────────────────────────
    _section(console, "COMMANDS")
    if is_article:
        new_desc = "start an article - topic → angles → outline + sections"
    else:
        new_desc = "start a book - idea → directions → plan + TOC"
    export_desc = "pdf · epub · html · docx · txt · md  (prompts if format omitted)"
    _cmd_table(console, [
        ("new --abstract \"...\"", new_desc),
        ("run", "write it - draft · critique · humanise · commit per section" if is_article
                else "write it - draft · critique · humanise · commit per chapter"),
        ("status · review", "where the project stands · answer escalations"),
        ("read", "section (--chapter N) · --summary · --manuscript" if is_article
                 else "chapter (--chapter N) · --summary · --manuscript"),
        ("export [--format <fmt>]", export_desc),
        ("memory · skills · list", "canon & timeline · craft skills · all projects"),
        ("delete [--yes]", "permanently delete a project"),
        ("/mode book", "switch to book mode (chapters, novel/nonfiction)") if is_article
        else ("/mode article", "switch to article mode (single long-form piece)"),
    ])

    # ── Slash commands ────────────────────────────────────────────────────────
    _section(console, "SLASH  &  CHAT")
    _cmd_table(console, [
        ("/model [agent] <slug>", "switch any model to any OpenRouter slug"),
        ("/set <key> <value>", "change a setting live (e.g. /set use_researcher true)"),
        ("/update [changes]", "describe your changes - AI reviews and advises"),
        ("/use <project> · /books", "set active project · list projects"),
        ("/skills · /seed-skills", "browse skills · install built-ins"),
        ("/retry · /reset · /compact", "retry last message · clear memory · compress memory"),
        ("/help · /clear · /exit", "full slash list · clear · quit"),
        ("", ""),
        ("💬 free chat", "type anything - the assistant will guide you"),
    ])

    # ── Getting started (first time) OR book/article status ──────────────────
    if not projects:
        _section(console, "GETTING STARTED")
        if is_article:
            _cmd_table(console, [
                ("Step 1", 'new --abstract "How Python async/await actually works"'),
                ("Step 2", "run                   ← writes every section automatically"),
                ("Step 3", "export   ← picks format interactively (docx · pdf · html · txt · md)"),
                ("", ""),
                ("Tip", "pick from 3 editorial angles (e.g. beginner vs deep-dive)"),
                ("Tip", "/set use_researcher true  for real web sources + citations"),
                ("Tip", "/set autonomous true  to run without any pauses"),
                ("Tip", "/mode book  to switch back to full-book mode"),
            ])
        else:
            _cmd_table(console, [
                ("Step 1", 'new --abstract "A thriller set on Mars in 2089"'),
                ("Step 2", "run                  ← writes every chapter automatically"),
                ("Step 3", "export   ← picks format interactively (epub · pdf · docx · txt · md)"),
                ("", ""),
                ("Tip", "you can also just describe your idea in plain English below"),
                ("Tip", "/set autonomous true  to run without any pauses"),
                ("Tip", "/set num_chapters 12  to change the book length (default 8)"),
                ("Tip", "/mode article  to write a single long-form article instead"),
            ])
    else:
        _section(console, "YOUR PROJECTS")
        rows = _book_status_rows(uid, projects)
        _cmd_table(console, rows)
        _cmd_table(console, [("", ""), ("/use <project>", "set active project to skip --book-id")])

    # ── Features ──────────────────────────────────────────────────────────────
    _section(console, "FEATURES")
    _cmd_table(console, [
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
        ("", ""),
        ("/set <key> true/false", "toggle any feature above and save instantly"),
    ])

    # ── Footer ────────────────────────────────────────────────────────────────
    console.print()
    foot = Text("  ")
    foot.append("mode ", style=DIM)
    foot.append(mode, style=f"bold {GOLD}" if is_article else INK)
    foot.append("   pro ", style=DIM)
    foot.append(cfg.model_for("writer").split("/")[-1], style=INK)
    foot.append("   flash ", style=DIM)
    foot.append(cfg.model_for("critic").split("/")[-1], style=INK)
    n_proj = len(projects)
    foot.append(f"   {len(skl)} skills   {n_proj} project{'s' if n_proj != 1 else ''}   {uid}",
                style=DIM)
    console.print(foot)
    console.print(Text(
        "  type a command · /help for slash commands · or just chat in plain English",
        style=DIM,
    ))


def _slash_help(console) -> None:
    if not console:
        for name, desc in _SLASH_HELP:
            print(f"  {name:<28} {desc}")
        return
    from rich.text import Text
    _section(console, "SLASH COMMANDS")
    _cmd_table(console, _SLASH_HELP)
    console.print(Text(f"  agents: {', '.join(_NODES)}", style=DIM))


# ── Slash handlers ────────────────────────────────────────────────────────────

def _cmd_model(console, cfg: ModelConfig, rest: list[str]) -> None:
    if not rest:
        rows = [("default", cfg.default)] + [(n, cfg.model_for(n)) for n in _NODES]
        if console:
            _section(console, "MODELS")
            _cmd_table(console, rows)
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
    if node != "default" and node not in _NODES:
        _out(console, f"[{ERR}]unknown agent '{node}'[/] - agents: {', '.join(_NODES)}")
        return
    cfg.set_default(slug) if node == "default" else cfg.set_node(node, slug)
    save_config(cfg)
    _out(console, f"[{GOLD}]{node}[/] -> [{GOLD}]{slug}[/] [dim](saved)[/]")


def _cmd_set(console, settings: Settings, rest: list[str]) -> None:
    import dataclasses
    if len(rest) < 2:
        fields = "  ".join(f.name for f in dataclasses.fields(settings))
        _out(console, f"usage: /set <key> <value>\nkeys: [dim]{fields}[/]")
        return
    key, raw = rest[0], rest[1]
    field_map = {f.name: f for f in dataclasses.fields(settings)}
    if key not in field_map:
        valid = "  ".join(sorted(field_map))
        _out(console, f"[{ERR}]unknown setting '{key}'[/]\nvalid keys: [dim]{valid}[/]")
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
    text = brain.read_text(brain.skills_dir(uid) / f"{brain.slugify(rest[0])}.md")
    _out(console, text if text else f"[dim](no skill '{rest[0]}')[/]")


# ── NL → command execution helpers ───────────────────────────────────────────

_NEEDS_PROJECT = {"run", "status", "read", "export", "review", "memory",
                   "delete", "produce", "consolidate"}

# The chat assistant must NOT silently auto-execute destructive or
# config/tenant-changing commands - the human has to type these. (The model may
# still mention them in prose.) `delete` = data loss; `/user` switches tenant;
# `/set` can disable human-in-the-loop (autonomous) and reroute models.
_CHAT_BLOCKED_CMDS = {"delete"}
_CHAT_BLOCKED_SLASH = {"user", "set"}


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


def _execute_cmd(cmd_line: str, console, cfg, settings, state) -> None:
    """Execute one command string emitted by the chat assistant.

    Destructive/config commands are refused here (defense in depth on top of the
    filtering in `_commands_in_response`) - the human must type those directly.
    """
    if cmd_line.startswith("/"):
        if cmd_line.lstrip("/").split()[0].lower() in _CHAT_BLOCKED_SLASH:
            _out(console, f"[dim](skipped /{cmd_line.lstrip('/').split()[0]} - type it yourself)[/]")
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

    # `export` with no --format: show Rich-styled format picker in TUI
    if first == "export" and "--format" not in argv and console:
        from .cli import _EXPORT_FORMATS
        choices_str = "  ·  ".join(_EXPORT_FORMATS)
        console.print(f"  [{GOLD}]formats[/]  [dim]{choices_str}[/]")
        fmt = console.input(f"  [{INK}]format[/] [dim][pdf]:[/] ").strip().lower() or "pdf"
        if fmt not in _EXPORT_FORMATS:
            _out(console, f"[{ERR}]unknown format '{fmt}'[/] - choose from: {choices_str}")
            return
        argv += ["--format", fmt]

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

class _RunDashboard:
    """Live, multi-line view for `run`: header (elapsed + live tokens), a chapter
    progress bar, the current unit + stage, and a short scroll of recent events."""

    def __init__(self, book_id: str, total: int, done: int):
        self.book_id = book_id
        self.total = max(total, 1)
        self.done = done
        self.unit = ""
        self.stage = "starting…"
        self.verdict = ""
        self.events: collections.deque = collections.deque(maxlen=7)
        self.start = time.time()

    def _elapsed(self) -> str:
        s = int(time.time() - self.start)
        return f"{s // 60:02d}:{s % 60:02d}"

    def render(self):
        from rich.console import Group
        from rich.text import Text

        from . import llm
        head = Text()
        head.append(f"{_FLEURON} {self.book_id}", style=f"bold {GOLD}")
        head.append(f"     {self._elapsed()} elapsed · {llm.current_tokens():,} tokens",
                    style=DIM)
        w = 24
        filled = min(w, round(self.done / self.total * w))
        bar = Text()
        bar.append("█" * filled, style=ON_CLR)
        bar.append("░" * (w - filled), style=DIM)
        bar.append(f"  {self.done}/{self.total}", style=PARCH)
        stage = Text("  ")
        if self.unit:
            stage.append(self.unit + "  ", style=PARCH)
        stage.append("· " + self.stage, style=f"italic {INK}")
        if self.verdict:
            stage.append("   " + self.verdict, style=DIM)
        rows = [head, bar, stage]
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
            self.stage, self.verdict = "drafting…", ""
        elif c.startswith("writing"):
            self.stage = "revising…" if "revision" in c else "drafting…"
        elif c.startswith("critiquing"):
            self.stage = "critiquing…"
        elif c.startswith("verdict="):
            self.stage = "reviewed"
            self.verdict = c
        elif c.startswith("humanizing"):
            self.stage = "humanising…"
        elif c.startswith("fetched") or c.startswith("generated SVG"):
            self.stage = "researching…"
            self.events.append(Text(f"  · {c}", style=DIM))
        elif "[OK] committed" in c:
            self.done += 1
            self.stage = "committed"
            self.events.append(Text(f"  ✓ {c[5:]}", style=ON_CLR))
        elif c.startswith("[!]"):
            self.events.append(Text(f"  {c}", style=f"bold {ERR}"))
        elif c.startswith("[OK]"):
            self.events.append(Text(f"  {c}", style=f"bold {ON_CLR}"))
        else:  # [i] / [usage] / [consolidate] / [production] / [learn] / [resume] / etc.
            self.events.append(Text(f"  {c}", style=DIM))


def _cmd_run_rich(args, cfg, settings, uid: str, console) -> None:
    """Run the pipeline with a live Rich dashboard."""
    from . import brain as _brain
    from . import orchestrator
    from .brain import ArticlePaths, BookPaths

    # book_id is resolved by callers (_auto_or_pick_project in the shell loop or _execute_cmd)
    book_id = getattr(args, "book_id", None)
    if not book_id:
        _out(console, f"[{ERR}]No active project.[/]  Run `/use <name>` or just type `run` from the shell.")
        return

    from rich.live import Live

    try:
        art = ArticlePaths(book_id, uid)
        st = (_brain.read_json(art.run_state) if art.run_state.exists()
              else _brain.read_json(BookPaths(book_id, uid).run_state)) or {}
        total = (max(st.get("num_sections", 1), 1) if st.get("mode") == "article"
                 else max(st.get("num_chapters", 1), 1))
        done_so_far = st.get("committed", 0)
    except Exception:
        total, done_so_far = 1, 0

    dash = _RunDashboard(book_id, total, done_so_far)
    with Live(dash.render(), console=console, refresh_per_second=8,
              transient=False, vertical_overflow="visible") as live:
        def _log(msg: str) -> None:
            dash.log(msg)
            live.update(dash.render())
        orchestrator.run(cfg, uid, book_id, force=getattr(args, "force", False), log=_log)
        live.update(dash.render())


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
    ] if v) or "none"
    active_line = (
        f"ACTIVE PROJECT: {active}  ← safe to run/status/read/export"
        if active else
        "ACTIVE PROJECT: (none set)  ← DO NOT execute run/status/read without /use <project> first"
    )
    today = datetime.date.today().strftime("%Y-%m-%d")
    all_proj = ", ".join(f"{p[0]}[{p[1]}]" for p in projects) if projects else "(none yet)"
    ctx = (
        "\n\nCURRENT SESSION CONTEXT:"
        f"\n  date: {today}"
        f"\n  {active_line}"
        f"\n  all projects: {all_proj}"
        f"\n  mode: {settings.mode}"
        f"\n  features on: {features_on}"
        f"\n  user: {uid}"
    )
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

        # 3. Stream remaining chunks with Rich Live (no manual ANSI cursor tricks)
        console.print(Rule(style=RULE))
        if chunks:
            with Live(
                Padding(Markdown(chunks[0] + "▌"), pad=(0, 2)),
                console=console,
                refresh_per_second=12,
                transient=False,
                vertical_overflow="visible",
            ) as live:
                for chunk in gen:
                    chunks.append(chunk)
                    live.update(Padding(Markdown("".join(chunks) + "▌"), pad=(0, 2)))
                # Final render without the streaming cursor
                live.update(Padding(Markdown("".join(chunks)), pad=(0, 2)))

    except KeyboardInterrupt:
        cancelled = True  # stop streaming, keep partial text, stay in the shell
        console.print(Text("  (cancelled)", style=DIM))
    except Exception as e:  # noqa: BLE001
        error = f"_(assistant unavailable: {e})_\n\nType `/help` to see all commands."

    full = "".join(chunks)
    if not full and error:
        console.print(Text(f"  {error}", style=ERR))

    # 4. Save history
    if full:
        state["last_chat"] = message
        _trim_history(history, {"role": "user", "content": message},
                      {"role": "assistant", "content": full})

    # 6. Execute any commands the model included in code blocks
    #    (skip when cancelled - a half-streamed response may carry a partial command)
    cmds = _commands_in_response(full, state.get("_known_commands", set())) if full and not cancelled else []
    if cmds:
        console.print(Rule(Text(f"  {_FLEURON}  running", style=f"bold {GOLD}"), style=RULE))
        for cmd_line in cmds:
            console.print(Text(f"  $ {cmd_line}", style=f"dim {GOLD}"))
            _execute_cmd(cmd_line, console, cfg, settings, state)

    # 7. Actionable hint footer
    console.print(Rule(Text(f"  {_FLEURON}  {_next_hint(state, settings)}", style=DIM), style=RULE))


# ── Prompt state indicator ────────────────────────────────────────────────────

def _book_progress(uid: str, book: str) -> str:
    """Short ' ch 3/8' / ' sec 2/6' / ' ⚠ review' / ' ✓ done' suffix for the toolbar."""
    if not book:
        return ""
    try:
        from .brain import ArticlePaths, BookPaths
        art = ArticlePaths(book, uid)
        if art.run_state.exists():
            st, unit, cur, tot = brain.read_json(art.run_state), "sec", "current_section", "num_sections"
        else:
            st, unit, cur, tot = brain.read_json(BookPaths(book, uid).run_state), "ch", "current_chapter", "num_chapters"
        if not st:
            return ""
        if st.get("pending_review"):
            return "  ⚠ review"
        if st.get("phase") == "done":
            return "  ✓ done"
        return f"  {unit} {st.get(cur, '?')}/{st.get(tot, '?')}"
    except Exception:
        return ""


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
        _slash_help(console)
    elif name in ("clear", "cls"):
        if console:
            console.clear()
    elif name in ("model", "models"):
        _cmd_model(console, cfg, rest)
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
            target = rest[0]
            valid = {p[0] for p in brain.list_projects(uid)}
            if target in valid:
                state["book"] = target
                _out(console, f"active book -> [{GOLD}]{target}[/]")
            else:
                sug = ui.did_you_mean(target, valid)
                if sug:
                    tail = f"did you mean '{sug}'?"
                else:
                    tail = "available: " + (", ".join(sorted(valid)) or "(none yet)")
                _out(console, f"[{ERR}]no project '{target}'[/] [dim]{tail}[/]")
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
    elif name == "mode":
        if not rest:
            _out(console, f"mode: [{GOLD}]{settings.mode}[/] [dim](book | article)[/]")
        elif rest[0] in ("book", "article"):
            settings.mode = rest[0]
            save_settings(settings)
            _out(console, f"mode -> [{GOLD}]{rest[0]}[/] [dim](saved - next `new` will use this mode)[/]")
        else:
            _out(console, f"[{ERR}]unknown mode '{rest[0]}'[/] - valid: book  article")
    else:
        sug = ui.did_you_mean(name, [s[0] for s in _SLASH_COMPLETIONS])
        hint = f"did you mean /{sug}?" if sug else "try /help"
        _out(console, f"[{ERR}]unknown slash command:[/] /{name}  [dim]({hint})[/]")
    return True


# ── prompt_toolkit autocomplete + status toolbar ──────────────────────────────

# Flat list of (slash-name, description) for the completion dropdown
_SLASH_COMPLETIONS = [
    ("help",        "show all slash commands"),
    ("model",       "show / set model routing"),
    ("set",         "change a setting  e.g. /set use_researcher true"),
    ("skills",      "list craft skills"),
    ("skill",       "show one skill by name"),
    ("seed-skills", "install built-in craft skills"),
    ("use",         "set active book / article"),
    ("books",       "list all projects"),
    ("user",        "switch user"),
    ("config",      "show model + settings config"),
    ("update",      "describe changes - AI reviews and suggests next steps"),
    ("retry",       "resend last chat message"),
    ("mode",        "show / set mode  book | article"),
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
        import datetime

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
                if sub == "use":                                 # → real project names
                    for pid, ptype in brain.list_projects(state["uid"]):
                        if pid.startswith(cur):
                            yield _comp(pid, -len(cur), ptype)
                elif sub in ("model", "models") and len(words) <= (1 if ends_space else 2):
                    for a in ["default", *_NODES]:
                        if a.startswith(cur):
                            yield _comp(a, -len(cur), "agent")
                elif sub == "set":
                    fields = {f.name: f for f in dataclasses.fields(settings)}
                    if len(words) <= (1 if ends_space else 2):   # the key
                        for n, f in fields.items():
                            if n.startswith(cur):
                                yield _comp(n, -len(cur), type(f.default).__name__)
                    else:                                        # bool values
                        key = words[1]
                        if key in fields and isinstance(fields[key].default, bool):
                            for v in ("true", "false"):
                                if v.startswith(cur):
                                    yield _comp(v, -len(cur))
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
                return

            # ── book commands ────────────────────────────────────────────────
            if not words:
                return
            if len(words) == 1 and not ends_space:               # first word
                for c in sorted(known_commands):
                    if c.startswith(cur):
                        yield _comp(c, -len(cur), "command")
                return
            if words[0] == "export":                             # → --format <fmt>
                from .cli import _EXPORT_FORMATS
                prior = words[-1] if ends_space else (words[-2] if len(words) >= 2 else "")
                if prior == "--format":
                    for f in _EXPORT_FORMATS:
                        if f.startswith(cur):
                            yield _comp(f, -len(cur))
                elif "--format".startswith(cur) and "--format" not in words:
                    yield _comp("--format", -len(cur))

    def _toolbar():
        model = cfg.model_for("writer").split("/")[-1]
        today = datetime.date.today().strftime("%Y-%m-%d")
        mode_part = "[article]" if settings.mode == "article" else "[book]"
        book = state.get("book") or ""
        book_part = f"● {book}{_book_progress(state['uid'], book)}" if book else "no active book"
        return f"  {model}  │  {mode_part}  │  {book_part}  │  {today}  "

    _DIM_HEX = "#6b6b6b"  # prompt_toolkit needs hex; Rich's "grey42" ≈ #6b6b6b
    pt_style = Style.from_dict({
        # Completion dropdown
        "completion-menu.completion":                f"bg:#111111 fg:{GOLD}",
        "completion-menu.completion.current":        f"bg:{RULE} fg:{GOLD_HI} bold",
        "completion-menu.meta.completion":           f"bg:#111111 fg:{_DIM_HEX}",
        "completion-menu.meta.completion.current":   f"bg:{RULE} fg:{PARCH}",
        # Bottom toolbar
        "bottom-toolbar":                            f"bg:#0a0a0a fg:{RULE}",
        "bottom-toolbar.text":                       f"bg:#0a0a0a fg:{RULE}",
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
            bottom_toolbar=_toolbar,
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

    _banner(console)
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
            prompt_plain = f"\n❧ {slug}{book_part}{sfx_plain} "
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
                    args, _ = parser.parse_known_args(argv)
            except SystemExit:
                err_text = stderr_buf.getvalue().strip()
                if err_text:
                    # Strip "book: error: " prefix that argparse prepends
                    msg = err_text.split(": error: ", 1)[-1] if ": error: " in err_text else err_text
                    _out(console, f"[{ERR}]error:[/] {msg}  [dim](try /help)[/]")
                continue
            # Auto-pick project when none is active and the command needs one
            if getattr(args, "book_id", None) is None:
                if first in _NEEDS_PROJECT and not state["book"]:
                    picked = _auto_or_pick_project(state["uid"], settings, console, state)
                    if not picked and first not in {"list", "new", "skills", "config"}:
                        continue
                if state["book"]:
                    args.book_id = state["book"]
            user = args.user if args.user != settings.default_user else state["uid"]
            try:
                # Special handling for destructive/interactive commands in Rich TUI
                if first == "run" and console:
                    _cmd_run_rich(args, cfg, settings, user, console)
                elif first == "delete" and console and not getattr(args, "yes", False):
                    book_id = getattr(args, "book_id", None) or state["book"] or ""
                    answer = console.input(
                        f"  [{ERR}]Delete '{book_id}' permanently?[/] [{DIM}][y/N][/] "
                    ).strip().lower()
                    if answer in ("y", "yes"):
                        args.yes = True
                        commands[args.command](args, cfg, settings, user)
                        if state.get("book") == book_id:
                            state["book"] = None
                    else:
                        _out(console, "[dim]aborted[/]")
                else:
                    commands[args.command](args, cfg, settings, user)
                _show_post_hint(console, state, settings)
            except KeyboardInterrupt:
                _out(console,
                     f"\n[{ERR}]interrupted[/] [dim]- state saved. Run again to resume.[/]")
            except SystemExit:
                pass
            except Exception as e:  # noqa: BLE001
                _out(console, f"[{ERR}]error:[/] {type(e).__name__}: {e}")
            continue

        # ── Everything else → conversational assistant ────────────────────────
        _chat_respond(line, console, cfg, settings, state)

    _out(console, f"[dim]{_FLEURON} closed.[/]")
