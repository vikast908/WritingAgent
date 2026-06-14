# Book Agent - Plan

A self-correcting, multi-book writing system. Not a chatbot and not a single prompt - a
**writing machine with memory** that drafts chapters, judges its own work, escalates to a
human when it's unsure, and **learns reusable craft skills per user across many books**.

> **The loop:** write → judge → (approve | revise | escalate to human) → commit canon →
> consolidate → learn skills → write the next chapter better.

> **Implementation status (v1, updated 2026-06-12).** Built in `src/book_agent/` and shipped as an
> interactive **WRITING AGENT** shell (a themed TUI with slash commands + per-agent model switching)
> plus a one-shot CLI (`writing-agent` / `bookwriter` / `book` / `python book.py`; see README).
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
`book status` lists open entries; `book review` opens, answers, and resumes them. No
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

---

## 9. Consolidation pass (GBrain "Dream Cycle" analog)

Per-chapter checks miss *global* drift. A periodic batch pass (between chapters / at
milestones / before book end) does what the inline Critic can't:
- **Contradiction detection** across the whole book (cached LLM judge - pay once per pair).
- **Character-fact dedup** and canon reconciliation.
- **Salience scoring** (what actually matters for future chapters).
- Flags unresolved threads with no planned payoff.

**Cadence (v1):** fixed - every `N=5` committed chapters (configurable) - **plus** a mandatory
pass before `BOOK_DONE`, **plus** manual `book consolidate`. Salience-adaptive cadence is
deferred: salience is an *output* of this pass, so it can't gate the first run; once available
it may only *tighten* the interval, never replace it.

Output feeds the Orchestrator and the canon (reconciled facts). When `escalate_on_contradiction`
is on (default), contradictions pause the run with a `reviews/consolidation-*.md` entry; the human
reviews and resumes with `book run --force`.

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
no key), and a `custom` escape hatch (`BOOK_AGENT_BASE_URL`). Aliases resolve shorthand (`grok→xai`,
`ds→deepseek`, `kimi→moonshot`, …). Adding a provider is **one registry entry**, nothing else.

Switch with **`/provider <id>`** (lists every host with a key/local/no-key marker, persists to
`settings.provider`, rebuilds the client), `/set provider <id>`, or **`BOOK_AGENT_PROVIDER`**.
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

- **Interactive shell - the WRITING AGENT TUI.** Run `writing-agent` / `book` / `python book.py`
  with no command (see `shell.py`). Themed masthead (gradient-filled ANSI Shadow wordmark; theme
  also sets palette/figlet/glyphs - `ui.THEMES`), a **compact welcome** (START + your projects +
  a status footer - sized so the wordmark is still on screen at the first prompt on a 30-row
  terminal; the full command list lives under `/help`, the feature board under `/features`; a
  red warning fires when `BOOK_AGENT_FAKE` is set so test mode can't silently eat real runs),
  live run dashboard (progress, stage, tokens vs budget, USD cost), `/dashboard` telemetry
  rollup, autocomplete + persistent history, and a `❧ <model>` prompt. No bottom toolbar (it
  read as noise; state lives in the prompt prefix + welcome footer). Type book commands without
  the `book` prefix; lines starting with `/` are slash commands; anything else is free chat.
- **One-shot CLI** - `python book.py <command> ...` (same commands), for scripting.

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
- **Accessibility**: `BOOK_AGENT_A11Y` line-mode (no in-place Live redraw — append-only full-sentence
  status for screen readers), `BOOK_AGENT_REDUCED_MOTION` (static stages, no spinner), a one-line
  wordmark on narrow (<60-col) terminals, and `NO_COLOR` / `--plain` honored throughout.
- **Proactive key check**: the banner warns when the active provider has no API key (before the first
  call fails); `BOOK_AGENT_PROVIDER` now syncs `settings.provider` so the masthead is accurate.
- **Progressive help**: `/help <topic>` shows only the matching commands.
- **Reading time** is prose-only — fenced code and the references list are excluded
  (`polish.read_time_min`, `READ_WPM`), so technical pieces no longer over-state "N min read".
- **Version** is single-sourced from `book_agent.__version__` (pyproject derives it via
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
| **Notification channel** | Markdown review queue in `books/<id>/reviews/` + terminal print (interactive); surfaced by `book status` / `book review`. Any later channel tails the file queue. (§7) |
| **Consolidation cadence** | Fixed: every `N=5` committed chapters + mandatory before `BOOK_DONE` + manual `book consolidate`. (§9) |
| **Skill efficacy metric** | Lift over baseline: promote at `applied≥5`, `p_skill≥p_base`, `target_failures=0`; retire on sustained under-performance. (§8) |
| **Researcher depth** | Two tiers, both optional. **Shallow** (`use_researcher`): one DuckDuckGo query -> snippets -> a short brief (facts + style cues). **Deep** (`deep_research`, layers on `use_researcher`): LLM query-expansion -> several queries fanned out concurrently -> dedup + per-domain cap -> fetch and extract the actual page text of the top sources -> a synthesis node reads across full pages and cites sources by number. See §15.2. |

### 15.1 Reliability, performance & safety (2026-06-10 hardening)

Durable decisions from the hardening pass. All thresholds are tunable config.

| Area | Decision |
|---|---|
| **Context compression** | `headroom-ai` is **optional** (lazy import, silent fallback). Pinned to **0.10.17** (the last pure-Python release; ≥0.21 is a Rust/pyo3 ext with no Windows wheel), installed `--no-deps`. `_compress` always tells headroom a **tiktoken** model for counting - compression is model-agnostic, so DeepSeek runs still compress. |
| **LLM call resilience** | We own retries: classified **exponential backoff + jitter**, honor `Retry-After`, **fail fast on 4xx**, per-request `request_timeout` (default 60s). Structured calls do a **repair retry** (feed the invalid output + error back). The OpenAI SDK's own retries are disabled. |
| **Concurrency** | The chapter/section *prose* chain is **sequential by design** (continuity: each unit reads the previous summary). Everything independent of prose overlaps via a small thread pool (`concurrency.gather`): (a) within a unit, research ∥ image/SVG ∥ skill retrieval; (b) **unit n+1's research/images/skills are prefetched while unit n is written/critiqued** (they depend only on the plan/TOC; prefetch results are disk-cached so escalations waste nothing); (c) at commit, **humanize ∥ summarize ∥ canon-extraction** run as one batch (`strict=True` - a failed summary/extraction still aborts the commit) since all three derive from the same approved draft; (d) production's front/back-matter components. The SQLite `Store` is only touched on the main thread. |
| **Prompt size** | The writer/critic canon block is capped at the **most recent `MAX_CANON_FACTS_PER_CHAR` (12) facts per character** - uncapped it grows linearly with the book and late chapters pay maximum latency/cost. Consolidation and extraction still see the full canon. |
| **Caching** | Web-search results (7-day TTL) and generated SVG diagrams are cached on disk under `.index/cache/` (best-effort; corrupt entries self-heal as misses). |
| **State durability** | `run_state.json` (and all brain writes) are written **atomically** (temp file + `os.replace`); `read_json` tolerates a corrupt file (returns `None`). A crash between commit and the state advance is caught by a **resume guard** that skips already-committed units - no double-commit, no duplicate canon facts. `BOOK_AGENT_HOME` relocates the writable brain + index off synced folders (OneDrive/Dropbox locks can break `os.replace` and slow every write). |
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
| **Diagram quality (spec → deterministic render, 2026-06-13)** | The model no longer emits SVG - it is bad at geometry, so labels overflowed and edge pills collided no matter the prompt (two prompt rounds failed). The `diagram` node now returns a **structured `DiagramSpec`** (nodes/edges/labels/archetype - what an LLM is good at) via `DIAGRAM_SPEC_SYS`, and **`diagram.py` lays it out deterministically**: text is measured (per-char widths) so boxes are sized to fit and labels wrap before overflowing; nodes are placed by archetype (column-ranked DAG for `flow`, stacked lane bands for `layered`, an evenly-spaced **ring for `cycle`**, two colour-headed **columns for `comparison`** - radius/column maths keep boxes clear; `cycle`<3 nodes or `comparison`<2 groups degrade to `flow`) so **boxes can't overlap by construction**; the ranker detects **back edges via DFS and excludes them** so a feedback/loop arrow doesn't reverse a pipeline; edges route as orthogonal elbows (adjacent) or stacked bottom channels (spanning/back) that never cross boxes; edge labels get measured white pills with collision-nudging; groups map to a consistent colour + a bottom legend; one `focus` node is emphasized. **Arrowheads are explicit polygons** (svglib drops `<marker>`, so marker-only arrows vanish in PDF). `_svg_fill_guard` (forces `fill="none"`) stays as a no-op safety net. A node-less spec → **flash-tier `diagram_fallback`** retry → minimal placeholder. Disk-cached by (model, heading, context, engine).<br>**Optional D2 backend (`diagram_engine`, default `auto`).** The same `DiagramSpec` can instead be laid out by the **[D2](https://d2lang.com) CLI with ELK** (`diagram.to_d2` → `d2 --layout elk`), which routes complex graphs (fan-out/fan-in, lane containers) better than the built-in engine - chosen after a side-by-side render comparison. D2 has no legend of its own, so `_inject_d2_legend` extends its outer viewBox and appends a colour legend matching the node borders. `engine`: `auto` (use d2 when the `d2` binary is on PATH or `$BOOK_AGENT_D2`, else built-in), `d2`, or `builtin`. The built-in engine stays the **zero-dependency default** (d2 is an ~18 MB Go binary, not required - CI and unconfigured users get built-in); any d2 failure falls back to it. |

### 15.2 Deep multi-source researcher (`deep_research`, off by default)

The "Deep Researcher" once deferred below, now built (`src/book_agent/deep_research.py`).
Opt-in via `deep_research: true` (it layers on `use_researcher`); both books and articles use it.

| Aspect | Decision |
|---|---|
| **Query expansion** | A `researcher`-model node (`nodes.propose_search_queries`) turns the chapter/section focus into a few distinct queries (core facts, recent developments, expert/critical angle, examples). Best-effort: on failure the deterministic seed query still runs. |
| **Fan-out + diversity** | The expansion LLM call runs **concurrently with a warm-up search for the seed query** (`orchestrator._deep_docs`; search results are disk-cached, so the merged pass re-reads it for free). Queries are then searched concurrently (`concurrency.gather` over `search.web_search`, one DDGS session per thread), hits merged in query order, **deduped by URL**, and capped at `max_per_domain` (2) so a brief spans multiple sites - then the top `max_sources` (6) are kept. |
| **Full-text fetch** | The kept sources have their actual page text fetched concurrently. **Fetch backend is pluggable:** if **Scrapo** (`github.com/vikast908/Scrapo`) is installed it's preferred - it returns clean page markdown and escalates HTTP -> browser -> stealth, reaching JS-rendered/soft-blocked pages; otherwise a pure-stdlib `urllib` + `html.parser` extractor is used (script/style/nav stripped, http(s) only, byte-capped, non-HTML skipped). All Scrapo coroutines share **one persistent background event loop** (no per-URL loop churn; enables session/browser reuse inside Scrapo). 7-day disk cache wraps both. Every step is non-fatal: Scrapo failure falls back to stdlib, which falls back to the snippet. `BOOK_AGENT_NO_SCRAPO=1` forces the stdlib path. |
| **Synthesis** | `nodes.deep_research` / `deep_research_article` read the numbered full-text sources and produce a brief that cites sources by number and flags agreement/disagreement. For articles the **real fetched URLs** become the persisted sources (more reliable than LLM-copied URLs), feeding the References section. |
| **Portability / cost** | Zero *required* deps - the stdlib fetch path keeps CI green on all three OSes x Python 3.10-3.13. Scrapo is an optional extra (`pip install '.[deep]'`; Python 3.11+, installs from git) for higher-fidelity fetching. Deep mode adds one query-planning LLM call + N page fetches per unit - hence opt-in. In fake/offline mode the whole path no-ops. |
| **Fetch safety** | Search results (and the LLM's query expansion behind them) decide what gets fetched, so every uncached fetch passes a gate: **SSRF guard** (host must resolve and every address must be globally routable - blocks loopback/private/link-local/cloud-metadata; the stdlib path re-validates **each redirect hop**), **robots.txt** honored per host (cached for the process; unreachable/missing robots = allow; `BOOK_AGENT_IGNORE_ROBOTS=1` skips), and a **per-host politeness interval** (`_HOST_MIN_INTERVAL`, 1s) between requests to the same host. Scrapo does its own fetching - the initial-URL guard still applies to it, and it has `SCRAPO_RESPECT_ROBOTS` for robots. |

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
unstable pre-1.0. `book_agent.api` is a thin **facade** that gives integrators a supported,
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
- **Lazy exports.** `book_agent/__init__.py` resolves the public names via PEP-562 `__getattr__`,
  so `import book_agent` / `from book_agent import brain` stay cheap and never eagerly pull the
  whole pipeline.
- **Versioning.** `book_agent.__version__` (kept in step with `pyproject`'s); the API module's
  docstring states the no-break-within-major contract. Surface is covered by `tests/test_api.py`
  (offline, `BOOK_AGENT_FAKE`).

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

The book (chapter) and article (section) pipelines run near-parallel code in `orchestrator.py`
(115 KB) and `shell.py` (144 KB) - the repo's #1 redundancy (~hundreds of lines). It must be paid
down **incrementally and test-gated**: these paths have a history of *silent drift* (the revise-parity
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

## 20.1 File split - orchestrator (done), shell (next)

Once dedup was paid down, the two god-files were split into packages behind a stable facade so
`orchestrator.X` / `shell.X` resolve unchanged for every caller and test (incl. the private names tests
reach for). Pure code movement, suite-gated per step.

- **`orchestrator/` - done.** 2274-line module → facade `__init__` (re-exports via `from .seam import *`)
  + six seams: `common` (shared leaf helpers), `book` (chapter pipeline + the public `run()` dispatcher),
  `article` (section pipeline), `export` (renderers/repolish/evidence), `manage` (lifecycle/state),
  `review` (approve/revise/table-read/evaluate). Acyclic: common ← {article,book,manage}; article ←
  export; book ← {article,manage}; review ← {book,article,common}. Genuinely-shared leaves that surfaced
  during the carve (`_escalate`, `_manuscript_section_bodies`, `_replace_manuscript_section`) went to
  `common`. A ruff per-file-ignore (`__init__.py` = F401/F403/F405) marks the intentional star re-exports.
- **`shell/` - planned.** Same recipe; seams: branding (banner/wordmark/flame/palette/welcome),
  help (tables/slash-help/toggle-grid), commands (`_cmd_*` + path/use-project), dashboard (`_RunControls`/
  `_KeyListener`/`_RunDashboard`/`run_with_dashboard`/cards), chat (respond/history/hints/system), repl
  (`run_shell`/`_handle_slash`/pt-session/input routing). Tests reach for many `shell._x` names, so the
  facade must re-export them.
