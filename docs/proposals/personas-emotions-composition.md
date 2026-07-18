# Proposal - Personas, Emotions, and Multi-Skill Composition

Status: **ADOPTED and built (v1)**, 2026-06-17 - see plan.md §23 and `compositor.py` /
`personas.py` / `emotions.py`. Originally a proposal for discussion (craft-engine design pass,
2026-06-16, branch `feat/craft-engine-all-tiers`). The owner approved "finish tiers, then
compositor; personas = archetypes + public-domain." All three verdicts below were implemented
as recommended: personas as register-gated voice bundles (46 shipped - initially 10; no living authors),
emotions as anti-cliché deny-lists + cues (NOT a symptom dictionary), and a precedence-cascade
compositor (the voice layer is wired; §23.6 lists what's deferred). This document is kept as the
design rationale; the build is on branch `feat/compositor-personas-emotions`.

---

## TL;DR verdict

| Idea | Verdict | Why |
|---|---|---|
| **Author personas** (Shakespeare.md, Nietzsche.md, "a voice with soul") | **Build - but reshaped.** | Worth it as *curated voice profiles that nudge manner*, reusing the voice-exemplar path we already have. NOT as "imitate famous author" costume, and NOT as a new parallel system. Ship public-domain + original **archetype** voices; gate by register; never impersonate living authors. |
| **emotions.md** (a description of each emotion) | **Reject the obvious version; build the inverse.** | A symptom dictionary ("fear = racing heart, sweaty palms") is a *cliché generator* - it makes prose *less* believable, not more. The valuable artifact is the opposite: per-emotion **anti-cliché lists + a craft technique** (subtext, restraint, objective correlative), most of which is already covered by show-don't-tell + the cliché detector. |
| **Plan B: use many skills at once** (persona + genre + emotion + craft skills stacked) | **Build a *compositor*, not a *stacker*.** | The honest finding: more layers ≠ better. A weak model given 8 simultaneous style instructions averages them into mush. The right design is a **precedence cascade** with single-select layers, a hard cap, and a conflict-resolution rule - its job is *selection*, not *accumulation*. |

**One-sentence synthesis:** these four things - register (genre), persona (voice), emotion
(affect), craft skills (technique) - are all *voice/constraint layers over the same draft*,
and the system already has three of them. The real work is not four new feature silos; it is
**one clean composition model** that decides how the layers stack, who wins a conflict, and
where to stop adding.

---

## The unifying insight (read this first)

The agent already has, today, three of the four layers the owner is describing - they're just
not named as a family:

1. **Voice exemplars** (`brain/voice/`, `/praise`): admired passages injected as "match this
   register." This is *exactly* what a persona is, minus curation. → **persona lives here.**
2. **Learned skills** (`skills/`, candidate→trusted, ablation duels): named techniques with
   when-to-apply / technique / anti-pattern, retrieved by relevance. → **craft skills already
   compose; emotion-as-technique belongs here.**
3. **Register / genre** (`registers.py`, new this branch): the contract - which rules apply,
   what's required, citation style, which deterministic metrics matter. → **the outermost layer.**

So "author skills," "emotions.md," and "multiple skills at once" are not three new systems.
They are: (1) **curating** layer #1, (2) **inverting** a bad idea into layer #2, and (3)
defining how all the layers **compose**. Building them as separate silos would create a fourth
and fifth overlapping voice mechanism and make the prompt a noisy junk-drawer. Don't.

---

## Plan A1 - Personas (author / "soul" voices)

### What to build
A **persona** = a named, reusable *voice profile*: a few exemplar paragraphs (the "match this"
target, same slot as voice exemplars) + a short **signature card** (diction level, sentence
rhythm, signature devices, stance/attitude, what it avoids). Shipped under
`personas/<name>.md`, selectable per project (`--persona hardboiled-minimalist`), and stacking
*one* persona onto the chosen register.

Two safe sources of personas:
- **Archetype voices** (recommended primary): "the wry skeptic," "the warm mentor," "the
  hard-boiled minimalist," "the lyrical maximalist," "the deadpan technical," "the firebrand
  essayist." These are original, reusable, legally clean, and *more useful* than impersonations
  because they're about manner, not a specific person's content.
- **Public-domain authors** (secondary, opt-in): Shakespeare, Nietzsche, Austen, Twain, the KJV
  cadence - their text is out of copyright, so curated excerpts can ship. Treat them as *manner
  nudges* ("aphoristic, declarative, contrarian" for Nietzsche), never as "produce Elizabethan
  English."

### Why reshaped, and the hard caveats (the honest part)
- **"Imitate a famous living author" is a landmine** - legal (their prose is copyrighted),
  ethical (style appropriation), and quality (the model spends capacity on costume, not
  substance). For modern/specific voices, the *correct* mechanism already exists: the user
  drops their own samples in `voice/` or hits `/praise`. We don't ship other people's voices.
- **Persona-as-costume is the failure mode.** A weak model told "write like Shakespeare"
  produces thee/thou cosplay, not Shakespearean quality. Personas must nudge *rhythm, stance,
  and device density* subtly; the signature card should explicitly say "do NOT pastiche archaic
  vocabulary or era-specific references." The win is *soul/consistency of voice*, which is what
  "Benny Thompson with soul" is really asking for - and archetypes deliver that better than
  impersonation.
- **Persona is subordinate to register.** "A Nietzschean API reference" is wrong. Each persona
  declares which registers it's compatible with; the compositor refuses or warns on a mismatch.
- **Persona ≠ content/era.** It controls *manner only*. The draft still argues the real thesis,
  cites the real sources, and lives in the present.

### Cost
Low-to-medium. ~80% reuses the voice-exemplar injection path + the craft metrics already built.
New: a `personas/` corpus, a signature-card format, a `--persona` selector, and register-
compatibility gating. **This is the cheapest of the three and the most fun for users.**

---

## Plan A2 - Emotions

### Reject the obvious version
A dictionary that describes each emotion by its physical symptoms ("anger = clenched jaw, hot
face; fear = racing heart, cold sweat") is the single most reliable way to *generate cliché*.
Those exact phrases are the most overused emotion-writing in existence. Feeding them to the
model - especially a weak one that already reaches for the nearest stock phrase - would make
the prose **less** believable and would fight directly against the anti-slop machinery and the
cliché detector we just built. **Do not build the symptom dictionary.**

### Build the inverse
The believable-emotion craft is the *opposite* of a symptom list. The useful artifact has three
parts, and two of them already exist:

1. **The technique (a craft skill, layer #2):** show emotion through specific, character-
   grounded, *fresh* detail and behavior; prefer subtext to statement; don't name the emotion;
   structure the emotional *turn* (trigger → suppression/leak → shift). This is the show-don't-
   tell surgical pass (Tier 2.5, already on the build list) plus one or two learned skills.
2. **Per-emotion anti-cliché lists (feeds the cliché detector + watch-list):** "for fear,
   FLAG: heart raced, palms sweaty, blood ran cold, time stood still." This is the genuinely
   new, genuinely useful piece - and it slots into machinery that already exists (`craft._CLICHES`,
   the learned watch-list). It's a *deny* list, not an *imitate* list.
3. **A per-unit emotional target (optional):** a single field on a scene/section - "this scene
   should land as *dread*, not stated" - injected as a one-line writer instruction and checked
   by the critic. Local, lightweight, scene-scoped. This is the only "new input" worth adding.

So: `emotions.md` becomes a **reference of what NOT to write per emotion + the one technique**,
not a glossary of what each emotion "is." Inverted, it's valuable; as proposed, it backfires.

### Cost
Low. Mostly content (anti-cliché lists) + one optional per-unit field + reuse of the show-don't-
tell pass and cliché detector. Highest risk if built the naive way; safe and cheap if inverted.

---

## Plan B - Multi-skill composition (the important one)

The owner's instinct ("use multiple skills at a time… genre and all") is right that the layers
should combine. The non-obvious truth is **how**, and where it breaks.

### The honest finding: more is worse past a small number
Concatenating persona + 2 genres + 4 emotions + 10 skills into one prompt does not produce
richer writing. It produces **mush**, because: (a) the instructions conflict (persona wants long
lyrical sentences; business register wants BLUF and short ones); (b) a weak model can't hold 8
simultaneous style constraints and averages them toward its mean; (c) the token cost crowds out
the actual content and source material. **The compositor's job is selection and conflict
resolution, not accumulation.**

### The model: a precedence cascade (outer = wins conflicts)

```
┌─ Register (genre contract) ─────────────── HARD. Sets rules: allowed/required devices,
│                                            citation style, format, which metrics gate.
│  ┌─ Field template (structure) ─────────── HARD-ish. Inverted pyramid / IMRaD / AIDA / BLUF.
│  │  ┌─ Persona (voice / manner) ────────── SOFT. Diction, rhythm, stance — fills the freedom
│  │  │                                       the register leaves open; cannot break its rules.
│  │  │  ┌─ Emotional target (per unit) ──── SOFT, LOCAL. Colors word choice + rhythm for THIS
│  │  │  │                                    scene/section only.
│  │  │  │  └─ Craft skills (techniques) ─── ADDITIVE, ≤3. Retrieved by relevance; already
│  │  │  │                                    efficacy-gated (candidate→trusted, duels).
```

**Conflict rule:** an inner layer may only fill degrees of freedom the outer layers leave open;
it may never violate an outer layer's hard constraint. Register hard-rules > field structure >
persona preference > emotional coloring > skill nudge. When a persona/emotion/skill would break
a register rule (e.g., persona wants em-dashes in a register that bans them), **the register
wins and the conflict is logged** to the run trace.

**Cardinality (this is the part that makes it work):**
- Register: **exactly 1.** You can't be two genres; a "literary thriller" is *one* hybrid
  register, not two stacked.
- Field template: **0 or 1.**
- Persona: **0 or 1.** You can't be two voices at once. A "blend" is a *new* persona, authored
  deliberately - not a runtime stack of two.
- Emotional target: **0 or 1 per unit** (can differ per scene/section).
- Craft skills: **0–3**, chosen by the existing relevance retrieval. This is the only genuinely
  "multi" layer, and it's already capped and validated.

So "use multiple skills at a time" resolves to: **one of each upper layer + up to three craft
skills**, assembled by a thin `compositor` that (1) selects, (2) resolves conflicts by
precedence, (3) enforces the cap, and (4) logs what it dropped. Validation is already in place:
the deterministic craft metrics + the critic judge the *result*, so a bad combination shows up
as low scores and gets revised - we don't have to predict every interaction up front.

### Cost
Medium. The cascade is a small assembly function; the layers mostly exist. The real work is the
**conflict-resolution + cardinality discipline** and surfacing it in the UI (`--register`,
`--persona`, `--emotion`, skills already automatic). The register layer being built now is the
top of this cascade, so it's the natural foundation.

---

## What's redundant or won't work (consolidated)

1. **A standalone persona system separate from voice exemplars + skills** - redundant; would be
   the 4th overlapping voice mechanism. Unify into the existing voice slot.
2. **A literal emotion symptom dictionary** - actively harmful; it's a cliché engine that fights
   the anti-slop core. Invert it to anti-cliché + technique.
3. **Impersonating living/copyrighted authors** - legal + ethical + quality failure. Public-
   domain + original archetypes + the user's own praised corpus only.
4. **Stacking many skills/personas/genres simultaneously** - degrades output, especially on a
   basic model. Single-select upper layers; cap skills at ~3; the compositor *selects*.
5. **Two personas or two genres at once** - incoherent. A blend is a new single profile, not a
   runtime stack.
6. **Persona over technical/business/academic registers** - usually wrong; gate by compatibility.
7. **Trusting any of this to "just work" on a weak model via instructions** - the same lesson as
   the rest of the craft engine: personas need *exemplars to imitate* (not adjectives), emotions
   need *deny-lists + a surgical pass* (not a glossary), and composition needs *deterministic
   validation* (the craft metrics), because a basic model executes demonstrations and checks far
   better than it follows abstract layered instructions.

---

## How this meshes with the in-flight work, and recommended sequencing

The `registers.py` layer just built is **the top of the Plan B cascade**. That's lucky: it means
the composition model isn't a rewrite, it's a generalization. Recommended order:

1. **Finish the current tiers** (register threading, exemplars, surgical passes incl. show-don't-
   tell, craft metrics wiring, fields, citation styles). These are the *layers* the compositor
   will assemble - and show-don't-tell + cliché detection are the backbone of believable emotion.
2. **Add the thin `compositor`** (Plan B): one function that assembles register + field + persona
   + emotion + skills with precedence, cap, and conflict logging. Small, once the layers exist.
3. **Add personas** (Plan A1) as curated voice bundles in the voice slot + register gating.
4. **Add inverted emotions** (Plan A2): anti-cliché lists into the cliché detector/watch-list +
   an optional per-unit emotional target field.

Net: ~one new small module (`compositor`) + two content corpora (`personas/`, emotion anti-
cliché lists) + one optional schema field. No silos, no parallel voice systems, no symptom
dictionary.

---

## Open decisions for the owner

1. **Personas: archetypes-first (recommended) or public-domain-authors-first?** Archetypes are
   safer, more reusable, and avoid cosplay; public-domain authors are more marketable but riskier
   on quality. (Living authors are off the table either way.)
2. **Emotional target as a per-unit field** - worth the extra input, or rely on the show-don't-
   tell pass + thesis/tone alone?
3. **Should I generalize `registers` into the `compositor` now**, or keep registers focused and
   add the compositor as a separate layer after the tiers land? (I lean: keep registers focused;
   add compositor after - less churn, and the cascade is cleaner as its own seam.)
