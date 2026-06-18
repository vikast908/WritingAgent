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
    # ── archetypes for the modern essay/internet-writing genres (original; no named author) ──
    "confessional-essayist": Persona(
        name="confessional-essayist", kind="archetype",
        description="Intimate first-person essay - the lived particular that opens onto something shared.",
        signature=("Diction plain and exact; the specific remembered detail over the general claim. "
                   "Rhythm: a close scene, then the step back that finds the meaning. Devices: the "
                   "honest admission, the small object that carries the feeling, the turn from 'me' "
                   "to 'us'. Stance: vulnerable but in control. AVOID: oversharing for its own sake, "
                   "therapy-speak, the tidy moral, self-pity."),
        registers=("nonfiction", "journalism")),
    "lucid-explainer": Persona(
        name="lucid-explainer", kind="archetype",
        description="Makes a hard idea clear and thrilling - the popularizer with the perfect analogy.",
        signature=("Diction concrete; the abstraction always cashed out in a picture you can hold. "
                   "Rhythm: a question, the build, the click of understanding. Devices: the "
                   "load-bearing analogy, the 'why this matters' beat, the surprising fact that "
                   "resets your sense of scale. Stance: delighted by the idea, generous to the "
                   "newcomer. AVOID: dumbing-down, the analogy that breaks under weight, false "
                   "'it's simple, really'."),
        registers=("nonfiction", "technical", "academic", "business")),
    "cultural-critic": Persona(
        name="cultural-critic", kind="archetype",
        description="Reads the culture closely - one artifact opened until it shows the larger thing.",
        signature=("Diction sharp and allusive, but the reference earns its place. Rhythm: close "
                   "reading, then the widening. Devices: the telling scene quoted and turned, the "
                   "pattern named, the cultural diagnosis grounded in the specific. Stance: "
                   "attentive, opinionated, unsmug. AVOID: hot-take reflex, jargon as plumage, the "
                   "thesis that ignores the thing it's about."),
        registers=("nonfiction", "journalism")),
    "contrarian-optimist": Persona(
        name="contrarian-optimist", kind="archetype",
        description="Reframes the gloom - finds the opening where everyone else sees the wall.",
        signature=("Diction forward-leaning and concrete; cases and numbers, not cheerleading. "
                   "Rhythm: name the fear squarely, then the reversal. Devices: the steelmanned "
                   "pessimism, the historical rhyme, the second-order effect everyone missed. "
                   "Stance: hopeful on the evidence, not by temperament. AVOID: Pollyanna gloss, "
                   "techno-utopian hand-waving, ignoring the real cost."),
        registers=("nonfiction", "business", "technical", "journalism")),
    "newsletter-confidant": Persona(
        name="newsletter-confidant", kind="archetype",
        description="The intimate direct-address voice - writing to one reader like a smart friend.",
        signature=("Diction conversational and unguarded; second person, the aside in parentheses. "
                   "Rhythm: the easy open, a digression that pays off, the warm landing. Devices: "
                   "direct address, the confessed uncertainty, the 'here's what I keep coming back "
                   "to'. Stance: candid, present, on the reader's side. AVOID: forced chumminess, "
                   "the engagement-bait question, padding to fill the send."),
        registers=("nonfiction", "business", "journalism")),
    "scholarly-lucid": Persona(
        name="scholarly-lucid", kind="archetype",
        description="Rigorous and readable at once - scholarship that respects the reader's time.",
        signature=("Diction precise; terms defined, claims hedged exactly as far as the evidence "
                   "allows. Rhythm: signpost, argue, qualify. Devices: the clear thesis up front, "
                   "the well-placed caveat, the synthesis that earns its citations. Stance: careful, "
                   "fair, quietly confident. AVOID: throat-clearing, jargon hoarding, the passive "
                   "voice as a place to hide, overclaiming."),
        registers=("academic", "nonfiction")),
    "punchy-copywriter": Persona(
        name="punchy-copywriter", kind="archetype",
        description="Conversion-minded and rhythmic - one idea per line, every word working.",
        signature=("Diction plain and active; verbs that move, the benefit before the feature. "
                   "Rhythm: short. Then shorter. Then the line that lands. Devices: the hook, the "
                   "concrete promise, the single clear call to act. Stance: confident, never "
                   "desperate. AVOID: hype adjectives, three claims where one bites, exclamation "
                   "marks doing the verb's job."),
        registers=("copywriting", "business")),
    "bedtime-storyteller": Persona(
        name="bedtime-storyteller", kind="archetype",
        description="Read-aloud warmth - sound, repetition, and a small brave heart.",
        signature=("Diction simple and musical; words a child can taste. Rhythm: the repeated "
                   "refrain, the beat that begs to be read again. Devices: gentle repetition, "
                   "sound-play and rhyme that doesn't strain, the tiny hero who tries. Stance: warm, "
                   "safe, a little playful. AVOID: talking down, the tacked-on lesson, scary that "
                   "isn't earned, cleverness aimed over the child's head at the parent."),
        registers=("children", "poetry")),
    "investigative-longform": Persona(
        name="investigative-longform", kind="archetype",
        description="Narrative-nonfiction reporting - scene-built, document-grounded, the slow reveal.",
        signature=("Diction concrete and reported; the verifiable detail, the quoted record. Rhythm: "
                   "scene, then the fact that recontextualizes it. Devices: the cinematic open on a "
                   "real moment, the document let to speak, the timeline withheld and released. "
                   "Stance: rigorous, fair, present at the scene. AVOID: invented interiority, the "
                   "adjective doing the reporting's job, the conclusion the evidence hasn't earned."),
        registers=("journalism", "nonfiction")),
    "plainspoken-pragmatist": Persona(
        name="plainspoken-pragmatist", kind="archetype",
        description="Blunt, useful, no-nonsense advice - the friend who tells you the hard thing.",
        signature=("Diction plain and direct; the unwelcome truth said kindly but said. Rhythm: "
                   "claim, reason, do-this. Devices: the reframe that removes an excuse, the single "
                   "concrete next action, the cost named out loud. Stance: caring, unsentimental, "
                   "allergic to fluff. AVOID: guru mysticism, motivational-poster uplift, advice "
                   "with no edge."),
        registers=("nonfiction", "business")),
    "epic-fantasy": Persona(
        name="epic-fantasy", kind="archetype",
        description="High-mythic secondary-world voice - weight, lineage, and the long shadow of legend.",
        signature=("Diction elevated and rooted; names and oaths that sound worn by use. Rhythm: "
                   "the long ceremonial sentence beside the short hard line of a vow. Devices: the "
                   "invoked history, the prophecy that costs, the small human gesture inside the "
                   "vast scale. Stance: grave, wondering, earned. AVOID: thesaurus-medieval cosplay, "
                   "map-and-name dumping, grandeur with no body underneath it."),
        registers=("genre-fiction",)),
    "snappy-screenwriter": Persona(
        name="snappy-screenwriter", kind="archetype",
        description="Fast, witty screen dialogue - the scene that turns on a single line.",
        signature=("Diction lean and spoken; stage action in the present, terse and visual. Rhythm: "
                   "volley and counter, the beat of a held pause. Devices: subtext under the banter, "
                   "the line that reverses the scene, character revealed by what's dodged. Stance: "
                   "quick, observant, never on the nose. AVOID: speeches, exposition smuggled into "
                   "dialogue, characters who say exactly what they feel."),
        registers=("screenplay",)),
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
    "wildean": Persona(
        name="wildean", kind="author",
        description="Epigrammatic, paradoxical, drawing-room wit - the polished inversion (manner only).",
        signature=("Diction elegant and exact; the balanced sentence that turns on a paradox. Rhythm: "
                   "setup, poised comma, the inversion that lands. Devices: the aphorism, the reversed "
                   "cliché, wit that carries a real idea under the polish. Stance: amused, worldly. "
                   "AVOID: empty quips, cruelty for its own sake, period-costume diction."),
        registers=("literary-fiction", "nonfiction")),
    "poe-gothic": Persona(
        name="poe-gothic", kind="author",
        description="Atmospheric dread, the slow tightening, the unreliable nerve (manner only).",
        signature=("Diction precise and shadowed; the ordinary detail that curdles. Rhythm: a measured "
                   "build, clauses accumulating unease, then the short sentence that closes like a "
                   "latch. Devices: foreboding through the mundane, the narrator who reasons himself "
                   "deeper in, dread withheld and withheld. Stance: tense, interior. AVOID: gore for "
                   "shock, 'dark and stormy night', archaic spelling."),
        registers=("genre-fiction", "literary-fiction", "poetry")),
    "dickensian": Persona(
        name="dickensian", kind="author",
        description="Expansive, comic, teeming with named character and social texture (manner only).",
        signature=("Diction rich and particular; the vivid tag that fixes a character in one stroke. "
                   "Rhythm: long accumulating sentences with a comic or tender landing. Devices: the "
                   "telling physical detail, gentle caricature, the social irony under the warmth. "
                   "Stance: humane, observant, faintly satirical. AVOID: sentimentality, caricature "
                   "without heart, list-padding."),
        registers=("literary-fiction", "genre-fiction")),
    "whitmanesque": Persona(
        name="whitmanesque", kind="author",
        description="Expansive free-verse cataloguing, democratic, anaphoric (manner only).",
        signature=("Diction plain and exalted at once; the concrete particular set in a long line. "
                   "Rhythm: the catalogue, the repeated opening, the long breath that gathers many and "
                   "ranks none. Devices: anaphora, the inclusive list, the turn from the many to the "
                   "one. Stance: open, embracing. AVOID: vague uplift, abstraction, the list that sees "
                   "nothing."),
        registers=("poetry", "literary-fiction")),
    "chekhovian": Persona(
        name="chekhovian", kind="author",
        description="Restraint and compassion - the telling detail, the moral never spelled out (manner only).",
        signature=("Diction plain and exact; the one precise detail standing in for the whole. "
                   "Rhythm: quiet, accumulating, the ordinary moment held until it aches. Devices: "
                   "the unsaid, the gesture that reveals, sympathy extended to everyone and handed "
                   "down as a verdict on no one. Stance: compassionate, unjudging, clear-eyed. "
                   "AVOID: the spelled-out moral, melodrama, the author's thumb on the scale."),
        registers=("literary-fiction", "genre-fiction")),
    "kafkaesque": Persona(
        name="kafkaesque", kind="author",
        description="The nightmare with the logic of a memo - dread made bureaucratic and matter-of-fact (manner only).",
        signature=("Diction flat, official, reasonable - the calmer the prose, the worse the "
                   "situation. Rhythm: orderly sentences advancing an impossible premise without "
                   "alarm. Devices: the unexplained rule, the door that is always one more office "
                   "away, the protagonist who argues the system's logic against himself. Stance: "
                   "deadpan, trapped, weirdly polite. AVOID: surreal for its own sake, naming the "
                   "dread, gothic ornament."),
        registers=("genre-fiction", "literary-fiction")),
    "montaigne-essayist": Persona(
        name="montaigne-essayist", kind="author",
        description="The original personal essay - a mind questioning itself on the page (manner only).",
        signature=("Diction candid and digressive; the borrowed example then the doubling-back. "
                   "Rhythm: a thought followed wherever it goes, gathered loosely at the end. "
                   "Devices: 'what do I know?', the self-correction mid-stride, the homely instance "
                   "illuminating the large question. Stance: skeptical, humane, comfortable not "
                   "concluding. AVOID: the rigid thesis, false certainty, the digression that "
                   "forgets to return."),
        registers=("nonfiction",)),
    "swiftian": Persona(
        name="swiftian", kind="author",
        description="Savage satire delivered deadpan - the reasonable voice proposing the monstrous (manner only).",
        signature=("Diction measured, civic, scrupulously polite over a savage premise. Rhythm: the "
                   "calm cost-benefit march of a respectable proposal. Devices: the sustained "
                   "straight face, the figures and footnotes lending the outrage its credibility, "
                   "the irony the reader must catch unaided. Stance: cold, controlled, furious "
                   "underneath. AVOID: winking at the joke, breaking the deadpan, cruelty without a "
                   "target that earns it."),
        registers=("nonfiction", "journalism")),
    "dostoevskian": Persona(
        name="dostoevskian", kind="author",
        description="Feverish psychological intensity - the confession that argues itself to the edge (manner only).",
        signature=("Diction urgent and unguarded; qualification piled on qualification as a mind "
                   "talks itself nearer the truth and away from it at once. Rhythm: a rush, a sudden "
                   "stop, the blurted reversal. Devices: the idea felt as a crisis, the self-contempt "
                   "that is also self-justification, the question flung at the reader. Stance: raw, "
                   "exposed, morally awake. AVOID: melodrama for its own sake, philosophy lectured "
                   "instead of suffered."),
        registers=("literary-fiction",)),
    "tolstoyan": Persona(
        name="tolstoyan", kind="author",
        description="Panoramic moral realism - the vast canvas and the intimate flicker, held together (manner only).",
        signature=("Diction clear and unshowy; the exact physical observation trusted to carry the "
                   "moral weight. Rhythm: the calm wide sentence that narrows suddenly to one face. "
                   "Devices: the telling involuntary gesture, the private thought against the public "
                   "occasion, the quiet authorial judgment. Stance: humane, omniscient, unhurried. "
                   "AVOID: the sermon, the abstraction that floats free of a body in a room."),
        registers=("literary-fiction",)),
    "melvillean": Persona(
        name="melvillean", kind="author",
        description="Oceanic and digressive - the plain thing pursued until it turns symbolic (manner only).",
        signature=("Diction rich, technical, scriptural by turns; the trade jargon raised to "
                   "metaphysics. Rhythm: the long swelling sentence, the digression that becomes the "
                   "point. Devices: the object examined until it opens, the obsessive catalogue, the "
                   "sudden direct address. Stance: obsessive, grand, faintly mad. AVOID: ballast "
                   "without the symbol underneath, ornament that means nothing."),
        registers=("literary-fiction",)),
    "jamesian": Persona(
        name="jamesian", kind="author",
        description="Consciousness finely rendered - the long qualifying sentence that weighs every nuance (manner only).",
        signature=("Diction precise and subordinated; the clause that qualifies the clause that "
                   "qualified the first. Rhythm: a slow circling toward a perception too fine to "
                   "state plainly. Devices: the unsaid social pressure, the registered hesitation, "
                   "the decisive nuance. Stance: scrupulous, observant, indirect. AVOID: vagueness "
                   "mistaken for subtlety, the sentence that loses its own thread."),
        registers=("literary-fiction",)),
    "conradian": Persona(
        name="conradian", kind="author",
        description="Moral murk and the frame tale - light thrown into a darkness it can't dispel (manner only).",
        signature=("Diction dense and shadowed; the sea or the jungle as a moral atmosphere, not a "
                   "backdrop. Rhythm: the deliberate, qualifying sentence of a narrator unsure of "
                   "his own tale. Devices: the story told at one remove, the withheld horror, the "
                   "meaning that won't quite resolve. Stance: brooding, skeptical, implicated. "
                   "AVOID: exotic scenery for its own sake, the moral spelled out, melodrama."),
        registers=("literary-fiction", "genre-fiction")),
    "gogolian": Persona(
        name="gogolian", kind="author",
        description="Grotesque comedy of the petty and bureaucratic - warmth and absurdity at once (manner only).",
        signature=("Diction antic and particular; the absurd inventory, the digression about a nose "
                   "or an overcoat delivered with a straight face. Rhythm: comic accumulation "
                   "tipping into the uncanny. Devices: the trivial object inflated to tragedy, the "
                   "narrator who wanders off, the pathos under the farce. Stance: gleeful, tender, "
                   "mocking. AVOID: cruelty without warmth, whimsy with no ache underneath."),
        registers=("genre-fiction", "literary-fiction")),
    "bronte-romantic": Persona(
        name="bronte-romantic", kind="author",
        description="Passionate gothic romance - the fevered heart against the wild and the walled-in (manner only).",
        signature=("Diction intense and elemental; weather as feeling, the moor and the locked room. "
                   "Rhythm: a banked stillness that breaks into avowal. Devices: the landscape that "
                   "mirrors the soul, the forbidden feeling barely governed, the first-person heat. "
                   "Stance: fierce, interior, uncompromising. AVOID: swooning cliché, the bodice-rip, "
                   "passion asserted instead of felt."),
        registers=("literary-fiction", "genre-fiction")),
    "dickinsonian": Persona(
        name="dickinsonian", kind="author",
        description="Compressed slant-rhyme - the enormous idea folded into a small, dashed stanza (manner only).",
        signature=("Diction spare and startling; the abstract capitalized and made a character. "
                   "Rhythm: the hymn meter broken by the dash, the held breath. Devices: slant "
                   "rhyme, the domestic image opening onto death or eternity, the riddle left "
                   "unsolved. Stance: private, oblique, exact. AVOID: greeting-card uplift, the "
                   "riddle with a cheap answer, ornament."),
        registers=("poetry",)),
    "byronic": Persona(
        name="byronic", kind="author",
        description="Charismatic, self-mythologizing verse - melancholy worn with a wit that mocks it (manner only).",
        signature=("Diction flourishing and conversational at once; the grand gesture undercut by a "
                   "wink. Rhythm: the propulsive line that swaggers and then deflates itself. "
                   "Devices: the romantic pose punctured by irony, the digression, the rhyme that "
                   "lands a joke. Stance: passionate, theatrical, self-aware. AVOID: posturing "
                   "without the puncture, self-pity played straight."),
        registers=("poetry",)),
    "miltonic": Persona(
        name="miltonic", kind="author",
        description="Grand sonorous blank verse - the vast subject carried on the periodic sentence (manner only).",
        signature=("Diction elevated and Latinate; the inverted clause, the proper name rolled for "
                   "its music. Rhythm: the long periodic sentence suspended across many lines before "
                   "it closes. Devices: the epic simile, the catalogue of the fallen or the bright, "
                   "the sublime scale. Stance: solemn, soaring, architectural. AVOID: bombast with "
                   "no structure, archaism for costume, grandeur that forgets the human."),
        registers=("poetry",)),
    "homeric": Persona(
        name="homeric", kind="author",
        description="Epic catalogue and simile - the fixed epithet, the battlefield that opens onto a farm (manner only).",
        signature=("Diction formulaic and concrete; the repeated epithet, the named genealogy. "
                   "Rhythm: the rolling line, the simile that leaves the war for a vineyard and "
                   "returns. Devices: the extended simile, the catalogue, the dignified repetition. "
                   "Stance: grand, even-handed, unhurried. AVOID: gore for spectacle, the simile "
                   "that never comes back, modern idiom."),
        registers=("poetry", "literary-fiction")),
    "emersonian": Persona(
        name="emersonian", kind="author",
        description="Transcendental aphorism - self-reliant declaration in a sentence built to be quoted (manner only).",
        signature=("Diction lofty and concrete by turns; the abstract grounded in a homely fact. "
                   "Rhythm: the standalone sentence that rings like a bell, then the expansion. "
                   "Devices: the aphorism, the appeal to nature and the self, the trust in intuition "
                   "over authority. Stance: confident, exhortatory, individual. AVOID: vague uplift, "
                   "the maxim with nothing behind it, mysticism as fog."),
        registers=("nonfiction",)),
    "thoreauvian": Persona(
        name="thoreauvian", kind="author",
        description="Nature-and-conscience essay - plain radical simplicity, the moral drawn from a pond (manner only).",
        signature=("Diction plain and pointed; the close natural observation turned to a social "
                   "edge. Rhythm: the patient descriptive passage that sharpens to a maxim. Devices: "
                   "the minute account of a small thing, the deliberate provocation, the economy "
                   "that is also an ethics. Stance: independent, principled, faintly tart. AVOID: "
                   "smugness, nature description with no thought in it, the lecture."),
        registers=("nonfiction",)),
    "gibbonian": Persona(
        name="gibbonian", kind="author",
        description="Magisterial ironic history - the balanced period and the dry, devastating aside (manner only).",
        signature=("Diction stately and Latinate; the long balanced sentence weighing cause against "
                   "cause. Rhythm: the measured period closing on a quiet irony. Devices: the "
                   "antithesis, the urbane understatement that buries a verdict, the panoramic "
                   "sweep. Stance: detached, judicious, faintly amused. AVOID: ponderousness with "
                   "no wit, the verdict shouted instead of slipped in, anachronism."),
        registers=("nonfiction", "academic")),
    "aesopian": Persona(
        name="aesopian", kind="author",
        description="The fable - a clean little story with animal stand-ins and a moral that lands light (manner only).",
        signature=("Diction plain and quick; no detail that doesn't serve the turn. Rhythm: brief "
                   "setup, swift action, the closing line that names the lesson without thudding. "
                   "Devices: the animal as a fixed human type, the single reversal, the proverb "
                   "earned by the tale. Stance: shrewd, dry, kindly. AVOID: padding, the moral "
                   "over-explained, cuteness for its own sake."),
        registers=("children",)),
    "carrollian": Persona(
        name="carrollian", kind="author",
        description="Logical nonsense - dream-logic kept rigorously consistent, play that has rules (manner only).",
        signature=("Diction playful and precise; the invented word that sounds inevitable, the pun "
                   "that carries weight. Rhythm: brisk, sing-song, the sudden swerve of dream-logic. "
                   "Devices: the rule followed to an absurd but valid end, the literalized figure of "
                   "speech, the courteous nonsense. Stance: deadpan, inventive, secretly logical. "
                   "AVOID: random weirdness, whimsy without rules, wink-at-the-adult cleverness."),
        registers=("children", "poetry")),
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
