# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Shipped defaults now bundled in the wheel (`src/writingagent/resources/`).** Pip installs
  used to get no `config/models.yaml` - so no per-node routing and **no fallback model** - and
  no `seeds/`, so `seed-skills` silently installed 0 of the 13 built-in craft skills. The wheel
  now bundles both: `load_config()` copies `models.yaml` out to `config/models.yaml` on first
  run (a real, user-editable file; read-only installs fall back to reading the bundle in place),
  and `seed_builtin()` reads the bundled seeds when the repo-root `seeds/` is absent. Sync tests
  (`tests/test_bundled_resources.py`) pin the bundled copies byte-identical to the repo originals.

### Changed
- **Model-agnostic messaging + de-slop sweep across the docs.** README and the human-authored
  docs were reworked to lead with "any OpenAI-compatible host, no blessed default" instead of an
  OpenRouter/DeepSeek default, and the project's own #1 anti-slop rule (no em-dashes) was applied
  to the human-authored prose and the banner / architecture SVGs. Redundant files were removed.
- **Book/article run-op bodies de-duplicated (`orchestrator/`).** The near-identical book and
  article run-op implementations were consolidated behind the shared scaffolding. Pure refactor,
  behavior-preserving, suite-gated.
- **CI maintenance.** GitHub Actions bumped to current majors (incl. `actions/setup-python` 5→6);
  `ruff check .` made green across the whole repo (CI lints everything, not just `src/`/`tests/`).

### Fixed
- **Docs.** Corrected the `write` invocation (it takes `--abstract`, not a positional) and fixed two
  README anchor links broken by de-em-dashing the headings.

### Removed
- **The npm launcher.** The `writingagent` npm launcher was removed entirely - it was never actually
  published or maintained. The Python install (`pip install writing-agent`, `pipx`, or source) is the
  only supported path.

## [0.2.0] - 2026-07-16

### Added
- **Provider reach + no blessed default (`providers.py`, first-run wizard).** Added first-party
  **Anthropic** (`claude-*` via the OpenAI-compatible endpoint), **Perplexity** (`sonar`),
  **Cerebras**, and **SambaNova**, plus **AWS Bedrock** and **Azure OpenAI** via an OpenAI-compatible
  gateway (`AWS_BEDROCK_BASE_URL` / `AZURE_OPENAI_BASE_URL`) — 23 hosts total, all one transport.
  There is **no default host**: the first-run wizard detects any key already in the environment and
  offers it, or lets the writer *choose* a provider (then paste its key); `providers.configured()`
  drives the picker. `.env.example` rewritten to show the choice across all vendors. (Native boto3
  Bedrock + native Azure are on the roadmap.)
- **Open-source hardening.** PyPI release automation (`.github/workflows/release.yml` — build +
  Trusted-Publishing/OIDC on a `v*` tag), CI now runs **coverage** (pytest-cov → Codecov, non-blocking)
  and a **gitleaks** secret-scan job; **Dependabot** (pip + actions); README **PyPI / Docs / Python /
  Platforms / License** badges; `CODEOWNERS`, issue-template `config.yml`, `CITATION.cff`, `FUNDING.yml`,
  and `ROADMAP.md`.
- **Install docs lead with `pip install writing-agent`.** README quickstart/install and `learning.md`
  now present the PyPI install as the primary path (with `pipx` and source as alternatives); example
  commands use the `writing-agent` console script.
- **Tidier repo root.** The maintainer journals moved to `docs/dev/` (`resume.md` session log,
  `test.md` verification log) with a `docs/dev/README.md` explaining them; references updated. `plan.md`
  (architecture spec) and `CLAUDE.md` (tooling) stay at the root.
- **Local web dashboard (`writing-agent web`).** A pure-stdlib `ThreadingHTTPServer` + Server-Sent-Events
  + single-page app (`src/writingagent/webui/`) runs the whole pipeline from the browser: Studio, live
  run (SSE), Projects, per-project Overview / Activity / Evals / Artifacts / **Rejected** / Export /
  Cost, Telemetry, Skills, Settings. Binds `127.0.0.1` only, no auth, one job at a time; reads and writes
  the same on-disk brain as the TUI. Export offers all six formats + a **Rewrite** (restyle) option.
  `--port` (default 8787) / `--no-browser`.
- **Editorial Design System (`design.md` v2) + rebrand.** A portable, cross-domain design system — ink on
  warm paper, one accent (**manuscript red `#a3341f`**), **Fraunces** serif for display + reading, the
  pilcrow `¶` brand mark, the **Caret `▍`** loader, flat/borderless **square** surfaces, **WCAG-AA
  verified** (all brand-critical pairs pass; warning/tertiary/dark-accent nudged to clear AA, brass
  restricted to large/rules). Applied to the web dashboard (vendored Fraunces woff2 served at
  `/static/fonts/`, semantic token layer, banner notifications, field-error states, themed tooltips,
  modal focus trap) and the TUI default skin (**"ink & brass"**: gold primary + brass + manuscript-red
  status). Named themes recolor the layout, never restructure it.
- **Persona library 14→46 + a `writing-personas` skill.** The voice catalog grew to **46** — **18
  archetypes** (added lucid-explainer, cultural-critic, contrarian-optimist, newsletter-confidant,
  scholarly-lucid, punchy-copywriter, bedtime-storyteller, investigative-longform, epic-fantasy,
  snappy-screenwriter, and more) and **28 public-domain manners** (added chekhovian, kafkaesque,
  montaigne-essayist, swiftian, dostoevskian, tolstoyan, melvillean, jamesian, conradian, gogolian,
  bronte-romantic, dickinsonian, byronic, miltonic, homeric, emersonian, thoreauvian, gibbonian,
  aesopian, carrollian). Still no living/in-copyright authors; each ships an original-pastiche
  exemplar + compatible-register list.
- **Craft-layer expansion — 4 personas + 4 emotions (plan §23, 2026-06-17).** Personas **10→14**: four
  public-domain *manners* with original-pastiche exemplars — `wildean` (epigram/paradox), `poe-gothic`
  (slow-tightening dread), `dickensian` (comic, character-teeming), `whitmanesque` (free-verse
  cataloguing); still no living/in-copyright authors and zero copyright surface. Emotions **8→12**:
  `disgust`, `surprise`, `jealousy`, `pride` — completing the basic-emotion canon (disgust + surprise)
  plus the two most common dramatic drivers, each with an anti-cliché deny-list wired into the `craft.py`
  detector, a show-don't-name cue, and aliases (`envy`→jealousy, `awe`→surprise, `revulsion`→disgust, …).
  New files: `personas/{wildean,poe-gothic,dickensian,whitmanesque}.md`.
- **Welcome footer shows agentic state.** The status footer now reads `agentic on|off` (replacing the
  redundant `flash` model slot, which duplicated `pro`), and the hint line surfaces `/agentic on|off`.
- **Lovability pass on the TUI.** The completion card now leads with **the argument the piece made**
  (its thesis claim) plus a **source tally** (N sources · high-influence · high-authority) and
  **reading time** — "proof, not vibes" the moment a run finishes (new `polish.source_stats()`, shared
  with the evidence report so they never disagree). The welcome shows a rotating, date-stable **writing
  epigraph** (public-domain voices only), prefixed with **"Welcome back."** for a returning writer, on a
  single line. And `ui.explain_error()` now maps **context-window overflow** and **token-budget**
  failures to actionable next steps (`/set max_context_chars …` / `/set max_run_tokens 0`) instead of a
  raw traceback.
- **The learned policy is now observable (`/agentic`).** The trace-policy training loop was already
  complete and wired (it auto-runs in the learn phase and writes `unit-outcome` labels at commit) — but
  invisible. `/agentic` with no args now surfaces what the learned policy concluded from this user's run
  traces ("learned from your runs · book: gather context first — reward 0.82 vs 0.61, n=5/4"), so the
  self-improving loop can be inspected. Corrected the policy help (it said `trace = record only`; trace
  actually *consults* a learned model, falling back to the heuristic until it has data). Discoverability:
  expanded `/path` (notes the no-args interactive menu) and `/praise` (mentions `/versions` for N) help,
  and `/set use_embeddings true` now warns with the `pip install sentence-transformers` hint when the
  optional package is missing.
- **Polish pass (discoverability + honesty).** `/help <topic>` now offers a fuzzy "did you mean"
  (`exprt → export`, `agentik → agentic`) instead of a dead end; `/provider` warns that a resumed or
  half-finished project will use the newly-selected host (the silent model-swap footgun); and the README
  test count is corrected (250 → 477, 2 skipped). Verified by a full fake-mode end-to-end run on the
  agentic + autonomous + skeleton config (`new → run → export`): completed cleanly, wrote every artifact
  incl. `agent_trace.jsonl`, and correctly abstained from a learned policy on thin data.
- **Live per-unit craft narration in the run dashboard.** A hands-off run now shows the *story* of its
  self-correction instead of generic log lines: the divergent variants drafted, the judge's pick, the
  draft's opening glimpse, **why** the critic sent it back (a new `critic flagged: <issue>` log in both
  episode loops), and a commit line that carries the final verdict chip
  (`✓ committed §3 · approved · insight 5/5`). Presentation-only curation of already-emitted signal,
  plus the one new log line per loop; the fixed pipeline's behavior is unchanged.
- **The compositor — personas, emotions, and layer composition (plan §23, 2026-06-17).** Built the
  §22.6 deferral as **one composition model**, not three feature silos: register (rules+voice), field
  (structure), persona (manner), emotion (affect), and skills (technique) are all voice/constraint
  layers over one draft. `compositor.py` resolves a precedence **cascade** —
  `register ⊃ field ⊃ persona ⊃ emotion ⊃ skills` — where outer layers win conflicts, upper layers are
  single-select, and the one place that decides what is selected/dropped **logs why** (it never silently
  concatenates, because a weak model given several voices at once averages them into mush).
  **Personas** (`personas.py` + `personas/*.md`) add a manner layer flavoring diction/rhythm/device-
  density within the register's rules — ten ship: six archetypes (`wry-skeptic`, `warm-mentor`,
  `hard-boiled-minimalist`, `lyrical-maximalist`, `deadpan-technical`, `firebrand-essayist`) and four
  public-domain *manners* (`shakespearean`, `nietzschean`, `austen-ironic`, `twain-vernacular`), each a
  signature card + an **original-pastiche** exemplar declaring its compatible registers. Hard boundaries:
  manner only, **no living/in-copyright authors** (the user's own `voice/` + `/praise` path covers a
  specific modern voice), zero copyright surface; a persona incompatible with the register is **dropped
  and logged** (the register wins). **Emotions** (`emotions.py`) ship the inverse of a symptom dictionary
  (a cliché generator, deliberately rejected): per-emotion **anti-cliché deny-lists** (wired into the
  `craft.py` cliché detector, so "her heart raced" is flagged wherever it appears — deterministic,
  model-independent) plus a one-line show-don't-name **cue**; believable emotion is then carried by the
  deny-list + the show-don't-tell surgical pass (§22.3), not a glossary. Eight emotions with alias
  tolerance (`dread`→fear). The voice layer is wired now: `compositor.voice()` resolves the writer's
  single "match this" anchor by precedence — **compatible persona (signature + exemplar) > user voice
  (`/praise`) > register gold (§22.2)** — then appends the emotion cue, replacing the bare
  `brain.style_exemplars` call at every writer site. New tunable settings (clamped against the known
  sets): `persona`, `emotion` (both `""`=none), stored in run-state so both modes carry them. New files:
  `personas.py`, `emotions.py`, `compositor.py`, `personas/*.md`, `tests/test_compositor.py`.
- **The craft engine — register-parameterized writing (plan §22, 2026-06-16).** Moves craft from
  *instructions the model must be clever enough to obey* to *demonstrations it imitates and deterministic
  checks it can't escape, parameterized by register* — the audit finding it answers is that the pipeline
  guaranteed a floor (no slop, no contradictions) and an argument ceiling (thesis, counterargument) but
  the craft contract was **monovocal**. **Register/genre profiles** (`registers.py`) encode the craft
  contract as **data**: eleven profiles tailor the anti-slop contract per genre — `nonfiction` (default),
  `technical`, `literary-fiction`, `genre-fiction`, `academic`, `journalism`, `copywriting`, `business`,
  `poetry`, `screenplay`, `children` — with bans that filter/invert per register (fiction keeps the
  em-dash; academic keeps `moreover` *and requires hedging*; copy keeps the exclamation and the rule of
  three). **Invariant:** `register=None` / the `nonfiction` profile reproduce the historical
  `slop.render_constraints()` / `tell_pattern()` **byte-for-byte** (test-asserted), so every pre-existing
  run is unchanged. To compensate for a basic model: **few-shot exemplars** (`exemplars.py`) — humanizer
  before/after pairs + critic 5-vs-2 score anchors (weak models imitate, they don't follow abstractions);
  a shipped **genre-tagged gold corpus** (`gold/*.md`) injected through the voice-exemplar slot as the
  **default** style anchor (`brain.style_exemplars` = user voice if any, else the register's gold); and
  **genre-aware deterministic craft metrics** (`craft.py`) — sentence-rhythm variance + opening-word runs,
  passive-voice ratio, adverb density, Flesch-Kincaid grade, cliché hits, opening/closing weakness, with
  fiction swapping in filter-verb density, dialogue ratio, said-bookisms, POV/tense consistency, and
  sensory density. **Surgical craft passes** (`surgery.py`) generalize the humanizer's
  detect → rewrite-only-the-flaw → guard → splice pattern to **show-don't-tell** and **passive → active**
  (citations/numbers preserved, defect strictly reduced, never an end-to-end regeneration), plus a
  deterministic **voice-drift** report (`polish.voice_drift`) folded into the book cohesion report.
  **Field structural templates** (`fields.py`) inject a structural grammar into the outline architect —
  inverted-pyramid, IMRaD, AIDA/PAS, BLUF, how-to, three-act, screenplay. **Citation styles** in
  references (`polish.build_references(style=...)`): `influence` (default, byte-for-byte the old output) ·
  `numeric` · `apa` · `mla` · `chicago` · `ap` · `none`. New tunable settings (all clamped): `register`,
  `field`, `citation_style`, `craft_passes`. New files: `registers.py`, `craft.py`, `exemplars.py`,
  `surgery.py`, `fields.py`, `gold/*.md`, `tests/test_craft_engine.py`.
- **Agentic controller — the "fully agentic" batch (8 gaps, plan §21).** (1) **Rich perception:** the
  run/unit views now carry per-unit quality + the weakest committed unit, open contradictions, and the
  token budget. (2) **`reoutline`** — the controller can regenerate the not-yet-written units' plan when
  the structure is wrong (also available before drafting = agentic start-of-run structural agency, #4).
  (3) **`revise`** — it can rewrite the weakest committed unit (re-processes it; canon extraction is
  idempotent so it's safe), capped. (5) **`escalate`** — it can choose to defer to the human. (6)
  **Richer learned policy:** `train_policy` is context-conditioned (book vs. article) on a composite
  first-pass+insight reward. (7) **Broader tools + multi-agent:** a `verify_fact` in-generation writer
  tool and a diverse-lens `critique_panel` (behind `agentic_critique_panel`, articles). (8)
  **Self-monitoring:** budget is in the view and a guard drops optional polish actions
  (reoutline/revise/table_read) under budget pressure so a low-budget run still converges. All new
  macro-actions are chosen only by `llm`/`trace` policies; the `default` policy stays the legacy loop,
  so the equivalence guarantee holds. New caps (`_MAX_REOUTLINE`/`_MAX_REVISE`) bound the autonomy.
  +12 tests.
- **In-generation tool use + a trained controller policy (plan §21 Phases 3 & 5).** The writer can now
  call tools **mid-draft**: `llm.complete_text_with_tools` runs a real OpenAI tool-use loop, and the
  writer nodes invoke `research`/`read_canon`/`verify_fact` while drafting (behind `agentic_inline_tools`,
  agentic runs only; falls back to a plain draft on any provider/tool error, so it's always safe). The
  loop is **double-bounded** (`max_tool_rounds` + a total `max_tool_calls` cap) so an eager model can't go
  on a research spree - a live OpenRouter run validated the loop end-to-end ($0.15, the writer really did
  call tools mid-draft) and surfaced the over-calling the cap now prevents. The whole loop is still one
  episode. And the controller policy is now **learned, not just heuristic**: `agentic/learn.py`
  `train_policy` distills a value model from the accumulated action-trace corpus (does gathering context
  before a draft lift the first-pass rate?), persisted per user and refreshed at every learn phase;
  `TracePolicy`/`TraceRunPolicy` consult it (a learned verdict overrides the online heuristic). Unit
  outcomes (`first_pass`) are now labelled into the trace at commit so decisions join to results. The
  model is opt-in (used only by the `trace` policy) and never auto-promoted into the default. +9 tests.
- **Run-level agentic controller — the phase machine is now self-directing (plan §21).** Beyond the
  existing per-unit controller, a new `agentic/runner.py` (`run_loop`) lets a policy choose the next
  MACRO-action over the whole piece — `draft` the next unit, `consolidate` (audit continuity), `repair`
  contradictions, `produce`, `learn`, `done` — instead of the hardcoded `while phase != "done"` loop.
  Engaged for `agentic_policy` `llm`/`trace`; the `default` policy stays on the legacy loop, so the
  equivalence guarantee (agentic+default == fixed pipeline, byte-identical) and the unit-only trace are
  preserved. `read_canon` is now **query-relevant** (an FTS slice via `store.search_excerpts`, not the
  whole canon block). `TracePolicy`/`TraceRunPolicy` are **activated** as online trace-conditioned
  policies (gather research up front once the trace shows a prior evidence gap; audit continuity early
  once it shows a past contradiction) — the swap point for a fully-trained policy remains. New
  `RUN_CONTROLLER_SYS` prompt, `RunDecision`/`RunOps` schema, `make_run_policy`. +10 tests. Both
  pipelines validated end-to-end through the macro controller (offline). Remaining toward full autonomy:
  true in-generation tool-calling and a trained policy π (seams in place for both).
- **Deferred-review batch (A-021/A-022/A-024/B-005/B-012/B-013/D-008/D-013/D-014).** Closed the
  pending review findings in one pass. **A-021:** process-global LLM accounting state is now serialized
  by `llm.run_session()` (a process lock + reset/tag/clear) wrapping the whole `orchestrator.run`, so two
  overlapping runs in a long-lived host (TUI/web) can't corrupt each other's token tally or telemetry
  attribution; the invariant is documented. **A-022:** the analytical nodes (`extract_canon`,
  `consolidate`, `learn`) now run at explicit low/0 temperatures (`models.yaml`) for reproducibility.
  **A-024:** a configurable, mild **repetition penalty** on the writer (`frequency_penalty: 0.3`,
  `presence_penalty: 0.1`) attacks token-level repetition — the core slop the humanizer cleans up — at the
  source. **B-005/A-017:** the embedding cache key is namespaced by model (no stale-vector contamination)
  and written atomically under a lock (no lost updates from concurrent prefetch). **B-012:** `stream_text`
  (TUI chat) now honors the run token budget and records usage + telemetry from the final stream chunk, so
  chat no longer bypasses the kill-switch and accounting. **B-013:** a `context_length_exceeded` rejection
  is recovered by shrinking the prompt (headroom, else truncation) and retrying once, instead of failing
  the node. **D-008:** the book pipeline gets a deterministic **cross-chapter cohesion report**
  (`cohesion_report.md`) flagging reused phrasings and formulaic openers across chapters (a detector — a
  full 10-chapter rewrite is impractical/lossy). **D-013:** an opt-in prompt/completion debug sink
  (`WRITINGAGENT_LLM_DEBUG=1` → `.index/llm_debug-*.jsonl`). **D-014:** the agentic action trace now
  carries the run's `run_id`/`ts`, so controller decisions join to the telemetry JSONL. +17 tests.
- **Resilience + safety hardening (from an exhaustive review).** A global **fallback model**
  (`models.yaml` `fallback:`, default `deepseek/deepseek-v4-flash`): any node whose primary model
  exhausts its retries (outage / 5xx / content filter) retries **once** on the cheap tier, so one
  failure degrades the run instead of killing an unattended book. A **context budget**
  (`Settings.max_context_chars`, default 24000) bounds the assembled canon+summaries+excerpts block by
  priority, so a long book can't silently overflow the model window. **Crash-safety ordering** in the
  commit path: canon is now committed to SQLite + rendered *before* the chapter `.md` (the resume
  marker) is written, so a crash mid-commit re-runs the chapter (idempotent extraction) instead of
  permanently skipping it with its facts missing from canon. The **web demo** now serializes runs
  (`_RUN_LOCK`) and clears every prior visitor's provider key from the process env before each run
  (no cross-visitor key/billing leak), and caps topic length. Plus `Critique` 1–5 scores are clamped,
  the fact-check panel gates on `deep_research` (can't false-refute on snippet-only sources), and the
  `ModelConfig` default model matches the DeepSeek-only spec. +6 tests.
- **Anti-slop single source of truth (`slop.py`).** The banned-word lexicon (verbs, adjectives,
  transitions, intensifiers, phrases, openers) now lives in one module; the writer's `NO_SLOP`
  constraint block is **generated** from it, and the deterministic humanizer is cross-checked against
  it by a test, so the writer's rules and the post-hoc stripper can't silently drift. Resolves the old
  contradiction where the writer prompt hard-banned "optimize" while the humanizer deliberately allowed
  it — both now treat `optimize`/`navigate` as documented `TECHNICAL_EXCEPTIONS` (precise in technical
  prose, the LLM judge decides). The humanizer also now catches every banned adjective the prompt lists.
- **Config range validation.** `load_settings` clamps out-of-range values (e.g. `min_insight: 99`,
  negative `max_revisions`, `escalate_below_confidence: 5.0`) to sane bounds, so a typo in
  `settings.yaml` degrades gracefully instead of producing baffling runtime behavior. +4 tests.
- **Agentic controller TUI surface.** `/agentic on|off|llm|default` (toggles the setting *and* flips
  the live project's controller via `orchestrator.apply_controller`), `/trace` (prints the project's
  `agent_trace.jsonl`), and a controller-decision line in the run dashboard. Phase-3 mid-unit research
  (an evidence gap pulls one research brief into the next revision) and the fact-check panel are wired
  into the article pipeline. Live-validated end-to-end on OpenRouter ($0.10, the LLM controller chose
  research→research→draft).
- **Agentic controller (opt-in self-directing loop, plan §21).** New `agentic/` package turns the
  fixed write→critique pipeline into a *self-directing* one: a controller chooses the next move for
  each unit (gather research / read canon, then draft) instead of always drafting immediately. The
  core safety property — tools wrap the **existing** functions at their current granularity, so
  `draft` *is* the unchanged `_process_chapter` / `_process_article_section` episode (duel +
  `record_chapter` fire inside it untouched) — means agency lives only *between* episodes and the
  self-improving loop can't regress. Ships **default-off** (`Settings.agentic=False`); enabling it
  bakes `controller="agentic"` into run-state and routes each unit through `agentic.run_unit`. Three
  pluggable policies behind one seam: **DefaultPolicy** (== the fixed pipeline; the fallback and the
  equivalence guarantee), **LlmPolicy** (a ReAct controller call via `CONTROLLER_SYS`, falling back
  to draft on any illegal/failed choice), and **TracePolicy** (the Phase-5 learned-policy swap seam).
  Adds an append-only `agent_trace.jsonl` per project, an `extra_context` seam on both unit
  processors for mid-draft tool use, and `panels.fact_check_panel` (majority-vote claim verification).
  Opt-in is free across surfaces — `Agent(agentic=True, agentic_policy="llm")` and `/set agentic true`
  both route through `Settings`. +15 offline tests incl. the agentic-vs-pipeline byte-equivalence
  check; full suite green.
- **First-run key wizard + `/setkey` (onboarding friction).** A writer with no API key used to hit a
  dead-end warning. Now the shell opens with a one-keypress choice: **paste a key** (written to `.env`
  *and* applied live — no restart), **try it free** (placeholder output, $0 — set live, no
  "restart with `WRITINGAGENT_FAKE=1`" dance), or **skip** and add one later. New **`/setkey [<key>]`**
  command saves the active provider's key to `.env`, applies it live, and turns off fake mode — the
  "I'll add a key later" path. The welcome leads with one action (`write`), points the no-key block at
  `/setkey`, and frames manual control as "press `m` to pause & steer" rather than a separate command.
- **Web demo is the front-door CTA.** `README.md` now opens with "Try it in your browser," linking
  the web demo before the install steps.
- **Zero-install web demo (`web/app.py`, `pip install -e ".[web]"`).** A small Gradio front-end over
  the public `Agent`/`Project` facade so anyone can try the pipeline in a browser — no terminal, no
  install, no key. A **free preview** runs the whole flow offline (fake mode) to show its shape at zero
  cost; a **real run** lets a visitor paste their own provider key and get a genuine piece plus the
  populated evidence report. Streams live progress, and ships with a Hugging Face Space config
  (`web/README.md`). The package never imports gradio (the demo imports it lazily). Lowers `PRD.md`'s
  #1 adoption barrier (CLI + API key).
- **Citation-quality gate (source authority).** Sources are now scored for *credibility*, not just
  influence: a deterministic `source_authority(url)` rates each domain 0–100 (government / standards /
  primary research and established outlets promoted; SEO / template / content-farm pages demoted; unknown
  domains stay neutral). Authority breaks influence ties so a heavily-cited low-authority pad ranks below
  an equally-cited credible source, an uncited low-authority pad is dropped from the References list, and
  the **evidence report now shows credibility** (high-authority count, average authority, and a ⚠️ flag
  when low-authority sources are present). The article/book critics flag a *decorative* citation (the
  source doesn't back its sentence) as BLOCKING and treat padding / low-authority / off-topic citations
  as nits (deliberately not blocking, to avoid revision thrash). Closes the blind-A/B "citation quantity
  ≫ quality" weakness. All authority tiers are tunable constants in `polish.py`.
- **Learning loop v2 — ablation duels (`skill_duels`, opt-in).** The old skill-efficacy signal was
  confounded (every applied skill got the same chapter-level credit; no counterfactual). Now, on a unit
  with an undecided skill, one **extra draft is written with that skill held out** and the critic
  compares it to the full-skill draft — a true cause-and-effect test of the skill's lift. `reconcile`
  prefers a smoothed duel win-rate (sample-gated) over the first-pass fallback. Adds a draft only while a
  skill is undecided; off by default. Also **`skill_distill`** (deterministic, non-destructive retirement
  of near-duplicate skills; off) and **`watch_blocking`** (watch-list now blocks only *clear/concrete*
  violations instead of unconditionally; `false` = advisory). `/skills` shows the duel win-rate.
- **`learning.md`** — a layman's, chronological guided tour of the whole codebase (folders, files, the
  studio-of-specialists model, the brain-on-disk design, model routing, and the *why* behind each).
- **Colourblind-safe `highcontrast` theme** (Okabe-Ito; ok = blue, error = vermillion — never a
  red/green pair). 11 themes total.
- **Whole-run ETA** on the live dashboard (~Nm left, from this session's average time-per-unit).
- **First-run onboarding**: with no API key set, the welcome shows how to set the key *or* try the whole
  flow free with `WRITINGAGENT_FAKE=1`, instead of suggesting a command that would fail.
- **Evidence report (shareable proof, deterministic).** Every article now ships an
  `evidence_report.md` - the thesis it argues + every source ranked by influence (0-100), built from
  the finished manuscript with no model call. Auto-generated at assembly, refreshed by `polish`,
  regenerated on demand via the new **`evidence`** command and `Project.evidence_report()`. Turns the
  otherwise-invisible trust machinery into something a reader can see.
- **Output-first README + positioning.** New spearhead one-liner ("argues a thesis and cites real
  sources - not slop"), a **"Why not just prompt ChatGPT?"** comparison, an **Evidence report**
  section with a real sample, and an **`examples/`** gallery shipping a complete generated article +
  its evidence report (and a Colab zero-install quickstart). Plus a **`PRD.md`** product-requirements
  doc (problem, users/non-users, JTBD, differentiation, OSS metrics, roadmap, validation, competitors).
- **Blind A/B benchmark kit** (`benchmarks/blind_ab/`) - validates the core "beats just prompting
  ChatGPT/Claude" claim: generate Writing Agent's side for a prompt set, paste the competitor side,
  score anonymized A/B (format tells stripped, key hidden), then tally the win-rate. Run-local
  artifacts are gitignored; only `RESULTS.md` is committed.
- **TUI UX overhaul (production-grade interaction layer).** A staff-level pass over the terminal
  experience: (1) **no command dead-ends** - a reserved word typed without its slash (`help`,
  `features`, `theme`, `provider`, …) now runs the command with a one-line hint instead of silently
  falling through to the chat assistant (a `\` prefix forces chat). (2) **Trust chip** - the critic's
  raw `verdict=approve confidence=0.50 blocking=1` line is normalized to `✓ approved · insight 5/5 ·
  confidence ●●●○○`, with the invariant that a blocking issue never reads as a bare "approve"
  (`ui.trust_chip`). (3) **Run dashboard** - a soft ETA (rolling-median per stage), an always-visible
  "Ctrl-C pauses · resumable" controls line, and a "self-edits" summary line (revisions/humanizer
  passes). (4) **Structured recovery** - a clear *paused* card (budget-cap vs interrupt, with resume
  + alternatives) and export failures that say *why and how to recover* (file locked / missing
  optional dep) instead of a quiet skip. (5) **Accessibility** - `WRITINGAGENT_A11Y` line-mode (no Live
  redraw; append-only full-sentence status for screen readers), `WRITINGAGENT_REDUCED_MOTION` (static
  stages, no spinner), and a one-line wordmark fallback on narrow (<60col) terminals. (6) **Proactive
  key check** - the banner warns when the active provider has no API key (before the first call fails).
  (7) **Progressive help** - `/help <topic>` shows just the matching commands. (8) **Live run
  controls** - a background, cross-platform key-listener lets you steer an autonomous run from the
  dashboard: **esc/p** pauses cleanly at the next unit boundary (resumable) and **m** drops to manual
  review. Wired through a new opt-in `orchestrator.run(control=...)` hook that's checked only at unit
  boundaries (a model call can't be interrupted mid-token); `control=None` keeps every existing caller
  unchanged. Active only for autonomous runs on a real TTY.
- **Clean references, citations & figures (deterministic polish)** - a new pure-Python `polish.py`
  pass (no LLM, ~0 tokens) runs at article assembly and fixes the output-quality problems that came
  from the *writer* authoring its own sourcing and figures. It builds **one end `## References` list
  ranked by influence** - how often each source is actually cited in the body (weighted) plus title
  overlap with the thesis/headings, scored 0-100, dated, sorted most-influential first
  (`rank_references`, on) - **strips the inline `[N]` markers** from the prose *after* scoring so the
  body reads clean and all sourcing lives in the end list (`strip_inline_citations`, on), pulls
  **stray mid-article reference dumps** out of the body (headed blocks *and* bare `[N] …` runs), and
  **de-duplicates figures** (drops any diagram the model still drew, its self-numbered "Figure N.N"
  caption-heading, and a redundant embedded SVG, so a figure never appears twice). `ARTICLE_WRITER_SYS`
  now **forbids the model from drawing figures, self-numbering `Figure N`/`Listing N`, writing
  captions, or emitting `[N] Author…` reference lines** - the producer owns references and figures.
  New **`polish` command** / `repolish_manuscript()` re-applies the whole pass to an *already
  generated* manuscript and refreshes its exports with no model call - the cheap way to fix an
  existing article.
- **Quality machinery II (independence · verification · compounding)** - breaks the "one model
  judges its own output" ceiling (plan §15.6). A **side-by-side tournament judge**
  (`tournament_judge`, on) reads the divergent drafts together and picks the winner instead of
  comparing each draft's isolated 1-5 self-score (scalar `_crit_better` is the fallback); the
  winner's noted weakness feeds the refinement pass. **Claim↔source verification**
  (`verify_claims`, on; articles) checks each in-text `[N]`-cited specific claim against its
  actual source text and makes an unsupported one BLOCKING. The article writer now **engages the
  thesis's steelmanned counterargument** head-on rather than dodging it. A **closed table-read
  loop** (`table_read_revise`, off, autonomous-only) applies the skeptical reader's single
  highest-impact fix as one bounded, version-snapshotted revision. The **learner** now distills
  skills from the model's own **preference data** (tournament outcomes + revision fixes, logged to
  `learning_signals.md`) as a secondary candidate-only signal. New `judge`/`verifier` model slugs
  (route cross-family for independent judging).
- **Quality machinery (originality over slop-absence)** - a per-article **thesis** (contestable
  claim + steelmanned counterargument/rebuttal) injected into every writer/critic call and
  enforced by the critic; **voice exemplars** (`brain/users/<id>/voice/`, fed by `/praise`)
  matched on every draft; **divergent first drafts** (best-of-N at varied temperatures, critic-
  or human-picked); an **insight score** (1-5) with a `min_insight` approval gate plus
  clarity/structure/evidence scores and deterministic structural style metrics; a **surgical
  humanizer** that detects AI tells deterministically and rewrites only flagged sentences
  (citations/numbers/length guarded) instead of re-generating approved prose.
- **Trust machinery** - **version snapshots** (`<project>/versions/`, every variant/revision/
  final) with `versions` and `read --v K`; **`revise --chapter N --instruction`** to rewrite one
  committed unit of a finished piece with a semantic + text diff to accept/reject; **`brief`**
  (goal panel) and a dashboard goal line; **`tableread [--as "persona"]`** skeptical-reader pass;
  **`eval`** quality report (judged 5-dimension rubric + deterministic metrics → `eval_report.md`).
- **Interactive TUI** - escalation picker (fix/instruct/approve-as-is/go-autonomous/read on a
  stalled unit), manual divergent-variant picking, outline+thesis approval gate after `new`,
  post-run summary card + terminal bell, and a draft-opening glimpse in the dashboard.
- **Diagram quality overhaul** - the `diagram` node moved to DeepSeek V4 Pro with a
  16k budget and a rewritten information-design prompt (archetypes, typography
  hierarchy, edge-label pills, lane layouts, on-figure metric annotations, legend
  placement, one focal emphasis). A deterministic **SVG fill guard** forces
  `fill="none"` onto every connector path (a missed one renders as a giant black
  polygon), and a **flash-tier fallback** (`diagram_fallback` node) draws the figure
  when the pro tier reasons itself out of budget and emits no SVG.
- **Animated run dashboard** - the dashboard is now a live Rich renderable
  (auto-refreshed ~8×/s), so the elapsed clock ticks and active stages
  (drafting/critiquing/humanising…) show a spinner with moving dots during long
  model calls instead of freezing until the next log event.
- **Compact welcome screen** - the startup screen shrank from ~66 to ~33 lines so the
  wordmark stays visible at the first prompt; the full command list moved to `/help` and
  the feature board to a new **`/features`** command (one-line feature status in the
  footer). The bottom status toolbar was removed (state lives in the prompt + footer),
  and a red warning fires at launch when `WRITINGAGENT_FAKE` is set so test mode can't
  silently swallow real runs.
- **Run-mode toggle** - `/auto [on|off]` (aliases `/autonomous`, `/manual`) and
  `run --autonomous`/`--manual`, which also clear a stalled per-unit review when going autonomous.
- **Export overhaul** - PDF code/diagram wrapping (no more right-edge clipping), Mermaid blocks
  rendered to PNG via mermaid.ink with a per-project disk cache (offline re-exports), EPUB packages
  diagrams as real image items, U+2011/U+202F glyph normalization, `[AUTHOR NAME]` placeholder and
  `Section N:` prefix cleanup, and per-section reference consolidation + renumbering.
- **`write` command** - one-shot autonomous flow: an upfront interview (LLM-generated
  clarifying questions on audience, depth, length, tone, must-includes, byline, output
  format) followed by a fully autonomous run to a finished, exported file. Answers are
  threaded into the planner and every writer/critic call as high-priority requirements.
- **Theme system** - 10 TUI themes (`editorial` default, `kazama`, `supabase`,
  `violet-bloom`, `t3-chat`, `starry-night`, `vercel`, `fallout`, `mimi`, `astrovista`),
  each with its own palette, wordmark figlet face, gradient, and glyphs. Switch live with
  `/theme <name>` (persisted via the new `theme` setting); pairwise accent-distinctness and
  font availability are test-enforced.
- **Deep multi-source researcher** (`deep_research` setting) - query expansion, concurrent
  multi-query search, full page-text fetch (Scrapo or stdlib), cross-source synthesis with
  numbered citations.
- **Run cost kill-switch** - `max_run_tokens` pauses a run cleanly once its total token
  spend crosses the cap; resumable as always. Live dashboard shows `tokens / budget` and
  real USD cost (OpenRouter `usage.cost`).
- **Structured telemetry** - one JSONL record per LLM call (run, project, unit, model,
  latency, attempts, tokens, cost, error) under `.index/telemetry/`; `/dashboard
  [<project>]` renders the rollup in the TUI with per-model and per-unit breakdowns.
- **Prompt-injection defense** - all web-fetched content is fenced as data-only
  (spoof-neutralized markers + standing instruction) at every research → prompt path.
- **Fetch safety gate** - the deep-research fetcher now enforces an SSRF guard (hosts
  must resolve to globally-routable addresses only; redirects re-validated per hop),
  honors robots.txt per host (`WRITINGAGENT_IGNORE_ROBOTS=1` to skip), and rate-limits
  requests per host (1s politeness interval).
- Open-source scaffolding: `LICENSE` (MIT), `CONTRIBUTING.md`, `SECURITY.md`,
  `CODE_OF_CONDUCT.md`, issue/PR templates, GitHub Actions CI (Linux/macOS/Windows
  × Python 3.10–3.13), ruff config, and pre-commit hooks.
- Live `run` dashboard (elapsed time, live token count, stage, event log).
- Argument/value autocomplete and persistent shell history in the TUI.
- Rich `status` (phase stepper + word count + reading time), Markdown-rendered
  `read`/`memory`, and skill efficacy bars.
- Token-usage telemetry, on-disk caching for web search + SVG diagrams, and a
  `--plain` / `NO_COLOR` mode.
- Per-request `request_timeout` setting.

### Changed
- **Cache-friendly prompt ordering (token efficiency, no quality cost).** The writer + critic prompts
  (book & article, `nodes.py`) now lead with the stable, cross-unit blocks (plan/outline → author
  requirements → thesis → voice exemplars) and place the per-unit blueprint + volatile revision state
  last, so a provider's prompt-prefix cache spans the shared head across every unit. Pairs with the
  `openrouter_providers` setting (pin a cache-capable upstream so DeepSeek's auto prefix-cache engages).
  This changes prompt *text*, not meaning — output is no longer byte-identical to prior runs, but
  quality/consistency are unaffected.
- **Run-scoped research memo (`agentic/tools.py`).** The inline-tool / controller writer re-issuing the
  same research query within a run no longer repeats the web search + LLM synthesis — the synthesized
  brief is cached by `(unit, query)` and auto-cleared when the `run_id` changes.
- **Natural language now runs *any* slash command, including `/set`.** The chat assistant's system
  prompt (`_const.py`) was expanded to document the full slash surface with NL triggers (`/agentic`,
  `/auto`, `/mode`, `/model`, `/provider`, `/path`, `/praise`, `/theme`, `/features`, `/dashboard`,
  `/trace`, …), and `/set` was removed from the chat denylist (`dispatch.py`) so config requests
  ("turn on researcher", "set chapters to 12", "use the poe-gothic persona", "write with a grief tone")
  execute from plain English. Reversible config + each executed line is echoed; only `/user` (identity)
  and `delete` (destructive) stay manual. Also fixed a latent inconsistency where the prompt told the
  model to emit `/set` while the extractor silently dropped it (so "turn on web search and write" never
  enabled search).
- **Anti-slop lexicon fully single-sourced (A-008 follow-up).** The humanizer's tell-detector regex
  (`_TELL_RE`) is now GENERATED from `slop.py` (`slop.tell_pattern()`) instead of being a parallel
  hand-maintained pattern — the morphological rules (verb inflections, apostrophe tolerance, the
  "in today's [anything]" wildcard) live in `slop.py` too. Adding a banned word there now updates both
  the writer prompt and the stripper, so they can't drift; the cross-check test became a guarantee by
  construction. (Also added `boast→have` to the lexicon.)
- **`cli.py` split into a `cli/` package (C-011).** The 1003-line CLI god-module is now a facade
  `__init__` over six seams — `_common` (console / project+path resolution / spinner / diff), `create`
  (the `new` command + outline gate), `interview` (the autonomous `write` flow), `commands` (the core
  project commands), `export` (export/polish/evidence), and `app` (registry + argparse + `main()`).
  `cli.X` and `from writingagent.cli import X` resolve unchanged for the entry point, the shell, and the
  test suite; largest seam is 301 lines. Pure code movement, suite-gated.
- **Exports show their absolute path** — `✓ pdf  /abs/path/manuscript.pdf` (clickable) so "where's my
  file?" is never a guess; the default export dir is the project's brain folder, not the writer's cwd.
- **Internals reorganised into packages (behavior-preserving).** The two largest modules were split
  behind stable facades so every `orchestrator.X` / `shell.X` import is unchanged: `orchestrator/`
  (`common · book · article · export · manage · review`) and `shell/` (`branding · help · commands ·
  dashboard · chat · dispatch · slash · session · repl`). Preceded by a book↔article de-duplication pass
  (shared draft/critique/finalize/learner scaffolding). No file now exceeds ~1k lines.
- **Friendlier, recoverable errors** — bad/missing API key, rate-limit, network blip, and locked export
  files now show a clear next step (`ui.explain_error`) instead of a raw `RuntimeError: …`.
- **`/features`** lists the new toggles (`skill_duels`, `skill_distill`, `watch_blocking`); live-run
  controls wording clarified (all interrupts are resumable; `/delete` discards).
- **Token / cost-efficiency pass** (telemetry-grounded; quality unchanged). Prompt tokens were ~58%
  of spend, mostly repeated prefixes, so the work targets repetition without touching output: (1)
  **cache-hit telemetry** - `usage.prompt_tokens_details.cached_tokens` captured per call, rolled into
  `usage_summary` ("N cached, X% of prompt") + the JSONL, so the provider prompt-cache discount is
  measurable; (2) **lossless schema shrink** - the JSON-Schema dumped on every structured call drops
  pydantic's auto `"title"` keys (~20-30% smaller; types/enums/required intact); (3) **`use_headroom`
  now defaults OFF** - it saved ~nothing on single-turn payloads and could perturb the cacheable
  system prefix; (4) **thesis brief** - the critic + judge get claim+arguments only
  (`nodes.thesis_brief`); the full thesis still goes to the writer (it must engage the
  counterargument); (5) **per-node `max_tokens`** in `models.yaml` + `ModelConfig.max_tokens_for`
  (defaults unchanged - a tuning lever); (6) chat history 10→8.
- **Actually claim the DeepSeek prompt-cache (OpenRouter).** Telemetry showed `cached_tokens: 0` -
  OpenRouter load-balances DeepSeek across upstreams and only some cache. New **`openrouter_providers`**
  setting pins the upstream order (e.g. `DeepSeek`, fallbacks on) via OpenRouter's `provider` routing;
  measured live, this cached ~80% of the prompt prefix at ~3.5x lower cost vs default routing (which
  never cached). Cache-hit detection also now reads DeepSeek-direct's `prompt_cache_hit_tokens`, so
  hits are visible whichever host is active. For guaranteed caching, `provider=deepseek` is best.
- **`divergent_skeletons` setting (opt-in, default off):** draft the N divergent variants SHORT, judge,
  then expand only the winner to full length - cuts discarded-draft completion tokens ~60%. Off by
  default (a skeleton reveals less than a full draft); enable and A/B against telemetry.
- **Diagrams: structured spec → deterministic renderer.** The model no longer emits SVG
  (it can't measure text, so labels overflowed and edge pills collided). It now returns a
  structured `DiagramSpec` (nodes/edges/labels/archetype) and a new pure-Python layout engine
  (`diagram.py`) measures text, sizes boxes to fit, places nodes on a grid (so boxes can't
  overlap), routes orthogonal edges, and draws explicit arrowheads (PDF-safe). Back edges are
  detected via DFS so a feedback arrow no longer reverses a pipeline. `flow` and `layered`
  archetypes; `cycle`/`comparison` degrade to `flow`.
- **`diagram_engine: auto` now defaults to the built-in engine** (`auto|d2|builtin`). It measures
  text and lays figures out compactly (~590px with title, lane headers, readable boxes), and the
  `comparison` archetype de-duplicates repeated relationship labels (`provides`×3 → ×1) so edge pills
  no longer stack/overlap. **D2 + ELK is now explicit opt-in** (`diagram_engine: d2`): the same
  `DiagramSpec` is laid out by the [D2](https://d2lang.com) CLI with ELK (a colour legend is injected
  to match the built-in engine), but it tends to render very wide and hard to read, so it is no longer
  auto-selected just because the `d2` binary is present ($WRITINGAGENT_D2 / PATH still locates it when
  opted in). The zero-dependency built-in engine stays the default and the fallback.
- **`use_researcher` now defaults on** - citations are unverifiable otherwise; with it off the
  critic flags specific stats/attributions as fabrication risks and production warns.
- **Critic routed to `deepseek-v4-pro`** - insight scoring and thesis checks need the pro tier's
  judgment (was flash). Writer temperature set explicit (0.9); humanizer dropped to 0.3.
- PDF page size A5 → A4 so code fits.
- Hardened LLM calls: classified retry with exponential backoff, fail-fast on 4xx,
  request timeout, and a real structured-output repair retry.
- Atomic, resumable on-disk state; durable against crashes mid-run.
- `pyproject.toml` is now the canonical dependency source; packaging metadata
  completed (license, authors, URLs, classifiers, `dev`/`headroom` extras).

### Fixed
- **Review-driven fix sweep (2026-07-16).** A full-codebase review (redundancy · mismatches ·
  optimization) across every subsystem drove one batch. All confirmed defects fixed; suite green
  (**523 passed / 1 skipped**), ruff clean. No dead `Settings` keys were found (all 55 are read).
  - **Escalation no longer desyncs the per-unit score arrays (`review.py`, `common.py`).** Approving an
    escalated chapter/section (`approve_escalation`) committed the unit but never appended to
    `state["scores"]`/`["insights"]`, so every later `scores[n-1]` lookup (the agentic `revise` target,
    the summary card) pointed at the WRONG unit (and could `IndexError`). `_escalate` now stashes the
    blocking critique's scores and `approve_escalation` re-appends them via `_record_escalated_score`,
    keeping the arrays 1:1 with `committed`.
  - **Citation-preservation guard was blind to `[N12]` markers (`humanizer.py`, `surgery.py`).** The
    guard matched only `[\d+]`, so a humanizer/surgery rewrite could silently strip an N-style
    synthesis citation while passing the guard. Now matches `[N?\d+]` (mirrors `polish._INLINE_CITE`).
  - **Surgical craft passes honor the register in their anti-slop guard (`surgery.py`).** A valid
    literary rewrite using a word the register permits (`landscape`, an em-dash) was rejected as "new
    slop" because the guard used the register-neutral tell matcher; the register's matcher is now
    threaded through `apply → show_dont_tell/de_passive → _guard`.
  - **`max_context_chars: 0` ("unbounded") is honored (`book.py`).** The orchestrator collapsed an
    explicit `0` to `None` (re-capping context at 24000), contradicting the config contract (`0` =
    unbounded, which `_within_budget` already honors); the setting is now passed through unchanged.
  - **Chapter-writer length-truncation recovery works (`llm.py`).** The empty-`finish_reason=length`
    recovery only grew `max_tokens` when below 16000, but the chapter writer requests 16000 — so a
    truncated chapter re-sent the same doomed budget until its retries were spent. A shared
    `_LEN_RETRY_CEILING` (32000) gives real headroom in both `complete_text` and `complete_structured`.
  - **Learned-policy corpus no longer poisoned by `revise` (`learn.py`, `book.py`, `article.py`).** A
    `revise` re-commit re-labelled a unit `first_pass=False`, overwriting the genuine first-draft
    outcome and skewing `train_policy`; unit-outcome trace records now carry `revised` and the collector
    keeps the first (unrevised) outcome per unit.
  - **Agentic critique panel now runs for books too (`book.py`, `nodes.py`).** `agentic_critique_panel`
    was wired only in the article pipeline (silently ignored on books); `critique_chapter` gained a
    `lens` param and the book gate runs the diverse-lens majority review. (The article fact-check panel
    has no book analogue — a chapter has no per-unit research source to verify against.)
  - **`Store.open` no longer leaks the SQLite connection on a corrupt/locked db (`store.py`).** A
    non-`OperationalError` during schema init now closes the connection before propagating, so a
    caller's `finally: store.close()` can't be starved (Windows/synced-folder resilience).
  - **Web dashboard: dropped raster images render (`webui/server.py`).** `images/*.png|jpg|…` were
    404'd (only `.svg` was whitelisted) and would have crashed a `read_text`; they're now served as a
    data-URI `<img>`. Finished/errored jobs are pruned (cap 20) so a long-lived dashboard can't grow its
    event buffers (or the `/api/state` payload) without bound. Removed a permanently-empty `_evals` glob.
  - **Exported `<img>` tags no longer corrupt on a recurring src (`export.py`).** The data-URI/path swap
    now replaces only the captured `src="…"` span, not a bare `str.replace` that also rewrote a matching
    `alt`/`title`.
  - **Shell: `seo`/`promote`/`polish`/`evidence` no longer silently no-op with ≥2 projects
    (`shell/dispatch.py`).** Added to `_NEEDS_PROJECT` so they trigger the project picker instead of a
    swallowed `SystemExit`.
  - **Emotion resolution matches whole words (`emotions.py`).** `hopeless` no longer resolves to its
    opposite `hope` via substring; free-text roles like "a sense of dread" still resolve.
  - **SEO keyword density uses word-boundary matching (`seo.py`).** A phrase keyword ("data model") no
    longer over-counts inside a longer word ("data modeling") and falsely trips the stuffing warning.
  - **Misc.** `apply_cost_mode` no longer mis-tags the telemetry thread (via a side-effect-free
    `ModelConfig.resolved_for`); `configure_timeout`/`configure_provider` only discard the cached OpenAI
    client when the value actually changes; `render_canon` batches its per-character reads (removed an
    N+1); book production gained the article's assembled-manuscript resume guard; `cmd_status` reads the
    manuscript once; stale `book review`/`book run`/`book new` hints in run messages → `review`/`run`/
    `new`; the `/agentic` help line and the chat theme list (missing `highcontrast`) were corrected;
    `web` is now discoverable in the shell command list.
  - **Dead code removed.** `prompts.HUMANIZER_SYS` (unused — the live path is the surgical humanizer;
    it also re-hardcoded the slop lexicon), `personas.Persona.exemplar` (never populated) and
    `personas._KINDS` (unreferenced); the duplicated `_avg` closure (now `_score_avg`) and the
    `_DELIVERABLE` filename table (now single-sourced from `brain.EXPORT_DELIVERABLE_BY_FORMAT`).
    `CRITIC_SYS`'s example tells are now generated from `slop.BANNED_VERBS/BANNED_TRANSITIONS` so they
    can't drift from the lexicon.
- **Structured-output truncation on the reasoning tier (`llm.py`, `models.yaml`).** A reasoning model
  (`deepseek-v4-pro`) spends tokens *thinking* before it emits JSON; when that filled `max_tokens` the
  reply came back empty / cut off with `finish_reason=length`, and the old retry re-sent the same
  too-small budget (futile repair turns) before degrading to the flash fallback — wasting a pro call each
  time (observed live once on the first real OpenRouter run). `complete_structured` now detects a
  length-truncation and **raises `max_tokens`** (double, capped at 16k) then retries the **same**
  model/prompt with no repair turn, so the call stays on its stronger routed tier. Complemented by a new
  `models.yaml` `max_tokens:` floor for the judgment nodes (`critic`/`judge`/`verifier` = 8000) so the
  common path has reasoning headroom up front — the same guard the `diagram` node's 16k budget relies on.
  Verified by a unit test and a real-API check (forced truncation recovers on-tier, no flash fallback).
- **Rich-markup hotkey/hint bug class (TUI).** A literal `[x]` whose contents read as a style name
  (letters/spaces) was parsed as a markup tag and silently dropped, eating the leading character. Fixed
  in the review/escalation menu (`dashboard.py` — the `[f]/[i]/[a]/[g]/[r]/[s]` hotkeys) and the `/path`
  + `/use` pickers (`commands.py` — the `[enter to cancel]` hint and the `[article]`/`[book]` type tag)
  by escaping the opening bracket (`\[…]`). `Text(...)`-rendered output (the run event log) is not
  markup-parsed and was unaffected.
- **Test suite no longer reads the developer's personal config (`tests/conftest.py`).** A new autouse
  `_isolated_settings` fixture points `config._SETTINGS` at a tmp path, so the suite always runs against
  shipped dataclass defaults; a local `config/settings.yaml` (e.g. `agentic=true`) can no longer turn a
  local run red while CI (which has no such file, it's gitignored) stays green.
- **Consolidation review no longer returns silently (`dashboard.py`).** A book run in manual mode that
  stalled on a continuity-check contradiction (`pending_review` with `review_kind="consolidation"`) fell
  through the post-run router — which only handled `chapter`/`section` escalations — and dropped back to
  the prompt with no card (only a `[!]` line buried in the event log). It now shows a `_consolidation_card`
  with the resume command (`run --force`), and a catch-all final branch guarantees no not-done terminal
  state ever returns silently. (Autonomous runs auto-repair contradictions, so they were unaffected.)
  Also added `explain_error` coverage for **context-window overflow** and **token-budget** failures.
- **Typing a command word without its slash** (e.g. `help`, `features`) silently went to the chat
  assistant - a dead end (and a wasted LLM call in real mode). It now runs the command.
- **The run summary card's border glued onto the last log line** (`manuscript.md┌─ ✓ complete`) - the
  Live region had no trailing newline before the Panel; a settle newline is now printed first.
- **The critic verdict could read as a contradiction** (`verdict=approve … blocking=1`); the
  normalized trust chip never shows a blocking issue as a bare "approve".
- **The banner hardcoded "OpenRouter · DeepSeek"** regardless of the active provider/model, and (a
  latent bug) `providers.resolve()` returns an id string, not a `Provider`, so the provider name was
  always the fallback - both fixed; the masthead now reflects the real provider, writer model, and
  version (single-sourced from `writingagent.__version__`, bumped 0.1.0 → 0.2.0).
- **`WRITINGAGENT_PROVIDER` configured the model client but never synced `settings.provider`**, so the
  banner and key-warning showed the stale (saved) provider while a different host was actually active;
  `_apply_provider` now updates `settings.provider` to the resolved id.
- `autonomous: true` in `settings.yaml` was silently ignored by `new` (a `store_true`
  flag default shadowed it), so runs paused for review on every low-confidence unit.
  `--autonomous` is now tri-state with a `--no-autonomous` override.
- Long streamed chat replies duplicated themselves into the terminal scrollback
  (non-transient Live + overflow); the reply is now rendered exactly once.
- `read --manuscript` resolves article paths (was hardcoded to books).
- Post-completion `revise` critiqued with less context than the pipeline (no
  watch-list, intake requirements, prior-unit context, or length target), so a
  revision violating them could pass; both book and article revise paths now
  critique with pipeline-parity context.
- A chat stream error mid-reply was rendered as assistant prose, saved to chat
  history, and command-parsed; it now renders as an error and the half-streamed
  reply is discarded from history.
- **CI was red on every Ubuntu job since the workflow landed** (install-time, all
  Python versions): svglib 1.6.0 (transitive via xhtml2pdf) hard-requires
  rlpycairo → pycairo, which has no Linux wheels and fails to build on a bare
  runner. Pinned `svglib<1.6` (xhtml2pdf only uses svg2rlg, not the cairo
  rasterizer) - Linux `pip install` works again with no system packages.
- Wikimedia image search silently returned no results against the live API:
  the code requested `formatversion=2` (pages as a list) but parsed the v1 dict
  shape, and the network-error guard swallowed the resulting exception.
- **PDF exports had no images** when cairosvg isn't installed (i.e. by default):
  the exporter dropped every SVG figure. xhtml2pdf's bundled svglib now renders
  SVG diagrams as vector art directly (cairosvg still preferred when present;
  svglib drops arrowheads but keeps the figure); svglib's per-label font
  warnings are silenced during export.
- **The test suite polluted real telemetry**: retry tests exercising the real
  LLM call path appended toy records (model "m", "401 bad key") to the
  developer's `.index/telemetry`, surfacing as phantom errors in `/dashboard`.
  Brain + index isolation is now autouse for every test.

### Security
- The conversational assistant can no longer auto-execute `delete` / `/user` /
  `/set`; project/user ids are validated and deletes are confined to the brain dir.
  (Later relaxed - `/set` is intentionally allowed from chat so natural-language
  config takes effect; see the "Natural language now runs *any* slash command" entry
  under Changed. `delete` and `/user` remain fenced.)
- Exported HTML is sanitized (script/iframe/event handlers stripped).
- Deep-research fetches are SSRF-guarded (public-address-only hosts, redirect
  re-validation), robots.txt-respecting, and per-host rate-limited.

### Removed
- **The checked-in `requirements.lock.txt` (C-010).** It pinned unresolvable versions and a stale
  editable git self-reference, and nothing consumed it (CI installs via `pyproject.toml` extras, which
  stays canonical). Replaced by `scripts/gen_lock.py` — a generator that resolves the closure of the
  project's declared deps against a clean installed environment (so a shared venv can't pollute the
  lock) — plus a CONTRIBUTING note on regenerating in a clean venv from public PyPI.
- Dead vertical-slice prototype (`run.py`, `src/writingagent/slice.py`).

## [0.1.0]
- Initial book + article pipelines: plan → write → critique → revise → humanise →
  commit, with canon/consolidation, learned craft skills, and six export formats.
