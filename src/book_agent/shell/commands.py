"""Slash-command handlers (/model /provider /path /set /auto /praise /skills ...) plus
path management and project selection."""
from __future__ import annotations

import re

from .. import brain, ui
from .. import skills as skills_mod
from ..config import ModelConfig, Settings, save_config, save_settings
from ..ui import DIM, ERR, GOLD, INK, OFF_CLR, ON_CLR, PARCH
from ._const import _MARKUP, _NODES
from .branding import _cmd_table, _out, _section, _sync_palette
from .help import _model_catalog

__all__ = [
    '_cmd_model',
    '_cmd_provider',
    '_norm_dir',
    '_ensure_dir',
    '_print_path_status',
    '_set_default_path',
    '_set_project_path',
    '_cmd_path',
    '_use_project',
    '_cmd_dashboard',
    '_set_theme',
    '_cmd_set',
    '_AUTO_ON',
    '_AUTO_OFF',
    '_cmd_auto',
    '_cmd_praise',
    '_print_skills',
    '_print_skill',
]


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
    from .. import llm, providers
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
    from .. import telemetry
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
    from .. import orchestrator
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
    from ..brain import ArticlePaths, BookPaths
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
        t.add_column("first-pass  (vs baseline)", style=PARCH)
        t.add_column("duels  (vs 50/50)", style=PARCH)
        for r in rows:
            if r["duels"]:
                # win-rate vs a 0.5 coin-flip baseline; this drives status once it has data.
                duel_cell = ui.efficacy_bar(r["duel_wr"], 0.5)
                duel_cell.append(f"  ({r['duels']})", style=DIM)
            else:
                duel_cell = "[dim]—[/]"
            t.add_row(r["name"], r["status"], str(r["applied"]),
                      ui.efficacy_bar(r["p_skill"], r["p_base"]), duel_cell)
        console.print(t)
        console.print(f"  [{DIM}]trusted/retired is decided by duels once a skill has data "
                      f"(/set skill_duels true), else by first-pass lift.[/]")
    else:
        for r in rows:
            duel = f" duel_wr={r['duel_wr']} ({r['duels']})" if r["duels"] else ""
            print(f"  {r['name']:<34} {r['status']:<10} applied={r['applied']} "
                  f"p={r['p_skill']}{duel}")


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
