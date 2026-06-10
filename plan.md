# Book Agent - Plan

A self-correcting, multi-book writing system. Not a chatbot and not a single prompt - a
**writing machine with memory** that drafts chapters, judges its own work, escalates to a
human when it's unsure, and **learns reusable craft skills per user across many books**.

> **The loop:** write → judge → (approve | revise | escalate to human) → commit canon →
> consolidate → learn skills → write the next chapter better.

> **Implementation status (v1, updated 2026-06-09).** Built in `src/book_agent/` and shipped as an
> interactive **WRITING AGENT** shell (a TUI with slash commands + per-agent model switching) plus a
> one-shot CLI (`writing-agent` / `bookwriter` / `book` / `python book.py`; see README).
> **Live-validated** on OpenRouter + DeepSeek V4 Pro/Flash: fully autonomous runs completed a book
> (9-page PDF, captured in `SampleRun/`) and a long-form article (6 sections, DOCX export).
>
> Features beyond the §1–16 spec: **article mode** (parallel section pipeline with editorial angle
> picker, flat `articles/<id>/` layout, inline citations + sources.json); **humanizer** pass (strips
> AI tells, 11 rules); **SVG diagram fallback** (LLM-generated `<svg>` when Wikimedia returns nothing,
> saved to `images/`); **6 export formats** (pdf · epub · html · docx · txt · md; interactive picker);
> **`/update` slash command** (describe changes → AI reviews and advises); seed craft-skills (9
> built-in); autonomous mode (best-draft commit + contradiction auto-repair); `NO_SLOP` guardrails
> injected into every writer/humanizer/critic prompt.
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
- Irreconcilable contradiction (plan says X, the chapter needs Y).
- Structural decision (kill a character, change the ending).

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
3. **Critic-only findings** → fix *this book* only; **never auto-promoted** to user learning
   (training on the Critic's own taste = circular convergence on bland, "safe" writing).

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
  critic:        deepseek/deepseek-v4-flash    # independent judge - a different model than the writer
  summarizer:    deepseek/deepseek-v4-flash    # summaries + canon extraction
  production:    deepseek/deepseek-v4-flash
  learner:       deepseek/deepseek-v4-flash
  researcher:    deepseek/deepseek-v4-flash
temperature:                                   # DeepSeek accepts sampling params
  toc:        0.4
  critic:     0.2
  summarizer: 0.0
```

Defaults route **DeepSeek V4 Pro** to Writer/Planner/Consolidation (the high-leverage nodes) and
**V4 Flash** to the rest - the bulk of calls by volume. All calls go through **OpenRouter** via the
OpenAI SDK (`OPENROUTER_API_KEY`); structured node outputs use **JSON mode + Pydantic validation**
(with one repair retry), since DeepSeek has no Anthropic-style `messages.parse`.

**Recommendation:** use a *different* model (or family) for the **Critic** than the **Writer**.
A model tends to be a lenient judge of its own output; an independent critic catches more. This
is the architectural reason the Critic is a separate node in the first place.

---

## 13. CLI design (the UI)

Two surfaces over one engine (plus the markdown brain repo, which is half the UI - read chapters
and canon in any editor):

- **Interactive shell - the BOOKWRITER TUI.** Run `bookwriter` / `book` / `python book.py` with no
  command (see `shell.py`). Editorial title-page banner, a command panel, and a `❧ <model>` prompt.
  Type book commands without the `book` prefix; lines starting with `/` are slash commands.
- **One-shot CLI** - `python book.py <command> ...` (same commands), for scripting.

| Command | Does |
|---|---|
| `new` | Abstract → directions (human/auto pick) → plan + TOC. Flags: `--autonomous`, `--no-humanize`, `--chapters N`, `--max-revisions N`, `--pick K` |
| `run` | Drive write → critique → humanize → commit → consolidate → produce → learn. `--force` passes a consolidation review |
| `status` | Where the book is; pending escalations |
| `review --chapter K --instruction "..."` | Answer an escalation; resume on next `run` |
| `read [--chapter K] [--summary] [--manuscript]` | Print a chapter / summary / assembled book |
| `export` | Render the manuscript to PDF |
| `memory` | Inspect canon (characters/timeline) + entity graph |
| `consolidate` · `produce` | Run those passes on demand |
| `skills` · `seed-skills` | List skills + efficacy · install built-in craft skills |
| `list` · `config` | List books · show model routing + settings |

**Slash commands (shell only):** `/help`, `/model [<agent>] <slug>` (switch any model, per agent,
persisted to `config/models.yaml`), `/skills`, `/skill <name>`, `/seed-skills`, `/use <book>`,
`/books`, `/user <id>`, `/config`, `/clear`, `/exit`.

Run modes: **interactive** (prompts inline on escalation), **autonomous** (`--autonomous`: never
pauses; commits the best draft + auto-repairs contradictions), **async** (background; resume via
`run` / `review` - the on-disk state is the checkpoint).

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
| **Safety** | The conversational assistant may **not** auto-execute `delete` / `/user` / `/set` (data-loss / tenant / config) - the human must type those. Project/user ids are validated (`is_safe_id`) and `delete_book` confines `rmtree` to the brain dir. Exported HTML is sanitized (no `<script>`/`<iframe>`/event handlers). |
| **Telemetry** | Token usage is aggregated per run and surfaced (`[usage]` line + live in the run dashboard). |
| **Revision loop** | The human review instruction survives every revision round (merged ahead of critique notes, never overwritten). Each revision passes the previous attempt as a PRIOR DRAFT - the writer revises, it doesn't regenerate from notes about text it can't see; an escalation resume revises the exact draft the human reviewed (`.draft.md`, deleted on commit). Autonomous mode commits the **best-judged** attempt (approve > fewer blocking > higher confidence), not the last one. |
| **Closed learning loop** | The learner's watch-list (`prefs/watch_list.md`) is injected into every critic call (patterns flagged as blocking); applied craft skills are also shown to the critic. The article learner runs **before** intermediate cleanup so it actually sees the `eval_*.json` critic findings. |
| **Citations / sources** | Per-project source registry (`sources.json`, deduped by URL, first-seen order = reference numbering). Articles renumber in-text `[N]` citations at commit so they always match the final References list. Books persist research sources too; production feeds them verbatim to bibliography-style back-matter components (which are otherwise forbidden from inventing entries). |
| **Length control** | `target_words` per chapter (TOC) / section (outline; falls back to an even share of `target_word_count`). The writer gets a target note; the critic gets the actual word count and flags >±40% misses as blocking. |
| **Article cohesion** | `article_cohesion` (default on): a whole-article smoothing pass over the assembled sections (transitions, cross-section repetition, terminology) before References. Guarded - if the edit shrinks the body >40% or loses headings, the original is kept. |
| **Long-range retrieval** | `assemble_context` augments canon + dependency summaries with FTS5 excerpts from *other* committed chapters matched on the blueprint's key terms (`store.search_excerpts`). Timeline events are recorded under the actual committing chapter (LLM-reported numbers were unreliable). |
| **Export fidelity** | All exporters resolve relative `images/` references against the project root: PDF rasterizes SVG via cairosvg when installed (else drops the tag, keeps the caption), EPUB packages images as items, DOCX passes `--resource-path` to pandoc, HTML inlines images as data URIs. |

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
