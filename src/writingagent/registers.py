"""Register / genre profiles - the craft contract, parameterized (plan §22).

A great writer is *polyvocal*: the rules that sharpen a blog post (no em-dashes, cut
hedging, kill the rule of three, no exclamation marks) are *wrong* for a novel, a journal
paper, or ad copy. The anti-slop machinery (`slop.py`) used to bake one register - the
"researcher voice" - into every prompt and the deterministic stripper. A `Register` makes
that contract a parameter: which bans apply, which invert, the voice the writer matches,
the rhythm/diction guidance, the citation style, and which deterministic craft metrics
matter for the genre.

The DEFAULT register (`nonfiction`) reproduces the historical behavior exactly, so
`slop.render_constraints()` / `slop.tell_pattern()` with no register are byte-for-byte
what they were before this module existed (a test asserts the round-trip).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_GOLD = Path(__file__).resolve().parent / "gold"


# Craft-metric keys (see craft.py). Surfaced to the critic as computed evidence; the
# set is per-register so a novel isn't scored for "specificity density" (data per 100
# words - a nonfiction measure) nor a whitepaper for dialogue ratio.
_NONFICTION_METRICS = (
    "paragraph_uniformity", "rule_of_three", "wrapups", "specificity",
    "sentence_variance", "passive", "adverbs", "reading_grade", "cliche", "opening",
)
_FICTION_METRICS = (
    "sentence_variance", "filter_words", "dialogue", "said_bookisms", "adverbs",
    "pov_tense", "cliche", "opening", "concrete_sensory",
)


@dataclass(frozen=True)
class Register:
    """A named writing register and the craft contract that goes with it."""

    name: str
    description: str
    # ── anti-slop allowances (what this register does NOT ban) ──────────────────
    allow_em_dash: bool = False          # fiction/essay/poetry: the em-dash is voice, not a tell
    allow_intensifiers: bool = False     # "extremely", "remarkably" - fine in some voices
    allow_enthusiasm: bool = False       # exclamation marks / cheerleading (copy, children's)
    allow_transitions: bool = False      # furthermore/moreover/notwithstanding (academic/legal)
    hedging_required: bool = False       # academic: epistemic hedges are honesty, not filler
    allow_terms: frozenset[str] = frozenset()   # specific banned verbs/terms this register permits
    # ── positive guidance (shown, not just enforced) ───────────────────────────
    voice_line: str = (
        "RESEARCHER VOICE: direct, grounded, specific. Delete any sentence generic "
        "enough to appear unchanged on any site. Make it specific or cut it.")
    concrete_line: str = (
        "CONCRETE OVER ABSTRACT. Every vague claim needs a specific fact, name, or date.")
    guidance: str = ""                   # rhythm / diction / person / tense cues, injected verbatim
    # ── output conventions ──────────────────────────────────────────────────────
    citation_style: str = "influence"    # influence | numeric | apa | mla | chicago | ap | none
    metrics: tuple[str, ...] = _NONFICTION_METRICS
    reading_grade: tuple[int, int] | None = None   # target Flesch-Kincaid grade band (advisory)
    gold: str = ""                       # gold-corpus filename in gold/ (style anchor; "" = none)


# ── The profiles ────────────────────────────────────────────────────────────────
# `nonfiction` is the default and MUST keep the historical contract verbatim.
_REGISTERS: dict[str, Register] = {
    "nonfiction": Register(
        name="nonfiction",
        description="Long-form argumentative nonfiction, essays, blog posts (the default).",
        guidance=("Lead with the point. Carry every claim with a name, number, or example. "
                  "Vary sentence length; let short sentences land."),
        reading_grade=(9, 13),
        gold="nonfiction.md",
    ),
    "technical": Register(
        name="technical",
        description="Documentation, engineering deep-dives, how-to and reference writing.",
        allow_transitions=False,
        allow_terms=frozenset({"facilitate", "enhance"}),   # often the precise term in docs
        voice_line=("ENGINEER VOICE: precise and unhurried. Define a term once, then reuse it. "
                    "Prefer the worked example to the adjective."),
        guidance=("Show the mechanism, not its importance. A code block or concrete example "
                  "beats a paragraph of description. Name versions, limits, and trade-offs."),
        reading_grade=(10, 14),
        gold="technical.md",
    ),
    "literary-fiction": Register(
        name="literary-fiction",
        description="Novels and literary short fiction.",
        allow_em_dash=True,
        allow_intensifiers=True,
        allow_terms=frozenset({"realm", "landscape", "tapestry"}),  # may be literal/imagery
        voice_line=("NARRATIVE VOICE: render, do not summarize. Put the reader in the scene "
                    "through sense and action; trust them to feel without being told what to feel."),
        concrete_line=("SHOW, DON'T TELL. Replace stated emotion ('she was afraid') and filter "
                       "verbs ('he saw', 'she felt') with the concrete image or action that earns it."),
        guidance=("Write in scene: specific sensory detail, action, and dialogue over exposition. "
                  "Vary sentence rhythm hard - fragments for impact, long sentences for momentum. "
                  "Keep one point of view per scene; hold the tense steady."),
        citation_style="none",
        metrics=_FICTION_METRICS,
        gold="literary-fiction.md",
    ),
    "genre-fiction": Register(
        name="genre-fiction",
        description="Plot-forward commercial fiction (thriller, romance, SFF, mystery).",
        allow_em_dash=True,
        allow_intensifiers=True,
        voice_line=("STORYTELLER VOICE: momentum first. Every scene turns on a want and an "
                    "obstacle; end beats on a hook."),
        concrete_line=("SHOW, DON'T TELL. Dramatize emotion and stakes in action and dialogue; "
                       "cut filter verbs ('he saw', 'she felt')."),
        guidance=("Keep the pages turning: scene and sequel, rising tension, cliff-edge chapter "
                  "ends. Dialogue carries conflict and subtext. One POV per scene; steady tense."),
        citation_style="none",
        metrics=_FICTION_METRICS,
        gold="genre-fiction.md",
    ),
    "academic": Register(
        name="academic",
        description="Scholarly papers and theses (IMRaD, hedged, cited).",
        allow_transitions=True,          # 'moreover'/'furthermore'/'notwithstanding' are connectives here
        hedging_required=True,           # 'these results suggest', 'may indicate' = epistemic honesty
        allow_terms=frozenset({"robust", "comprehensive", "nuanced", "facilitate", "enhance",
                               "multifaceted", "paramount"}),
        voice_line=("SCHOLARLY VOICE: precise, measured, qualified. State claims at the strength "
                    "the evidence supports - hedge when the data does, do not overclaim."),
        concrete_line=("EVIDENCE OVER ASSERTION. Tie each claim to a citation, a result, or a "
                       "defined construct; quantify where you can."),
        guidance=("Foreground the contribution and its limits. Signpost structure explicitly. "
                  "Hedging ('suggests', 'may', 'appears to') is required where certainty is not "
                  "warranted - it is honesty, not filler."),
        citation_style="apa",
        reading_grade=(13, 17),
        gold="academic.md",
    ),
    "journalism": Register(
        name="journalism",
        description="News and feature reporting (lede, nut graf, attribution).",
        voice_line=("REPORTER VOICE: lead with the news. Attribute every claim to a named source; "
                    "keep the writer out of it."),
        concrete_line=("ATTRIBUTE AND VERIFY. Who said it, when, how known. No claim floats free "
                       "of a source."),
        guidance=("Open with the lede - the most newsworthy fact - then the nut graf (why it "
                  "matters). Inverted pyramid: most important first. Short paragraphs. Attribute "
                  "with 'said'; let quotes carry voice."),
        citation_style="ap",
        reading_grade=(7, 11),
        gold="journalism.md",
    ),
    "copywriting": Register(
        name="copywriting",
        description="Marketing, ads, landing pages, sales copy.",
        allow_intensifiers=True,
        allow_enthusiasm=True,           # the craft of copy USES energy and the exclamation
        allow_terms=frozenset({"seamless", "cutting-edge", "innovative"}),
        voice_line=("BRAND VOICE: speak to one reader about one desire. Benefit before feature; "
                    "concrete promise before claim."),
        concrete_line=("BENEFIT, PROOF, ACTION. Turn every feature into a reader benefit, back it "
                       "with proof, and end on one clear call to action."),
        guidance=("Hook in the first line. One idea per line; rhythm and the rule of three are "
                  "tools, not tells. Drive to a single call to action. Specific beats clever."),
        citation_style="none",
        reading_grade=(5, 9),
        gold="copywriting.md",
    ),
    "business": Register(
        name="business",
        description="Memos, reports, executive summaries, briefs.",
        allow_terms=frozenset({"comprehensive", "robust"}),
        voice_line=("EXECUTIVE VOICE: bottom line up front. State the ask, the why, and the "
                    "decision needed before any detail."),
        concrete_line=("BLUF: the recommendation and its cost/impact come first, in numbers."),
        guidance=("Lead with the conclusion (BLUF). Then the few reasons that matter, each "
                  "quantified. Bullets over paragraphs for options. End with the decision asked for."),
        citation_style="numeric",
        reading_grade=(9, 13),
        gold="business.md",
    ),
    "poetry": Register(
        name="poetry",
        description="Poems and verse.",
        allow_em_dash=True,
        allow_intensifiers=True,
        allow_enthusiasm=True,
        allow_terms=frozenset({"tapestry", "symphony", "beacon", "realm", "landscape"}),
        voice_line=("POET VOICE: compress. The image carries the meaning; the line break is "
                    "punctuation. Sound is argument."),
        concrete_line=("IMAGE OVER STATEMENT. Show the thing; let the reader infer the feeling."),
        guidance=("Line and stanza are the form - honor the requested shape (free verse, sonnet, "
                  "haiku...). Sound matters: meter, assonance, consonance. Compress ruthlessly; "
                  "every word earns its place."),
        citation_style="none",
        metrics=("cliche", "concrete_sensory", "sentence_variance"),
        gold="poetry.md",
    ),
    "screenplay": Register(
        name="screenplay",
        description="Film/TV scripts and stage plays.",
        allow_em_dash=True,
        voice_line=("SCREEN VOICE: only what the camera sees and the mic hears. Present tense, "
                    "active, lean."),
        concrete_line=("ON THE SCREEN. Externalize interior states into visible action and "
                       "subtext-laden dialogue; never narrate thoughts."),
        guidance=("Standard format: scene heading (INT./EXT. - LOCATION - TIME), then present-"
                  "tense action lines, then CHARACTER cues and dialogue. Action is visual and "
                  "brief. Dialogue carries subtext; trim the on-the-nose line."),
        citation_style="none",
        metrics=("dialogue", "said_bookisms", "sentence_variance", "cliche"),
        gold="screenplay.md",
    ),
    "children": Register(
        name="children",
        description="Children's stories and early-reader prose.",
        allow_enthusiasm=True,
        allow_intensifiers=True,
        voice_line=("STORYTELLER-FOR-KIDS VOICE: warm, clear, playful. Concrete nouns, strong "
                    "verbs, rhythm a child can hear read aloud."),
        concrete_line=("SHOW IT SIMPLY. One idea per sentence; name things a child can picture."),
        guidance=("Short sentences and a steady, read-aloud rhythm. Simple, concrete vocabulary "
                  "for the age band. Repetition and refrain are features here, not slop."),
        citation_style="none",
        metrics=("reading_grade", "sentence_variance", "dialogue", "cliche"),
        reading_grade=(1, 5),
        gold="children.md",
    ),
}

DEFAULT = "nonfiction"


def names() -> list[str]:
    return list(_REGISTERS)


def get(name: str | None) -> Register:
    """Resolve a register by name; unknown / None -> the default (never raises)."""
    if not name:
        return _REGISTERS[DEFAULT]
    return _REGISTERS.get(str(name).strip().lower().replace("_", "-"), _REGISTERS[DEFAULT])


# ── inference from a project's genre/mode (so existing flows pick a sane register) ──
_FICTION_HINTS = ("novel", "fiction", "story", "fantasy", "sci-fi", "science fiction",
                  "thriller", "romance", "mystery", "horror", "literary", "saga", "tale")
_GENRE_FICTION_HINTS = ("thriller", "romance", "mystery", "sci-fi", "science fiction",
                        "fantasy", "horror", "adventure", "crime")


def infer(genre: str = "", mode: str = "article", explicit: str | None = None) -> str:
    """Pick a register name from an explicit setting, else from the project's genre/mode.

    Explicit wins. Otherwise map the free-text genre to the closest profile; an article
    defaults to `nonfiction`, a book to `nonfiction` unless its genre reads as fiction.
    """
    if explicit:
        r = get(explicit)
        return r.name
    g = (genre or "").lower()
    if any(h in g for h in ("poem", "poetry", "verse")):
        return "poetry"
    if any(h in g for h in ("screenplay", "script", "teleplay", "stage play", "film")):
        return "screenplay"
    if any(h in g for h in ("children", "picture book", "early reader", "kids")):
        return "children"
    if any(h in g for h in ("academic", "thesis", "dissertation", "scholarly", "journal paper")):
        return "academic"
    if any(h in g for h in ("news", "report", "journalis", "feature story")):
        return "journalism"
    if any(h in g for h in ("marketing", "advert", "copywrit", "sales", "landing page")):
        return "copywriting"
    if any(h in g for h in ("memo", "business", "executive", "whitepaper", "white paper")):
        return "business"
    if any(h in g for h in ("documentation", "technical", "engineering", "how-to", "tutorial")):
        return "technical"
    if any(h in g for h in _GENRE_FICTION_HINTS):
        return "genre-fiction"
    if any(h in g for h in _FICTION_HINTS):
        return "literary-fiction"
    return DEFAULT


# ── gold corpus (default style anchor, injected like voice exemplars) ─────────────
def gold_exemplars(name: str | None, max_chars: int = 1200) -> str | None:
    """Shipped, genre-tagged exemplar prose for a register - a default 'match this'
    target so a weak model has a concrete style anchor even when the user supplied no
    voice files. Returns None when the register has no gold file or it is missing."""
    reg = get(name)
    if not reg.gold:
        return None
    path = _GOLD / reg.gold
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    # Same shape as brain.voice_exemplars: leading prose paragraphs under a budget,
    # skipping headings and fences.
    import re as _re
    chunks: list[str] = []
    total = 0
    for para in _re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para or para.startswith("#") or para.startswith("```") or para.startswith(">"):
            continue
        if total + len(para) > max_chars:
            break
        chunks.append(para)
        total += len(para)
    return "\n\n".join(chunks) or None
