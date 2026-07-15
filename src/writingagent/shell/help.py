"""Command + feature tables, slash-help, the feature toggle grid, and the model catalog."""
from __future__ import annotations

from ..config import Settings, save_settings
from ..ui import DIM, GOLD, GOLD_HI, OFF_CLR, ON_CLR, PARCH, did_you_mean
from ._const import _MARKUP, _NIB, _NODES, _SLASH_HELP
from .branding import _cmd_table, _feat_row, _out, _section

__all__ = [
    '_command_help_rows',
    '_commands_table',
    '_features_table',
    '_FEATURE_KEYS',
    '_toggle_grid',
    '_slash_help',
    '_slash_help_topic',
    '_model_catalog',
]


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
        ("seo [--keyword X]", "on-page audit + keyword/hashtag pack → seo_report.md"),
        ("promote [--to fmt]", "X thread · LinkedIn · teaser · TL;DR + headlines → promo/"),
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
    """Feature toggles with live state (lives under /features; was the welcome screen).

    The toggle rows are built from `_FEATURE_KEYS` (the single source of truth, also
    used by the interactive grid) so the table and grid never drift; the trailing
    'quality knobs' / '/set' rows are the only hand-maintained, non-toggle entries."""
    rows = [_feat_row(label, getattr(settings, key, False), desc)
            for key, label, desc in _FEATURE_KEYS]
    rows += [
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
    ("skill_duels",       "skill duels", "A/B-test learned skills (one extra draft) - causal efficacy"),
    ("skill_distill",     "distill",     "retire near-duplicate skills so retrieval stays sharp"),
    ("watch_blocking",    "watch-block", "watch-list blocks clear violations (off = advisory only)"),
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
        # Fuzzy "did you mean" against the command/slash names so a near-miss isn't a dead end.
        names = []
        for (n, _d) in (cmd_rows + slash_rows):
            parts = _MARKUP.sub("", n).strip().lstrip("/").split()
            if parts:
                names.append(parts[0])
        sug = did_you_mean(topic, names)
        hint = f" Did you mean [{GOLD}]{sug}[/]?" if sug else ""
        _out(console, f"[dim]no help entry matches “{topic}”.{hint}  /help lists everything.[/]")
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
    from .. import providers
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
