# Writing Agent - Plan

A self-correcting, multi-book writing system. Not a chatbot and not a single prompt - a
**writing machine with memory** that drafts chapters, judges its own work, escalates to a
human when it's unsure, and **learns reusable craft skills per user across many books**.

> **The loop:** write → judge → (approve | revise | escalate to human) → commit canon →
> consolidate → learn skills → write the next chapter better.

> **Implementation status (v1, updated 2026-06-12).** Built in `src/writingagent/` and shipped as an
> interactive **WRITING AGENT** shell (a themed TUI with slash commands + per-agent model switching)
> plus a one-shot CLI (`writing-agent` / `python writingagent.py`; see README).
> **Live-validated** on OpenRouter + DeepSeek V4 Pro/Flash: fully autonomous runs completed a book
> (9-page PDF, captured in `SampleRun/`) and a long-form article (6 sections, DOCX export).
>
> Features beyond the §1–16 spec: **article mode** (parallel section pipeline with editorial angle
> picker, flat `articles/<id>/` layout, inline citations + sources.json); **`write` one-shot flow**
> (upfront interview → fully autonomous run → exported file, §15.3); **humanizer** pass (strips
> AI tells, 11 rules); **SVG diagram fallback** (LLM-generated `<svg>` when Wikimedia returns nothing,
> saved to `images/`); **6 export formats** (pdf · epub · html · docx · txt · md; interactive picker);
> **deep multi-source researcher** (§15.2); **10 TUI themes** (palette + wordmark figlet per theme,
> `/theme`); **production guards** (run token budget kill-switch, per-call JSONL telemetry +
> `/dashboard`, untrusted-web-content fencing - §15.1); **`/update` slash command** (describe changes
> → AI reviews and advises); seed craft-skills (13 built-in); autonomous mode (best-draft commit +
> contradiction auto-repair); `NO_SLOP` guardrails injected into every writer/humanizer/critic prompt.
>
> Two deliberate deviations: (1) the orchestrator (§6) is a **durable on-disk state machine**, not
> LangGraph - the brain on disk is the checkpoint, giving resumable runs; LangGraph stays an
> optional wrapper (§12). (2) genre-relevance (§10) uses **lexical similarity**, not embeddings
> (clean seam to swap later). Verified: all modules compile; the data layer + whole orchestrator
> (incl. escalation/review/resume, low-confidence + contradiction escalation, autonomous repair)
> pass an offline fake-LLM pytest suite (**11 passing**).

---

## 1. Architecture in one sentence

> A **LangGraph** pipeline that writes into a **GBrain-style** markdown-canonical memory and
> learns **Hermes-style** skills, per user, across books.

Three layers, no overlap:

| Layer | Borrowed pattern | Responsibility |
|---|---|---|
| **Memory substrate** | GBrain | markdown = source of truth, synced queryable index, entity graph, periodic consolidation |
| **Learning layer** | Hermes | skills generated from experience, user modeling across books |
| **Orchestration** | LangGraph | state machine, checkpointing, human-interrupt on escalation |

We borrow these projects' **patterns**, not their surface area. No multi-platform gateways,
no CRM schemas, no 40-tool general agents. This is a narrow book pipeline.

---

## 2. Scope (v1) and non-goals

**v1 is CLI-first, single-machine, one user at a time, local storage.**

In scope:
- CLI to start a book, run the pipeline, review escalations, read output, inspect memory.
- Full engine: planner → TOC → writer → critic → orchestrator state machine.
- Markdown-canonical memory with a synced local index (SQLite/PGLite).
- Entity graph for continuity; periodic consolidation pass.
- Skill learning (candidate → trusted) and per-user, genre-relevance retrieval.
- Human-in-the-loop via checkpoint/resume + directed instructions on reject.

Explicit non-goals for v1 (deferred, not rejected):
- Web/GUI front-end.
- Real multi-tenant server + Postgres (architecture supports it; we don't build it yet).
- Research agent depth (kept as an optional, shallow node).
- Autonomous "skill creation with no validation" - every skill must earn trust (see §8).

---

## 3. Memory model

### 3.1 Three scopes

| Scope | Lives where | Contents | Leaks across books? |
|---|---|---|---|
| **Book canon** | `books/<book>/` | plan, TOC, characters, timeline, world rules, chapters, summaries | **Never** |
| **User craft** (genre-tagged) | `user/skills/`, `user/prefs/` | reusable skills + craft prefs, retrieved by genre relevance | Yes - to *similar* books |
| **User global** | `user/profile.md`, `user/prefs/_global.md` | who the user is, universal mechanics ("no em-dashes", chapter length) | Always |

### 3.2 Markdown is the source of truth (GBrain pattern)

- All durable knowledge is **markdown files in a git repo**.
- A **synced index** (SQLite/PGLite) is a *derived* read model for query/retrieval - rebuilt
  from markdown, never the authority. Deletions in git → soft-deletes in the index.
- Every canonical entity is a page with **YAML frontmatter + a timeline section**.
- This resolves the markdown-vs-structured tension: one canonical store, still queryable.

### 3.3 File layout

```text
brain/                              # the git repo ("brain")
  user/
    profile.md                      # who the user is (global)
    prefs/
      _global.md                    # universal prefs/mechanics
      <freeform-tag>.md             # craft prefs, freeform genre tag (retrieved by similarity)
    skills/
      <skill-name>.md               # learned skills (markdown, agentskills.io-style)
  books/
    <book-id>/
      book_plan.md                  # premise, themes, genre, tone, audience, constraints, world rules
      toc.md                        # chapter blueprints
      canon/
        characters/<name>.md        # frontmatter + canon facts + voice + timeline
        locations/<name>.md
        threads/<thread>.md         # plot threads: setup, status, payoff
        timeline.md                 # discrete dated/ordered events
        world_rules.md
      chapters/
        ch01.md
        ch01.summary.md
      eval/
        ch01.json                   # critic output
      reviews/
        <ts>-ch03.md                # escalation review queue (pending + answered)
      revision_log.md               # audit of revisions + human instructions
.index/                             # derived, gitignored: SQLite/PGLite, FTS, embeddings, graph
```

### 3.4 Entity graph (continuity engine, GBrain pattern)

On chapter **commit**, a deterministic extraction step (no LLM where avoidable) updates:
- **Nodes:** Character, Location, Object, PlotThread, Event, Faction.
- **Edges:** `appears_in`, `present_at@time`, `knows`/`relationship`, `possesses`,
  `advances` (chapter→thread), `foreshadows`, `causes`.
- **Wikilinks** `[[maya]]` between canon pages auto-resolve.

This graph is how the Writer pulls a *relevant slice* (the characters in this scene, the
threads it advances, the events it depends on) instead of re-reading the whole book.

### 3.5 Example pages

Character page:

```markdown
---
type: character
name: Maya
aliases: [Dr. Chen]
status: alive
first_appearance: ch01
tags: [protagonist]
---
## Canon
- Father died before ch1.  <!-- ref: ch01 §scene2 -->
## Voice
- Terse, clinical; deflects with dry humor. Never uses contractions when angry.
## Timeline
- ch01: introduced at the clinic
- ch03: learns of the breach
```

Skill page (Hermes/agentskills.io-style markdown):

```markdown
---
name: slow-burn-tension
genre_tags: [thriller, psychological]
scope: user
created_from: { book: <id>, chapter: 12, via: human-instructed-revision }
status: candidate            # candidate | trusted | retired
efficacy: { applied: 3, approved_first_pass: 2 }
---
## When to apply
Scenes where two characters share a secret the reader already knows.
## Technique
- Withhold the explicit statement; let subtext and physical beats carry it.
- End the scene one line before the reveal.
## Anti-pattern it replaces
- Dumping the secret in dialogue ("exposition-heavy dialogue").
```

---

## 4. Nodes (collapsed agent set)

Down from the original ten to what earns its place. Old Continuity/Style/Logic agents are now
**dimensions the Critic checks**, not separate agents.

| Node | Job | Writes prose? |
|---|---|---|
| **Orchestrator** | State machine: route, cap revisions, decide escalation, trigger consolidation/learning | No |
| **Planner** | Abstract → premise/themes/genre/tone/audience/constraints/world rules; proposes directions | No |
| **Researcher** *(optional)* | Shallow fact/style gathering to feed the Writer | No |
| **TOC** | Approved plan → chapter blueprints (purpose, setup, payoff, dependencies) | No |
| **Writer** | Draft a chapter from its retrieved context slice + applicable skills | **Yes** |
| **Critic** | One pass; replaces Continuity/Style/Logic *and* the old Evaluator | No |
| **Consolidation** | Periodic global sweep (GBrain Dream Cycle): contradictions, dedup, salience | No |
| **Learner** | Turn human instructions + cross-book recurrence into skills/prefs | No |
| **Production** | Decide + generate front/back matter; assemble final manuscript | Yes (matter) |

---

## 5. The Critic (replaces the 100-point rubric)

No false-precision scoring. LLM self-scoring clusters at 78–85 and jitters on re-runs; a
weighted sum also hides *which* thing is broken. The Critic outputs **blocking issues vs.
nits + a confidence + a verdict**.

```json
{
  "chapter_id": 3,
  "verdict": "revise",
  "confidence": 0.62,
  "blocking": [
    {
      "type": "continuity",
      "where": "scene 2",
      "detail": "Timeline conflict with ch1: Maya's father is alive here, dead in ch1.",
      "fix": "Make this a past-tense memory, or correct ch1 canon."
    }
  ],
  "nits": ["Maya's voice drifts formal in scene 2"]
}
```

- `approve` only if **zero blocking issues**.
- **Low confidence is itself an escalation trigger** - the Critic may say "I'm not sure,"
  which routes to the human rather than guessing.
- Dimensions checked: continuity, character integrity, plot progress, style match, clarity,
  setup/payoff, memory alignment. (Kept as *checks*, not as scored sub-totals.)

**Quality scores (added 2026-06-12) - the ceiling, not just the floor.** Blocking/nits above
guarantee the *floor* (no slop symptoms, no continuity breaks). Originality needs a separate
signal, so the Critic also returns four independent 1-5 scores - `insight`, `clarity`,
`structure`, `evidence` (5 = a contestable argument a generic piece wouldn't contain; 3 =
competent but predictable; 1 = could appear unchanged on any site). Judged *separately from
the verdict* - a chapter can be flawless and score 1.
- **`min_insight` gate** (default 3): `approve` also requires `insight >= min_insight`; a
  correct-but-generic draft gets a "sharpen the argument" revision pass, not a pass.
- **Thesis-advancement check** (articles): a section that merely *covers* the topic without
  advancing the piece's thesis (§15.4) is a BLOCKING issue.
- **Deterministic style metrics** feed the Critic as computed evidence (paragraph-length
  uniformity, rule-of-three density, wrap-up tells, specificity density) - structural tells a
  lexicon can't catch.
- **Best-of-N:** with `divergent_drafts > 1` the first attempt samples N drafts at varied
  temperatures. A dedicated **side-by-side judge** (`tournament_judge`, default on; §15.6) reads
  the variants together and picks the winner - far more reliable than comparing each draft's
  isolated 1-5 self-score; the scalar `_crit_better` (approve > fewer-blocking > higher-insight >
  higher-confidence) is the fallback when the judge is off or errors. The winner is refined against
  the judge's noted weakness. In manual interactive runs the human picks instead.

---

## 6. Orchestrator state machine

```text
PLAN ──(human picks direction)──▶ TOC ──▶ ┌─ per chapter ──────────────────────────────┐
                                          │ WRITE ──▶ CRITIQUE                           │
                                          │   approve            ─▶ COMMIT ─▶ next       │
                                          │   revise (< cap)     ─▶ WRITE (with fixes)   │
                                          │   revise (= cap)     ─▶ ESCALATE             │
                                          │   low-confidence     ─▶ ESCALATE             │
                                          │   contradiction      ─▶ ESCALATE             │
                                          └─────────────────────────────────────────────┘
                                                          │
                              (every N chapters / milestone) ─▶ CONSOLIDATE
                                                          │
              BOOK_DONE ─▶ CONSOLIDATE (final) ─▶ PRODUCTION ─▶ LEARN
```

- **Hard revision cap** (default 2): the 3rd failed attempt **escalates** - no infinite loops.
- **COMMIT** is the only place canon changes: update entity pages, graph edges, timeline,
  write the chapter summary. Append-mostly, audited (git history + soft-deletes).
- **CONSOLIDATE** runs periodically (not every chapter) - see §9.
- **PRODUCTION** assembles the deliverable at book end - front/back matter + manuscript (§16).
- **LEARN** runs at escalation and at book end - see §8.

---

## 7. Human-in-the-loop (autonomous by default, human as exception handler)

Escalation triggers:
- Revision cap hit.
- Critic low confidence (numeric gate: `confidence < escalate_below_confidence`, default 0.5).
- Low insight after the sharpening pass (`insight < min_insight`); see §5, §15.4.
- Irreconcilable contradiction (plan says X, the chapter needs Y).
- Structural decision (kill a character, change the ending).

**Escalation picker (TUI, added 2026-06-12) - resolution is interactive, not a printed hint.**
When a unit stalls, the shell shows the Critic's blocking issues and offers one keypress:
`[f]ix automatically` (records the critique as the instruction) · `[i]nstruct in your words` ·
`[a]pprove as-is` (commits the stalled draft via the normal commit path - `approve_escalation()`)
· `[g]o autonomous & finish` (flips the project to autonomous and runs to the end) ·
`[r]ead draft` · `[s]top`. Every choice resumes the run itself. The file queue + `review`
command remain the non-interactive path.

Escalation contract:
1. Orchestrator **checkpoints** (LangGraph interrupt) and records a pending review.
2. Human is notified; the run can pause for as long as needed.
3. Human responds with **directed instructions** ("make the confrontation colder, cut the
   backstory") - they **do not edit prose**; they steer, the model always writes.
4. Instruction is appended to the context slice; flow **resumes at WRITE**.
5. The instruction + the Critic finding it answers are logged to `revision_log.md` - this is
   the **gold-standard learning signal** (see §8).

**Notification channel (v1):** on escalation the Orchestrator writes a markdown entry to
`books/<id>/reviews/` (the review queue) and, in interactive mode, prints it to the terminal.
`writing-agent status` lists open entries; `writing-agent review` opens, answers, and resumes them. No
email/desktop/push in v1 - the file queue is the single source, so any later channel just
tails it.

Why directed instructions instead of edits: an instruction encodes the *principle* and
generalizes; a diff only tells you what changed in one chapter.

**Alternative interaction model (§15.3):** for "ask me everything upfront, then deliver,"
the `write` command front-loads all questions into a single interview and then runs fully
autonomously (no mid-run escalation). The mid-run human-as-exception-handler model above is the
default for `new`/`run`; `write` is the opt-in one-shot path.

**Run-mode toggle (added 2026-06-12):** `/auto on|off` (aliases `/autonomous`, `/manual`) and
`run --autonomous` / `run --manual` switch a project between autonomous (never pause, commit the
best draft) and manual (human-in-the-loop) at any time - `orchestrator.apply_autonomous()`
rewrites the run-state and *clears a pending per-unit review* when switching to autonomous, so a
stalled run finishes. An **outline gate** (manual mode, TTY only) shows the outline + thesis claim
after `new` for `[Enter] write · r regenerate · g regenerate-with-guidance` before any prose.

**Post-completion revision (added 2026-06-12):** `revise --chapter N --instruction "..."`
rewrites ONE committed unit of a *finished* piece (write → critique → optional fix pass →
humanize), shows a semantic Added/Removed/Improved summary + a unified diff, and on accept patches
the section file *and* the assembled manuscript (`_replace_manuscript_section`); books re-run
production. Canon is **not** re-extracted - a polish must not mutate the knowledge base later
units were written against. This closes the gap between "pipeline done" and "author satisfied"
without a full re-run.

---

## 8. The Learner (skills + watch-list)

Produces **two** artifacts - positive *and* negative - because a pile of "don'ts" causes
instruction overload (the writer honors the first few and drops the rest), while reusable
positive procedures compose.

| Artifact | Polarity | Used by |
|---|---|---|
| **Skill library** (markdown, §3.5) | positive - "what to do" | Writer, retrieved by relevance |
| **Watch-list** | negative - "what to catch" | Critic, small, hard traps only |

**Signal priority (teacher hierarchy):**
1. **Human directed-instructions** (gold) → strongest source of new skills/prefs.
2. **Cross-book recurrence** (≥2 of the user's books, similar genre) → promotes to user scope.
3. **Critic-only findings** and **model preference data** (tournament winners + revision fixes,
   §15.6) → fix *this book* only; **never auto-promoted** to user learning (training on the
   model's own taste = circular convergence on bland, "safe" writing). They enrich the *candidate*
   pool the efficacy gate then validates - they do not bypass it.

**Promotion rule (kills overfitting):** a lesson leaves book scope for user scope only on a
human signal *or* cross-book recurrence. A one-book pattern stays book-scoped.

**Efficacy validation (closes the open loop):** a skill starts `candidate`. Track per skill:
`applied` (chapters where it was retrieved + applied), `first_pass_approvals` (of those,
approved by the Critic with no revision), and `target_failures` (applied chapters where a
blocking issue of the *type the skill targets* still occurred). Judge by **lift over
baseline**, where `p_base` = the user's overall first-pass approval rate and
`p_skill` = the skill's:

- **Minimum sample:** `applied >= 5` before any promotion/retirement decision.
- **candidate → trusted:** `applied >= 5` **and** `p_skill >= p_base` **and**
  `target_failures == 0`. (Lift over baseline, not an absolute bar - easy chapters can clear
  an absolute threshold without the skill helping.)
- **→ retired:** `applied >= 5` **and** (`p_base - p_skill > 0.2` **or** `target_failures >= 2`).
- **Explore/exploit:** trusted skills are retrieved by default; candidates are applied more
  sparingly so they accumulate a fair sample without dominating; retired skills are excluded
  from retrieval but kept for audit/history.

All thresholds are tunable config. Neither Hermes nor GBrain clearly solves trust - this is
the gate we add.

**Ablation duels (the causal efficacy signal · `skill_duels`, opt-in).** The first-pass-lift
rule above is *confounded*: `record_chapter` credits every applied skill with the same
chapter-level outcome (no per-skill attribution, no counterfactual), and `target_failures` was
never written. The fix reuses the best-of-N machinery: on a unit that still has an *undecided*
skill, `_divergent_first_draft` drafts **one extra variant with that skill held out**, at v0's
temperature, so the only difference is the skill. `_crit_better(crit[v0], crit[ablated])` is the
skill's **causal lift** - a true counterfactual. `skills.record_duel` logs win/loss (a loss is
an attributed `target_failure`), `pick_duel_target` chooses the least-dueled candidate and tapers
off at `MIN_DUELS`, and `reconcile` prefers a **Laplace-smoothed duel win-rate** (`TRUST_WR` /
`RETIRE_WR`, gated by `MIN_DUELS`) over the first-pass fallback. De-risks: a variant is *added*,
not substituted (no real contender lost; cost = one extra draft only while a skill is undecided);
the win-rate is smoothed + sample-gated so noise can't flip a skill; skipped in skeleton mode.

**Distillation (`skill_distill`, opt-in).** As the library grows, near-duplicate skills dilute
top-N retrieval. `skills.distill` retires the weaker of each near-duplicate cluster (Jaccard over
body tokens ≥ `DEDUP_SIM`, keeping the best duel win-rate / applied count). Deterministic and
**non-destructive** (status only; the md is kept), and only meaningful once duels score skills -
hence off by default.

**Watch-list enforcement (`watch_blocking`, default on).** The watch-list was unconditionally
blocking (false-positive / revision-thrash risk). It now blocks only **clear, concrete**
violations (borderline/stylistic → nit); `False` makes it fully advisory.

---

## 9. Consolidation pass (GBrain "Dream Cycle" analog)

Per-chapter checks miss *global* drift. A periodic batch pass (between chapters / at
milestones / before book end) does what the inline Critic can't:
- **Contradiction detection** across the whole book (cached LLM judge - pay once per pair).
- **Character-fact dedup** and canon reconciliation.
- **Salience scoring** (what actually matters for future chapters).
- Flags unresolved threads with no planned payoff.

**Cadence (v1):** fixed - every `N=5` committed chapters (configurable) - **plus** a mandatory
pass before `BOOK_DONE`, **plus** manual `writing-agent consolidate`. Salience-adaptive cadence is
deferred: salience is an *output* of this pass, so it can't gate the first run; once available
it may only *tighten* the interval, never replace it.

Output feeds the Orchestrator and the canon (reconciled facts). When `escalate_on_contradiction`
is on (default), contradictions pause the run with a `reviews/consolidation-*.md` entry; the human
reviews and resumes with `writing-agent run --force`.

---

## 10. Retrieval strategy (build only what earns its cost)

| Need | Mechanism | Why |
|---|---|---|
| In-book continuity slice | **FTS + entity graph** | cheap, deterministic; exact facts/relations |
| Cross-book skill/pref retrieval | **embeddings (semantic similarity)** | freeform genre tags fragment on exact match; similarity groups "thriller" ≈ "psychological thriller" ≈ "suspense" |

Freeform genre is the surface UX; we **never key learning on the exact string** - we retrieve
by similarity to the book's profile, so cross-book learning still accumulates.

---

## 11. Multi-tenancy (designed in, built later - GBrain brain⊥source)

- **User = brain** (one git repo + one index).
- **Book = source** within the brain.
- One index per brain; per-source sync state.
- v1 runs one brain locally. The same shape scales to a server + Postgres without redesign.

---

## 12. Tech stack

| Concern | v1 choice | Scale-up path |
|---|---|---|
| Orchestration | **LangGraph** (graph + checkpointer + `interrupt()`) | same |
| Why LangGraph | durable pause/resume for human-in-the-loop is first-class; nodes are mostly *deterministic LLM calls*, so we use the graph/checkpoint/interrupt - not "agentic" behavior | - |
| State store / index | **SQLite or PGLite** + FTS + pgvector-style embeddings | Postgres (Supabase/self-hosted) |
| Canonical memory | **markdown in a git repo** | same |
| Provider | **OpenRouter** via the OpenAI SDK (`OPENROUTER_API_KEY`) | any OpenAI-compatible host |
| Models | DeepSeek **V4 Pro** (planner/writer/consolidation) + **V4 Flash** (rest) | per-node in §12.1 |
| Language | Python (LangGraph-native) | same |
| Platforms | **Linux · macOS · Windows** - CI runs the suite on all three × Python 3.10–3.13 | same |

Caveat: the real engineering is the **memory schema + retrieval + state machine** - all
framework-independent. Don't let LangGraph tempt nodes into being more agentic than they need.

### 12.1 Model routing (per node)

Each node's model is configured in `config/models.yaml` (a default plus per-node overrides).

```yaml
# config/models.yaml - OpenRouter slugs
default: deepseek/deepseek-v4-pro
nodes:
  planner:       deepseek/deepseek-v4-pro      # high tier (the "Opus 4.8 space")
  writer:        deepseek/deepseek-v4-pro      # prose quality
  consolidation: deepseek/deepseek-v4-pro      # global reasoning across the whole book
  toc:           deepseek/deepseek-v4-flash
  critic:        deepseek/deepseek-v4-pro      # insight scoring + thesis checks need real judgment
  judge:         deepseek/deepseek-v4-pro      # ranks divergent drafts side-by-side (best-of-N, §15.6)
  verifier:      deepseek/deepseek-v4-pro      # checks cited claims against source text (§15.6)
  summarizer:    deepseek/deepseek-v4-flash    # summaries + canon extraction
  production:    deepseek/deepseek-v4-flash
  learner:       deepseek/deepseek-v4-flash
  researcher:    deepseek/deepseek-v4-flash
  humanizer:     deepseek/deepseek-v4-flash    # surgical line edits only
  diagram:       deepseek/deepseek-v4-pro      # SVG figures: pro composes better; 16k budget
  diagram_fallback: deepseek/deepseek-v4-flash # draws the figure if pro emits no SVG
temperature:                                   # DeepSeek accepts sampling params
  toc:        0.4
  critic:     0.2
  summarizer: 0.0
  writer:     0.9   # base; divergent first drafts sample 0.7 / 1.0 / 1.2
  humanizer:  0.3   # surgical - must not get creative
```

Defaults route **DeepSeek V4 Pro** to Writer/Planner/Consolidation (the high-leverage nodes) and
**V4 Flash** to the rest - the bulk of calls by volume. All calls go through **OpenRouter** via the
OpenAI SDK (`OPENROUTER_API_KEY`); structured node outputs use **JSON mode + Pydantic validation**
(with one repair retry), since DeepSeek has no Anthropic-style `messages.parse`.

**Fallback model (resilience).** `models.yaml` carries one global `fallback:` slug (default
`deepseek/deepseek-v4-flash`, the cheapest reliable tier). After *any* node's primary model exhausts
its retries - a provider outage, a persistent 5xx, or a content-filter 4xx - `llm.complete_text` /
`complete_structured` retry the call **once** on the fallback (`_allow_fallback=False` on that call,
so it can't recurse). One node's failure degrades the run instead of killing an unattended multi-hour
book. Wired at startup from `ModelConfig.fallback` via `llm.configure_fallback` (api + cli); empty =
off. **Context budget (`Settings.max_context_chars`, default 24000):** the assembled
canon+summaries+excerpts block is bounded by priority (canon kept first, then summaries, then
cross-chapter excerpts) so a long book can't silently overflow the model window and hard-fail.

**Recommendation:** use a *different* model (or family) for the **Critic** than the **Writer**.
A model tends to be a lenient judge of its own output; an independent critic catches more. This
is the architectural reason the Critic is a separate node in the first place. *(Current default
keeps the Critic on `deepseek-v4-pro` - same family as the writer - because insight scoring and
thesis checks needed the pro tier's judgment more than cross-family independence; the watch-list,
deterministic style metrics, and `/praise` are the compensating defenses. Route `critic` - and the
`judge`/`verifier` nodes (§15.6) - to any non-DeepSeek slug to restore cross-family independence
where it matters most.)*

### 12.2 Provider selection (the model host)

The pipeline speaks **one** wire format - OpenAI chat-completions (text + JSON-mode structured
output, no tool-calls or thinking-block replay) - so it talks to any OpenAI-compatible host through
a **single transport**. `providers.py` is a small frozen-dataclass registry (`id`, `name`,
`base_url`, key env vars, optional `*_BASE_URL` override, `reports_cost`, extra headers, `local`).
**OpenRouter is the default** (and the only host that reports real USD `usage.cost`); also built in:
DeepSeek, OpenAI, Google Gemini (compat endpoint), xAI, Groq, Mistral, Moonshot/Kimi, Qwen/DashScope,
Zhipu GLM, NVIDIA NIM, Together/Fireworks/DeepInfra aggregators, **Ollama** and **LM Studio** (local,
no key), and a `custom` escape hatch (`WRITINGAGENT_BASE_URL`). Aliases resolve shorthand (`grok→xai`,
`ds→deepseek`, `kimi→moonshot`, …). Adding a provider is **one registry entry**, nothing else.

Switch with **`/provider <id>`** (lists every host with a key/local/no-key marker, persists to
`settings.provider`, rebuilds the client), `/set provider <id>`, or **`WRITINGAGENT_PROVIDER`**.
Credentials are resolved lazily - switching to a key-less host never crashes startup; the clear
"set `XAI_API_KEY`" error only fires on the first real call. Each host reads its own key env var; a
`*_BASE_URL` var points any provider at a proxy/self-hosted gateway. *Deliberately out of scope
(Hermes has them; a writing pipeline doesn't need them): Anthropic-native / Bedrock / Codex-Responses
transports (all reachable via OpenRouter or a compat shim), a `NormalizedResponse` layer (one wire
format ⇒ nothing to normalize), and OAuth-device/AWS-SDK auth. Model **slugs are not auto-translated**
across hosts - set them per host with `/model`.*

---

## 13. CLI design (the UI)

Two surfaces over one engine (plus the markdown brain repo, which is half the UI - read chapters
and canon in any editor):

- **Interactive shell - the WRITING AGENT TUI.** Run `writing-agent` / `python writingagent.py`
  with no command (see the `shell/` package). Themed masthead (gradient-filled ANSI Shadow wordmark; theme
  also sets palette/figlet/glyphs - `ui.THEMES`), a **compact welcome** (START + your projects +
  a status footer - sized so the wordmark is still on screen at the first prompt on a 30-row
  terminal; the full command list lives under `/help`, the feature board under `/features`; a
  red warning fires when `WRITINGAGENT_FAKE` is set so test mode can't silently eat real runs),
  live run dashboard (progress, stage, tokens vs budget, USD cost), `/dashboard` telemetry
  rollup, autocomplete + persistent history, and a `❧ <model>` prompt. No bottom toolbar (it
  read as noise; state lives in the prompt prefix + welcome footer). Type commands directly (no
  command-name prefix); lines starting with `/` are slash commands; anything else is free chat.
  **First-run key wizard** (`_first_run_setup`, before the welcome): with no key at an interactive
  prompt, the writer gets a one-keypress choice - *paste a key* (written to `.env` **and** applied
  live, no restart), *try it free* (`WRITINGAGENT_FAKE=1` set **live**, no restart dance), or *skip*.
  **`/setkey [<key>]`** is the "add a key later" path (upserts `.env` via `_write_env_key`, applies
  live, clears fake mode). The welcome leads with one action (`write`) and points the no-key block at
  `/setkey`. **Front door:** the README opens with the zero-install web demo (§18.1) so a writer can
  try the whole flow before any install or key.
- **One-shot CLI** - `python writingagent.py <command> ...` (same commands), for scripting.
  Exports print the **absolute** path (the default export dir is the project's brain folder, not the
  cwd) so "where's my file?" is never a guess.

| Command | Does |
|---|---|
| `write` | One-shot (§15.3): topic → upfront interview → fully autonomous run → exported finished file. Flags: `--abstract`, `--chapters N`, `--max-revisions N`, `--no-humanize` |
| `new` | Abstract → directions (human/auto pick) → plan + TOC. Flags: `--autonomous` / `--no-autonomous` (else `settings.autonomous`), `--no-humanize`, `--chapters N`, `--max-revisions N`, `--pick K` |
| `run` | Drive write → critique → humanize → commit → consolidate → produce → learn. `--force` passes a consolidation review; `--autonomous` / `--manual` flips run mode as it resumes (also clears a stalled review) |
| `status` | Where the book is; pending escalations |
| `review --chapter K --instruction "..."` | Answer an escalation; resume on next `run` |
| `revise --chapter K --instruction "..."` | Rewrite ONE committed unit of a *finished* piece (diff + accept/reject), patch the manuscript (§7) |
| `read [--chapter K] [--summary] [--manuscript] [--v N]` | Print a chapter / summary / assembled book / draft **version** N (§15.5) |
| `versions [--chapter K]` | List draft snapshots (variants, revisions, committed finals) - git-for-writing (§15.5) |
| `brief` | The goal panel: thesis / premise, audience, target length, intake, voice/watch state |
| `tableread [--as "persona"]` | Skeptical-reader cold read of the finished piece (optional persona) (§15.4) |
| `eval` | Quality report: judged 5-dim rubric + deterministic metrics → `eval_report.md` (§15.5) |
| `export [fmt ... \| all]` | Render the manuscript: pdf · epub · html · docx · txt · md. Takes one format, a list (`export pdf epub`), or **`all`**; one failing format never aborts the rest (§16.5) |
| `memory` | Inspect canon (characters/timeline) + entity graph |
| `consolidate` · `produce` | Run those passes on demand |
| `skills` · `seed-skills` | List skills + efficacy · install built-in craft skills |
| `list` · `config` | List books · show model routing + settings |

**Slash commands (shell only):** `/help`, `/auto [on|off]` (autonomous ↔ manual run mode; aliases
`/autonomous`, `/manual`), `/praise [N]` (mark a committed unit as great → saved to `voice/`,
feeds the writer + learner; §15.4), `/model [<agent>] <slug>` (switch any model, per agent,
persisted to `config/models.yaml`), `/skills`, `/skill <name>`, `/seed-skills`, `/use <book>`,
`/books`, `/user <id>`, `/config`, `/theme [<name>]` (themes change *everything* - palette,
wordmark figlet face, fleuron, gradient; each a distinct hue family. `editorial` blue-ink default
with semantic status colors; alternates `kazama` (flame, sheared) · `supabase` (emerald) ·
`violet-bloom` (purple) · `t3-chat` (pink) · `starry-night` (indigo+gold) · `vercel` (monochrome) ·
`fallout` (CRT amber) · `mimi` (rose pastels) · `astrovista` (mars rust); registry in `ui.THEMES`
incl. `FONT`/`WORDS`/`SHEAR`, persisted via `settings.theme`), `/dashboard [<project>]` (telemetry
rollup - calls/tokens/cost/latency/errors; per-unit breakdown when a project is named; reads the
JSONL call log, §15.1), `/provider [<id>]` (switch the model host, §12.2), `/features` (interactive
toggle grid), `/path` (where exports are saved, §16.5), `/set <key> <value>`, `/clear`, `/exit`.

Run modes: **interactive** (prompts inline on escalation via the picker, §7), **autonomous**
(`--autonomous` / `/auto on`: never pauses; commits the best draft + auto-repairs contradictions),
**async** (background; resume via `run` / `review` - the on-disk state is the checkpoint).

**Live run dashboard (writing-centric, 2026-06-12):** the goal line (thesis claim / book premise)
stays visible in the header; each attempt logs a one-line draft *glimpse* (the opening sentence,
so a run going wrong can be cancelled before it costs more); a finished run rings the terminal
bell and shows a **summary card** (units · words · elapsed · tokens · cost · avg insight +
clarity/structure/evidence scorecard + pointers to `eval` / `tableread`). A pending review
surfaces via the prompt suffix and the escalation picker (the bottom toolbar was removed).

### 13.1 Interaction & accessibility layer (production-grade UX pass, 2026-06-14)

- **No command dead-ends.** A reserved command word typed without its slash (`help`, `features`,
  `theme`, `provider`, …) runs the command with a one-line hint instead of silently falling through to
  the chat assistant; a leading `\` forces chat. (`shell._SLASH_WORDS` / `_STRONG_SLASH`; ambiguous
  English words like `set`/`use`/`model` only auto-route as a single bare token.)
- **Trust chip.** The critic's raw `verdict=… confidence=… blocking=…` is normalized to
  `✓ approved · insight N/5 · confidence ●●●○○` (`ui.trust_chip`), with the **invariant** that a
  blocking issue never renders as a bare "approve" (it reads "revising").
- **Live run controls** (autonomous + real-TTY only): a background, cross-platform key-listener
  (`shell._KeyListener` → `_RunControls`) lets **esc/p** pause and **m** drop to manual; honored by the
  opt-in `orchestrator.run(control=…)` hook **at unit boundaries only** (a model call can't be
  interrupted mid-token; `control=None` = unchanged behavior). The dashboard also shows a **soft ETA**
  (rolling median per stage) and a **"self-edits"** line (revision / humanizer counts).
- **Structured recovery**, never a dead stop: a *paused* card (budget-cap vs interrupt, with resume +
  alternatives) and export failures that say why + how to recover (file locked / missing optional dep).
- **Accessibility**: `WRITINGAGENT_A11Y` line-mode (no in-place Live redraw — append-only full-sentence
  status for screen readers), `WRITINGAGENT_REDUCED_MOTION` (static stages, no spinner), a one-line
  wordmark on narrow (<60-col) terminals, and `NO_COLOR` / `--plain` honored throughout.
- **Proactive key check**: the banner warns when the active provider has no API key (before the first
  call fails); `WRITINGAGENT_PROVIDER` now syncs `settings.provider` so the masthead is accurate.
- **Progressive help**: `/help <topic>` shows only the matching commands.
- **Second UX pass (2026-06-14, P1–P3):**
  - **First-run onboarding** — with no API key, the welcome shows a "NO API KEY YET" block (set the key
    *or* try the whole flow free with `WRITINGAGENT_FAKE=1`) instead of suggesting a command that fails.
  - **Friendly recoverable errors** (`ui.explain_error`) — bad/missing key (401), rate-limit (429),
    network blip, and locked files map to a clear next step (every hint notes progress is saved), wired
    into the shell + chat error sinks; unknown errors fall back to the raw message.
  - **Whole-run ETA** — `_RunDashboard._run_eta` shows "~Nm left" from this session's average
    time-per-unit, beside the X/N bar (complements the per-stage soft ETA).
  - **Colourblind-safe theme** — `highcontrast` (Okabe-Ito; ok = blue, error = vermillion, never a
    red/green pair; white text). The trust chip was already glyph+word+dot-meter, so status is never
    colour-only. **11 themes.**
  - **Duel-aware `/skills`** — shows the ablation-duel win-rate (vs a 50/50 baseline) + count next to
    first-pass lift, and which signal decides trusted/retired (see §8).
  - **Discoverability** — the new learning toggles (`skill_duels`, `skill_distill`, `watch_blocking`)
    appear in `/features` (grid + static table). Live-run controls wording: all interrupts resumable;
    `/delete` discards.
- **Reading time** is prose-only — fenced code and the references list are excluded
  (`polish.read_time_min`, `READ_WPM`), so technical pieces no longer over-state "N min read".
- **Version** is single-sourced from `writingagent.__version__` (pyproject derives it via
  `dynamic`/`attr`); the TUI imports it. Currently **0.2.0**.

---

## 14. Build order (re-weighted: hard part first, learner last)

1. **Memory substrate** - markdown layout, frontmatter schema, synced index, entity graph,
   context-slice retrieval. *(The foundation, not boilerplate.)*
2. **Planner → TOC.**
3. **Writer** that pulls a context slice + applies retrieved skills.
4. **One Critic** (approve/revise/escalate + confidence + blocking/nits).
5. **Orchestrator graph** - revision cap, escalation, checkpoint/resume, COMMIT.
6. **CLI** wrapping the above (`new`/`run`/`status`/`review`/`read`).
7. **Consolidation pass.**
8. **Book Production** - front/back-matter decisioning, generation, manuscript assembly (§16).
9. **Multi-tenant namespacing** + genre-relevance retrieval for user scope.
10. **Learner** - human-signal-driven, recurrence-gated, efficacy-validated. *(Last, after
    we've watched real mistakes recur.)*

---

## 15. Resolved decisions (v1 defaults)

The open items are now settled. All numeric thresholds are **tunable config**, not hard-coded.

| Question | v1 decision |
|---|---|
| **Notification channel** | Markdown review queue in `books/<id>/reviews/` + terminal print (interactive); surfaced by `writing-agent status` / `writing-agent review`. Any later channel tails the file queue. (§7) |
| **Consolidation cadence** | Fixed: every `N=5` committed chapters + mandatory before `BOOK_DONE` + manual `writing-agent consolidate`. (§9) |
| **Skill efficacy metric** | Lift over baseline: promote at `applied≥5`, `p_skill≥p_base`, `target_failures=0`; retire on sustained under-performance. (§8) |
| **Researcher depth** | Two tiers, both optional. **Shallow** (`use_researcher`): one DuckDuckGo query -> snippets -> a short brief (facts + style cues). **Deep** (`deep_research`, layers on `use_researcher`): LLM query-expansion -> several queries fanned out concurrently -> dedup + per-domain cap -> fetch and extract the actual page text of the top sources -> a synthesis node reads across full pages and cites sources by number. See §15.2. |

### 15.1 Reliability, performance & safety (2026-06-10 hardening)

Durable decisions from the hardening pass. All thresholds are tunable config.

| Area | Decision |
|---|---|
| **Model fallback (2026-06-16)** | `models.yaml` carries one global `fallback:` slug (default `deepseek/deepseek-v4-flash`, the cheapest reliable tier). After *any* node's primary model exhausts its retries - outage, persistent 5xx, or a content-filter 4xx - `llm.complete_text`/`complete_structured` retry the call **once** on the fallback (`_allow_fallback=False` on that call, so it can't recurse). One node's failure degrades the run instead of killing an unattended book. Wired at startup from `ModelConfig.fallback`; empty = off. |
| **Context budget (2026-06-16)** | `Settings.max_context_chars` (default 24000) bounds the assembled canon+summaries+excerpts block (`retrieval.assemble_context` / `_within_budget`) **by priority** - canon kept first, then prior summaries, then cross-chapter excerpts - so a long book can't silently overflow the model window and hard-fail. 0 = unbounded. |
| **Crash-safe commit ordering (2026-06-16)** | `_commit` now writes canon to the store (`update_from_extraction` + `render_canon`) **before** the chapter `.md` - which is the resume guard's "committed" marker - then indexes. A crash mid-commit re-runs the chapter (extraction is idempotent: `INSERT OR IGNORE`) instead of the file existing while its facts are permanently missing from canon. `_commit_section` likewise writes the continuity summary before the section file. |
| **Anti-slop single source (2026-06-16)** | The banned-word lexicon lives in one module (`slop.py`); the writer's `NO_SLOP` block is **generated** from it and the deterministic humanizer is cross-checked against it by a test, so the writer's rules and the post-hoc stripper can't drift. `TECHNICAL_EXCEPTIONS` (`optimize`, `navigate`) are neither hard-banned nor auto-stripped - precise in technical prose, the LLM judge decides (resolves the old "optimize" contradiction). |
| **Config validation (2026-06-16)** | `load_settings` clamps out-of-range values (`min_insight∈[0,5]`, `escalate_below_confidence∈[0,1]`, `max_revisions≥0`, `divergent_drafts≥1`, positive `request_timeout`, valid `mode`/`agentic_policy`) so a typo in `settings.yaml` degrades gracefully instead of producing baffling runtime behavior. |
| **Run-session serialization (A-021, 2026-06-16)** | The LLM wrapper's accounting state (`_client`, `_usage`, `_run_id`, the per-thread `unit`/`project` tags) is **module-global** - the design is one unattended run per process. `llm.run_session(project, budget=)` (a `threading.Lock` + reset-usage/set-project/set-budget on enter, clear tags on exit) wraps the whole `orchestrator.run` body (now a thin `run()` → `_run()`), so overlapping runs in a long-lived host (TUI/web) **serialize** instead of interleaving and corrupting each other's token tally / run-id / telemetry attribution. The web demo's own `_RUN_LOCK` is complementary. |
| **Deterministic analytical nodes (A-022, 2026-06-16)** | `extract_canon`/`consolidate`/`learn` now pass explicit low/0 temperatures (`models.yaml`: `summarizer 0.0`, `consolidation 0.0`, `learner 0.2`) - they previously ran at the model default, making canon extraction and the continuity audit non-reproducible. |
| **Writer repetition penalty (A-024, 2026-06-16)** | Per-node `frequency_penalty`/`presence_penalty` maps in `models.yaml` (clamped to OpenAI's [-2, 2] by `ModelConfig`); the writer ships `0.3`/`0.1` so token-level repetition is attacked at generation time rather than only cleaned up by the humanizer after the fact. Tunable; remove a node to leave it unset. |
| **Context-overflow recovery (B-013, 2026-06-16)** | A `context_length_exceeded` rejection (sniffed from the error code/message, distinct from a generic 400) is recovered by `_shrink_for_context` (headroom compression, else truncate the longest message to 60%) and **one** retry, in both `complete_text` and `complete_structured` - so an over-long prompt shrinks instead of failing the node. |
| **Structured-output truncation recovery (2026-06-17)** | A reasoning model (e.g. `deepseek-v4-pro`) spends tokens *thinking* before it emits the JSON; if that fills `max_tokens` the reply is empty / cut off mid-object with `finish_reason=length`. `complete_structured` now detects this and **raises `max_tokens`** (double, capped at 16k) then retries the **same** model/prompt - no repair turn (the prompt was fine) - so the call stays on its routed (stronger) tier instead of burning its retries on the same budget and degrading to the flash fallback. Complemented by a `models.yaml` `max_tokens:` floor for the reasoning judgment nodes (`critic`/`judge`/`verifier` = 8000), the same headroom the `diagram` node's 16k budget already relies on. Confirmed live: the first real OpenRouter run hit this exactly once (sec05) and the fix recovers on-tier in one extra try. |
| **Chat stream accounting (B-012, 2026-06-16)** | `stream_text` now honors the run budget (`_check_budget` up front), requests `stream_options.include_usage` + cost, and records usage + telemetry + the debug sink from the terminal chunk - TUI chat no longer bypasses the kill-switch or token accounting. No auto-retry (a stream can't be replayed once chunks are emitted; the caller holds the partial output). |
| **Cross-chapter cohesion report (D-008, 2026-06-16)** | Books get a deterministic, LLM-free `cohesion_report.md` after assembly (`polish.cross_chapter_repetition`/`cohesion_report`, gated by `book_cohesion`, default on): it flags verbatim phrasings reused across chapters and near-identical chapter openers. A **detector, not a rewriter** - a whole 10-chapter rewrite (the article-cohesion analog) is impractical and risks losing narrative content, so the report feeds a targeted `revise`. |
| **Observability join keys (D-013/D-014, 2026-06-16)** | Opt-in `WRITINGAGENT_LLM_DEBUG=1` records full prompt+completion to `.index/llm_debug-YYYYMMDD.jsonl` (`telemetry.log_debug`, off by default - large + may carry user text) for "why did it produce/escalate this" without a re-run. The agentic action trace now stamps the run's `run_id` (`llm.run_id()`) + `ts`, so controller decisions join to the call telemetry. |
| **Context compression** | `headroom-ai` is **optional** (lazy import, silent fallback). Pinned to **0.10.17** (the last pure-Python release; ≥0.21 is a Rust/pyo3 ext with no Windows wheel), installed `--no-deps`. `_compress` always tells headroom a **tiktoken** model for counting - compression is model-agnostic, so DeepSeek runs still compress. |
| **LLM call resilience** | We own retries: classified **exponential backoff + jitter**, honor `Retry-After`, **fail fast on 4xx**, per-request `request_timeout` (default 60s). Structured calls do a **repair retry** (feed the invalid output + error back). The OpenAI SDK's own retries are disabled. |
| **Concurrency** | The chapter/section *prose* chain is **sequential by design** (continuity: each unit reads the previous summary). Everything independent of prose overlaps via a small thread pool (`concurrency.gather`): (a) within a unit, research ∥ image/SVG ∥ skill retrieval; (b) **unit n+1's research/images/skills are prefetched while unit n is written/critiqued** (they depend only on the plan/TOC; prefetch results are disk-cached so escalations waste nothing); (c) at commit, **humanize ∥ summarize ∥ canon-extraction** run as one batch (`strict=True` - a failed summary/extraction still aborts the commit) since all three derive from the same approved draft; (d) production's front/back-matter components. The SQLite `Store` is only touched on the main thread. |
| **Prompt size** | The writer/critic canon block is capped at the **most recent `MAX_CANON_FACTS_PER_CHAR` (12) facts per character** - uncapped it grows linearly with the book and late chapters pay maximum latency/cost. Consolidation and extraction still see the full canon. |
| **Caching** | Web-search results (7-day TTL) and generated SVG diagrams are cached on disk under `.index/cache/` (best-effort; corrupt entries self-heal as misses). |
| **State durability** | `run_state.json` (and all brain writes) are written **atomically** (temp file + `os.replace`); `read_json` tolerates a corrupt file (returns `None`). A crash between commit and the state advance is caught by a **resume guard** that skips already-committed units - no double-commit, no duplicate canon facts. `WRITINGAGENT_HOME` relocates the writable brain + index off synced folders (OneDrive/Dropbox locks can break `os.replace` and slow every write). |
| **Safety** | The conversational assistant may **not** auto-execute `delete` / `/user` / `/set` (data-loss / tenant / config) - the human must type those. Project/user ids are validated (`is_safe_id`) and `delete_book` confines `rmtree` to the brain dir. Exported HTML is sanitized (no `<script>`/`<iframe>`/event handlers). A chat **stream error renders as an error**, not as assistant prose - a half-streamed reply is never saved to chat history or command-parsed (an error chunk that passed for prose would be). Deep-research fetches pass an SSRF/robots/politeness gate (§15.2). |
| **Telemetry** | Token usage is aggregated per run and surfaced (`[usage]` line + live in the run dashboard, with real USD cost when OpenRouter reports `usage.cost`). Every LLM call also appends a structured JSONL record - ts, run_id, project, unit (chXX/secXX/phase), kind, model, latency, attempts, tokens, cost, error - to `.index/telemetry/calls-YYYYMMDD.jsonl` (best-effort, never breaks a run). `/dashboard [<project>]` renders the rollup (totals, per-model; per-unit when a project is named). |
| **Run budget (kill-switch)** | `max_run_tokens` (0 = unlimited): checked before every LLM call; crossing it raises `BudgetExceeded`, which `run()` catches to pause cleanly - state stays resumable, nothing committed is lost. Budget is read live from settings at run start; the dashboard shows `tokens / budget`. |
| **Untrusted web content** | Every web→prompt path (search snippets, deep-research page text, the interview's quick peek) is fenced via `prompts.wrap_untrusted`: data-only markers (spoofed markers inside the content are neutralized) + a standing instruction that the block is never instructions. |
| **Revision loop** | The human review instruction survives every revision round (merged ahead of critique notes, never overwritten). Each revision passes the previous attempt as a PRIOR DRAFT - the writer revises, it doesn't regenerate from notes about text it can't see; an escalation resume revises the exact draft the human reviewed (`.draft.md`, deleted on commit). Autonomous mode commits the **best-judged** attempt (approve > fewer blocking > higher confidence), not the last one. Post-completion `revise` critiques with **pipeline-parity context** - watch-list, intake requirements, prior-unit context (canon for books, section summaries for articles), and the length target - so a revision can't pass a weaker bar than the original draft did. |
| **Closed learning loop** | The learner's watch-list (`prefs/watch_list.md`) is injected into every critic call (patterns flagged as blocking); applied craft skills are also shown to the critic. The article learner runs **before** intermediate cleanup so it actually sees the `eval_*.json` critic findings. |
| **Citations / sources** | Per-project source registry (`sources.json`, deduped by URL, first-seen order = reference numbering). Articles renumber in-text `[N]` citations at commit so they always match the final References list. Books persist research sources too; production feeds them verbatim to bibliography-style back-matter components (which are otherwise forbidden from inventing entries). |
| **Length control** | `target_words` per chapter (TOC) / section (outline; falls back to an even share of `target_word_count`). The writer gets a target note; the critic gets the actual word count and flags >±40% misses as blocking. |
| **Article cohesion** | `article_cohesion` (default on): a whole-article smoothing pass over the assembled sections (transitions, cross-section repetition, terminology) before References. Guarded - if the edit shrinks the body >40% or loses headings, the original is kept. |
| **Long-range retrieval** | `assemble_context` augments canon + dependency summaries with FTS5 excerpts from *other* committed chapters matched on the blueprint's key terms (`store.search_excerpts`). Timeline events are recorded under the actual committing chapter (LLM-reported numbers were unreliable). |
| **Export fidelity** | All exporters resolve relative `images/` references against the project root: PDF renders SVG as **vector art via xhtml2pdf's svglib** (always available - it's a hard dep; arrow markers degrade to plain lines), preferring **cairosvg rasterization** when installed (full marker fidelity); EPUB packages images as items, DOCX passes `--resource-path` to pandoc, HTML inlines images as data URIs. |
| **Diagram quality (spec → deterministic render, 2026-06-13)** | The model no longer emits SVG - it is bad at geometry, so labels overflowed and edge pills collided no matter the prompt (two prompt rounds failed). The `diagram` node now returns a **structured `DiagramSpec`** (nodes/edges/labels/archetype - what an LLM is good at) via `DIAGRAM_SPEC_SYS`, and **`diagram.py` lays it out deterministically**: text is measured (per-char widths) so boxes are sized to fit and labels wrap before overflowing; nodes are placed by archetype (column-ranked DAG for `flow`, stacked lane bands for `layered`, an evenly-spaced **ring for `cycle`**, two colour-headed **columns for `comparison`** - radius/column maths keep boxes clear; `cycle`<3 nodes or `comparison`<2 groups degrade to `flow`) so **boxes can't overlap by construction**; the ranker detects **back edges via DFS and excludes them** so a feedback/loop arrow doesn't reverse a pipeline; edges route as orthogonal elbows (adjacent) or stacked bottom channels (spanning/back) that never cross boxes; edge labels get measured white pills with collision-nudging; groups map to a consistent colour + a bottom legend; one `focus` node is emphasized. **Arrowheads are explicit polygons** (svglib drops `<marker>`, so marker-only arrows vanish in PDF). `_svg_fill_guard` (forces `fill="none"`) stays as a no-op safety net. A node-less spec → **flash-tier `diagram_fallback`** retry → minimal placeholder. Disk-cached by (model, heading, context, engine).<br>**Optional D2 backend (`diagram_engine`, default `auto`).** The same `DiagramSpec` can instead be laid out by the **[D2](https://d2lang.com) CLI with ELK** (`diagram.to_d2` → `d2 --layout elk`), which routes complex graphs (fan-out/fan-in, lane containers) better than the built-in engine - chosen after a side-by-side render comparison. D2 has no legend of its own, so `_inject_d2_legend` extends its outer viewBox and appends a colour legend matching the node borders. `engine`: `auto` (use d2 when the `d2` binary is on PATH or `$WRITINGAGENT_D2`, else built-in), `d2`, or `builtin`. The built-in engine stays the **zero-dependency default** (d2 is an ~18 MB Go binary, not required - CI and unconfigured users get built-in); any d2 failure falls back to it. |

### 15.2 Deep multi-source researcher (`deep_research`, off by default)

The "Deep Researcher" once deferred below, now built (`src/writingagent/deep_research.py`).
Opt-in via `deep_research: true` (it layers on `use_researcher`); both books and articles use it.

| Aspect | Decision |
|---|---|
| **Query expansion** | A `researcher`-model node (`nodes.propose_search_queries`) turns the chapter/section focus into a few distinct queries (core facts, recent developments, expert/critical angle, examples). Best-effort: on failure the deterministic seed query still runs. |
| **Fan-out + diversity** | The expansion LLM call runs **concurrently with a warm-up search for the seed query** (`orchestrator._deep_docs`; search results are disk-cached, so the merged pass re-reads it for free). Queries are then searched concurrently (`concurrency.gather` over `search.web_search`, one DDGS session per thread), hits merged in query order, **deduped by URL**, and capped at `max_per_domain` (2) so a brief spans multiple sites - then the top `max_sources` (6) are kept. |
| **Full-text fetch** | The kept sources have their actual page text fetched concurrently. **Fetch backend is pluggable:** if **Scrapo** (`github.com/vikast908/Scrapo`) is installed it's preferred - it returns clean page markdown and escalates HTTP -> browser -> stealth, reaching JS-rendered/soft-blocked pages; otherwise a pure-stdlib `urllib` + `html.parser` extractor is used (script/style/nav stripped, http(s) only, byte-capped, non-HTML skipped). All Scrapo coroutines share **one persistent background event loop** (no per-URL loop churn; enables session/browser reuse inside Scrapo). 7-day disk cache wraps both. Every step is non-fatal: Scrapo failure falls back to stdlib, which falls back to the snippet. `WRITINGAGENT_NO_SCRAPO=1` forces the stdlib path. |
| **Synthesis** | `nodes.deep_research` / `deep_research_article` read the numbered full-text sources and produce a brief that cites sources by number and flags agreement/disagreement. For articles the **real fetched URLs** become the persisted sources (more reliable than LLM-copied URLs), feeding the References section. |
| **Portability / cost** | Zero *required* deps - the stdlib fetch path keeps CI green on all three OSes x Python 3.10-3.13. Scrapo is an optional extra (`pip install '.[deep]'`; Python 3.11+, installs from git) for higher-fidelity fetching. Deep mode adds one query-planning LLM call + N page fetches per unit - hence opt-in. In fake/offline mode the whole path no-ops. |
| **Fetch safety** | Search results (and the LLM's query expansion behind them) decide what gets fetched, so every uncached fetch passes a gate: **SSRF guard** (host must resolve and every address must be globally routable - blocks loopback/private/link-local/cloud-metadata; the stdlib path re-validates **each redirect hop**), **robots.txt** honored per host (cached for the process; unreachable/missing robots = allow; `WRITINGAGENT_IGNORE_ROBOTS=1` skips), and a **per-host politeness interval** (`_HOST_MIN_INTERVAL`, 1s) between requests to the same host. Scrapo does its own fetching - the initial-URL guard still applies to it, and it has `SCRAPO_RESPECT_ROBOTS` for robots. |

### 15.3 Upfront-interview `write` flow (interview once, then deliver)

An alternative to the "autonomous + human as mid-run exception handler" default (§7), for users
who want "ask me everything upfront, then only come back with the finished material." Opt in per
run via the **`write`** command (the `new`→`run`→`export` path is unchanged and still available).

| Aspect | Decision |
|---|---|
| **One command** | `write` does topic → quick best-effort web peek → interview → forced-autonomous run → auto-export, with no further prompts. It never reuses an active project id (it creates one) and sets the new project active on completion. |
| **Interview** | A `planner`-model node (`nodes.interview`, schema `Interview`) turns the topic (+ chosen approach + quick research) into a small batch of tailored clarifying questions, each with a default. All are shown and answered **once** upfront; nothing is asked again. Markup-safe rendering. |
| **Intake threading** | Answers ("intake") are (a) folded into the planner/outline prompt so structure/length/audience reflect them, and (b) injected into every writer/critic call as a high-priority `requirements` block (new kwarg). A clear violation (wrong audience/length/tone, missing must-include) is BLOCKING. Persisted to `run_state` + `intake.md`. |
| **Hard-blocker facts** | Author/byline name is captured in the interview and written to `user/profile.md` (`_record_author`, never clobbers an existing profile), so Production fills bylines/copyright instead of escalating. Contradictions are auto-repaired (autonomous). Net effect: the run does not pause. |
| **Autonomous resolution** | `--autonomous` is tri-state (`--autonomous`/`--no-autonomous`/unset); unset falls back to `settings.autonomous`. (Previously a `store_true` default of `False` silently shadowed the setting, forcing non-autonomous runs that escalated repeatedly - the bug this flow's users hit.) |

### 15.4 Quality machinery - originality over slop-absence (2026-06-12)

A code review concluded the pipeline guaranteed the *floor* (no banned words, no continuity
breaks) but had no machinery for the *ceiling* (a thesis, a voice, a risk). Every node optimized
for the absence of negatives; none for the presence of a take. The fix, in order of leverage:

- **Thesis node** (`generate_thesis`, articles): one structured call at `start_article` produces a
  contestable `claim` + `stakes` + supporting arguments + a steelmanned `counterargument`/
  `rebuttal` + `non_goals`. Persisted as `thesis.md`/`.json`; injected into every writer and Critic
  call. The Critic blocks sections that cover the topic without advancing it.
- **Voice exemplars** (`brain/users/<uid>/voice/`): admired paragraphs (user-dropped, or saved by
  `/praise`) are injected into every writer call as *register to match* - showing voice beats
  describing it. The learner also reads `/praise`d passages as positive exemplars (not only the
  watch-list of negatives).
- **Surgical humanizer** (replaced the wholesale rewrite): tells are detected deterministically
  (the NO_SLOP lexicon as a regex scanner), only flagged sentences are rewritten, and each rewrite
  is guarded (inline citations + numbers preserved, length sane, tell actually gone) before
  splicing. Approved prose is never re-generated end-to-end, so a Flash paraphrase can't drift
  facts or regress the whole unit toward that model's mean. `mechanical_clean` always runs last.
- **Divergent first drafts** (`divergent_drafts`, default 2): see §5 (best-of-N).
- **Insight gate** (`min_insight`, default 3) + deterministic style metrics: see §5.
- **Table read** (`table_read`, default on): a whole-piece cold read by a *skeptical
  target-audience reader* (not a line editor) → `table_read.md` (where I got bored / stopped
  trusting it / didn't understand / what's missing). Report-only; feeds `revise`. `tableread
  --as "persona"` runs it on demand as a specific reader.
- **Researcher on by default** (`use_researcher: true`): citations are unverifiable otherwise.
  With it off, the Critic treats specific stats/attributions as fabrication risks (BLOCKING), and
  production warns when in-text `[n]` markers exist with an empty source registry.
- **Critic = deepseek-v4-pro** (insight scoring + thesis checks need real judgment). Same family
  as the writer shares its blind spots - the watch-list, deterministic metrics, and `/praise` are
  the defenses; route `critic` to any other slug in `models.yaml` for a cross-family judge.

### 15.5 Trust machinery - version history, diffs, eval (2026-06-12)

Audited the TUI against a 20-point writing-agent framework. Its core claim - *"the equivalent of
a coding agent's diff viewer is a writing agent's version comparison system; that's where trust is
won or lost"* - was exactly our weakest spot (we discarded drafts after commit). Built:

- **Version snapshots** ("git for writing"): every generated draft - divergent variants (labeled
  with temperature), each revision, the committed final, every `revise` output - is saved under
  `<project>/versions/<unit>.vNN.md`. Survives article cleanup. `versions [--chapter N]` lists;
  `read --chapter N --v K` reads one.
- **Semantic + text diff on `revise`**: a Flash Added/Removed/Improved summary + a colored unified
  diff are shown *before* applying; `[Y/n]` accept/reject in a TTY (discard touches nothing).
- **`brief`** + the dashboard goal line (§13): the goal is always visible.
- **Scorecard-lite**: clarity/structure/evidence (§5) tracked per commit, averaged on the summary
  card.
- **`eval`**: a post-hoc quality report combining deterministic metrics (words, AI-tell-sentence
  scan via the humanizer lexicon, structural metrics, citation vs. verified-source coverage) with
  a pro-model 5-dimension rubric (insight/clarity/structure/evidence/persuasiveness) whose
  strengths/weaknesses must quote the text. Calibrated against published work, not other AI output.
  Writes `eval_report.md`; weaknesses are designed to feed straight into `revise`.

**Deliberately NOT built** (a different product - a co-editor, not an autonomous pipeline):
document-first 70-80% layout, and sentence-level inline-suggestion accept/reject (our acceptance
unit is the section/chapter, correct for long-form).

### 15.6 Quality machinery II - independence, verification, compounding (2026-06-13)

§15.4 added the *ceiling* (a thesis, a voice, a take). The gap that remained: almost every
"good/bad" judgment routed through **one model judging its own output** (writer and critic are the
same family, §12.1), so quality was capped at that model's taste and the learning loop converged
*toward* it (the §8 "circular convergence on bland safe writing" risk). These four levers break
that bound - independence, verification, preference-over-score, and a real compounding signal. All
are tunable config; all fail safe (a judge/verify/loop error degrades to the prior behavior, never
a broken run).

- **Tournament judge** (`tournament_judge`, default on): when `divergent_drafts > 1`, a dedicated
  `judge` node (`nodes.rank_variants`) reads all variants **side by side** and picks the winner,
  replacing the old scalar `_crit_better` comparison of each draft's *isolated* 1-5 self-score
  (jittery and lenient). It returns a ranking, the reason the winner beats the runner-up, and the
  winner's biggest remaining weakness - which is fed into the refinement pass. Scalar comparison
  remains the fallback when the judge is off or errors; in manual runs the human still overrides.
  Both `judge` and `verifier` run at a **low temperature (0.2)** for stable, repeatable verdicts.
  **Route `judge`/`verifier` to a non-DeepSeek slug in `models.yaml` for an independent,
  cross-family comparison** - the cheapest way to decorrelate the critic's blind spots (§12.1).
  *This is left as a deliberate one-line user opt-in, not a default: the standing decision is
  DeepSeek-pro/flash-only (no other providers), so the engine does not pull in a second provider on
  its own.*
- **Claim ↔ source verification** (`verify_claims`, default on; articles): turns the critic's
  `evidence` *opinion* into a structural check. After each section draft, `nodes.verify_claims`
  checks every in-text `[N]`-cited specific claim (a stat, date, quote, attribution) against the
  actual source text it cites (threaded through `_section_fetch` as `source_text`, never persisted).
  **Severity is gated on ground-truth strength** so a default-on setting can't tank a good draft on
  weak evidence: with **deep research** (full page text) an unsupported claim is BLOCKING - it
  downgrades `approve`→`revise` and seeds a targeted revision note; with **shallow research**
  (snippets only, where a true claim may simply be absent from the snippet) it is surfaced as a
  non-blocking **nit**. No-ops entirely when verification is off, research is off (no source
  material), or the draft has no citations. (Enforcement therefore wants `deep_research: true`;
  shallow mode is advisory.)
- **Counterargument engagement** (writer prompt): the thesis already carries a steelmanned
  `counterargument`/`rebuttal` (§15.4); the article writer is now told to **engage it head-on**
  (concede what's true, then answer it) where a section naturally meets it, rather than dodging -
  optimizing for persuasion, not just coverage.
- **Closed table-read loop** (`table_read_revise`, default **off**; autonomous only): the
  skeptical-reader pass (§15.4) was report-only. A structured `nodes.reader_report` now also names
  the single highest-impact fix and the section it targets; when enabled, an autonomous run applies
  that one fix as a bounded targeted revision (`_targeted_section_revise`: write → critique → fix
  pass → humanize → patch the section file + manuscript). Default off because it mutates finished
  content; every draft is version-snapshotted (`reader-fix` label), so it is auditable and
  reversible. Canon-free (a polish, not a re-run).
- **Compounding learner** (preference data → skills, §8): every run already generates gold the
  learner threw away. Tournament outcomes (what won, why, the winner's weakness) and revisions
  (the blocking issues a fix addressed) are now recorded to `<project>/learning_signals.md` and
  fed to `nodes.learn` as a new **secondary** signal. Per §8 these are model-judged, so they yield
  **candidate skills only** - never auto-promoted to user scope (same gate as critic-only findings;
  human signal or cross-book recurrence still required). This is what makes book 10 better than
  book 1 instead of equal to it, without overfitting to the critic's taste.

### Still post-v1 (deliberately deferred)

- **Web UI** - chapter reader, escalation review with side-by-side revision diffs,
  timeline/graph browser, multi-book/user dashboard. Built only after the CLI proves the engine.
- **Salience-adaptive consolidation** - once §9 produces salience scores, let high canon-churn
  tighten the interval.
- **External notifications** - email / desktop / push, tailing the review queue.

---

## 16. Book Production layer (front + back matter, assembly)

The re-scoped survivor of the original "Post-production agent." Runs at book end, after the
final consolidation, on committed canon. Two jobs: **decide** which components the book needs,
then **generate + assemble** them into a deliverable.

### 16.1 Decide (format/genre-aware)

Driven by `book_plan.md` (genre, format, audience) + user prefs, the Production node selects the
component set - a literary novel and a technical nonfiction book need very different matter.

| Front matter | Back matter |
|---|---|
| Half-title / title page | Epilogue / afterword (fiction) |
| Copyright / colophon | Acknowledgments |
| Dedication | About the author |
| Epigraph | Appendix |
| Table of contents (from committed chapters) | Glossary |
| Foreword / preface / introduction | Notes / bibliography / references (nonfiction) |
| List of figures / maps (illustrated/nonfiction) | Index (nonfiction) |
|  | "Also by" / next-book teaser |

### 16.2 Generate + assemble

- Generates each selected component as a file under `books/<id>/frontmatter/` and
  `books/<id>/backmatter/`.
- TOC is generated from the committed chapter files/titles - never hand-written.
- Assembles the ordered deliverable **front matter → chapters → back matter** into
  `books/<id>/manuscript.md` (export formats - EPUB/PDF/DOCX - are post-v1).

### 16.3 Facts it can't invent

Copyright holder/year, author bio, dedication text, real acknowledgments, ISBN/publisher are
**facts, not prose**. Production reads what it can from `user/profile.md` + `book_plan.md`,
inserts clearly-marked placeholders for the rest, and **escalates** (same review queue, §7) for
any required-but-missing item. It never fabricates author/publishing facts.

### 16.4 Scope discipline

Production does **not** re-judge chapter prose - that's the Critic's job, done per chapter. Its
only prose work is the matter it generates plus light *global* consistency (heading styles,
formatting, front/back-matter coherence). No re-litigating the body.

### 16.5 Save location (where exports land)

The brain working dir (drafts, `manuscript.md` source, run-state) is the source of truth and never
moves. Separately, the **rendered deliverables** an `export` produces - `manuscript.{pdf,epub,html,
docx,txt}` and `manuscript_export.md` - can be written to a folder the writer chooses, while
`base_dir` (image/diagram resolution) stays the brain root. Resolution order (`brain.resolve_export_dir`):
**per-project override** (a `export_dir.txt` sidecar in the project root) → **global default**
(`settings.export_dir`, namespaced by project id) → **the project's brain root** (the original
behaviour; the empty default). An unwritable target silently falls back to the root - an export
never crashes on a bad path.

Driven by **`/path`**: no-arg opens a menu (set the default, or pick a project from the ongoing
list → enter a folder → it offers to **move** that project's existing deliverables to the new home,
source file untouched). Direct forms: `/path default <dir>`, `/path <project> <dir>`, `/path show`,
`/path clear [<project>]`. The move only ever relocates the rendered files in `EXPORT_DELIVERABLES`.

### 16.6 References, citations & figures (deterministic polish, `polish.py`)

The **producer owns** references and figures; the writer must not. `ARTICLE_WRITER_SYS` forbids the
model from drawing diagrams (mermaid/ASCII/charts), self-numbering `Figure N`/`Listing N`, writing
figure captions, or emitting bare `[N] Author…` reference lines - it only places inline `[N]` markers
in prose. At assembly (`_assemble_article`) the deterministic `polish.py` pass then:

- **References, end-only, ranked.** `score_sources` rates each source's *influence* = how often it's
  actually cited in the body (weighted) + title overlap with the thesis/headings; `build_references`
  emits one `## References` list **sorted most-influential first**, each line `N. **score** · date ·
  [title](url)` (0–100). Dates normalized (`n.d.` when unknown). Zero-influence noise is pruned only
  when there's signal to rank against. `rank_references` setting (default on).
- **Source authority (citation-quality gate, deterministic).** `source_authority(url)` scores each
  source's domain 0–100 (`AUTH_HIGH` gov/standards/primary research · `AUTH_REPUTABLE` established
  outlets & official docs · `AUTH_NEUTRAL` unknown — absence of signal is not a penalty · `AUTH_LOW`
  SEO/template/content-farm signals). Authority **breaks influence ties** (a heavily-cited low-authority
  pad ranks below an equally-cited credible source) and lets `build_references` drop an *uncited
  low-authority* pad. The evidence report surfaces it (high-authority count, average authority, and a
  ⚠️ flag when low-authority sources are present). All tiers/tables are tunable constants in `polish.py`.
  This closes the blind-A/B "citation quantity ≫ quality" loophole *deterministically*; the critic
  prompts (`ARTICLE_CRITIC_SYS` / `CRITIC_SYS`) reinforce it by flagging a *decorative* citation (source
  doesn't back its sentence) as BLOCKING, with padding/low-authority/off-topic raised only as nits (not
  blocking, to avoid revision thrash).
- **Citations stripped.** `strip_inline_citations` (setting, default on) removes every `[N]` from the
  prose *after* scoring, so the body reads clean and all sourcing lives in the end list.
- **Stray dumps removed.** `strip_reference_dumps` pulls writer-emitted reference lists out of the
  body (headed blocks *and* bare `[N] …` runs) - references never appear mid-article.
- **Figures de-duped.** `strip_model_figures` (going forward) drops any diagram the model still drew;
  `dedupe_figures` (for existing manuscripts) removes the model's `Figure N.N` caption-heading and a
  redundant embedded SVG when a diagram is already present, so a figure never appears twice.

**`polish` command / `repolish_manuscript(uid, id, settings)`** re-applies all of the above to an
*existing* manuscript with **no LLM call** (≈0 tokens) and refreshes the exports - the cheap way to
fix an already-generated article.

**Evidence report (`polish.build_evidence_report` → `evidence_report.md`).** A shareable trust
artifact built deterministically from the finished manuscript: the thesis it argues + every source
ranked by influence (the same 0-100 score the References list carries). Auto-generated at assembly,
refreshed by `polish`, and regenerable via the **`evidence`** command / `Project.evidence_report()`.
It makes the otherwise-invisible quality machinery visible - the OSS "show, don't tell" of the
"argues a thesis, cites real sources" claim (see `PRD.md`).

**Figure engine.** `diagram_engine: auto` (the default) now uses the **built-in** engine - it measures
text and lays out compactly (a ~590px figure with title, lane headers, readable boxes), and the
comparison archetype **de-duplicates repeated relationship labels** (`provides`×3 → ×1) so edge labels
never stack/overlap. **D2+ELK is explicit opt-in** (`diagram_engine: d2`) - it tends to render very
wide (~1700px), hard-to-read figures, so it is no longer auto-selected just because the `d2` binary is
present.

**Glanceability rule (figure content).** Every figure must obey the **3-second-glance test**: if a
reader can't explain it after a 3-second glance, it carries too much for a visual - cut detail, drop
non-essential nodes/edges, or split it into two figures. Encoded in `DIAGRAM_SPEC_SYS` (the spec the
model authors) alongside the "ONE idea / 5-9 nodes, 12 max" budget; it governs both the pro and the
`diagram_fallback` paths.

---

## 17. Working process - `resume.md` (session continuity)

Build work spans multiple Claude sessions, so progress is journaled at the project root.

- **`plan.md`** = the spec (durable decisions; what to build).
- **`resume.md`** = the log (what happened, what's next; newest entry on top).
- **`CLAUDE.md`** = a pointer telling each new session to read `resume.md` then `plan.md` first.

Rule: at the **start** of a session, read `resume.md` → `plan.md`. At the **end**, prepend a
dated entry to `resume.md` (changes, decisions, concrete next step) and move any durable
decision into `plan.md`. Never duplicate content between the two.

---

## 18. Public Python API (stable embedding surface)

**Why:** the internals (`orchestrator`, `nodes`, `brain`, …) are importable but explicitly
unstable pre-1.0. `writingagent.api` is a thin **facade** that gives integrators a supported,
semver-guaranteed surface to embed the pipeline in their own programs, while leaving the internals
free to change. The CLI/TUI and the API are siblings over the same orchestrator - neither wraps the
other.

**Shape:** an `Agent` + `Project` facade (chosen over a bare one-shot so the *whole* lifecycle -
create, run, **resume a paused run**, revise, evaluate, export - is reachable from code), with a
one-shot `write()` convenience layered on top.

- **`Agent(*, user, settings, models, autonomous, **overrides)`** - bundles the per-call plumbing
  (`user`, `Settings`, `ModelConfig`) so callers don't thread it. `**overrides` are validated
  against `Settings` fields; `models=` accepts a `ModelConfig` or a slug string (→ `set_all`).
  Methods: `plan(topic, mode=, n=) -> [Approach]`, `create(...) -> Project`, `write(...) ->
  WriteResult`, `open(id) -> Project`, `projects() -> [Project]`.
- **`Project`** - a cheap handle (all state on disk). `run(progress=, autonomous=, force=)`,
  `status() -> Status`, `review(unit, instruction)` (answers an escalation), `revise(unit,
  instruction, confirm=)`, `evaluate() -> Evaluation`, `table_read(persona=)`, `read(unit=,
  manuscript=, summary=, version=)`, `word_count()`, `memory()`, `consolidate()`, `produce()`,
  `export(fmt) -> Path`, `delete()`.
- **Value types** (frozen dataclasses, *not* the internal pydantic schemas, so the wire shape is
  stable): `Approach`, `Status`, `Evaluation`, `WriteResult`. `Status` normalizes the book/article
  run-state split into `mode/phase/unit/total_units/committed/pending_review/done/open_reviews`
  (+ `raw`).

**Design decisions:**
- **Non-interactive by default.** `create`/`write` auto-pick the first creative approach; callers
  override with `approach=` (a 1-based `int`, an `Approach` from `plan()`, or a
  `selector(list[Approach]) -> Approach|int` callback). The CLI's interactive "pick a direction"
  gate is a CLI concern, not the library's.
- **Sync + `progress` callback**, matching the synchronous, network-bound engine (the orchestrator
  already takes `log=`). Async is intentionally *not* in the surface - it's a `to_thread` wrapper
  away if a caller needs it.
- **`requirements`** (str or dict) is the library's door to the same intake the upfront-interview
  (§15.3) feeds the writer/critic; `write()` always runs autonomously (a one-shot can't answer a
  review prompt).
- **Lazy exports.** `writingagent/__init__.py` resolves the public names via PEP-562 `__getattr__`,
  so `import writingagent` / `from writingagent import brain` stay cheap and never eagerly pull the
  whole pipeline.
- **Versioning.** `writingagent.__version__` (kept in step with `pyproject`'s); the API module's
  docstring states the no-break-within-major contract. Surface is covered by `tests/test_api.py`
  (offline, `WRITINGAGENT_FAKE`).

### 18.1 Zero-install web demo (`web/app.py`)

**Why:** the terminal + own-API-key requirement is `PRD.md`'s #1 adoption barrier - a non-developer
can't try the product at all. A hosted browser demo is the try-before-you-build front door.

**Shape:** a small **Gradio** front-end built *only* on the public `Agent`/`Project` facade (§18) -
it never imports an internal module, so it stays stable across releases. Topic + mode + size in;
live progress, the manuscript, the evidence report, and a `.md` download out.

- **Free preview (default).** No key: `configure_runtime` forces `WRITINGAGENT_FAKE=1`, so the whole
  pipeline runs offline with placeholder output - a visitor sees the *shape* of a run (plan → draft →
  critique → verify → humanize → assemble) at zero cost and zero setup.
- **Real run (BYO key).** A toggle reveals a provider dropdown + key field; the key is installed on
  the provider's env var for that run only (nothing persisted), fake mode is cleared, and the run
  produces a genuine piece with a populated evidence report.
- **Streaming.** The blocking `Project.run(progress=)` runs in a worker thread; its log lines flow
  through a queue into the Gradio generator so progress is live.
- **Packaging.** A `[web]` optional extra (gradio only); gradio is imported **lazily** (inside
  `build_ui`) so the runtime helpers stay importable/testable without it (mirrors `deep`/`headroom`).
  Ships HF-Space deploy files (`web/requirements.txt`, `web/README.md` front-matter). Covered by
  `tests/test_web.py` (offline, incl. a full fake-mode run through the demo).
- **Caveat (tracked):** `configure_runtime` mutates process-global env, so a public deploy must stay
  single-worker (the Gradio default) or serialize runs; a key-less public deploy needs a server-side
  key + rate-limiting first.

---

## Appendix - what we borrowed (traceability)

**From Hermes (NousResearch):** markdown skill format (agentskills.io), "create a skill after a
complex/successful task" trigger, `USER.md`-style user modeling across sessions, FTS +
summarization recall. *Left:* gateways, terminal backends, trajectory-training. *Caution:*
Hermes's auto-skill-creation lacks a clear validation gate - we add efficacy validation (§8).

**From GBrain (Garry Tan):** markdown = source of truth with a synced derived index,
frontmatter + timeline per page, self-wiring entity graph (no LLM), wikilinks, the "Dream
Cycle" → our Consolidation pass, cached LLM contradiction judge, PGLite→Postgres path,
brain⊥source multi-tenancy. *Left:* CRM/VC schema (people/companies/deals), domain-tuned
source-tier boosting. The *mechanisms* transfer; the *entity types* are replaced with
narrative ones.

**From the discussion:** collapse 10 agents → the set in §4; drop the 100-point rubric for
blocking/nits + confidence; per-user (not per-book) learning, genre-relevance retrieved;
fully autonomous with human escalation via directed instructions; CLI-first. *Later additions:*
per-node model routing (§12.1); a Book Production layer for front/back matter + assembly (§16,
re-scoped from the original Post-production agent); a `resume.md` session-log convention (§17).

---

## 19. Token & cost efficiency

Reviewed against real telemetry (`.index/telemetry`): prompt tokens dominate (~58% of spend) and are
mostly **repeated prefixes** across the ~16-21 calls per unit. The architecture is already
cache-friendly - every node sends a **stable system prefix** (`prompts.py` constants + the JSON-schema
dump) with the **variable content in the user message** - so the dominant lever is the provider's
prompt-cache discount, not prompt rewriting. Durable decisions:

- **Prefix stability is an invariant.** Keep static instruction in the system block and per-unit
  content in the user message, so the system prefix is byte-identical across calls and the provider
  caches it. Cache hits are measured via both `prompt_tokens_details.cached_tokens` (OpenAI /
  OpenRouter) and `prompt_cache_hit_tokens` (DeepSeek-direct), surfaced in `usage_summary` + the JSONL.
- **Claim the cache discount (OpenRouter caveat, measured).** OpenRouter load-balances DeepSeek across
  upstreams and only some support caching, so by default `cached_tokens` stays 0 (verified live:
  default routing never cached). Setting **`openrouter_providers: DeepSeek`** (→ request
  `provider.order`, fallbacks kept on) pins the caching-capable backend - a live 2-call check then
  cached ~80% of the prompt prefix at ~3.5x lower cost. It's not 100% reliable over OpenRouter
  (instance load-balancing), so for guaranteed caching prefer **DeepSeek-direct** (`provider=deepseek`),
  whose context cache is automatic.
- **`use_headroom` defaults OFF.** Compression saved ~nothing on single-turn payloads and risked
  perturbing the cacheable prefix.
- **Schema dump is lossless-minimized** (`llm._strip_schema_noise` drops pydantic's auto `title`s).
- **Thesis is split** (`nodes.thesis_brief`): writer gets the full thesis (it must engage the
  counterargument), critic + judge get claim+arguments only.
- **Per-node `max_tokens`** via `models.yaml` `max_tokens:` + `ModelConfig.max_tokens_for` (a tuning
  lever; defaults already tight - summaries 600-1500, verify excerpts capped at 1500 chars/source).
- **`divergent_skeletons`** (opt-in, default off): draft the divergent variants short, judge, then
  expand only the winner - cuts discarded-draft completion ~60% at some loss of selection signal, so
  it is a deliberate quality/cost trade left to the operator.
- **Do NOT shrink** `NO_SLOP`, the scoring rubric, or the thesis machinery for tokens - cache them
  instead; trimming raises slop/insight-miss rates and triggers *more* revision loops (net increase).

---

## 20. Refactor backlog - book↔article de-duplication

The book (chapter) and article (section) pipelines run near-parallel code in the `orchestrator/`
package (`book.py` / `article.py`, shared tail in `common.py`) and the `shell/` package - the repo's
#1 redundancy (~hundreds of lines). It must be paid down **incrementally and test-gated**: these paths have a history of *silent drift* (the revise-parity
bug), so behavior-preserving extraction + the full suite (and ideally a live run) between steps is
mandatory. Already shared (do not re-extract): `_pick_variant`, `_save_version`, `_record_preference`,
`_length_note`, `_merge_fix_notes`, `_escalate`. **Done:** `_run_learner` (shared learner tail);
`_base_run_state` (shared run-state keys for `start_book`/`start_article`); `_divergent_first_draft` +
`_finalize_unit` (shared attempt-0 divergent drafting and post-loop bookkeeping - Tier 2);
`_mark_escalated` + `_log_run_complete` (shared run-loop escalation + completion footer - Tier 3).

Prioritized, by risk:

- **Tier 1:** ✅ `_base_run_state` (the shared run-state dict; mode-specific keys spread in by each
  caller) - **done**. ❌ `_commit`/`_commit_section` - **evaluated and deliberately NOT merged**: the
  paths differ structurally (canon-extraction + Store updates vs citation-renumber-before-gather), so a
  shared helper would be callback-soup that reads worse than the ~8 duplicated lines. Leave separate.
- **Tier 2 (MEDIUM):** ✅ `_divergent_first_draft` (attempt-0 divergent drafting: N variants at varied
  temps → critique → side-by-side judge picks the winner; article-only skeleton-expand behind a flag) and
  ✅ `_finalize_unit` (post-loop bookkeeping: best-judged fallback in autonomous mode, `first_pass`,
  insight/score history) - **done**. Both take the unit's own `_write`/`_critique` closures (the only
  mode-specific leaves) so the control flow stays linear in one place - the chunk most prone to silent
  drift now has a single source. ❌ `_chapter_fetch`/`_section_fetch` - **evaluated and NOT merged**: the
  only shared line is the `concurrency.gather({...})` call itself; the three strategy fns differ in
  schema, node calls, return arity, path naming, and gating, so a wrapper is pure indirection. ❌ the
  full per-attempt revision loop - **NOT merged**: it's woven with `break`/`continue` and mutates five
  locals (`best`, `approved_attempt`, `fix_notes`, `judge_note`, `base_draft`); extracting it needs
  signal-return callback-soup that reads worse than the duplication. Leave the loop bodies inline.
- **Tier 3 (evaluated):** ✅ `_mark_escalated` (durable pending-review + resolver hint) and
  `_log_run_complete` (done line + usage summary) - two pure, byte-identical idioms pulled out of both
  run loops - **done**. ❌ the `run()`/`_run_article()` **phase-machine loop unification** - **evaluated
  and deliberately NOT merged**: the two machines share only a shape - they differ in phase *set* (book
  chapters/consolidate/production/learn vs article sections/produce/learn), in the `Store` lifecycle (book
  opens/closes it, article is stateless), and in book's consolidation-interleave + pending-review
  branching that has no article analog. A shared loop would be a dispatch table of closures over a dozen
  shared mutable locals (cfg/paths/plan/toc/store/prefetch/pool/...) plus signal-return control flow -
  strictly worse to read than two linear machines. Revisit only if a 3rd pipeline variant appears.
- **Keep separate (semantically different, by design):** context assembly (book persistent Store vs
  article stateless summaries), production (front/back-matter vs cohesion+polish), and the per-mode
  learner inputs.

Each tier is its own PR: extract, run the suite, and a fake-mode end-to-end for BOTH modes before the
next.

## 20.1 File split - orchestrator, shell, cli (all done)

Once dedup was paid down, the god-files were split into packages behind a stable facade so
`orchestrator.X` / `shell.X` / `cli.X` resolve unchanged for every caller and test (incl. the private
names tests reach for). Pure code movement, suite-gated per step.

- **`orchestrator/` - done.** 2274-line module → facade `__init__` (re-exports via `from .seam import *`)
  + six seams: `common` (shared leaf helpers), `book` (chapter pipeline + the public `run()` dispatcher),
  `article` (section pipeline), `export` (renderers/repolish/evidence), `manage` (lifecycle/state),
  `review` (approve/revise/table-read/evaluate). Acyclic: common ← {article,book,manage}; article ←
  export; book ← {article,manage}; review ← {book,article,common}. Genuinely-shared leaves that surfaced
  during the carve (`_escalate`, `_manuscript_section_bodies`, `_replace_manuscript_section`) went to
  `common`. A ruff per-file-ignore (`__init__.py` = F401/F403/F405) marks the intentional star re-exports.
- **`shell/` - done.** Facade `__init__` + seven seams: `_const` (glyphs/vocab/regexes/chat-prompt),
  `branding` (banner/wordmark/flame/palette/welcome/`_section`/`_cmd_table`), `help` (tables/slash-help/
  toggle-grid/model-catalog), `commands` (`_cmd_*` + path/provider/model/set/auto/praise/skills/use-
  project), `dashboard` (`_RunControls`/`_KeyListener`/`_RunDashboard`/cards/`run_with_dashboard`), `chat`
  (respond/history/hints/system), `repl` (`run_shell`/`_handle_slash`/pt-session/input routing). Acyclic
  except `chat._chat_respond → repl` (broken by a lazy import). The split surfaced two real fixes worth
  remembering: **`_sync_palette` must refresh every seam + the facade** (each from-imports the ui palette
  at import time, so a live `/theme` switch has to rebind all copies), and the **facade re-exports the ui
  palette** (`shell.GOLD` etc.). Per-file-ignore F401/F403/F405 on the facade `__init__`.
  - `shell/repl.py` was itself split further (it was 816 lines): `dispatch` (input interpretation +
    `_execute_cmd`), `slash` (`_handle_slash`), `session` (`_make_pt_session`), and `repl` (now just
    `_prompt_state` + `run_shell`). The chat→dispatcher lazy back-edge points at `dispatch`. No shell
    file now exceeds ~580 lines.
- **`cli/` - done (C-011).** 1003-line module → facade `__init__` + six seams: `_common` (console /
  project+path resolution / spinner / unified diff), `create` (`new` + the manual-mode outline gate +
  `_autonomous_value`), `interview` (the autonomous `write` flow), `commands` (the core project commands -
  run/status/review/revise/versions/brief/tableread/eval/read/memory/produce/consolidate/skills/delete/
  list/config), `export` (export/polish/evidence - format parsing + isolated per-format failures), `app`
  (`_COMMANDS` registry, `build_parser`, `_apply_provider`, `main`). Acyclic: `_common` ←
  {create,interview,commands,export,app}; export ← {interview,app}; {create,interview,commands} ← app.
  Largest seam is 301 lines. The facade re-exports the private names the suite patches/reads
  (`_resolve_formats`, `_EXPORT_FORMATS`, `_EXPORT_FNS`, `_paths_for`, `_export_failed`, `_autonomous_value`,
  `_conduct_interview`); **as with the shell split, tests that monkeypatch a now-relocated global
  (`_console`, `_EXPORT_FNS`) patch it at its seam home** (`cli.export` / `cli.interview`), since a
  function resolves its globals in its defining module, not the facade. Per-file-ignore F401/F403/F405.

---

## 21. Agentic controller (self-directing loop over the existing pipeline)

> **Goal.** Make the system *self-directing* (an agent that chooses its next move) and not just
> *self-correcting* (a fixed pipeline with quality gates). This consciously revisits the §12 caveat
> ("don't let nodes be more agentic than they need") - correct for v1, now the thing we want. The
> entire design is built so that turning agency **on** cannot regress the existing pipeline or the
> self-improving loop: it ships behind a default-**off** toggle and the fixed pipeline remains the
> agent's fallback policy.

> **Implementation status (2026-06-16 - BUILT, two-tier controller, opt-in).** Shipped as the
> `agentic/` package (`tools` · `controller` (unit) · `runner` (run) · `policy` · `panels` · `trace` ·
> `_schema`) + `CONTROLLER_SYS`/`RUN_CONTROLLER_SYS` in `prompts.py`. `Settings.agentic` (default
> **False**) bakes `controller` into run-state via `_base_run_state`. **Two decision scopes now exist:**
> a **unit controller** (`run_unit`: gather research/`read_canon` then draft one unit) and a **run
> controller** (`run_loop`: choose the next MACRO-action over the whole piece - draft / consolidate /
> repair / produce / learn / done - instead of the hardcoded `while phase != done`). Both share the
> default/llm/trace policy design. **Routing:** `agentic_policy == "default"` stays on the legacy phase
> loop (so the equivalence guarantee + the unit-only trace are byte-identical); `llm`/`trace` policies
> drive `run_loop` (macro agency) with the unit controller inside each `draft`. The fixed pipeline is
> always the floor (`DefaultPolicy`/`DefaultRunPolicy` == the legacy order; the guard maps any illegal
> pick to it). **`read_canon` is now query-relevant** (FTS slice via `store.search_excerpts`, not the
> whole canon block). **`TracePolicy`/`TraceRunPolicy` are activated** as online trace-conditioned
> policies (the unit policy gathers research up front once the trace shows a prior evidence gap; the run
> policy audits continuity early once the trace shows a past contradiction) - the swap point for a
> fully-trained π remains. Phase 4 is `panels.fact_check_panel` (article + `deep_research`, behind
> `agentic_factcheck_panel`). **TUI surface:** `/agentic on|off|llm|default`, `/trace`, a controller line
> in the dashboard. Opt-in is free: `Agent(agentic=True, agentic_policy="llm")` and `/set agentic true`.
> **41 offline tests** (`tests/test_agentic.py` 31 + `tests/test_agentic_tui.py` 9 + `test_agentic_tui`),
> including the equivalence guarantee and full macro runs of both pipelines through `run_loop`. Full
> suite green (424 passed / 2 skipped), agentic code ruff-clean. **In-generation tool use is now built**
> (`llm.complete_text_with_tools` - a real OpenAI tool-use loop; the writer may call `research`/
> `read_canon` WHILE drafting, behind `agentic_inline_tools`, falling back to a plain draft on any
> provider/tool error). **The learned policy is now built** (`agentic/learn.py`): `train_policy` distills
> a model from the accumulated trace corpus (off-policy value estimation - does gathering lift the
> first-pass rate?), persisted per user and refreshed at every learn phase; `TracePolicy`/`TraceRunPolicy`
> consult it (a learned model overrides the online heuristic).
>
> **"Fully agentic" batch (2026-06-16).** Eight gaps from the self-review closed: (1) **rich perception**
> (per-unit quality + weakest unit, open contradictions, token budget in the run/unit views); (2)
> **`reoutline`** (regenerate the un-written units' plan) and (4) the same available *before* drafting =
> agentic start-of-run structural agency; (3) **`revise`** the weakest committed unit (re-processes it,
> idempotent, capped); (5) **`escalate`** as a deliberate defer-to-human choice; (6) **context-conditioned
> learned policy** (book vs. article, composite first-pass+insight reward); (7) a **`verify_fact`**
> in-generation tool + a diverse-lens **`critique_panel`** (`agentic_critique_panel`); (8) **self-monitoring**
> (budget in the view + a guard dropping optional polish actions under budget pressure). All new macro
> actions are `llm`/`trace`-only (default == legacy → equivalence holds), bounded by `_MAX_REOUTLINE`/
> `_MAX_REVISE` + the token budget. The only things left are *scale*, not code: live tool-call validation
> on a tool-capable provider, and a trace corpus large enough for the learned policy to bite (it correctly
> stays undecided on thin data). Suite 432 passed / 2 skipped, ruff clean.

### 21.0 The three invariants (what must never break)

Everything below is constrained by three things that stay exactly as they are today:

1. **The brain is the world model.** Markdown canon + entity graph + synced index (§3) is the
   substrate the agent perceives and mutates. We do not rebuild or bypass it.
2. **`WRITE → CRITIQUE` is one atomic, instrumented episode.** The agent decides *when* to draft and
   *what to do first/next*, never *how to bypass the critic*. Every draft still flows through
   `critique_*` and still calls `skills.record_chapter` / `record_duel`. Agency lives **between**
   episodes, not inside them.
3. **The efficacy gate owns promotion.** §8's `candidate → trusted → retired` machinery (first-pass
   lift, ablation duels, `reconcile`) is untouched. The controller's *own* choices are a new
   candidate signal, logged and quarantined - **never auto-promoted** (same circularity guard §8
   already applies to model-taste).

The mechanism that enforces invariant #2 cheaply: **tools wrap existing orchestrator functions at
their current granularity.** `draft_unit` *is* `_process_chapter` / `_process_article_section`
(`book.py:294`, `article.py:232`) - the full divergent-draft + duel + revise-loop + commit +
`record_chapter`. The controller calls it as one tool; the measured episode is literally the same
code. There is no raw `write_chapter` tool that could bypass critique.

### 21.1 Layers

| Layer | Status today | Change |
|---|---|---|
| **State / world model** (the brain) | strong - §3 | none; the agent reads/writes through it |
| **Action interface** (tools) | implicit - node fns wired in fixed order | **Phase 0**: expose existing fns as a typed registry |
| **Controller** (picks next action) | hardcoded `while phase != done` + threshold gates | **Phase 1+**: a policy that *chooses* the next tool, with the fixed loop as the default/fallback |

### 21.2 The tool registry (Phase 0)

New module `agentic/tools.py`. A `Tool` is `{name, description, params (Pydantic/JSON-schema), fn,
mutates: bool}`. Each tool is a thin adapter over a function that already exists - **pure refactor,
no behavior change.** Granularity is the existing function, not the raw LLM call.

| Tool | Wraps | Returns | Notes |
|---|---|---|---|
| `research(query?)` | `propose_search_queries`+`research`/`deep_research(_article)` | brief attached to ctx | the shallow/deep researcher (§15.2) on demand |
| `read_canon(query\|entity)` | `store.canon_context` / retrieval (§10) | markdown slice | relevant-slice pull from the graph |
| `outline()` / `reoutline(guidance?)` | `build_toc` / `build_article_outline` | TOC/outline | re-plan structure |
| `draft_unit(n, fix_notes?)` | **`_process_chapter` / `_process_article_section`** | `{outcome: commit\|escalate, critique}` | **the atomic episode** - duel + revise-loop + `record_chapter` happen inside, unchanged |
| `revise_unit(n, instruction)` | `review.revise` path | diff summary | post-commit single-unit rewrite (§7) |
| `verify_claims(n)` | `_verify_claims_gate` / `verify_claims` | claim audit | evidence gate (§15.6) |
| `consolidate()` | `_consolidation` | `ConsolidationReport` | cross-unit audit (§9) |
| `repair_contradiction(n)` | `_repair_contradictions` | none | autonomous fix |
| `produce()` | `_production` | none | front/back matter + assembly (§16) |
| `learn()` | `_run_learner` | `LearnerOutput` | distill skills/watch-list (§8) |
| `evaluate()` / `table_read(persona?)` | `evaluate_manuscript` / `table_read` | report | quality reads (§15.4) |
| `escalate(reason)` | `_escalate` + `_mark_escalated` | none | hand to human |
| `done()` | sets `phase="done"` | none | terminal |

Tools that mutate canon (`draft_unit`, `commit`-side-effects, `repair_contradiction`) carry
`mutates: true` and run through the guard (§21.4). The registry is the only thing the controller can
call - capability is bounded by what's in the table.

> **Shipped scope (2026-06-16).** Two registries are now policy-selectable. The **unit** tools
> (`UNIT_ACTIONS`: `draft`, `research`, `read_canon`) are chosen by the unit controller before each
> draft. The **run/macro** tools (`RUN_ACTIONS`: `draft`, `consolidate`, `repair`, `table_read`,
> `produce`, `learn`, `done`) are chosen by the run controller (`runner.run_loop`) - so the phase
> machine is no longer hardcoded for `llm`/`trace` policies; the policy decides when to draft, audit
> continuity, repair, produce, and finish (the legal subset per step comes from `RunOps.legal_actions`).
> Still future work as *controller-selectable*: `outline`/`reoutline`, `revise_unit`, and a standalone
> `verify_claims`/`evaluate` action (the verify gate + fact-check panel already run inside `draft`).

### 21.3 The controller seam (Phase 1)

New module `agentic/controller.py`. The loop mirrors `pi-agent-core`'s shape (perceive → decide →
guard → act → record), with the existing state machine as the **default policy** and **fallback**:

```python
def controller_run(cfg, state, paths, registry, control, log):
    while state["phase"] != "done":
        view   = build_state_view(state, paths)              # perceive (compact, see 21.6)
        action = policy.next_action(view, registry.schemas)  # decide  (default policy or LLM, 21.3.1)
        action = before_tool(action, state, registry)        # guard   (21.4) - may rewrite to fallback
        result = registry[action.name](cfg, paths, state, **action.args)  # act (may be an episode)
        after_tool(action, result, state, paths)             # record  (21.4) - trace + persist
        if _apply_run_control(control, state, paths, log):   # existing live pause/manual hook
            return state
        if result and result.get("outcome") == "escalate" and not state["autonomous"]:
            return state                                     # pause for human (unchanged contract)
    return state
```

`next_default_action(state)` returns **exactly what today's loop would do** (chapters → consolidate
→ production → learn → done; within `chapters`, draft the next uncommitted unit). With the LLM
policy disabled, `controller_run` must produce **byte-identical output to the legacy `run()`** - this
equivalence is the Phase-1 acceptance test and the core safety proof.

**Dispatch.** In `run()` (`book.py:100`) and `_run_article` (`article.py:110`), after loading state:
`if state.get("controller") == "agentic": return agentic.controller_run(...)` else the existing loop.
`agentic` sits *above* the orchestrator seams (imports `common`/`book`/`article`); the dispatch uses a
**lazy import** to keep the DAG acyclic - the same pattern as the existing `chat → repl` back-edge.

#### 21.3.1 Policy = default | LLM (Phase 2)

`policy.next_action` has two implementations behind one interface (the seam that Phase 5 later
swaps):
- **`DefaultPolicy`** - the hardcoded state machine (Phase 1). Always legal, deterministic.
- **`LlmPolicy`** - a ReAct-style call (Phase 2): a `CONTROLLER_SYS` prompt (new in `prompts.py`) +
  the compact state view + the tool schemas → one tool choice + args. Routed to a configurable model
  (`agentic_controller_model`, §21.7) since controller reasoning is light. **On any parse failure,
  illegal action, or budget pressure it returns `DefaultPolicy.next_action(...)`** - the fixed
  pipeline is always the floor.

### 21.4 Guard + record hooks (where safety and learning are enforced)

These mirror `pi`'s `beforeToolCall` / `afterToolCall` - the seam that makes invariants #2/#3 hold.

**`before_tool(action, state, registry)`** - runs before execution, can rewrite the action to a
fallback:
- **Legality**: can't `commit`/`verify` a unit not yet drafted; can't `produce` before all units
  committed; unknown tool → `DefaultPolicy`. Illegal → fallback (never crash).
- **Revision cap**: `draft_unit` enforces `max_revisions` internally (unchanged); the guard also
  blocks re-drafting an **already-committed** unit (the existing `if paths.ch(n) exists` resume guard
  protects canon) → maps to the next legal action.
- **Budget kill-switch**: on `llm.BudgetExceeded` pressure → force `escalate`/`done` + checkpoint
  (reuses §15.1).
- **Loop bound**: the per-unit `agentic_max_unit_steps` (default 3) caps gathering steps before the
  guard forces `draft` (so every unit terminates in ≤ N+1 controller decisions). The run-wide
  runaway kill-switch is the token budget (§15.1, `BudgetExceeded`); `state["agent_steps"]` is a
  recorded per-decision counter (telemetry / trace), not itself an enforced cap. *(A dedicated
  lifetime step cap for a future learned policy is a noted TODO, not yet wired.)*

**`after_tool(action, result, state, paths)`** - runs after execution:
- Appends `{step, action, args, result_summary, unit, phase}` to **`agent_trace.jsonl`** (new
  append-only file per project, sibling of `revision_log.md`). Auditable now; the training corpus for
  Phase 5 later. (Echoes `pi`'s session-sharing ethos - logged traces are the policy-learning fuel.)
- **Does not touch the learning index.** `record_chapter` / `record_duel` already fired *inside*
  `draft_unit`. The controller's choices are logged to the trace as candidate signal only -
  quarantined behind the §8 efficacy gate, never auto-promoted.

### 21.5 Episode & duel integrity (the proof invariant #2/#3 hold)

Because `draft_unit` *is* the unchanged `_process_chapter` / `_process_article_section`:
- the divergent-draft + ablation **duel** (`common.py:496`, same temp, same context, only the skill
  list differs) fires exactly as today when `skill_duels` is on;
- `record_chapter(uid, applied_names, first_pass)` and `record_duel(uid, name, won)` are called with
  identical arguments;
- `reconcile` / `distill` (post-hoc, §8) are untouched.

**Acceptance test (the guard against silent regression):** on the same fake-LLM input, an agentic run
driven by `DefaultPolicy` produces the **same committed text, the same episode count, and the same
duel count** as the legacy pipeline. If those three match, the self-improving loop provably still
sees the same signal.

### 21.6 State & resume

`run_state.json` (§6 durable checkpoint) gains these keys, set in `_base_run_state`
(`common.py`) alongside the existing toggles: `controller` (`"pipeline" | "agentic"`, default
`"pipeline"`), `agentic_policy`, `agentic_controller_model`, `agentic_max_unit_steps`,
`agentic_factcheck_panel`, and `agent_steps: int` (a recorded per-decision counter). The compact
state view is **not** persisted - it's rebuilt each step from the durable state.

`build_state_view(state, paths)` produces the compact perception the policy reasons over: current
phase + unit, last critique (verdict/confidence/insight/blocking), open contradictions, committed
count vs. total, budget remaining, and the retrieved skill names for this unit. Kept small (cache-
friendly, §19).

**Resume is free**: the controller re-enters `controller_run`, rebuilds the view from durable state,
and continues. `draft_unit`'s own resume guard (committed file exists → skip) means a re-run never
re-drafts or double-records. Escalation pause/approve (`approve_escalation`, `record_instruction`,
`apply_autonomous`) work unchanged - the agentic path returns `state` on escalate exactly like the
pipeline.

### 21.7 Config (tunable, per CLAUDE.md)

Added to `Settings`, threaded through `_base_run_state` like the existing toggles (these are the
five fields actually shipped):
- `agentic: bool = False` - master switch. **Default off ⇒ today's behavior, zero risk.**
- `agentic_policy: str = "default"` - `default` (== fixed pipeline) | `llm` (ReAct controller) |
  `trace` (Phase-5 seam).
- `agentic_controller_model: str = "judge"` - per-node routing key for the `llm` policy's model
  (light reasoning; a flash/judge tier via `models.yaml`, §12.1).
- `agentic_max_unit_steps: int = 3` - max research/read_canon gathering steps before a unit is drafted.
- `agentic_factcheck_panel: bool = False` - majority-vote fact-check panel (§21.10; article + deep
  research only).

### 21.8 Public API & UX surface

- `Agent(agentic=True, agentic_policy="llm", ...)` opts in via the generic `Settings` override path
  (`dataclasses.replace`), baking `controller="agentic"` at create time. There is **no**
  `Project.run(agentic=)` arg; flip an **existing** project with `orchestrator.apply_controller`
  (mirrors `apply_autonomous`) or the shell `/agentic on`. Default stays `"pipeline"` ⇒
  backward-compatible; web demo + one-shot `write()` are unaffected unless opted in.
- Shell: a dedicated **`/agentic on|off|llm|default`** command (`shell/commands._cmd_agentic`,
  registered in `_const`/`slash`/`help`) that toggles the setting *and* flips the live project via
  `apply_controller`; **`/trace`** prints the project's `agent_trace.jsonl`; and the run dashboard
  surfaces the latest controller decision. (Not in the `/features` bool grid - it's policy-bearing.)

### 21.9 Build order (end-to-end, suite-gated per step)

| Phase | Deliverable | Gate (offline fake-LLM) |
|---|---|---|
| **0. Tool registry** | `agentic/tools.py` - existing fns wrapped, schemas, registry. No control-flow change. | each tool callable; schema validates; output identical to direct call |
| **1. Controller seam + default policy** | `agentic/controller.py` (`controller_run`, `DefaultPolicy`, `before/after_tool`, `build_state_view`); `run()`/`_run_article` dispatch; `run_state` keys; `Settings.agentic`. LLM policy **off**. | **equivalence test**: agentic+DefaultPolicy == legacy pipeline (text, episode count, duel count); resume mid-run |
| **2. LLM policy (real agency)** | `LlmPolicy` + `CONTROLLER_SYS`; trace logging; `/agentic` toggle; API flag | fake controller picks a non-default-but-legal sequence (e.g. `research`→`draft_unit`); run completes; learning-signal counts unchanged; illegal action → fallback |
| **3. Dynamic mid-draft tools** | writer may request `research`/`read_canon` *during* a draft (a bounded sub-loop) - still ends in one draft → one critique | a draft that fires an on-demand research call still records **exactly one** episode |
| **4. Multi-agent crew (where it earns it)** | reuse the judge panel (`rank_variants`); add an independent fact-checker/critic panel for `verify_claims`; research fan-out already exists (deep_research) | panel verify needs ≥majority; no peer-to-peer chatter built |
| **5. Learned policy π** | consume `agent_trace.jsonl` + episode outcomes (first_pass, insight, reader-report) as reward; distill a policy that replaces `policy.next_action` | gated through the **same** candidate→trusted validation as skills; never auto-promoted; `next_action` is the clean swap point |

Phases 0–2 deliver the "self-directing loop + real tool use + end-to-end autonomy" the user asked
for. 3 deepens tool use, 4 is multi-agent, 5 is the endgame. Each is independently shippable behind
the toggle.

**Status:** 0-2 ✅ built · **the run-level controller (`runner.run_loop`) now lifts the whole phase
machine into a policy** for `llm`/`trace` runs (macro actions draft/consolidate/repair/produce/learn/
done), so agency is no longer confined to per-unit gathering; `default` stays on the legacy loop for
the equivalence floor · 3 ✅ **true in-generation tool use built** (`llm.complete_text_with_tools`: the
writer calls `research`/relevance-sliced `read_canon` mid-draft, behind `agentic_inline_tools`), with the
reactive `extra_context` pull retained as a complement · 4 ✅ `panels.fact_check_panel` (wired into the
article gate behind `agentic_factcheck_panel`) · 5 ✅ **trained policy built** (`agentic/learn.py`
`train_policy` distills a value model from the trace corpus, persisted per user + refreshed each learn
phase; `Trace*Policy` consult it). Remaining is *scale*, not code: live tool-call validation + a larger
trace corpus. See the implementation-status note at the top of §21.

### 21.10 Multi-agent - honest scope (Phase 4)

Most "crews" are Phase-2's loop with role prompts; we already have the degenerate form (planner /
writer / critic / judge as sequential roles). Add **real** parallel agents only where independent
perspectives beat one pass: the **judge panel** (already seeded by `rank_variants`) and an
**adversarial fact-checker panel** over `verify_claims` (N skeptics, majority refute ⇒ block). Skip
free-form agent-to-agent negotiation - it adds latency and nondeterminism that fights the duel
machinery.

### 21.11 Learned policy π - the endgame (Phase 5)

A trained policy that picks the next tool is the natural top of the self-improving loop, but it is
*last* for a reason: it needs (a) the tool interface (Phase 0), (b) logged episodes with outcomes
(`agent_trace.jsonl`, Phase 2+), and (c) a reward signal - which we already have (first-pass
approval, insight, reader-report). Jumping here first would have no trace data to learn from. When
ready, it slots in behind `policy.next_action` and is validated by the **same** efficacy gate that
governs skills - a self-directing policy is just another taste, quarantined identically.

### 21.12 Risk & rollback

- **Default off.** `agentic=False` ⇒ the legacy `run()` path runs verbatim. Opt-in only.
- **Equivalence test (Phase 1)** is the regression net: any drift between agentic+DefaultPolicy and
  the pipeline fails CI.
- **Bounded.** Per-unit gathering cap (`agentic_max_unit_steps`) + budget kill-switch + legality guard ⇒ no
  runaway, no canon corruption; worst case the run finishes on the deterministic default policy.
- **Learning loop provably intact.** `draft_unit` wraps the unchanged episode; `record_*` /
  `reconcile` untouched; the episode/duel-count assertion guards it.
- **Files.** New: `agentic/{__init__,tools,controller}.py`, `tests/test_agentic.py`, `CONTROLLER_SYS`
  in `prompts.py`. Edited: `config.py`, `orchestrator/{common,book,article}.py` (state keys +
  dispatch), `api.py`, `shell/{commands,_const}.py`. The orchestrator seams' `__init__` re-exports are
  unaffected (the agentic facade is additive).

## 22. The craft engine - register-parameterized writing (2026-06-16)

The agentic loop made the agent *self-directing*; this layer makes it a *great writer in more
than one field*. The audit finding it answers: the pipeline guaranteed a **floor** (no slop, no
contradictions) and an argument **ceiling** (thesis, counterargument) - but the craft contract was
**monovocal** (one "researcher voice" baked into every prompt and the stripper), and almost all
remaining craft (voice, rhythm, show-don't-tell) lived **inside the model**, reached by zero-shot
instructions. Both fail the standing goal of running well on a **basic model**: the floor is code
(model-independent), the ceiling was prompt-hope (model-dependent). This layer moves craft from
*instructions the model must be clever enough to obey* to *demonstrations it imitates and
deterministic checks it can't escape, parameterized by register*.

### 22.1 Registers (the spine) - `registers.py`

A `Register` is the craft contract as **data**, not hard-code: which anti-slop bans apply, which
**invert** (academic *requires* hedging; copy *keeps* the exclamation and the rule of three; fiction
*keeps* the em-dash), the voice/concreteness lines, rhythm/diction guidance, the citation style, the
target reading grade, and **which deterministic craft metrics matter** for the genre. Eleven ship:
`nonfiction` (default), `technical`, `literary-fiction`, `genre-fiction`, `academic`, `journalism`,
`copywriting`, `business`, `poetry`, `screenplay`, `children`. `registers.infer(genre, mode, explicit)`
picks one from the project's genre/angle unless `register:` is pinned in settings.

**Invariant:** `register=None` (and the `nonfiction` profile) reproduce the historical
`slop.render_constraints()` / `slop.tell_pattern()` **byte-for-byte** (a test asserts it), so every
pre-existing run is unchanged. `slop.render_constraints(register)` / `tell_pattern(register)` filter
the banned lists by the register's allowances; `humanizer` compiles a per-register tell matcher and
keeps em-dashes where the register treats them as voice.

### 22.2 Compensating for a basic model (the point)

- **Few-shot, not just rules** (`exemplars.py`): before/after pairs in the surgical humanizer and
  **score anchors** (a 5 vs a 2 per dimension) in the critic. Weak models imitate; they don't follow
  abstractions. Stable, so they sit in the (cached) system prompt.
- **Gold corpus** (`gold/<register>.md`, shipped as package-data): a genre-tagged "match this"
  exemplar injected through the voice-exemplar slot by **default** (`brain.style_exemplars` = user
  voice if any, else the register's gold). A weak model imitating a strong paragraph beats one told
  to "write vivid prose."
- **Genre-aware craft metrics** (`craft.py`): `structural_report(text, register)` now also computes
  sentence-rhythm variance + opening-word runs, passive-voice ratio, adverb density, Flesch-Kincaid
  grade, cliché hits, opening/closing weakness - and for fiction swaps in filter-verb density,
  dialogue ratio, said-bookisms, POV/tense consistency, and sensory density. Computed evidence to the
  critic, model-independent. (The historical four nonfiction lines are preserved exactly.)

### 22.3 Surgical craft passes (Tier 2) - `surgery.py`

Generalizes the humanizer's detect → rewrite-only-the-flaw → **guard** → splice pattern (citations +
numbers preserved, defect strictly reduced, no new slop, length sane) to: **show-don't-tell** (filter
verbs + told emotion → the concrete image; fiction registers) and **passive → active** (prose
registers). Approved prose is never regenerated end-to-end, so a Flash micro-edit can't drift facts.
Gated by `craft_passes` (default on); no-op in fake mode. Plus an opening/closing detector and a
deterministic **voice-drift** report (`polish.voice_drift`: function-word-profile outliers across
chapters, folded into the book cohesion report).

### 22.4 Field templates + citation styles (Tier 3)

`fields.py` injects a **structural grammar** into the outline architect (TOC / article outline):
inverted-pyramid, IMRaD, AIDA/PAS, BLUF, how-to, three-act, screenplay - chosen by the register's
default or a pinned `field:`. `polish.build_references(style=...)` renders the same ranked sources in
the register's citation convention (`influence` default · `numeric` · `apa` · `mla` · `chicago` · `ap`
· `none`); `influence` is byte-for-byte the old output.

### 22.5 Config & wiring

New tunable settings (all clamped): `register`, `field`, `citation_style` (""=infer/register-default),
`craft_passes` (bool). Threaded as run-state keys and passed to `nodes.write_*/critique_*/cohesion_edit`
and `humanizer.humanize` via a `register` argument (default `None` ⇒ unchanged). New files:
`registers.py`, `craft.py`, `exemplars.py`, `surgery.py`, `fields.py`, `gold/*.md`,
`tests/test_craft_engine.py`. Edited: `slop.py`, `humanizer.py`, `polish.py`, `prompts.py`, `nodes.py`,
`config.py`, `brain.py`, `pyproject.toml` (package-data), `orchestrator/{common,book,article,review}.py`.

### 22.6 Deliberately deferred (see `docs/proposal-personas-emotions-composition.md`)

The **compositor** (a precedence cascade: register ⊃ field ⊃ persona ⊃ emotion ⊃ skills, single-select
upper layers, conflict-resolution by precedence), **author/archetype personas** (curated voice bundles
in the voice slot, public-domain + original; never living-author impersonation), and **emotions** as
*anti-cliché deny-lists + the show-don't-tell pass* (NOT a symptom dictionary, which is a cliché
generator). Decision recorded: finish these tiers first, then add the compositor; personas = archetypes
+ public-domain.

## 23. The compositor - personas, emotions, and layer composition (2026-06-17)

Built the §22.6 deferral. The insight (from `docs/proposal-personas-emotions-composition.md`):
register (rules+voice), persona (manner), emotion (affect), and skills (technique) are all
**voice/constraint layers over one draft**, and the system already had three of them - so the work is
**one composition model**, not three feature silos. And the honest constraint: *more layers is worse,
not better* - a weak model given several voices at once averages them into mush. The compositor's job
is **selection + conflict resolution**, not accumulation.

### 23.1 The cascade

```
register  ⊃  field  ⊃  persona  ⊃  emotion  ⊃  skills
(rules+voice) (structure) (manner)  (affect)   (technique, ≤3)
```

Outer layers win conflicts; an inner layer may only fill the freedom the outer leaves open, never
break it. Upper layers are **single-select** (one register, one field, one persona, one emotion); only
skills are multi, and they were already capped + efficacy-gated (§8). `compositor.py` is the one place
that decides what is selected, what is dropped, and **logs why** - it never silently concatenates.

### 23.2 Personas - `personas.py` + `personas/*.md`

A persona is a **manner** layer: it flavors diction, rhythm, device-density, and stance *within* the
register's rules. Each ships a **signature card** (the manner nudge) + an **exemplar** (original
pastiche prose) and declares its **compatible registers**. Fourteen ship: six archetypes (`wry-skeptic`,
`warm-mentor`, `hard-boiled-minimalist`, `lyrical-maximalist`, `deadpan-technical`,
`firebrand-essayist`) and eight public-domain *manners* (`shakespearean`, `nietzschean`,
`austen-ironic`, `twain-vernacular`, `wildean`, `poe-gothic`, `dickensian`, `whitmanesque`).
**Hard boundaries:** manner only (obey the register, stay in the
present, invent no archaic words); **no living/in-copyright authors** (for a specific modern voice the
user's own `voice/` + `/praise` path already exists); exemplars are **original pastiche**, not the
authors' text, so there is zero copyright surface. A persona incompatible with the register is
**dropped and logged** (a Nietzschean API reference is not a thing) - the register wins.

### 23.3 Emotions - `emotions.py` (anti-dictionary)

A symptom dictionary ("fear = racing heart, sweaty palms") is a **cliché generator** and was rejected.
The inverse ships: per-emotion **anti-cliché deny-lists** (wired into the `craft.py` cliché detector, so
"her heart raced" is flagged wherever it appears - deterministic, model-independent) + a one-line craft
**cue** (the show-don't-name technique) injected by the compositor. Believable emotion is then carried
by the deny-list + the show-don't-tell surgical pass (§22.3), not a glossary. Twelve emotions - the
basic-emotion canon (`fear`, `anger`, `grief`, `joy`, `love`, `shame`, `tension`, `hope`, `disgust`,
`surprise`, `jealousy`, `pride`) - with alias tolerance (`dread`→fear, `envy`→jealousy, `awe`→surprise)
so a free-text role resolves.

### 23.4 The voice layer (what's wired now)

`compositor.voice(uid, register, persona, emotion, log)` resolves the writer's single "match this"
anchor by precedence: **compatible persona (signature + exemplar) > user voice (`/praise`) > register
gold (§22.2)**, then appends the emotion cue. It replaces the bare `brain.style_exemplars` call at every
writer site (book, article, review, reader-loop). One slot, no new node params - persona + emotion are
manner guidance for the *writer*; the critic already enforces the register and the deterministic metrics.

### 23.5 Config & wiring

New tunable settings (clamped against the known sets): `persona`, `emotion` (both ""=none). Stored in
run-state (`_base_run_state`, so both modes) and read by the writer sites via the compositor. New files:
`personas.py`, `emotions.py`, `compositor.py`, `personas/*.md`, `tests/test_compositor.py`. Edited:
`config.py`, `craft.py` (emotion clichés), `pyproject.toml` (package-data), `orchestrator/{common,book,
article,review}.py`.

### 23.6 Deferred (next)

Per-unit emotion (map a book chapter's `emotional_role` → an emotion key instead of one run-level
target), persona-aware critic notes (don't flag a persona's deliberate choices), a "blend = author a new
persona" workflow, and surfacing the cascade in the TUI. The cascade seam is in place; these are
additive.
