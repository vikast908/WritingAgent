"""Vertical slice: Planner -> TOC -> Writer -> Critic (+ revision loop), files-only.

No orchestrator, no synced index, no entity graph yet — this exists to prove the
core write -> judge -> revise loop end to end before building the LangGraph engine.
"""
from __future__ import annotations

import argparse
import sys

from . import brain
from . import schemas as S
from .config import load_config
from .nodes import (
    build_toc,
    critique_chapter,
    planner_directions,
    planner_expand,
    summarize_chapter,
    write_chapter,
)


def render_plan_md(plan: S.BookPlan) -> str:
    lines = [
        f"# {plan.title}",
        "",
        f"- **Genre:** {plan.genre}",
        f"- **Tone:** {plan.tone}",
        f"- **Audience:** {plan.audience}",
        "",
        "## Premise",
        plan.premise,
        "",
        "## Themes",
        *(f"- {t}" for t in plan.themes),
        "",
        "## Constraints",
        *(f"- {c}" for c in plan.constraints),
        "",
        "## World rules",
        *(f"- {w}" for w in plan.world_rules),
        "",
        "## Main characters",
        *(f"- {c}" for c in plan.main_characters),
    ]
    return "\n".join(lines)


def render_toc_md(toc: S.TOC) -> str:
    out = ["# Table of Contents", ""]
    for c in toc.chapters:
        deps = ", ".join(map(str, c.depends_on)) or "—"
        out += [
            f"## {c.number}. {c.title}",
            f"- **Purpose:** {c.purpose}",
            f"- **Emotional role:** {c.emotional_role}",
            f"- **Plot function:** {c.plot_function}",
            f"- **Setup:** {c.setup}",
            f"- **Payoff:** {c.payoff}",
            f"- **Depends on:** {deps}",
            "",
        ]
    return "\n".join(out)


def render_fix_notes(crit: S.Critique) -> str:
    lines = [f"- [{b.type}] {b.where}: {b.detail} (fix: {b.fix})" for b in crit.blocking]
    lines += [f"- nit: {x}" for x in crit.nits]
    return "\n".join(lines)


def write_review(bdir, n: int, crit: S.Critique) -> None:
    lines = [
        f"# Review needed — chapter {n}",
        "",
        f"- verdict: {crit.verdict}",
        f"- confidence: {crit.confidence:.2f}",
        "",
        "## Blocking",
        *(f"- [{b.type}] {b.where}: {b.detail}\n  fix: {b.fix}" for b in crit.blocking),
        "",
        "## Nits",
        *(f"- {x}" for x in crit.nits),
        "",
        "## Your directed instructions",
        "_Reply here, then re-run to revise (this is the review-queue stand-in)._",
    ]
    brain.write_text(bdir / "reviews" / f"ch{n:02d}.md", "\n".join(lines))


def main() -> None:
    for _stream in (sys.stdout, sys.stderr):  # Windows consoles default to cp1252
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    ap = argparse.ArgumentParser(
        description="Book Agent vertical slice (Planner -> TOC -> Writer -> Critic)."
    )
    ap.add_argument("--abstract", help="One- or two-paragraph book idea")
    ap.add_argument("--book-id", help="Override the book folder name")
    ap.add_argument("--chapters", type=int, default=8, help="TOC length")
    ap.add_argument("--chapter", type=int, default=1, help="Which chapter to draft")
    ap.add_argument("--pick", type=int, help="Pick direction (1-based) non-interactively")
    ap.add_argument("--max-revisions", type=int, default=2)
    args = ap.parse_args()

    abstract = args.abstract or input("Book abstract: ").strip()
    if not abstract:
        print("No abstract provided.", file=sys.stderr)
        sys.exit(1)

    cfg = load_config()

    print("\n== Planning directions ==")
    directions = planner_directions(cfg, abstract).directions
    for i, d in enumerate(directions, 1):
        print(f"\n[{i}] {d.title}\n    {d.premise}\n    tone: {d.tone} | hook: {d.hook}")

    if args.pick:
        idx = args.pick
    else:
        idx = int(input(f"\nPick a direction [1-{len(directions)}]: ").strip())
    chosen = directions[idx - 1]
    print(f"\n-> Chosen: {chosen.title}")

    print("\n== Expanding book plan ==")
    plan = planner_expand(cfg, abstract, chosen)
    book_id = args.book_id or brain.slugify(plan.title)
    bdir = brain.ensure_book(book_id)
    brain.write_text(bdir / "book_plan.md", render_plan_md(plan))
    print(f"   wrote {bdir / 'book_plan.md'}")

    print("\n== Building TOC ==")
    toc = build_toc(cfg, plan, args.chapters)
    brain.write_text(bdir / "toc.md", render_toc_md(toc))
    print(f"   wrote {bdir / 'toc.md'} ({len(toc.chapters)} chapters)")

    n = args.chapter
    if n < 1 or n > len(toc.chapters):
        print(f"Chapter {n} out of range (1..{len(toc.chapters)}).", file=sys.stderr)
        sys.exit(1)
    blueprint = toc.chapters[n - 1]

    prior_summary = None
    if n > 1:
        prior_summary = brain.read_text(bdir / "chapters" / f"ch{n - 1:02d}.summary.md")

    print(f"\n== Drafting chapter {n}: {blueprint.title} ==")
    fix_notes = None
    crit: S.Critique | None = None
    draft = ""
    approved = False
    for attempt in range(args.max_revisions + 1):
        label = "draft" if attempt == 0 else f"revision {attempt}"
        print(f"   writing ({label})...")
        draft = write_chapter(cfg, plan, blueprint, prior_summary, fix_notes)
        print("   critiquing...")
        crit = critique_chapter(cfg, plan, blueprint, draft, prior_summary)
        print(
            f"   verdict: {crit.verdict}  confidence: {crit.confidence:.2f}  "
            f"blocking: {len(crit.blocking)}  nits: {len(crit.nits)}"
        )
        for b in crit.blocking:
            print(f"     - [{b.type}] {b.where}: {b.detail}")
        if crit.verdict == "approve":
            approved = True
            break
        if crit.verdict == "escalate":
            break
        if attempt == args.max_revisions:
            print("   revision cap reached -> escalate to human")
            break
        fix_notes = render_fix_notes(crit)

    assert crit is not None
    brain.write_json(bdir / "eval" / f"ch{n:02d}.json", {"chapter_id": n, **crit.model_dump()})

    if approved:
        ch_path = bdir / "chapters" / f"ch{n:02d}.md"
        brain.write_text(ch_path, draft)
        summary = summarize_chapter(cfg, blueprint, draft)
        brain.write_text(bdir / "chapters" / f"ch{n:02d}.summary.md", summary)
        print(f"\n[OK] Approved. Wrote {ch_path} (+ summary, eval)")
    else:
        draft_path = bdir / "chapters" / f"ch{n:02d}.draft.md"
        brain.write_text(draft_path, draft)
        write_review(bdir, n, crit)
        print(f"\n[!] Not approved ({crit.verdict}). Wrote {draft_path} + review entry + eval.")
        print("    (In the full system this checkpoints and waits for directed instructions.)")


if __name__ == "__main__":
    main()
