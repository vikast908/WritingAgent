"""Personas - selectable author/archetype voices (plan §23).

A persona is a *manner* layer: it flavors diction, rhythm, device-density, and stance
WITHIN whatever the register's rules allow. It is NOT a costume and NOT a content/era
override - a persona never lets the draft break the register's hard rules, invent archaic
vocabulary, or leave the present. It plugs into the existing voice-exemplar slot (so it
composes with the gold corpus and the user's own /praise'd voice), chosen by the compositor.

Two safe sources only (see docs/proposal-personas-emotions-composition.md):
- archetypes: original, reusable voices ("the wry skeptic", "the lyrical maximalist") - the
  primary, legally-clean, cosplay-proof option;
- public-domain manner: the *techniques* of out-of-copyright authors (aphoristic-declarative,
  free-indirect-irony, KJV cadence). The shipped exemplars are ORIGINAL pastiche written to
  carry the manner, not the authors' text - so there is no copyright surface at all.

Living / in-copyright authors are deliberately unsupported: for a specific modern voice the
user drops their own samples in voice/ or hits /praise (that path already exists).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from . import registers

_DIR = Path(__file__).resolve().parent / "personas"


@dataclass(frozen=True)
class Persona:
    """A named voice and the manner nudge that defines it."""

    name: str
    description: str
    kind: str                         # "archetype" | "author"
    signature: str                    # the manner card: diction / rhythm / devices / stance / avoid
    registers: tuple[str, ...] = ()   # compatible register names; () = compatible with all
    exemplar: str = ""                # filename in personas/ (original pastiche prose)


_PERSONAS: dict[str, Persona] = {
    # ── archetypes (original, reusable; the recommended default) ────────────────────
    "wry-skeptic": Persona(
        name="wry-skeptic", kind="archetype",
        description="Dry, doubting, quietly funny - trusts evidence, distrusts hype.",
        signature=("Diction plain with the occasional precise, surprising word. Rhythm: a long "
                   "measured sentence undercut by a short flat one. Devices: understatement, the "
                   "deflating aside, the rhetorical concession. Stance: skeptical but fair. AVOID: "
                   "sarcasm that sneers, jokes that don't carry an idea."),
        registers=("nonfiction", "technical", "business", "journalism")),
    "warm-mentor": Persona(
        name="warm-mentor", kind="archetype",
        description="Patient, generous, encouraging - explains as if to a smart friend.",
        signature=("Diction warm and concrete; second person where it helps. Rhythm steady and "
                   "unhurried. Devices: the well-chosen analogy, the 'here's the part that tripped "
                   "me up' confession. Stance: on the reader's side. AVOID: condescension, "
                   "false cheer, exclamation-point enthusiasm."),
        registers=("nonfiction", "technical", "business", "children")),
    "hard-boiled-minimalist": Persona(
        name="hard-boiled-minimalist", kind="archetype",
        description="Spare, declarative, unsentimental - says less, implies more.",
        signature=("Diction concrete and Anglo-Saxon; almost no adverbs. Rhythm: short, hard "
                   "sentences; the rare long one earns it. Devices: implication, white space, the "
                   "withheld feeling. Stance: detached, watchful. AVOID: abstraction, ornament, "
                   "explaining the emotion you just showed."),
        registers=("literary-fiction", "genre-fiction", "screenplay")),
    "lyrical-maximalist": Persona(
        name="lyrical-maximalist", kind="archetype",
        description="Rich, sensory, musical - long sentences that accumulate and turn.",
        signature=("Diction sensory and exact; trusts the long, subordinated sentence. Rhythm: "
                   "accretion and release, clause stacking on clause until a short line lands. "
                   "Devices: extended image, anaphora, the sentence that turns at the semicolon. "
                   "Stance: immersed. AVOID: purple mush, adjective piles that don't see anything."),
        registers=("literary-fiction", "poetry", "nonfiction")),
    "deadpan-technical": Persona(
        name="deadpan-technical", kind="archetype",
        description="Precise, calm, faintly funny about complexity - an engineer who can write.",
        signature=("Diction exact; terms defined once and reused. Rhythm even, with a dry beat at "
                   "the end of a paragraph. Devices: the worked example, the honest caveat, the "
                   "understated punchline about a foot-gun. Stance: unflappable. AVOID: hype, "
                   "anthropomorphizing the system, hand-waving."),
        registers=("technical", "nonfiction", "business")),
    "firebrand-essayist": Persona(
        name="firebrand-essayist", kind="archetype",
        description="Urgent, argumentative, morally serious - takes a side and defends it.",
        signature=("Diction muscular and direct; the occasional one-sentence paragraph for a "
                   "hammer-blow. Rhythm builds to a claim. Devices: the steelmanned objection then "
                   "the turn, the concrete case standing in for the principle. Stance: committed, "
                   "not shrill. AVOID: cheap outrage, strawmen, slogans."),
        registers=("nonfiction", "journalism")),
    # ── public-domain MANNER (original pastiche; the technique, never the text) ──────
    "shakespearean": Persona(
        name="shakespearean", kind="author",
        description="Heightened, metaphor-dense, the cadence of dramatic blank verse (manner only).",
        signature=("Diction elevated but not archaic - reach for the metaphor, not the 'thee'. "
                   "Rhythm leans iambic; let a line scan. Devices: extended metaphor, antithesis, "
                   "the turned phrase. Stance: grand, human. AVOID: 'forsooth' cosplay, fake Early "
                   "Modern spelling, anachronism."),
        registers=("literary-fiction", "poetry", "screenplay")),
    "nietzschean": Persona(
        name="nietzschean", kind="author",
        description="Aphoristic, declarative, contrarian - argues by provocation (manner only).",
        signature=("Diction sharp and absolute; short aphoristic sentences, the occasional em-dash "
                   "or colon that detonates. Rhythm: claim, pause, harder claim. Devices: the "
                   "inversion of a comfortable truth, the rhetorical question left to bleed. "
                   "Stance: provocative, unsentimental. AVOID: nihilist edgelord posturing, jargon."),
        registers=("nonfiction",)),
    "austen-ironic": Persona(
        name="austen-ironic", kind="author",
        description="Free indirect speech, social irony, a smiling blade (manner only).",
        signature=("Diction poised and exact; the well-balanced sentence. Rhythm: a measured "
                   "build to a dry comic landing. Devices: free indirect discourse (slip into a "
                   "character's judgment without saying so), understatement, the ironic universal "
                   "truth. Stance: amused, precise. AVOID: arch pastiche, period-costume diction."),
        registers=("literary-fiction",)),
    "twain-vernacular": Persona(
        name="twain-vernacular", kind="author",
        description="Plainspoken, wry, American - high meaning in low diction (manner only).",
        signature=("Diction plain and spoken; the homely image doing serious work. Rhythm: an easy "
                   "drawl that snaps shut on a punchline. Devices: deadpan exaggeration, the "
                   "deflating last clause, vernacular that's smarter than it looks. Stance: folksy, "
                   "shrewd. AVOID: minstrel dialect, forced folksiness."),
        registers=("literary-fiction", "nonfiction")),
}

_KINDS = ("archetype", "author")


def names() -> list[str]:
    return list(_PERSONAS)


def get(name: str | None) -> Persona | None:
    """Resolve a persona by name (normalized); None / unknown -> None (no persona)."""
    if not name:
        return None
    return _PERSONAS.get(str(name).strip().lower().replace("_", "-"))


def compatible(name: str | None, register: str | None) -> bool:
    """True if the persona fits this register (or declares no register restriction)."""
    p = get(name)
    if p is None:
        return False
    if not p.registers:
        return True
    return registers.get(register).name in p.registers


def _exemplar_text(filename: str, max_chars: int) -> str | None:
    try:
        text = (_DIR / filename).read_text(encoding="utf-8")
    except OSError:
        return None
    chunks: list[str] = []
    total = 0
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para or para.startswith("#") or para.startswith("```") or para.startswith(">"):
            continue
        if total + len(para) > max_chars:
            break
        chunks.append(para)
        total += len(para)
    return "\n\n".join(chunks) or None


def block(name: str | None, register: str | None, max_chars: int = 1400) -> str | None:
    """The persona voice block (signature + exemplar) for the writer's voice slot, or None
    when there is no such persona or it is incompatible with the register (the caller logs
    the mismatch and falls back to the user's voice / the register gold)."""
    p = get(name)
    if p is None or not compatible(name, register):
        return None
    parts = [f"PERSONA — write in the voice of the {p.name} ({p.description}). "
             f"This shapes MANNER ONLY; obey the register's rules, stay in the present, invent "
             f"no archaic words.\n{p.signature}"]
    ex = _exemplar_text(p.exemplar or f"{p.name}.md", max_chars)
    if ex:
        parts.append("Exemplar of this voice - match its rhythm, diction, and stance; do NOT "
                     "copy its content:\n\n" + ex)
    return "\n\n".join(parts)
