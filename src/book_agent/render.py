"""Markdown rendering for plan, TOC, and fix-notes (shared by orchestrator + CLI)."""
from __future__ import annotations

from . import schemas as S


def render_plan_md(plan: S.BookPlan) -> str:
    lines = [
        f"# {plan.title}", "",
        f"- **Genre:** {plan.genre}", f"- **Tone:** {plan.tone}",
        f"- **Audience:** {plan.audience}", "",
        "## Premise", plan.premise, "",
        "## Themes", *(f"- {t}" for t in plan.themes), "",
        "## Constraints", *(f"- {c}" for c in plan.constraints), "",
        "## World rules", *(f"- {w}" for w in plan.world_rules), "",
        "## Main characters", *(f"- {c}" for c in plan.main_characters),
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


def render_outline_md(outline) -> str:
    """Render an ArticleOutline to a human-readable Markdown document."""
    lines = [
        f"# {outline.title}", "",
        f"*{outline.angle}*", "",
        f"Target: ~{outline.target_word_count:,} words", "",
        "## Sections", "",
    ]
    for s in outline.sections:
        flags = "".join([" `[code]`" if s.include_code else "",
                         " `[image]`" if s.include_image else ""])
        lines += [f"### {s.number}. {s.heading}{flags}", f"- {s.purpose}", ""]
    return "\n".join(lines)
