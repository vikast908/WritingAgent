# Writing Agent - Product Requirements Document

> **Status:** living doc · **Type:** open-source project (success = installs, activation,
> retention, contributors, word-of-mouth - not revenue) · **Owner:** @vikast908
> Companion docs: `README.md` (the pitch), `plan.md` (the engineering spec), `CHANGELOG.md`.

## 1. One-line product definition (the spearhead)

**The autonomous long-form writer that argues a thesis and cites real sources - not slop.**
You give it a topic; it researches, drafts, critiques itself, verifies its citations, strips AI
tells, and hands you a finished, exported article (or book) - local-first, on your own model key,
for cents.

Lead with **articles** (fast, cheap, shareable, large audience); books are the "it also does that."

**As of this session the writer is also a *great writer across many fields*, not just argumentative
nonfiction** - and on a *basic* model, not only a frontier one. A register-parameterized **craft
engine** (plan §22) + a **compositor** (plan §23) move craft from zero-shot instructions the model
must be clever enough to obey to *demonstrations it imitates and deterministic checks it can't escape*,
selectable by genre: eleven registers (technical, literary/genre fiction, academic, journalism, copy,
business, poetry, screenplay, children, …), forty-six personas (manner), and emotion as anti-cliché craft.
The historical "researcher voice" nonfiction default is preserved **byte-for-byte**.

## 2. The problem

Generic AI writing is **fluent slop**: confident, samey, structurally identical, often unsourced or
fabricated. For people who *publish* long-form, that's not a finished product - it's a first draft
they must fact-check, de-cliché, and give a point of view. The pain is **frequent** (every piece),
**real** (reputation + time), and **rising** (readers increasingly recognize and discount AI prose).

The unmet need: **"draft me something publication-ready that has a defensible take and real
sources, without me babysitting the model."**

## 3. Target users

| Persona | Who | Why it's (near) must-have | Notes |
|---|---|---|---|
| **P1 - Burned technical long-form creator** | DevRel, technical-content writers, indie hackers, solo founders/consultants who publish explainers + thought-leadership *regularly* | Sick of slop; values a *take*; comfortable in a terminal + an API key; doesn't blink at ~$0.25/article | **The bullseye.** |
| **P2 - Developer-integrator** | Builds a product/pipeline and embeds generation via the `Agent`/`Project` Python API | Stable, scriptable, local-first generation primitive | Smallest, stickiest. |
| **P3 - Technical novelist / self-publisher** | Drafts books with canon/continuity tracking | Continuity audits + production layer | Smaller, taste-driven; book quality least-proven. |

### Non-users / poor fit (say so explicitly)
- **Non-technical writers** wanting a polished web GUI - the terminal + API-key + Python/Node setup is a wall.
- **Teams** needing collaboration, review queues, shared accounts (single-user, local-first).
- **Short-form** needs - tweets, emails, ad copy, SEO snippets (Jasper/Copy.ai own this; the pipeline is overkill).
- **Hosted-SaaS / compliance** seekers (no hosted option, SSO, SOC2).
- **Sentence-level co-writers** who want to steer every line (this is autonomous-first).

## 4. Jobs To Be Done & top use cases

**Core JTBD:** *"Turn a topic into a publication-ready, non-generic, sourced long-form piece I'd be
willing to put my name on - in one command, without supervising it."*

Top use cases (highest value first):
1. **Technical blog post / explainer** with real citations and diagrams. *(Primary wedge.)*
2. **Thought-leadership / opinion article** that takes a contestable position.
3. **Embed generation** in another app via the Python API.
4. **Book / novel draft** with continuity + front/back matter.
5. **Re-fix an existing piece** for free (`polish`) - clean references, citations, figures.

Essential actions: `write` (one-shot) / `new → run → export`; the live dashboard; `evidence`.
Optional/power: themes, `revise`, `tableread`, `eval`, `praise`, model routing, deep research.

## 5. Value proposition & differentiation

**Core value:** not "AI writes," but **"AI writes something with a point of view and real evidence,
and self-corrects until it isn't slop"** - and you own the data and the spend.

| Differentiator | What it is | Who else has it |
|---|---|---|
| **Anti-slop machinery** | Per-piece *thesis* the critic enforces, a side-by-side *judge*, an *insight gate*, a surgical *humanizer* | Rare - ChatGPT/Claude don't self-critique; Jasper/Sudowrite don't enforce a thesis; STORM is neutral/encyclopedic |
| **A great writer across many fields - on a basic model** | A register-parameterized **craft engine** (plan §22): the anti-slop/craft contract as *data*, with **11 genre profiles** (nonfiction default, technical, literary-fiction, genre-fiction, academic, journalism, copywriting, business, poetry, screenplay, children) that invert the rules per register (fiction keeps the em-dash; academic *requires* hedging; copy keeps the exclamation). It runs well on a *weak* model because craft moves out of zero-shot prompts and into **few-shot exemplars**, a shipped **genre gold corpus** as a default style anchor, and **genre-aware deterministic craft metrics** the model can't argue with. Plus surgical show-don't-tell / passive→active passes, voice-drift stylometry, and per-field structural templates + 7 citation styles. | No OSS long-form writer parameterizes its anti-slop contract by genre or compensates for a basic model with exemplars + a gold corpus + deterministic metrics; ChatGPT/Claude are monovocal per prompt |
| **Composable voice - persona, emotion, register, all selected (not stacked)** | A **compositor** (plan §23): one precedence cascade `register ⊃ field ⊃ persona ⊃ emotion ⊃ skills` that *selects + resolves conflicts and logs why*, never accumulates (more layers is worse on a weak model). **46 personas** (18 archetypes + 28 public-domain *manners* - e.g. Shakespearean, Nietzschean, Austen-ironic, Chekhovian, Kafkaesque, Dostoevskian, Tolstoyan; **no living authors**, original-pastiche exemplars, register-gated and dropped-with-a-log on mismatch). **Emotion as anti-cliché** - deny-lists wired into the cliché detector + show-don't-name cues, *not* a symptom dictionary (which only generates clichés). | Sudowrite has style tools but no register-gated conflict resolution; nobody else treats emotion as a deterministic anti-cliché deny-list |
| **Self-directing *and* self-improving** | Opt-in **agentic controller** (plan §21): instead of a fixed order, an agent *chooses its next move* - gather research / read canon / draft / re-outline / revise / consolidate / repair / table-read / produce / learn / escalate - and the writer can call tools (research, canon lookup, fact-verify) *mid-draft*. A **learned policy**, distilled from the agent's own action trace, improves the choices with use. The fixed pipeline remains the safety floor (default-off). | Few OSS writers are self-directing; fewer pair it with a self-improving loop *and* a deterministic fallback |
| **Claim↔source verification** | Cited claims checked against the actual source; unsupported = blocking; opt-in **multi-agent panels** (majority-vote fact-check, diverse-lens critique) | Almost no one |
| **Evidence report** | A shareable artifact: thesis + every source ranked by influence (0–100) | Unique |
| **Autonomy → finished file** | One command → researched, written, self-edited, exported, resumable | Few do end-to-end-to-file |
| **Local-first + BYO model** | Plain markdown on disk; your OpenRouter/DeepSeek key; cost guardrails | OSS-aligned; SaaS rivals can't match |

## 6. Scope

**In scope (now):** long-form articles + books; research (shallow + deep); the quality machinery;
6 export formats; diagrams; TUI + CLI + npm launcher + Python API + a **local web dashboard**; the
markdown brain + learning loop; a register-parameterized **craft engine** (11 genre profiles +
persona/emotion **compositor**) that makes the writer good across many fields on a basic model, with
the nonfiction default unchanged byte-for-byte; an opt-in self-directing (agentic) controller atop
the fixed pipeline - a run-level macro-action controller, in-generation tool use, a learned
(trace-distilled) policy, and multi-agent panels, all default-off and bounded by call-caps + a token
budget; a **local distribution layer** - a deterministic on-page **SEO** audit + keyword pack, and
**promote/repurpose/restyle** (platform variants, headline variants, voice restyle). The SEO and
promote layers write **local artifacts only** - they never post or schedule to any platform.

**Out of scope (deliberate):** short-form/marketing copy as the *product*; real-time collaboration;
a hosted/multi-user SaaS (the shipped web dashboard is **local-only**, `127.0.0.1`, single-user);
auto-posting or scheduling to social/CMS platforms; non-text media.

**Watch (scope risk):** "books + articles + diagrams + themes + API + 11 genres + personas" dilutes the
one-line pitch. Resolution: **lead with articles** (technical long-form is still the bullseye); present
the craft engine / compositor as *depth* (better prose in any field on a basic model), not a new
audience - and keep the nonfiction default byte-for-byte so the wedge persona sees zero behavior change.

## 7. Success metrics (open-source)

- **Activation (north star):** install → **first finished piece** conversion. Instrument; expect the
  biggest drop at "get an API key."
- **Try-without-install:** demo runs (Colab/HF Space) per week.
- **Retention:** % of installers who generate ≥3 pieces in 30 days.
- **Virality:** shares of generated artifacts + evidence reports; GitHub stars/forks trend.
- **Contribution:** external PRs; good-first-issues closed.
- **Quality proof:** blind-A/B win-rate vs ChatGPT long-form (target: clearly >50%).
- **Craft-engine proof (basic-model claim):** the deterministic craft metrics (`craft.py`) improve
  register-over-register with the engine on, *and* a register/persona run on a **basic** model reads as
  on-genre to blind readers - i.e. the engine earns the "great writer across many fields, on a basic
  model" claim rather than merely being told. Measure per register vs the nonfiction baseline.
- **Agentic efficacy (when opt-in):** does the self-directing controller *beat its own fixed pipeline*?
  Measure first-pass rate, insight-gate pass rate, and cost/latency for `agentic` runs vs `default`,
  at equal token budget - the agentic mode has to *earn* its caps. Learned-policy uplift only becomes
  measurable once the action-trace corpus is large enough to bite (see roadmap/Next).

## 8. Roadmap

### Now (shipped this session)
- **Local web dashboard** (`writing-agent web`, plan §25): a browser UI over the same engine the
  TUI drives - pure-stdlib `ThreadingHTTPServer` + SSE + a single-page app (`src/writingagent/webui/`),
  binding `127.0.0.1` only with no auth and running one job at a time. Studio / Live run / Projects /
  Project (Overview · Activity · Evals · Artifacts · Rejected · Export · Cost) / Telemetry / Skills /
  Settings; export in all six formats + a restyle "Rewrite". **This is the local-GUI answer to the
  terminal-only ceiling - it is not a hosted SaaS** (still local-first, single-user).
- **Distribution layer - SEO + promote/repurpose/restyle** (plan §24): the pipeline no longer stops
  at "manuscript on disk". `seo.py` runs a **deterministic on-page audit** (title/meta lengths,
  keyword placement + density, heading hierarchy, word-count floor, reading grade, link/image-alt
  hygiene) plus a one-call flash **keyword pack**; the keyword is threaded into the writer up front
  (`seo_keyword`) and the title optimized after validation (`seo_report.md`). `promote.py` produces
  platform-native variants (`x-thread`, `linkedin`, `newsletter-teaser`, `tldr`), 5 headline
  variants, and a voice **restyle** (register / persona / emotion). Runs automatically after a
  finished `write` (`auto_promote`, default on) or on demand (`writing-agent seo` / `promote`).
  **Local artifacts only - it edits the piece and names keywords/hashtags, but never posts or
  schedules anywhere.**
- **Cost - budget mode** (plan §19): `cost_mode: budget` (the shipped default) pins the spend-heavy
  knobs lean, routes the judgment nodes (critic/judge/verifier/consolidation/diagram) to the flash
  tier, and auto-scales the run token budget by unit count (`budget_tokens_per_unit`, ~20k/unit +
  overhead) so a full piece *finishes* rather than pausing - targeting **≤100k tokens/article**.
  `max_run_tokens` is a hard ceiling that always wins. Per-node / per-unit telemetry attribution
  feeds the dashboard Telemetry / Cost views. **Context-compression "headroom" was removed** (it
  saved ~nothing single-turn and hurt the DeepSeek prompt-cache hit rate); prompt-cache pinning
  (`openrouter_providers`) + budget mode are the cost story now.
- **Craft engine - a great writer across many fields, on a basic model** (plan §22, branch
  `feat/craft-engine-all-tiers`): the pipeline guaranteed a *floor* (no slop) and an argument *ceiling*
  (thesis, counterargument) but its craft contract was **monovocal** - one "researcher voice" baked
  into every prompt - and the rest of craft lived *inside the model*, reached by zero-shot instructions
  that only a clever model obeys. This layer moves craft to *demonstrations the model imitates +
  deterministic checks it can't escape, parameterized by register*. What shipped:
  - **Registers as data** (`registers.py`): the anti-slop/craft contract is now a `Register` profile,
    not hard-code. **11 ship** - `nonfiction` (default), `technical`, `literary-fiction`,
    `genre-fiction`, `academic`, `journalism`, `copywriting`, `business`, `poetry`, `screenplay`,
    `children`. Each says which bans apply, which **invert** (fiction *keeps* em-dashes; academic
    *requires* hedging + keeps "moreover"; copy *keeps* the exclamation), plus voice/rhythm/diction,
    reading-grade target, and which craft metrics matter.
  - **Built to run on a *basic* model** (the point), three compensations for weak zero-shot craft:
    (a) **few-shot exemplars** (`exemplars.py`) - humanizer before/after pairs + critic 5-vs-2 score
    anchors (weak models imitate; they don't follow abstractions); (b) a shipped **genre gold corpus**
    (`gold/*.md`) injected as the *default* style anchor (a weak model imitating a strong paragraph
    beats one told to "write vivid prose"); (c) **genre-aware deterministic craft metrics** (`craft.py`)
    - sentence-rhythm variance, passive/adverb density, Flesch-Kincaid, cliché hits, opening/closing
    weakness, and for fiction filter-verb density / dialogue ratio / said-bookisms / POV-tense / sensory
    density - computed as model-independent evidence to the critic.
  - **Tier 2 surgical craft passes** (`surgery.py`): generalize the humanizer's detect → rewrite-only-
    the-flaw → **guard** → splice pattern to **show-don't-tell** (filter verbs + told emotion → image)
    and **passive→active**, so approved prose is never regenerated end-to-end and a micro-edit can't
    drift facts. Plus an opening/closing detector and a deterministic **voice-drift stylometry** report.
  - **Tier 3 field templates + citation styles** (`fields.py`): a structural grammar injected into the
    outline architect - inverted-pyramid / IMRaD / AIDA-PAS / BLUF / how-to / three-act / screenplay -
    and 7 citation conventions (`influence` default · `numeric` · `apa` · `mla` · `chicago` · `ap` ·
    `none`).
  - **Settings:** `register`, `field`, `citation_style`, `craft_passes` (all clamped/tunable).
  - **Invariant:** `register=None` / the `nonfiction` profile reproduce the historical nonfiction
    behavior **byte-for-byte** (asserted by test), so every pre-existing run is unchanged.
- **Compositor - composable voice without mush** (plan §23, branch
  `feat/compositor-personas-emotions`): builds the §22.6 deferral. The insight: register (rules+voice),
  persona (manner), emotion (affect), and skills (technique) are all *voice/constraint layers over one
  draft* - so it's **one composition model**, not three feature silos - and the honest constraint is
  that *more layers is worse, not better* (a weak model given several voices at once averages them into
  mush). The compositor's job is therefore **selection + conflict resolution, never accumulation**.
  What shipped:
  - **The cascade** (`compositor.py`): `register ⊃ field ⊃ persona ⊃ emotion ⊃ skills`. Outer layers
    win; upper layers are **single-select** (only skills are multi, already capped + efficacy-gated).
    One place decides what's selected, what's dropped, and **logs why** - it never silently concatenates.
  - **Personas** (`personas.py` + `personas/*.md`): a **manner** layer (diction, rhythm, device-density)
    *within* the register's rules. **46 ship** - 18 archetypes (`wry-skeptic`, `warm-mentor`,
    `hard-boiled-minimalist`, `lyrical-maximalist`, `deadpan-technical`, `firebrand-essayist`,
    `lucid-explainer`, `cultural-critic`, `investigative-longform`, `epic-fantasy`, and more) + 28
    public-domain *manners* (`shakespearean`, `nietzschean`, `austen-ironic`, `twain-vernacular`,
    `wildean`, `poe-gothic`, `dickensian`, `whitmanesque`, `chekhovian`, `kafkaesque`, `dostoevskian`,
    `tolstoyan`, `melvillean`, `gogolian`, and more).
    **Hard boundaries:** manner only, **no living/in-copyright authors**, exemplars are **original
    pastiche** (zero copyright surface). A persona incompatible with the register is **dropped and
    logged** - the register wins.
  - **Emotions** (`emotions.py`, anti-dictionary): a symptom dictionary ("fear = racing heart") is a
    *cliché generator* and was rejected; the inverse ships - per-emotion **anti-cliché deny-lists** wired
    into the `craft.py` cliché detector (deterministic, model-independent) + a show-don't-name **cue**.
    Believable emotion is carried by the deny-list + the show-don't-tell pass, not a glossary.
  - **The voice layer:** `compositor.voice()` resolves the writer's single "match this" anchor by
    precedence - **compatible persona > user voice (`/praise`) > register gold** - then appends the
    emotion cue, replacing the bare style-exemplar call at every writer site. One slot, no new node
    params.
  - **Settings:** `persona`, `emotion` (both ""=none, clamped against the known sets).
  - **Suite (current):** 524 passed / 1 skipped, ruff clean, cross-platform Python 3.10–3.13.
- **Self-directing (agentic) controller - opt-in** (`agentic`, plan §21): the system is now optionally
  an *agent that chooses its next move*, not only a fixed pipeline with quality gates. **Off by default**
  (`Settings.agentic`); when off, behavior is byte-identical to the fixed pipeline, which remains the
  agent's fallback. What shipped:
  - **Run-level macro controller** (`agentic/runner.py`, `run_loop`): replaces the hardcoded
    `while phase != done` loop with a policy that picks the next *macro-action* over the whole piece -
    `draft` / `reoutline` / `revise` / `consolidate` / `repair` / `table_read` / `produce` / `learn` /
    `escalate` / `done` - so the agent can re-plan structure, fix the weakest committed unit, audit
    continuity early, or defer to a human.
  - **Three policies behind one seam:** `default` (== the fixed pipeline, the deterministic equivalence
    floor), `llm` (a ReAct controller over a compact state view + tool schemas), `trace` (a learned,
    trace-conditioned policy). Any illegal/parse-failed pick falls back to `default`.
  - **In-generation tool use:** the writer can call `research` / `read_canon` / `verify_fact`
    *mid-draft* (a real OpenAI tool-use loop), bounded by a per-round cap *and* a total-call cap, falling
    back to a plain draft on any provider/tool error.
  - **A learned policy** (`agentic/learn.py`): distilled from the agent's *own* action trace
    (context-conditioned, book vs. article; reward = first-pass + insight). It is **never
    auto-promoted** - the efficacy gate still owns promotion - and it needs run volume before it bites
    (it correctly stays undecided on thin data).
  - **Multi-agent panels:** majority-vote fact-check + diverse-lens critique (opt-in).
  - **Safety by construction:** the `WRITE → CRITIQUE` episode stays atomic (the self-improving loop is
    untouched - agency lives *between* episodes, never inside them); every decision is logged to an
    append-only `agent_trace.jsonl`; the whole thing is bounded by call/action caps + a token budget.
    New `/agentic on|off|llm|default` and `/trace` shell commands, a dashboard controller line, and
    `Agent(agentic=True, agentic_policy="llm")` / `/set agentic true` opt in.

  *Live-validated across two real OpenRouter runs: 2026-06-16 (~$0.15) surfaced tool over-calling - now
  capped; 2026-06-17 a full **agentic** article (~$0.52, 606k tokens, 108 calls) finished clean, the
  controller chose `research` on an evidence gap, the writer called tools mid-draft, the DeepSeek
  prefix-cache pin was confirmed engaging (**36% of prompt tokens cached**), and the run surfaced a
  structured-output truncation on the reasoning tier - now fixed (raise `max_tokens`, stay on-tier).*
  Suite: 524 passed / 1 skipped, ruff clean. *(Advanced mode; the fixed pipeline stays the recommended
  default. Maturity caveat: the learned `trace` policy is still corpus-hungry - it needs ≥3 labelled
  units per arm and runs so far yield too few "gather" units, so it abstains - see Next.)*
- **Resilience + safety hardening** (from an exhaustive code review): a global **`fallback` model**
  (any node whose primary exhausts its retries degrades once onto a cheaper tier rather than killing an
  unattended run); a **context budget** (`max_context_chars`, default 24000) that priority-bounds the
  assembled canon+summaries+excerpts so a long book can't silently overflow the window;
  **crash-safety** (canon is committed to the store *before* the chapter `.md` resume marker, so a
  mid-commit crash re-runs the chapter idempotently instead of skipping it with missing canon); a
  hardened **web demo** (serialized runs + per-visitor key isolation so there's no cross-visitor key /
  billing leak; topic length capped); a **single-source anti-slop lexicon** (`slop.py` - the writer's
  NO_SLOP block and the humanizer are generated from / cross-checked against one module, so they can't
  drift); and **config validation** that clamps out-of-range settings to sane bounds.
- **Learning loop v2 - ablation duels** (`skill_duels`): the system now earns skill-trust by a true
  cause-and-effect A/B test (draft with vs without a skill, critic compares), not a confounded proxy.
  Plus `skill_distill` (de-dup) and a guarded `watch_blocking`. *(Makes "it improves with use" real -
  and honest: memory, not retraining.)*
- **UX audit P1–P3**: first-run onboarding (no-key → set key or try fake mode free), friendly
  recoverable errors, whole-run ETA, a colourblind-safe theme, duel-aware `/skills`.
- **Internals hardened**: book↔article de-duplication + the orchestrator & shell god-modules split into
  packages (behavior-preserving) - lowers contributor friction (no file >~1k lines).
- **`learning.md`** - a layman's guided tour of the whole codebase (onboarding for non-experts).
- Earlier this session: **Evidence report** (`evidence_report.md` + `evidence` command +
  `Project.evidence_report()`), **output-first README**, **`examples/` gallery** + **Colab quickstart**.
- Prior session: token/cost-efficiency pass, TUI UX overhaul, prose read-time, v0.2.0.

### Next (P1 - weeks)
- **Hosted/zero-install demo** (HF Space or rate-limited web) - the single biggest acquisition lever.
- **Blind A/B harness** - 5 prompts, this vs ChatGPT/Claude long-form, blind reads; publish results.
- **Activation instrumentation** - measure install → first-finished-piece.
- **First-run cliff** reduction - *partly shipped* (no-key onboarding + fake-mode nudge); still want a
  60-sec asciinema/GIF.
- **Agentic controller - prove it at scale** (the code is done; what's left is *volume*, not features):
  (a) **live tool-call validation at volume** - many real runs on tool-capable providers, not one, to
  confirm the in-generation loop + caps hold up and that agentic beats `default` at equal budget;
  (b) **a learned-policy trace corpus large enough to bite** - accumulate enough labelled action traces
  that `train_policy` produces a decided, net-positive policy (today it correctly abstains on thin data).
- **Compositor - additive next steps** (plan §23.6; the cascade seam is in place, these are additive):
  **per-unit emotion** (map a book chapter's `emotional_role` → an emotion key instead of one run-level
  target), a **persona-aware critic** (don't flag a persona's deliberate choices as defects), a
  "blend = author a new persona" workflow, and **surfacing the cascade in the TUI** (today persona /
  emotion / register / field are settable but not yet a first-class dashboard control).

### Later (P2 - only if pull is proven)
- A **VS Code extension** to break the terminal ceiling further. *(A local **web dashboard** now
  ships - see Now; a hosted/zero-install demo is the remaining acquisition lever, above.)*
- Community: examples-of-the-week, Discord, good-first-issues.
- Book-length coherence hardening (10+ chapters) + public proof.

## 9. Validation plan (assumptions to test BEFORE building more)

1. **Quality claim:** does output beat ChatGPT/Claude long-form on blind reads? → 5-prompt blind A/B
   (**harness shipped:** `benchmarks/blind_ab/` - generate → paste competitor → blind score → tally).
2. **Segment pull:** do 5 DevRel/technical writers call it must-have after one real run? → interviews.
3. **Funnel:** what's install → first-finished-piece conversion, and where do people drop? → telemetry.
4. **Book coherence** at 10+ chapters (the riskiest, least-proven claim). → one long live run, read end-to-end.
5. **Agentic efficacy:** does the opt-in self-directing controller beat its own fixed pipeline at equal
   token budget (first-pass / insight / cost-latency)? → many real `agentic` vs `default` runs at volume
   (today: a single live run validated the loop end-to-end, not its uplift).
6. **Craft-engine / basic-model claim:** does a register/persona run on a **basic** model actually read
   as on-genre to blind readers (not just to the deterministic metrics)? → per-register blind reads +
   craft-metric deltas vs the nonfiction baseline (the engine ships and the suite passes; the
   reads-as-good-on-a-weak-model uplift is built-for, not yet measured at volume).

## 10. Risks & mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| Terminal-only caps the audience | High | Zero-install demo; later GUI/extension - but only after artifact pull |
| Differentiator is *told*, not *shown* | High | Evidence report (done) + ChatGPT side-by-side + examples gallery |
| Setup/cost friction (key, Python+Node) | Med | Fake mode (done) + clear cost expectation + npm `setup` |
| Book quality unproven | Med | Validate before promoting; lead with articles |
| **Agentic mode adds cost/latency or loops** (extra controller + tool calls; an eager model over-researches) | Med | **Default-off** (opt-in only); per-round + total tool-call caps; a token budget that drops optional polish actions under pressure; the fixed pipeline is the always-legal fallback. *(A live run did surface tool over-calling - caught and capped.)* |
| **Agentic mode unproven at scale** (single live run; learned policy needs corpus volume) | Med | Frame honestly as advanced/opt-in; the deterministic `default` pipeline stays recommended; learned policy never auto-promoted (efficacy gate owns promotion); validate at volume before promoting (roadmap/Next) |
| **Craft engine widens genres → dilutes the wedge** (11 registers + personas can read as "tool for everyone") | Med | Lead with technical articles; frame the engine as *depth* (better prose on a basic model), not a new audience; nonfiction default stays byte-for-byte so the wedge persona sees no change |
| **Composing layers degrades a weak model** (several voices at once average into mush) | Med | The compositor **selects + resolves conflicts, never accumulates**; upper layers are single-select; incompatible persona is dropped + logged; the register always wins |
| **Persona = author-impersonation / copyright surface** | Med | **No living/in-copyright authors**; public-domain personas are *manners* only; all exemplars are **original pastiche**, not the authors' text (zero copyright surface); incompatible personas dropped |
| **Basic-model craft claim unproven on real basic models** (built for it; not yet measured at volume) | Med | Deterministic craft metrics give model-independent evidence; validate per-register quality on a basic model via the blind-read / craft-metric proof (§7) before promoting the claim hard |
| Scope dilutes the pitch | Med | One-line spearhead; articles first; agentic mode is opt-in, not the headline |

## 11. Verdict (from the product review)

**Solving a real problem? Yes** - for a specific niche (slop fatigue at long-form), narrowed by the
terminal + API-key gate. **The engineering is ahead of the go-to-market.** As an OSS project it will
win a small loyal niche as-is; it spreads only once there's a zero-install try and the output is
*shown* beating ChatGPT. Those two moves - not more features - unlock adoption.

**Keep:** quality machinery, autonomy, local-first, cost guardrails, the API.
**Rework:** positioning → output-first + a sharp one-liner (in progress).
**Add:** demo, examples, the evidence report (done).
**Don't add:** more pipeline surface area yet.

---

### Appendix - competitive landscape

- **ChatGPT / Claude (Projects/Canvas)** - the real default. *Their edge:* zero install, GUI,
  conversational control. *Our edge:* autonomy (one command vs much prompting), the
  thesis/critic/claim-verify anti-slop loop, an opt-in self-directing controller that re-plans / revises /
  audits *and* learns from its own trace (with a deterministic fallback floor), local-first, repeatable,
  cheap.
- **Sudowrite / NovelCrafter** - fiction, polished web UI, subscription. *Our edge:* autonomy, cost,
  local-first, verification, articles too - and now a **register-gated craft engine** (fiction *and*
  nonfiction genres from one tool, with deterministic fiction metrics - filter-verb density, said-
  bookisms, POV/tense, sensory density) plus a **compositor** that composes persona + emotion without
  averaging them into mush. *Their edge:* UX, fiction tooling, community.
- **Jasper / Copy.ai** - marketing/short-form SaaS. Different segment; not a real competitor.
- **Stanford STORM (OSS)** - the closest analog for researched articles; very popular. *Their edge:*
  hosted demo, mindshare. *Our edge:* a *thesis/stance* (STORM is neutral/encyclopedic), the quality
  machinery, books, export formats, the learning loop, an opt-in self-directing controller, local-first.
- **GPT-Researcher (OSS)** - research reports. *Our edge:* publication-ready prose with a take, not a
  report dump; export + production layer. *Their edge:* simpler pitch, demo, stars.
