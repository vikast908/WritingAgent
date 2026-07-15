"""The autonomous `write` flow: an upfront interview (pick an approach, answer one
batch of tailored questions) followed by a full unattended run to an exported file."""
from __future__ import annotations

import sys

from .. import nodes, orchestrator, ui
from ._common import _console, _spin
from .export import _EXPORT_FORMATS, _resolve_formats, _run_exports

__all__ = [
    "cmd_write",
    "_quick_research",
    "_ask_batch",
    "_pick_approach",
    "_render_intake",
    "_conduct_interview",
]


def _quick_research(settings, topic: str) -> str | None:
    """A fast, best-effort web peek so the interview can ask sharper questions. Never
    blocks: researcher off, offline, or any error -> None and the flow continues."""
    if not settings.use_researcher:
        return None
    try:
        from .. import search as search_mod
        results = search_mod.web_search(topic, max_results=3)
        return search_mod.format_results(results) or None
    except Exception:  # noqa: BLE001 - research is optional
        return None


def _ask_batch(console, intro: str, items: list[tuple[str, str]]) -> list[str]:
    """Show every question upfront, then collect answers one line at a time.
    `items` is [(question, default)]; an empty answer takes the default."""
    answers: list[str] = []
    if console:
        from rich.markup import escape
        console.print(f"\n[bold {ui.GOLD}]{escape(intro)}[/]\n")
        for i, (q, d) in enumerate(items, 1):
            dflt = f"  [dim](default: {escape(d)})[/]" if d else ""
            console.print(f"  [{ui.GOLD}]{i}.[/] {escape(q)}{dflt}")
        console.print()
        for i, (_q, d) in enumerate(items, 1):
            raw = console.input(f"  [{ui.GOLD}]{i} ›[/] ").strip()
            answers.append(raw or d)
    else:
        print("\n" + intro + "\n")
        for i, (q, d) in enumerate(items, 1):
            print(f"  {i}. {q}" + (f"  (default: {d})" if d else ""))
        print()
        for i, (_q, d) in enumerate(items, 1):
            answers.append(input(f"  {i} > ").strip() or d)
    return answers


def _pick_approach(console, topic: str, items: list[str]) -> int:
    """Show candidate angles/directions; return the chosen 1-based index (default 1)."""
    if console:
        from rich.markup import escape
        console.print(f"\n[bold {ui.GOLD}]Approaches[/] [dim]for: {escape(topic)}[/]")
        for i, it in enumerate(items, 1):
            console.print(f"  [{ui.GOLD}]{i}[/]  {escape(it)}")
        raw = console.input("\n  [dim]pick an approach[/] [dim][1]:[/] ").strip()
    else:
        print(f"\nApproaches for: {topic}")
        for i, it in enumerate(items, 1):
            print(f"  {i}  {it}")
        raw = input("\n  pick an approach [1]: ").strip()
    try:
        idx = int(raw or "1")
    except ValueError:
        idx = 1
    return max(1, min(idx, len(items)))


def _render_intake(topic: str, approach: str, qa_pairs, author: str) -> str:
    lines = ["# Author requirements (captured upfront)", "",
             f"Topic: {topic}", f"Approach: {approach}", "", "## Answers"]
    for q, a in qa_pairs:
        a = (a or "").strip()
        if a:
            lines.append(f"- **{q}**\n  {a}")
    if author:
        lines.append(f"- **Author / byline:** {author}")
    return "\n".join(lines)


def _conduct_interview(cfg, settings, uid, topic, mode, console):
    """Gather everything upfront: pick an approach, then answer one batch of tailored
    questions. Returns (chosen, intake_md, export_format, author)."""
    research = _quick_research(settings, topic)
    if mode == "article":
        angles = _spin("studying the topic + planning angles",
                       lambda: nodes.plan_article_angles(cfg, topic)).angles
        approach_items = [f"{a.title} - {a.angle}  (for {a.audience})" for a in angles]
        choices = angles
    else:
        dirs = _spin("planning directions",
                     lambda: nodes.planner_directions(cfg, topic)).directions
        approach_items = [f"{d.title} - {d.premise}  (tone: {d.tone})" for d in dirs]
        choices = dirs
    idx = _pick_approach(console, topic, approach_items)
    chosen = choices[idx - 1]

    chosen_focus = f"{topic}\n\nChosen approach: {approach_items[idx - 1]}"
    iv = _spin("preparing your questions",
               lambda: nodes.interview(cfg, chosen_focus, mode, research)).questions

    default_fmt = "docx" if mode == "article" else "pdf"
    qa_items = [(q.question, q.suggestion or "") for q in iv]
    qa_items.append(("Your name for the byline / author credit (Enter to skip)", ""))
    qa_items.append((f"Output file format ({' / '.join(_EXPORT_FORMATS)}, or 'all')", default_fmt))
    answers = _ask_batch(
        console, "A few questions - then I'll research, write, self-edit, and hand you "
                 "the finished piece. No more interruptions:", qa_items)

    fmts, _bad = _resolve_formats(answers[-1] or default_fmt)
    if not fmts:                       # empty or all-unrecognised -> the mode default
        fmts = [default_fmt]
    author = answers[-2].strip()
    qa_pairs = list(zip([q.question for q in iv], answers[:-2], strict=False))
    return chosen, _render_intake(topic, approach_items[idx - 1], qa_pairs, author), fmts, author


def cmd_write(args, cfg, settings, uid):
    """One-shot autonomous flow: topic -> upfront interview -> full run -> exported file."""
    from .. import skills as skills_mod
    skills_mod.seed_builtin(uid)
    mode = settings.mode
    label = "Article topic" if mode == "article" else "Book idea"
    topic = args.abstract or input(f"{label}: ").strip()
    if not topic:
        sys.exit("No topic provided.")
    console = _console()

    chosen, intake_md, fmts, author = _conduct_interview(cfg, settings, uid, topic, mode, console)

    units = args.chapters or (settings.num_sections if mode == "article"
                              else settings.num_chapters)
    max_rev = args.max_revisions if args.max_revisions is not None else settings.max_revisions
    humanize = False if getattr(args, "no_humanize", False) else None

    if mode == "article":
        pid = _spin("building the outline", lambda: orchestrator.start_article(
            cfg, settings, uid, topic, chosen, args.book_id, units, max_rev,
            autonomous=True, humanize=humanize, intake=intake_md, author=author))
    else:
        pid = _spin("building the plan + chapters", lambda: orchestrator.start_book(
            cfg, settings, uid, topic, chosen, args.book_id, units, max_rev,
            autonomous=True, humanize=humanize, intake=intake_md, author=author))

    msg = (f"Writing '{pid}' autonomously - research, drafting, self-review, assembly. "
           "This can take a while; no more questions.")
    if console:
        console.print(f"\n[{ui.GOLD}]{msg}[/]")
    else:
        print("\n" + msg)

    if console:
        from ..shell import run_with_dashboard
        run_with_dashboard(cfg, uid, pid, console)
    else:
        orchestrator.run(cfg, uid, pid, log=print)

    # Only export a FINISHED piece: a budget-pause or escalation used to fall straight
    # through to _run_exports, printing export failures (or shipping a partial
    # manuscript) directly under the paused card.
    st = orchestrator.status(uid, pid)
    if st.get("phase") != "done":
        why = "review pending" if st.get("pending_review") else f"phase: {st.get('phase')}"
        msg = (f"Run paused before completion ({why}) - skipping export. "
               f"Resume with: writing-agent run --book-id {pid}")
        console.print(f"\n  [{ui.DIM}]{msg}[/]") if console else print("\n" + msg)
        return pid

    # SEO audit + promo pack (plan §24), before export so the HTML export picks up the
    # fresh keywords.json meta tags. LOCAL artifacts only: seo_report.md, keywords.json,
    # and promo/*.md drafts - the manuscript is untouched and NOTHING is posted anywhere.
    if getattr(settings, "auto_promote", True):
        plog = (lambda m: console.print(f"  [{ui.DIM}]{m}[/]")) if console else print
        try:
            orchestrator.apply_seo(cfg, uid, pid, log=plog)   # optimize title/meta for the keyword
            orchestrator.build_promo_pack(cfg, uid, pid, log=plog)
        except Exception as e:  # noqa: BLE001 - promotion is additive, never fails a write
            plog(f"[promote] skipped ({type(e).__name__}) - run `seo` / `promote` manually")

    ok = _run_exports(console, fmts, uid, pid)
    if ok and console:
        tail = f"exported {ok} formats" if ok > 1 else "finished"
        console.print(f"\n  [bold {ui.ON_CLR}]✓ done[/]  [{ui.DIM}]{tail}[/]")
    return pid
