"""The live Rich run dashboard: run controls, the key listener, the dashboard widget,
status cards, and run_with_dashboard."""
from __future__ import annotations

import collections
import os
import threading
import time

from .. import brain, ui
from ..ui import DIM, ERR, GOLD, INK, ON_CLR, PARCH, RULE
from ._const import _FLEURON
from .branding import _out, _section

__all__ = [
    '_reduced_motion',
    '_a11y',
    '_RunControls',
    '_KeyListener',
    '_RunDashboard',
    '_ring',
    '_summary_card',
    '_paused_card',
    '_escalation_picker',
    'run_with_dashboard',
    '_cmd_run_rich',
]


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
        self._done0 = done          # units already committed before this session (for the run ETA)
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

    def _run_eta(self) -> str:
        """Coarse whole-run ETA from this session's average time-per-unit. Only once at
        least one unit has committed this session; silent on resume until then."""
        completed = self.done - self._done0
        remaining = max(0, self.total - self.done)
        if completed < 1 or remaining == 0:
            return ""
        secs = int((time.time() - self.start) / completed * remaining)
        return f" · ~{secs // 60}m left" if secs >= 60 else f" · ~{secs}s left"

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

        from .. import llm
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
        bar.append(self._run_eta(), style=DIM)
        stage = Text("  ")
        if self.unit:
            stage.append(self.unit + "  ", style=PARCH)
        stage.append("· " + self._stage_label(), style=f"italic {INK}")
        if self.verdict:
            stage.append("   " + self.verdict, style=DIM)
        hint = ("  esc pause · m manual · Ctrl-C stop — all resumable" if self.live_controls
                else "  Ctrl-C pauses — saved & resumable (discard a project with /delete)")
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

    from .. import llm
    from ..brain import ArticlePaths, BookPaths
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

    from .. import llm
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

    from .. import orchestrator
    from ..brain import ArticlePaths, BookPaths
    from ..config import load_settings as _load_settings
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

    from .. import brain as _brain
    from .. import orchestrator
    from ..brain import ArticlePaths, BookPaths

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
