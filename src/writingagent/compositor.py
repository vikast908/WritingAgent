"""The compositor (plan §23): assemble the writing layers with precedence.

The cascade, outer layers winning conflicts:

    register  ⊃  field  ⊃  persona  ⊃  emotion  ⊃  skills

`register` (the rules + voice) and `field` (the structure) are resolved at project creation
(see registers.py / fields.py). Skills are retrieved and capped elsewhere. This module owns
the MANNER layers - persona (a selected voice) and emotion (a per-run affective cue) - and
the one rule that makes stacking safe: **the inner layer may only fill the freedom the outer
leaves open, never break it.** A persona that doesn't fit the register is dropped (the
register wins), not blended; there is at most one persona and one emotion (single-select),
because a weak model given two voices averages them into mush.

Today the compositor produces the writer's single "match this" voice string. As the cascade
grows it stays the one place that decides what is selected, what is dropped, and why - logged,
never silently accumulated.
"""
from __future__ import annotations

from . import brain, emotions, personas, registers


def voice(uid: str, register: str | None = None, persona: str | None = None,
          emotion: str | None = None, *, log=None) -> str | None:
    """The writer's manner anchor, resolved by precedence.

    Voice precedence (single-select): a compatible selected persona (its signature + exemplar)
    > the user's own voice exemplars > the register's gold corpus. An incompatible persona is
    LOGGED and skipped - the register wins the conflict (a Nietzschean API reference is not a
    thing). When an emotion is set, its show-don't-name craft cue is appended.

    Returns the combined voice string for the writer's voice slot, or None when nothing
    resolves (no persona, no user voice, no gold, no emotion).
    """
    block = None
    if persona:
        block = personas.block(persona, register)
        if block is None and personas.get(persona) is not None and log:
            log(f"[compositor] persona '{persona}' does not fit the "
                f"'{registers.get(register).name}' register - using the register voice instead.")
    if block is None:
        block = brain.style_exemplars(uid, register)
    cue = emotions.cue(emotion) if emotion else ""
    if cue:
        block = ((block + "\n\n") if block else "") + "EMOTIONAL TARGET (show it, never name it): " + cue
    return block or None
