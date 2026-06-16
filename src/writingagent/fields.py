"""Field structural templates (plan §22, Tier 3).

A register fixes the *voice* and the *rules*; a field template fixes the *shape* - the
structural grammar a genre's readers expect. A news story is an inverted pyramid; a paper
is IMRaD; ad copy is a hook→problem→benefit→proof→CTA arc; a memo is BLUF. These are
injected into the outline architect (TOC / article outline) so the *structure* is right
before a single section is drafted, the same way the register tailors the prose.

Kept deliberately small and data-only: a name → a one-paragraph structural instruction.
Each register declares its default field via `for_register`; an explicit `field` setting
can override. The future compositor (docs/proposal-personas-emotions-composition.md) treats
this as the structure layer that sits inside the register and outside the persona.
"""
from __future__ import annotations

from . import registers

# name -> the structural skeleton to organize the outline around.
_STRUCTURES: dict[str, str] = {
    "inverted-pyramid": (
        "STRUCTURE - inverted pyramid (journalism): open with the LEDE (the single most "
        "newsworthy fact) and a NUT GRAF (why it matters, who is affected). Then supporting "
        "detail and attributed quotes in descending order of importance, so the piece stays "
        "complete if cut from the bottom. Background and context come last."),
    "imrad": (
        "STRUCTURE - IMRaD (academic): Abstract, Introduction (problem + contribution + the "
        "gap in prior work), Methods, Results, Discussion (interpretation + limitations + "
        "future work), Conclusion. Signpost each section explicitly; state claims at the "
        "strength the evidence supports."),
    "aida": (
        "STRUCTURE - AIDA / PAS (copy): hook ATTENTION in the first line; build INTEREST with "
        "the reader's problem made vivid; create DESIRE by turning features into benefits with "
        "proof; end on one unambiguous ACTION (a single CTA). One idea per line."),
    "bluf": (
        "STRUCTURE - BLUF (business): Bottom Line Up Front - the recommendation, the ask, and "
        "the cost/impact in numbers come FIRST. Then the few reasons that matter (each "
        "quantified), options as bullets with trade-offs, and the explicit decision required "
        "and by when."),
    "how-to": (
        "STRUCTURE - how-to / tutorial: state the goal and the prerequisites, then ordered "
        "steps each with the command/code and the expected result, then common failure modes "
        "and how to verify success. Lead with the mechanism, not its importance."),
    "three-act": (
        "STRUCTURE - dramatic arc: setup (world, character want, inciting incident), "
        "confrontation (rising obstacles, midpoint reversal, escalating stakes), resolution "
        "(climax + falling action). Each chapter turns on a want and an obstacle and ends on "
        "a hook or a shift."),
    "screenplay": (
        "STRUCTURE - screenplay: organize by scenes (sluglines: INT./EXT. - LOCATION - TIME). "
        "Each scene has a goal, a turn, and an exit on tension. Externalize interior states "
        "into visible action and subtext-laden dialogue."),
    "essay": (
        "STRUCTURE - argumentative essay: a hook that earns attention, the thesis (a "
        "contestable claim), each section advancing one supporting argument with evidence, an "
        "honest engagement with the strongest counterargument, and a close that lands the "
        "stakes (not a summary)."),
}

# Each register's default structural shape.
_BY_REGISTER: dict[str, str] = {
    "journalism": "inverted-pyramid",
    "academic": "imrad",
    "copywriting": "aida",
    "business": "bluf",
    "technical": "how-to",
    "literary-fiction": "three-act",
    "genre-fiction": "three-act",
    "screenplay": "screenplay",
    "nonfiction": "essay",
}


def names() -> list[str]:
    return list(_STRUCTURES)


def for_register(register: str | None) -> str:
    """The default field-structure name for a register ('' when it has no strong default)."""
    return _BY_REGISTER.get(registers.get(register).name, "")


def guidance(name_or_register: str | None, *, is_register: bool = False) -> str:
    """The structural instruction for a field name (or a register's default field).
    Returns '' when unknown / none, so callers can append unconditionally."""
    if not name_or_register:
        return ""
    name = for_register(name_or_register) if is_register else str(name_or_register).strip().lower()
    return _STRUCTURES.get(name, "")


def resolve(register: str | None, explicit_field: str = "") -> str:
    """The outline structural instruction for a run: an explicit `field` setting wins,
    otherwise the register's default field. '' when neither resolves (the architect then
    uses its own default ordering)."""
    if explicit_field:
        return guidance(explicit_field)
    return guidance(register, is_register=True)
