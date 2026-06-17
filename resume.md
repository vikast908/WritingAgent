# Resume - WRITING AGENT

> **Read this first, then `plan.md`.** This is the session log: what happened last time and
> where to pick up. Newest entry on top. **Update it at the end of every working session.**

## Current status

- **New (2026-06-17 - token-efficiency + UX hardening + craft-layer expansion - DONE):** a working
  session on top of the merged compositor branch. Suite green throughout (471 passed, 2 skipped; ruff
  clean). Three threads:
  - **Token efficiency (no quality cost).** (1) **Cache-friendly prompt ordering** - reordered the
    writer + critic prompts (book & article, `nodes.py`) so the stable, cross-unit blocks (plan/outline →
    requirements → thesis → voice) lead and the per-unit blueprint + volatile revision state follow, so
    the provider's prompt-prefix cache spans the shared head across every unit. (2) **Run-scoped research
    memo** (`agentic/tools.py`) - the inline-tool/controller writer re-issuing the same query within a
    run no longer repeats the web search + LLM synthesis; keyed by `(unit, query)`, auto-cleared per
    `run_id`. (3) Personal defaults in (gitignored) `config/settings.yaml`: `divergent_skeletons=true`
    (article skeleton→expand, ~60% fewer discarded-draft tokens), `openrouter_providers=DeepSeek` (pins a
    cache-capable upstream so DeepSeek's auto prefix-cache actually engages - this is what makes the
    reorder pay off). NOTE: the reorder changes prompt *text* (not meaning), so new output is not
    byte-identical to old - quality/consistency unaffected.
  - **UX.** Fixed a **Rich-markup bug class**: a literal `[x]` whose contents look like a style name
    (letters/spaces) gets parsed as a tag and silently dropped. Hit the review/escalation menu
    (`dashboard.py`, hotkeys `[f]/[i]/[a]/[g]/[r]/[s]` vanished) and the `/path` + `/use` pickers
    (`commands.py`, the `[enter to cancel]` hint and the `[article]`/`[book]` type tag vanished). Fixed
    by escaping the opening bracket (`\[…]`, raw f-strings). `Text(...)` paths (the run event log) are
    NOT markup-parsed and were safe. Also: the welcome **footer now shows `agentic on/off`** (replacing
    the redundant `flash` model slot) and surfaces `/agentic on|off` in the hint line (`branding.py`).
  - **NL → any slash command.** Expanded the chat system prompt (`_const.py`) to document the full slash
    surface with natural-language triggers, and removed `/set` from the chat denylist (`dispatch.py`) so
    config requests run from plain English ("turn on researcher", "set chapters to 12", "use the
    poe-gothic persona"). Only `/user` + `delete` stay manual. Fixed a latent bug where the prompt told
    the model to emit `/set` while the extractor dropped it. Test updated (`test_hardening.py`).
  - **TUI lovability pass.** Audited the shell for delight and found the base is already strong
    (`_summary_card`, `_paused_card` exist + are wired). Implemented the genuine gaps: the completion
    card now leads with the **argument made** + **source tally** + **reading time** (new
    `polish.source_stats()`, shared with the evidence report); the welcome shows a rotating, date-stable
    **writing epigraph** + a **"Welcome back."** lead for returning writers (one line; compactness guard
    bumped 14→15); `ui.explain_error()` maps **context-overflow** and **budget** failures to actionable
    fixes. Skipped a redundant `/why` (eval/tableread/summary already show the work).
  - **Test hermeticity.** Added an autouse `_isolated_settings` fixture (`tests/conftest.py`) pointing
    `config._SETTINGS` at a tmp path, so the suite always runs against shipped dataclass defaults and a
    developer's personal `settings.yaml` (e.g. `agentic=true`) can't turn the local run red. CI already
    ran on defaults (the file is gitignored); this makes local match CI.
  - **Craft-layer expansion.** Personas **10→14** (`personas.py` + 4 new original-pastiche exemplars):
    `wildean`, `poe-gothic`, `dickensian`, `whitmanesque` (public-domain manners; no living authors).
    Emotions **8→12** (`emotions.py`): `disgust`, `surprise`, `jealousy`, `pride` - completes Ekman's six
    + the two top dramatic drivers; each adds an anti-cliché deny-list + show-don't-name cue + aliases.
    Counts refreshed in README, plan.md §23, and learning.md.
  - **NEXT STEP:** the bigger UX gap from the audit is **failure feedback in full-auto (autonomous)
    runs** - context-overflow/budget errors aren't mapped in `ui.explain_error()`, and a non-escalation
    pause may show no recovery card. Verify the control flow in `dashboard.run_with_dashboard` and
    `explain_error`, then make those failures actionable. (Audit also flagged discoverability wins:
    `/agentic` policy explainer, `/praise`/`/path` help, missing-dep hints.)

- **New (2026-06-17 - the compositor: personas, emotions, layer composition - DONE, branch
  `feat/compositor-personas-emotions`, stacked on the craft-engine branch):** built the §22.6 deferral
  (the next chapter after the craft engine). Insight: register/persona/emotion/skills are all *voice
  layers over one draft*, so the work is **one composition model**, not silos - and *more layers is
  worse*, so the compositor **selects + resolves conflicts**, never accumulates. Suite green throughout
  (now 250 passed, 1 skipped; ruff clean):
  - **Personas (`personas.py` + `personas/*.md`)** - a *manner* layer (signature card + original-
    pastiche exemplar + compatible registers). 10 ship: 6 archetypes (wry-skeptic, warm-mentor,
    hard-boiled-minimalist, lyrical-maximalist, deadpan-technical, firebrand-essayist) + 4 public-domain
    *manners* (shakespearean, nietzschean, austen-ironic, twain-vernacular). **No living authors**
    (legal/quality); exemplars are original pastiche (zero copyright surface); a persona that doesn't
    fit the register is dropped + logged (register wins).
  - **Emotions (`emotions.py`)** - the *inverse* of a symptom dictionary (which is a cliché generator):
    per-emotion **anti-cliché deny-lists** wired into the `craft.py` cliché detector ('her heart raced'
    now flagged) + a show-don't-name **cue**. 8 emotions, alias-tolerant.
  - **Compositor (`compositor.py`)** - the cascade register⊃field⊃persona⊃emotion⊃skills, single-select
    upper layers. v1 owns the **voice layer**: `compositor.voice()` resolves persona(signature+exemplar)
    > user voice > register gold, + emotion cue; replaces `brain.style_exemplars` at every writer site
    (book/article/review/reader-loop). One slot, no new node params.
  - **Wiring:** `persona`/`emotion` settings (clamped) → `_base_run_state` → writer sites. Spec in
    **plan.md §23**; design+critique in `docs/proposal-personas-emotions-composition.md` (now marked
    ADOPTED/built). Tests in `tests/test_compositor.py`.
  - **NEXT STEP:** §23.6 deferrals - per-unit emotion (map a chapter's `emotional_role` → emotion key),
    persona-aware critic notes, "blend = a new persona" workflow, surface the cascade in the TUI. Both
    branches (`feat/craft-engine-all-tiers`, `feat/compositor-personas-emotions`) pushed, not yet
    merged - open PRs / merge to master when ready.

- **New (2026-06-16 - craft engine: register-parameterized writing, all tiers - DONE, branch
  `feat/craft-engine-all-tiers`):** acted on a craft-POV review that found the agent excellent at the
  *floor* (anti-slop) and the argument *ceiling* (thesis) but **monovocal** (one researcher voice forced
  on every genre) and **model-dependent** for everything else (zero-shot prompts a basic model can't
  execute). Built the fix bottom-up, suite green at every step (now 198 passed, 1 skipped; ruff clean):
  - **Registers (`registers.py`)** - the craft contract as data, 11 profiles (nonfiction default,
    technical, literary/genre fiction, academic, journalism, copywriting, business, poetry, screenplay,
    children). `slop.render_constraints(register)`/`tell_pattern(register)` filter/invert the bans per
    genre (fiction keeps em-dash; academic keeps `moreover` + requires hedging; copy keeps the
    exclamation). **Invariant held + tested: `register=None`/`nonfiction` is byte-for-byte the old
    output.** Inferred from genre/angle unless pinned.
  - **Basic-model levers:** few-shot `exemplars.py` (humanizer before/after + critic 5-vs-2 score
    anchors), a shipped genre-tagged **gold corpus** (`gold/*.md`, package-data) injected by default via
    `brain.style_exemplars`, and a genre-aware **craft-metrics suite** (`craft.py`: sentence-rhythm
    variance, passive ratio, adverbs, FK grade, clichés, opening/closing, and for fiction filter-verbs /
    dialogue / said-bookisms / POV-tense / sensory density) fed to the critic as computed evidence.
  - **Tier 2 (`surgery.py`):** generalized the humanizer's detect→rewrite-only→guard pattern to
    show-don't-tell + passive→active (guards: citations/numbers preserved, defect strictly reduced, no
    new slop); opening/closing detector; deterministic **voice-drift** (`polish.voice_drift`, function-
    word stylometry) folded into the book cohesion report.
  - **Tier 3:** field structural templates (`fields.py`: inverted-pyramid/IMRaD/AIDA/BLUF/how-to/
    three-act/screenplay) injected into the outline architect; citation styles in
    `polish.build_references(style=...)` (influence default · numeric · apa · mla · chicago · ap · none).
  - **Wiring:** `register`/`field`/`citation_style`/`craft_passes` settings (clamped) → run-state →
    threaded through `nodes.write_*/critique_*/cohesion_edit` + `humanizer.humanize` (default `None` ⇒
    unchanged). Spec in **plan.md §22**.
  - **NEXT STEP:** the user approved "finish tiers, then compositor." Next session: build the
    **compositor** (precedence cascade register⊃field⊃persona⊃emotion⊃skills, single-select upper
    layers) + **personas** (archetypes + public-domain, in the voice slot - NO living authors) +
    **emotions** as anti-cliché deny-lists (NOT a symptom dictionary). Full design +
    honest critique in `docs/proposal-personas-emotions-composition.md`. Branch not yet
    committed/merged - review the diff, then commit on `feat/craft-engine-all-tiers`.

- **New (2026-06-16 - all docs refreshed for the agentic controller, parallel agents - DONE):** brought
  the documentation set current with the now-built, live-validated agentic controller, via 5 parallel
  doc agents (each grounded in plan §21 + CHANGELOG + the file's own voice). **README.md:** repositioned
  as "self-correcting AND optionally self-directing" + a real Self-directing-mode section (two scopes,
  three policies, mid-draft tools, panels, safety invariants, `/agentic`+`/trace`, the new settings, the
  live-validation note). **PRD.md:** agentic as a shipped differentiator; roadmap Now/Next; metrics +
  risks. **learning.md:** new plain-English chapter (self-correcting vs self-directing + the learned
  policy) + glossary + section renumber. **test.md:** new session-14 verification entry (433 passed;
  live OpenRouter run). **writingagent/README.md + web/README.md:** one-line agentic mentions. Left
  `plan.md`/`resume.md`/`CHANGELOG.md` (already current this session) and seeds/boilerplate/templates
  (not agentic-related) untouched. Spot-checked README + test.md for accuracy. Committed + pushed
  (`7917e75`). **Nothing left on the agentic front but scale** (live tool-call validation at volume + a
  learned-policy trace corpus large enough to bite); the older showstoppers (independent blind A/B,
  10+ chapter book validation) remain.
- **New (2026-06-16 - LIVE agentic validation + tool-call cap - DONE):** ran the agentic pipeline LIVE
  on OpenRouter (real spend, key from `.env`) to validate the two "scale" items. **Confirmed live:**
  in-generation tool-calling fires (the writer called `research` AND `verify_fact` mid-draft), the
  run-level LLM macro-controller decided (`draft,draft` - sensibly linear for 2 sections), the fallback
  model engaged (pro length-limit → flash), claim-check + critique + revision loop ran, and unit outcomes
  were labelled into the trace for the learned policy. **One full article: `done`, 1,547 words, 61 calls,
  186k tokens (35% cached), $0.15, ~18 min.** **Finding → fixed:** the writer **over-called `verify_fact`**
  (~12 tool calls/draft → the time overrun). Added a **total `max_tool_calls=4` cap** (+ lowered
  `max_tool_rounds` default 3→2) to `llm.complete_text_with_tools` - once either bound is hit, tools are
  dropped and the model must write. +1 test (`test_tool_loop_caps_total_tool_calls`). Throwaway run
  artifacts (script, `livetest` project, debug logs) cleaned up + telemetry scrubbed. **433 passed / 2
  skipped, ruff clean.** Docs: CHANGELOG. **Learned policy still needs corpus volume** (one run isn't
  enough; `train_policy` correctly stays undecided) - that's the only remaining scale item.
- **New (2026-06-16 - "make it completely agentic": all 8 review gaps built - DONE):** closed every gap
  from the agentic review. **#1 rich perception:** `build_run_view`/`build_state_view` now carry per-unit
  quality + weakest unit (`weakest_committed_unit`), open contradictions, and the token budget
  (`_budget_line`). **#2 reoutline + #4 start-of-run:** new `reoutline` macro-action regenerates the
  not-yet-written units' plan (books: TOC; articles: outline.sections), preserving committed units +
  count; legal *before* drafting too = structural agency at the start. **#3 revise:** `revise` rewrites
  the weakest committed unit by re-processing it with a targeted instruction (idempotent canon
  extraction makes it safe; per-unit score arrays re-aligned after). **#5 escalate:** the controller can
  deliberately defer to the human (pause). **#6 richer policy:** `train_policy` is context-conditioned
  (book vs article) on a composite first-pass+insight reward; `research_decision(model, ctx)` consumed by
  `TracePolicy`. **#7 tools+panels:** `verify_fact` in-generation writer tool + `panels.critique_panel`
  (diverse-lens majority) wired into the article gate behind `agentic_critique_panel`; `lens` kwarg added
  to the article critic. **#8 self-monitoring:** budget in the view + `runner._legal_now` drops optional
  polish actions (`OPTIONAL_RUN_ACTIONS`) under budget pressure so low-budget runs still converge.
  Caps `_MAX_REOUTLINE=2`/`_MAX_REVISE=3` bound the autonomy; `RunDecision` Literal widened. All new
  actions are `llm`/`trace`-only → `default` stays the legacy loop → equivalence guarantee intact. +12
  tests (`test_agentic` 36->44). **432 passed / 2 skipped, ruff clean.** Smoke-ran both pipelines with
  all flags (inline tools + critique panel + trace policy) to `done`. Docs: plan §21, CHANGELOG. **Only
  scale remains (not code):** live tool-call validation on a tool-capable provider + a larger trace
  corpus for the learned policy to bite.

- **New (2026-06-16 - "fill the gaps": in-generation tool use + trained policy - DONE):** closed the two
  remaining agentic gaps from the review. **Gap 1 (Phase 3, in-generation tool-calling):**
  `llm.complete_text_with_tools` is a real OpenAI tool-use loop (model emits `tool_calls` → we run
  `tool_runner(name,args)` → feed results back → repeat until prose; final round drops tools to force the
  draft). The writer nodes (`write_chapter`/`write_article_section`) gained `tools`/`tool_runner` params
  and use it when set; the orchestrator builds a runner (`_chapter_tool_runner`/`_section_tool_runner` →
  `unit_research`/`_read_canon_slice`) behind the new `agentic_inline_tools` setting (agentic only,
  default off). Robust: fake mode + any provider/tool error fall back to a plain draft, so a draft is
  always produced; the loop is still ONE episode. `agentic.WRITER_TOOL_SCHEMAS` defines the tool surface.
  **Gap 2 (Phase 5, trained policy):** new `agentic/learn.py` `train_policy(uid)` distills a value model
  from the accumulated trace corpus across the user's projects (off-policy estimation: first-pass rate
  with vs. without gathering; `_MIN_PER_ARM=3` guard → undecided writes nothing), persisted to
  `user_dir/agent_policy.json`, refreshed at every learn phase (`common._train_agentic_policy`, fires
  only when a trace exists). Unit outcomes (`first_pass`) are now labelled into the trace at commit
  (`scope:"unit-outcome"`) so decisions join to results. `TracePolicy`/`TraceRunPolicy` load the model
  and follow it (a learned verdict overrides the online heuristic; falls back when undecided). Opt-in
  only (the `trace` policy), never auto-promoted into the default (invariant §21.0 #3). +9 tests
  (`test_hardening` tool-loop ×3, `test_agentic` ×6). **424 passed / 2 skipped, ruff clean.** Docs: plan
  §21 (status + §21.9), CHANGELOG. **Only scale remains** (not code): live tool-call validation on a
  tool-capable provider + a larger trace corpus for the trained policy to bite.

> **PENDING - remaining items (as of 2026-06-16).** The 9-item deferred-review batch plus C-011, C-010,
> and the A-008 follow-up are all **DONE** (see the top session entries). Suite green (406/2). What's left:
> - **Two deferred showstoppers (older):** independent blind A/B (third-party judge, n≥5) and a real
>   10+ chapter book validation. Both need real API spend (and a human/third-model judge for the A/B) -
>   they cannot be completed in this sandbox. These are the only open review items.

- **New (2026-06-16 - "make it completely agentic": run-level controller + macro agency - DONE):**
  reviewed the agentic system and found agency was confined to per-unit gathering inside a hardcoded
  phase machine; built the macro level. New **`agentic/runner.py`** (`run_loop`) drives the WHOLE run via
  a `RunPolicy`: it chooses the next macro-action (`draft`/`consolidate`/`repair`/`table_read`/`produce`/
  `learn`/`done`) from `RunOps.legal_actions` instead of the fixed `while phase != "done"` loop. New
  `RunDecision` schema, `RUN_CONTROLLER_SYS` prompt, `DefaultRunPolicy`/`LlmRunPolicy`/`TraceRunPolicy`,
  `make_run_policy`, `tools.RunOps`/`RUN_ACTIONS`/`build_run_view`. **Routing (the safety design):**
  `agentic_policy == "default"` STAYS on the legacy phase loop (so the equivalence guarantee +
  unit-only trace are byte-identical - both pinned by tests); only `llm`/`trace` engage `run_loop`, with
  the unit controller (`run_unit`) running inside each `draft`. Mode-specific `_book_run_ops` /
  `_article_run_ops` built at the orchestrator call sites (closures over store/prefetch/plan/toc),
  faithfully reproducing escalation/budget/consolidation-cadence; book exposes `consolidate`/`repair`
  as genuine mid-run choices. Also closed the two narrower review gaps: **read_canon is now
  query-relevant** (`book._read_canon_slice` -> FTS `search_excerpts`, not the whole canon block), and
  **`TracePolicy`/`TraceRunPolicy` are activated** as online trace-conditioned policies (research up
  front after a prior evidence gap; audit early after a past contradiction). +10 tests
  (`test_agentic.py` 21->31), incl. full macro runs of both pipelines through `run_loop` and the
  unchanged equivalence/trace guarantees. **416 passed / 2 skipped, ruff clean.** Docs: plan §21
  (status note + §21.2/§21.9), CHANGELOG. **Honest remaining gap toward "fully autonomous":** true
  in-generation tool-calling (writer calls tools mid-draft, vs today's reactive `extra_context` pull)
  and a *trained* policy π (offline ML on accumulated traces) - seams exist for both, but neither is
  doable in this sandbox (needs a training corpus + a deeper writer-node change).
- **New (2026-06-16 - C-010 + A-008 follow-up: low-priority items closed - DONE):** **A-008:** the
  anti-slop lexicon is now FULLY single-sourced. The humanizer's tell-detector `_TELL_RE` is generated
  from `slop.tell_pattern()` (new) instead of a parallel hand-maintained regex - the morphology rules
  (verb inflections via silent-e stem + `\w*`, apostrophe tolerance, the `in today's [anything]`
  wildcard, caveat/template skipping) live in `slop.py` now, so adding a banned word updates both the
  writer prompt AND the stripper. `test_lexicon_single_source_consistency` strengthened (inflections +
  phrase coverage + caveat-skip) - the cross-check is now a guarantee by construction. Added `boast→have`
  to the lexicon (preserves the old "boasts" detection + bans it in the prompt). **C-010 (user chose
  "delete"):** removed the checked-in `requirements.lock.txt` - it pinned unresolvable versions + a stale
  `-e git+...` self-reference and nothing consumed it (CI installs via pyproject extras = canonical).
  Replaced with **`scripts/gen_lock.py`** - parses pyproject's deps + optional groups, resolves the
  closure against the *installed* env (so a shared/dev venv can't pollute the lock; excludes the project's
  own editable install), prints exact pins; reports uninstalled optional deps on stderr. CONTRIBUTING
  documents regenerating in a clean public-PyPI venv. (Root finding: this sandbox's own PyPI mirror pins
  "future" versions that don't resolve on real PyPI, so no correct lock could be generated *here* - hence
  delete + tool, not regenerate.) **406 passed / 2 skipped, ruff clean.** Docs: CHANGELOG, CONTRIBUTING.
  That closes every actionable review item; only the two API-spend showstoppers remain.
- **New (2026-06-16 - C-011: cli.py split into a cli/ package - DONE):** the last god-module
  (`cli.py`, 1003 lines) is now `cli/` - a 25-line facade `__init__` (`from .seam import *`) + six seams:
  **_common** (110: `_console`/`_project_word_count`/`_paths_for`/`_resolve_book`/`_spin`/`_print_diff`),
  **create** (112: `cmd_new`/`_cmd_new_book`/`_cmd_new_article`/`_outline_gate`/`_autonomous_value`),
  **interview** (171: the autonomous `write` flow - `cmd_write`/`_conduct_interview`/`_ask_batch`/
  `_pick_approach`/`_quick_research`/`_render_intake`), **commands** (301: the 17 core project commands),
  **export** (222: `cmd_export`/`cmd_polish`/`cmd_evidence` + `_resolve_formats`/`_EXPORT_FORMATS`/
  `_EXPORT_FNS`/`_run_exports`/`_report_export`/`_export_failed`), **app** (194: `_COMMANDS`/`build_parser`/
  `_apply_provider`/`main`). DAG acyclic (`_common` ← all; export ← {interview,app}; {create,interview,
  commands} ← app). Facade re-exports every public + test-reached private name, so `cli.X` and
  `from writingagent.cli import X` are unchanged for the `writing-agent` entry point, the shell
  (`from ..cli import _EXPORT_FORMATS`), and the suite. **Same monkeypatch-on-facade gotcha as the shell
  split**: 3 test patch sites that set a now-relocated global (`_console`, `_EXPORT_FNS`) were repointed
  to the seam home (`cli.export`/`cli.interview`) - a function resolves its globals in its defining
  module, not the facade. Per-file-ignore F401/F403/F405 added for the facade. Verified the real launcher
  (`python writingagent.py list`) + facade re-export identity. **406 passed / 2 skipped, ruff clean.**
  Docs: CHANGELOG, plan §20.1. That closes the last god-file. **Next:** C-010 (lockfile regen - needs a
  clean reference env), A-008 followup, the two older showstoppers.
- **New (2026-06-16 - deferred-review batch: 9 findings closed in one pass - DONE):** cleared the whole
  PENDING review list (the user asked to "build all at once"). **A-021 (High):** `llm.run_session()` -
  a process lock + reset/tag/clear context manager - now wraps the entire `orchestrator.run` body
  (split into a thin `run()` + `_run()`), so two overlapping runs in the long-lived TUI/web host
  serialize instead of corrupting each other's token tally / run-id / telemetry attribution; the
  module-global invariant is documented. **A-022:** `extract_canon`/`consolidate`/`learn` now pass
  explicit low/0 temps (added `consolidation: 0.0`, `learner: 0.2` to `models.yaml`; extract_canon picks
  up `summarizer: 0.0`) - they were silently running at the model default. **A-024:** new per-node
  `frequency_penalty`/`presence_penalty` maps in `models.yaml` (+ `ModelConfig` getters that clamp to
  [-2,2], + to_dict/save_config round-trip); the writer ships `0.3`/`0.1` to attack token repetition at
  the source. **B-005/A-017:** `embeddings._key` is namespaced by `_MODEL_NAME` (no stale-vector
  contamination) and `embed_texts` reads-computes-writes under a lock with an atomic `brain.write_text`.
  **B-012:** `stream_text` now `_check_budget()`s, requests `stream_options.include_usage` + cost, and
  records usage + telemetry + debug from the terminal chunk (no auto-retry - a stream can't be replayed;
  documented). **B-013:** `_is_context_overflow` + `_shrink_for_context` recover a `context_length_exceeded`
  rejection by shrinking (headroom else truncate) and retrying once in both `complete_text` and
  `complete_structured`. **D-008:** new `polish.cross_chapter_repetition`/`cohesion_report` (deterministic,
  no LLM) write `cohesion_report.md` after book assembly, gated by the new `book_cohesion` setting -
  a detector (reused phrasings + formulaic openers across chapters), not a rewriter (a 10-chapter rewrite
  is impractical/lossy). **D-013:** opt-in `WRITINGAGENT_LLM_DEBUG=1` → `telemetry.log_debug` →
  `.index/llm_debug-*.jsonl` (full prompt+completion, same run_id/unit keys). **D-014:** `trace.append`
  stamps `run_id` (new `llm.run_id()`) + `ts`, so the agentic action trace joins to the telemetry JSONL.
  **+17 tests (test_hardening/test_config/test_polish/test_retrieval/test_agentic); 406 passed / 2 skipped
  (env: live-net opt-in + d2 not installed), ruff clean.** Docs: CHANGELOG, this file. **Next:** the
  remaining PENDING items above (C-011 cli split as its own session; C-010 lockfile; A-008 followup; the
  two older showstoppers).
- **New (2026-06-16 - A-008 lexicon single-source + C-007 config validation + all md docs + git - DONE):**
  closed the "next batch". **A-008:** new `src/writingagent/slop.py` is the single source for the
  anti-slop lexicon (verbs/terms/transitions/intensifiers/phrases/openers + `TECHNICAL_EXCEPTIONS`);
  `prompts.NO_SLOP` is now GENERATED from it (`slop.render_constraints()`), the humanizer regex is
  cross-checked against it by `test_quality.test_lexicon_single_source_consistency`, and the old
  contradiction is resolved - `optimize`/`navigate` are documented exceptions (not hard-banned, not
  stripped). Extended the humanizer to catch every banned adjective + `enhance` (it had missed
  vital/innovative/intricate/nuanced/realm/landscape/enhance). **C-007:** `config._clamp_settings` (run
  in `load_settings`) clamps out-of-range settings to sane bounds + normalizes `mode`/`agentic_policy`;
  +`tests/test_config.py` (3) + the consistency test. **Docs:** updated README, PRD, learning.md, test.md
  (via a doc agent), plus plan §15.1 (4 new hardening rows), CHANGELOG, this file. **390 passed / 1
  skipped, ruff clean.** Committed + pushed to git. **Next:** the PENDING list above.
- **New (2026-06-15 - review Critical/High batch fixed - DONE):** fixed the five items I flagged as
  the next pass. **A-020 fallback model:** `models.yaml` `fallback: deepseek/deepseek-v4-flash` +
  `ModelConfig.fallback` + `llm.configure_fallback` (wired in api + cli); `complete_text`/
  `complete_structured` retry ONCE on the fallback after the primary exhausts retries (`_allow_fallback`
  guards recursion). **A-014 context budget:** `Settings.max_context_chars=24000` threaded into
  run-state; `retrieval.assemble_context(..., max_chars)` + `_within_budget` drop lowest-priority
  blocks (excerpts→summaries→canon) so long books can't overflow the window. **A-016 crash-safety:**
  `_commit` now commits canon (SQLite + render) BEFORE writing the chapter `.md` (the resume marker),
  then indexes - so a mid-commit crash re-runs the chapter (idempotent INSERT OR IGNORE extraction)
  instead of skipping it with missing canon; `_commit_section` writes the summary before the section
  file. **C-002/D-010 web:** `_RUN_LOCK` serializes runs + `configure_runtime` clears all prior provider
  keys from env before each run (no cross-visitor leak) + `MAX_TOPIC_CHARS` cap. **Cross-test leak
  caught:** `_fallback_model` is process-global and leaked into `test_complete_text_gives_up_on_fatal`
  (it fell back instead of raising) - fixed by resetting it in the conftest autouse fixture (also closes
  review C-004's "isolate global state"). +6 tests (4 fallback in test_hardening, 2 budget in
  test_retrieval). **386 passed / 1 skipped, ruff clean.** Verified the fallback slug loads live
  (`deepseek/deepseek-v4-flash`). Docs: plan §12.1, CHANGELOG. **Still deferred (offered):** A-001
  (mid-unit research can't fire on terminal attempt - assessed as arguably-correct, not a bug),
  A-008 (anti-slop lexicon drift across 3 files), A-021 (process-global LLM state in long-lived TUI),
  C-007 (config range validation), C-011 (cli.py god-module), D-013 (no prompt/completion logging).
- **New (2026-06-15 - agentic TUI + Medium gaps + exhaustive review + fixes - DONE):** (1) **TUI layer**
  (parallel agent): `/agentic on|off|llm|default` (toggles setting + flips the live project via new
  `orchestrator.apply_controller`, mirroring `apply_autonomous`), `/trace` (prints `agent_trace.jsonl`),
  controller-decision line in the run dashboard. (2) **Mediums** (parallel agent): `fact_check_panel`
  wired into the article approval gate behind `agentic_factcheck_panel`; Phase-3 mid-unit research (a
  BLOCKING evidence gap under the agentic controller pulls one research brief into the next revision,
  folded via `extra_context`/`full_context` closure late-binding). All gated on `controller=="agentic"`
  so the equivalence guarantee holds. (3) **Live validation:** real OpenRouter run ($0.10, 21 calls,
  2174 words) - the LLM controller chose research→research→draft on `deepseek/deepseek-v4-pro` (so the
  v4 slugs ARE real, contra the review's speculation). (4) **Bug found + fixed:** a `save_settings`
  round-trip during the TUI agent's test iteration wrote `export_dir:` (bare) → YAML `None` → literal
  `export_dir: None`, breaking `test_export_formats`/`test_write_flow` (gitignored settings.yaml, so a
  `git stash` check mis-reported it as pre-existing). Fixed `save_settings` to emit `""` for empty
  strings + repaired the file. (5) **Exhaustive 4-agent code review** (17 dimensions) - ~50 findings;
  applied the safe high-value ones: **B-002** panel now gates on `deep_research` (inherits verify-gate
  snippet policy, can't false-refute on thin evidence); **B-009** clamp Critique insight/clarity/
  structure/evidence to [1,5]; **B-004** honest `read_canon` tool desc; **D-006** `ModelConfig` default
  `claude-opus-4-8`→`deepseek/deepseek-v4-pro`; and **§21 plan-drift** corrections (D-001/2/3/5/7:
  `agent_steps` is a counter not a backstop, real 5 config fields, no `Project.run(agentic=)`, `/agentic`
  is a command not a grid toggle, registry scope = 3 policy-selectable tools, test count 15→28).
  **381 passed / 1 skipped, ruff clean** (only `examples/colab_quickstart.ipynb` E401/I001 remains -
  upstream notebook). **Deferred from review (offered, not done):** A-020 no fallback model on failure
  (Critical, pre-existing); A-014 no context token-budget; A-016 `_commit` writes chapter file before
  canon/index commit (resume guard can skip a chapter with missing canon); C-002/D-010 web demo
  process-global key/env not serialized under concurrency; C-004 no autouse fake-mode guard in conftest;
  C-007 no config range validation; A-001 mid-unit research can't fire on the terminal attempt;
  C-011 `cli.py` 1001-line god-module.
- **New (2026-06-15 - agentic controller BUILT end-to-end, opt-in, all phases - DONE):** implemented
  plan §21. New **`agentic/` package**: `_schema` (ControllerDecision), `tools` (Tool catalog + UnitOps
  + `unit_research`/`unit_research_article`), `policy` (DefaultPolicy / LlmPolicy / TracePolicy +
  `make_policy`), `controller` (`run_unit` bounded perceive→decide→guard→act→record loop +
  `build_state_view`), `panels` (`fact_check_panel`), `trace` (append-only `agent_trace.jsonl`).
  Added `CONTROLLER_SYS` to `prompts.py`; 5 `Settings` fields (`agentic`, `agentic_policy`,
  `agentic_controller_model`, `agentic_max_unit_steps`, `agentic_factcheck_panel`) threaded through
  `_base_run_state` (adds `controller`/`agent_steps`); `book.run()` + `_run_article` dispatch each unit
  through `agentic.run_unit` (lazy import) when `controller=="agentic"`, else the unchanged
  `_process_chapter`/`_process_article_section`. Added an optional `extra_context` param to both unit
  processors (mid-draft tool use; None in the fixed path → identical). **Core invariant held:** `draft`
  IS the existing episode, so duel + `record_chapter` are byte-for-byte unchanged. **Phases:** 0-2
  production-complete; 3 = `extra_context` + on-demand research/canon seam; 4 = `fact_check_panel`
  utility; 5 = `TracePolicy` swap seam. Opt-in is free: `Agent(agentic=True, agentic_policy="llm")` and
  `/set agentic true` both go through the generic Settings path (no API/shell code). **+15 tests
  (`tests/test_agentic.py`)** incl. the equivalence guarantee (agentic+DefaultPolicy == fixed pipeline:
  identical manuscript + episode count). **367 passed / 1 skipped; agentic code ruff-clean.** Docs:
  plan §21 status note + build-order status, CHANGELOG [Unreleased]. **Pre-existing (NOT mine):**
  `ruff check .` flags `shell/repl.py:143` (E741) + `examples/colab_quickstart.ipynb` (E401/I001) -
  both came in with the upstream merge (b3458a9); left untouched. **Next:** evaluate `agentic_policy=llm`
  on a real key (the controller's research/draft choices); decide whether to wire `fact_check_panel`
  into the article section commit; the two deferred showstoppers (blind A/B, 10+ chapter validation).
- **New (2026-06-15 - agentic-controller plan written, NOT yet built):** the user wants a *self-directing*
  writer (choose-next-move agent), not just the current *self-correcting* fixed pipeline - and explicitly
  asked it not break the self-improving loop. Evaluated `earendil-works/pi` (TS agent harness, 62.8k★): good
  design reference, wrong runtime for us (TS vs our Python; a coding agent; no brain/efficacy loop). Verdict =
  borrow the *pattern* (`pi-agent-core`'s perceive→decide→guard→act→record loop + before/afterToolCall hooks),
  keep our brain + learning loop. Wrote the **end-to-end plan as `plan.md` §21** (Phases 0-5: tool registry →
  controller seam+default policy → LLM policy → mid-draft tools → multi-agent → learned policy π). **Core
  safety idea:** tools wrap *existing* orchestrator fns at current granularity, so `draft_unit` IS the
  unchanged `_process_chapter`/`_process_article_section` - the write→judge→`record_chapter`/`record_duel`
  episode stays atomic *inside* one tool; agency lives only *between* episodes. Default toggle OFF
  (`Settings.agentic=False`) ⇒ zero risk; Phase-1 acceptance = agentic+DefaultPolicy is byte-identical to
  legacy `run()` (same text, episode count, duel count). **Next (build):** Phase 0 - create
  `agentic/tools.py` registry over existing fns (pure refactor, suite-gated), then Phase 1 controller seam.
  New files planned: `agentic/{__init__,tools,controller}.py`, `tests/test_agentic.py`, `CONTROLLER_SYS` in
  `prompts.py`; edits to `config.py`, `orchestrator/{common,book,article}.py`, `api.py`, `shell/{commands,
  _const}.py`. See plan §21.0-§21.12.

- **New (2026-06-15 - self-review hardening of the day's work - DONE):** critical pass over the same-day
  changes found and fixed two real issues. (1) **`_write_env_key` could crash the shell at startup for
  installed users**: `brain._ROOT` is read-only under site-packages (pip/npm install), and the unwrapped
  `write_text` would raise *before* the live `os.environ` set - so the first-run wizard's "paste a key"
  would both crash and not even apply the key. Fixed: set the live env FIRST (always works this session),
  wrap the persist in try/except, return `Path | None`; wizard + `/setkey` now show a "set for this
  session - couldn't write .env" message on failure. +1 test. (2) **Critic citation-padding rule was
  unconditionally BLOCKING**, fighting the project's `watch_blocking` anti-thrash philosophy - softened so
  only a *decorative* citation (source doesn't back its sentence) blocks; padding/low-authority/off-topic
  are nits. Docs corrected (CHANGELOG, plan §13/§18.1). **352 passed / 2 skipped, ruff clean.**
- **New (2026-06-15 - writer-journey friction pass - DONE):** mapped the journey for a non-technical
  writer and found the friction is *front-loaded* - the in-shell loop (review menu, live cost/ETA
  dashboard, default-laden interview) is already strong; writers bounce **before the first word** on
  install + the API-key wall. Fixes shipped: (1) **first-run key wizard** (`branding._first_run_setup`,
  called from `repl.run_shell` before the welcome) - at an interactive prompt with no key, offers
  *paste a key* / *try free* / *skip* in one keypress; paste writes `.env` **and** applies live,
  "try free" sets `WRITINGAGENT_FAKE=1` **live** (kills the "restart with the env var" dance). (2)
  **`/setkey [<key>]`** (`commands._cmd_setkey`, aliases `key`/`apikey`) - saves the active provider's key
  to `.env`, applies live, clears fake mode; the "add a key later" path, in `/help` + completions. (3)
  **`branding._write_env_key`** - upsert a `KEY=value` into `brain._ROOT/.env` (the file the CLI
  auto-loads) and set it live. (4) **Welcome progressive disclosure** - leads with one action (`write`),
  no-key block points at `/setkey`, manual framed as "press `m` to pause & steer"; still ≤14 lines
  (renders at 12). (5) **`README` front-door CTA** - "Try it in your browser - no install, no key" before
  the install steps. (6) **Exports print the absolute path** (`cli._report_export`) so "where's my file?"
  is answered. +5 tests (`test_ui.py`: env writer, wizard free/paste/no-op, `/setkey`). **351 passed / 2
  skipped, ruff clean.** Docs: CHANGELOG, plan §13. **Next (still open):** the two deferred showstoppers
  - independent blind A/B and a real 10+ chapter book validation.
- **New (2026-06-15 - zero-install web demo, #4 of the "what's next" review - DONE):** added `web/app.py`
  - a Gradio front-end over the **public `Agent`/`Project` facade** (never touches internals), so a
  non-developer can try the pipeline in a browser. **Free preview** (default) forces `WRITINGAGENT_FAKE=1`
  → runs the whole flow offline with placeholder output (no key, no cost, shows the run's shape);
  **real run** toggle takes a BYO provider key (OpenRouter/DeepSeek/OpenAI/Gemini) and produces a genuine
  piece + populated evidence report. Streams progress live via a worker thread + queue feeding the Gradio
  generator; outputs manuscript + evidence tabs + a `.md` download. gradio is imported **lazily** (only in
  `build_ui`), so the runtime helpers stay testable without it - mirrors the `deep`/`headroom` optional-dep
  pattern. New `[web]` extra in `pyproject.toml`; HF Space deploy files (`web/requirements.txt`,
  `web/README.md` with the gradio-SDK front-matter). +5 smoke tests (`test_web.py`, incl. a full offline
  run through the demo). **346 passed / 2 skipped, ruff clean** (src+web+tests). Docs: CHANGELOG, plan
  §13. **Next:** the two showstoppers the user deferred - independent blind A/B (third-party judge, n≥5)
  and a real 10+ chapter book validation. Caveat to revisit: `configure_runtime` mutates process-global
  env, so a public deploy must stay single-worker or serialize runs.
- **New (2026-06-15 - citation-quality gate, #3 of the "what's next" review - DONE):** closed the
  blind-A/B "citation quantity ≫ quality" weakness (the model padded with low-authority sources -
  resume-template sites - to hit volume). Added a **deterministic source-authority heuristic** in
  `polish.py`: `source_authority(url)` scores a domain 0–100 (`AUTH_HIGH` gov/standards/primary research,
  `AUTH_REPUTABLE` established outlets & official docs, `AUTH_NEUTRAL` unknown = no penalty, `AUTH_LOW`
  SEO/template/content-farm signals; all tiers tunable). Wired in three places: (1) `score_sources` adds
  an `authority` field and uses it to **break influence ties** (a heavily-cited low-authority pad ranks
  below an equally-cited credible source); (2) `build_references` drops an *uncited low-authority* pad,
  not just zero-overlap noise (References row format unchanged → existing tests stable); (3)
  `build_evidence_report` now surfaces **credibility** - high-authority count, average authority, and a
  ⚠️ flag listing low-authority sources (parses the URL already in each ranked row, so the row format
  didn't change). Reinforced by prompt gates in `ARTICLE_CRITIC_SYS` + `CRITIC_SYS` (decorative / padded /
  off-topic citations are BLOCKING). +3 tests (`test_polish.py`); **full suite green, ruff clean.** Docs:
  plan §13 (References block), CHANGELOG [Unreleased]. **Next:** #4 zero-install web demo (decide
  framework - Gradio HF Space reusing the `Agent`/`Project` facade is the lightest path).

- **New (2026-06-14 - UX audit P1-P3 + all md docs refreshed):** ran a UX audit (framework: audit-then-
  approve) and implemented everything. **P1:** `/skills` now shows the duel win-rate (vs 50/50) + count
  next to first-pass lift, and notes duels decide trusted/retired once a skill has data (closes the debt
  from learning-v2); first-run no-key onboarding block in the welcome (set key OR try `WRITINGAGENT_FAKE=1`
  free). **P2:** new toggles (`skill_duels`/`skill_distill`/`watch_blocking`) in `/features` grid + static
  table; whole-run ETA on the dashboard (`_run_eta`); friendly recoverable errors (`ui.explain_error`:
  401/429/network/locked-file) wired into the shell + chat error sinks. **P3:** colourblind-safe
  `highcontrast` theme (Okabe-Ito; ok=blue, error=vermillion); clearer pause/stop wording (all resumable).
  +4 tests. **339 passed / 1 skipped, ruff clean.** Then refreshed **all state-tracking md files**:
  `docs.md` (fixed stale "gitignored" claim + package file-refs + new ledger pass-2), `CHANGELOG.md`
  ([Unreleased] Added/Changed), `plan.md` §13.1, `learning.md`, `README.md`, `PRD.md`. Boilerplate
  (LICENSE/CONTRIBUTING/SECURITY/CODE_OF_CONDUCT) intentionally untouched.
- **New (2026-06-14 - learning loop v2: causal skill efficacy):** fixed the loop's *showstopper* (the
  efficacy signal was confounded - `record_chapter` credited every applied skill with the same
  chapter-level `first_pass`, no counterfactual, `target_failures` never written) with the *gamechanger*:
  **ablation duels** (`skill_duels`, opt-in). On a unit with an undecided skill, `_divergent_first_draft`
  drafts one EXTRA variant with that skill held out (same temp as v0); `_crit_better(v0, ablated)` is the
  skill's causal lift. New `skills.record_duel` / `pick_duel_target`; `reconcile` prefers a Laplace-smoothed
  duel win-rate (`MIN_DUELS`/`TRUST_WR`/`RETIRE_WR`) over the first-pass fallback, and a lost duel finally
  drives `target_failures`. De-risks: variant is *added* not substituted (no real contender lost; cost =
  one extra draft, only while undecided), smoothed+sample-gated stats, skipped in skeleton mode. Plus
  **`skill_distill`** (opt-in, deterministic, non-destructive near-duplicate retirement - keeps retrieval
  sharp; only meaningful after duels score skills) and **`watch_blocking`** (default on: watch-list now
  blocks only CLEAR/CONCRETE violations instead of unconditionally - cuts false-positive revision thrash;
  False = advisory). +7 offline tests (`test_skills.py`), fake-mode e2e fires a real duel on both
  pipelines. **337 passed / 1 skipped, ruff clean.** See plan §8.
- **New (2026-06-14 - repl.py split into 4 seams):** the largest remaining shell file, `repl.py` (816
  lines), is now four concerns behind the same facade: **dispatch** (247, input interpretation +
  `_execute_cmd` - the chat assistant's guarded command runner: confirmation detection, project auto-pick,
  argv fix, command extraction), **slash** (175, the `/command` dispatcher `_handle_slash`), **session**
  (177, the prompt_toolkit `_make_pt_session` + autocomplete), and **repl** (221, now just `_prompt_state`
  + `run_shell`). `_SLASH_COMPLETIONS` moved to `_const` (shared by session + slash). Acyclic except the
  existing `chat → dispatch` back-edge (chat's lazy import, repointed from `.repl`). Largest shell file is
  now dashboard (564) / commands (578); nothing over ~580 lines anywhere. **330 passed / 1 skipped, ruff
  clean**; smoke-rendered `/help` + `/theme` and built the pt-session through the new seams.
- **New (2026-06-14 - shell.py split into a package - DONE):** `shell.py` (~2900 lines) is now `shell/`
  - a facade `__init__` (30 lines) + seven seams: **_const** (257, glyphs/vocab/regexes/chat-prompt),
  **branding** (389, banner/wordmark/flame/palette/welcome/_section/_cmd_table), **help** (278, tables/
  slash-help/toggle-grid/model-catalog), **commands** (578, `_cmd_*` + path/provider/model/set/auto/
  praise/skills), **dashboard** (564, _RunControls/_KeyListener/_RunDashboard/cards/run_with_dashboard),
  **chat** (333, respond/history/hints/system), **repl** (816, run_shell/_handle_slash/pt-session/input
  routing). Acyclic except `chat._chat_respond → repl` (command dispatch), broken with a lazy import.
  Facade re-exports every public + test-used name so `shell.X` is unchanged for cli.py + tests. **Two
  real cross-facade fixes the split surfaced** (not test-only): (1) `_sync_palette` now refreshes the
  palette in every seam + the facade after a live `/theme` switch (each seam from-imports the colors) and
  the facade re-exports the ui palette so `shell.GOLD` resolves/re-colours; (2) `test_shell_chat` patches
  `_execute_cmd` at its new home `shell.repl`. **330 passed / 1 skipped, ruff clean**; a smoke render of
  banner/welcome/tables/slash-help through the seams produced 10k chars cleanly. **Both god-files are now
  split** (orchestrator + shell) - that closes the file-split work in plan §20.1.
- **New (2026-06-14 - orchestrator.py split into a package):** the 2274-line `orchestrator.py`
  god-module is now `orchestrator/` - a documented facade `__init__` (33 lines) re-exporting six seam
  modules: **common** (592, shared leaf helpers), **book** (632, chapter pipeline + `run()` dispatcher),
  **article** (651, section pipeline), **export** (203, pdf/epub/.../repolish/evidence), **manage** (128,
  lifecycle/state), **review** (296, approve/revise/table-read/evaluate). Dependency DAG is acyclic
  (common <- {article,book,manage}; article <- export; book <- {article,manage}; review <-
  {book,article,common}). `orchestrator.X` is unchanged for every caller and test (incl. the private
  names tests reach for) - pure code movement, no logic changes. Done in 6 suite-gated commits (package
  conversion → common → article+export → manage → book+review → facade); a ruff per-file-ignore marks the
  facade's intentional star re-exports. **330 passed / 1 skipped, ruff clean** at every step, plus a
  fake-mode e2e drove both pipelines to `done` through the new seams. (Also a standalone `style(shell)`
  commit for a pre-existing ruff E262 nit.) **Next:** apply the same package split to `shell.py` (144 KB)
  - seams: branding / help / commands / dashboard / chat / repl (user-approved order: orchestrator then
  shell).
- **New (2026-06-14 - book↔article dedup, Tier 3 evaluated; refactor backlog closed):** pulled two pure,
  byte-identical idioms out of both run loops - **`_mark_escalated`** (durable pending-review + the
  "resolve with..." hint) and **`_log_run_complete`** (the `[OK] ... complete` line + per-run usage
  summary). **Deliberately did NOT unify the `run()`/`_run_article()` phase machines:** they share only a
  shape - different phase *sets* (chapters/consolidate/production/learn vs sections/produce/learn), the
  `Store` lifecycle (book opens/closes, article stateless), and book's consolidation-interleave +
  pending-review branching with no article analog. A shared loop = a dispatch table of closures over a
  dozen shared mutable locals + signal-return control flow, strictly worse than two linear machines.
  Suite **330 passed / 1 skipped**, ruff clean, fake-mode e2e drove BOTH pipelines to the shared
  completion footer. That closes the §20 dedup backlog: everything cleanly shareable is shared; the rest
  is documented as *evaluated-and-declined* (not "todo"). **Next deferred win:** split the giant files
  (`shell.py` 144 KB, `orchestrator.py` 115 KB) along their natural seams now that cross-path duplication
  is paid down.
- **New (2026-06-14 - book↔article dedup, Tier 2 done):** extracted two shared helpers in
  `orchestrator.py` so the drift-prone chapter/section paths share one source: **`_divergent_first_draft`**
  (attempt-0 divergent drafting - N variants at varied temps → critique → side-by-side judge picks the
  winner; article-only skeleton-expand behind the `skeletons` flag; takes the unit's own `_write`/`_critique`
  closures so the only mode-specific leaves stay leaves and control flow is linear in one place) and
  **`_finalize_unit`** (post-loop bookkeeping: best-judged fallback in autonomous mode, `first_pass`,
  insight/score history). Book `_write` gained a no-op `skeleton=False` for a uniform signature.
  **Deliberately NOT merged** (callback-soup / pure indirection, same discipline as Tier-1 `_commit`):
  the `_chapter_fetch`/`_section_fetch` fetch pair (only the one-line `concurrency.gather` is shared; the
  research/images/skills strategy fns differ in schema, node calls, return arity, paths, gating) and the
  full per-attempt revision loop (woven with `break`/`continue`, mutates 5 locals). Suite **330 passed /
  1 skipped**, ruff clean, and a fake-mode end-to-end ran BOTH a 2-variant article and book to commit
  (divergent branch + finalize both fired, no drift). See `plan.md` §20.
  **Next:** Tier 3 (the `run()`/`_run_article()` phase-machine loop) is deferred low-value until a 3rd
  pipeline variant appears; after dedup, the deferred win is splitting the giant files (`shell.py` 144 KB,
  `orchestrator.py` 115 KB).
- **New (2026-06-13, session 16 - export quality: references/citations/figures overhaul):** root
  cause of the bad PDFs = the **writer model authors its own figures (mermaid), figure numbers,
  captions, listings, inline `[N]` citations, and bare per-section reference dumps**, which collide
  with the pipeline's own SVG figure + final References list (duplicate figures, double captions,
  mid-article references, mismatched numbering). Fixes: new **`polish.py`** (pure, deterministic, no
  LLM): `strip_inline_citations`, `strip_reference_dumps` (headed blocks + bare `[N]` runs),
  `strip_model_figures`/`dedupe_figures`, `score_sources` (influence = body-citation count + thesis/
  heading title-overlap) + `build_references` (one end list, `N. **score** · date · [title](url)`,
  sorted high→low, dates normalized, zero-influence pruned only when there's signal). Wired into
  `_assemble_article` (going forward) gated by two new settings **`strip_inline_citations`** (default
  on) + **`rank_references`** (default on), threaded into article run-state. `ARTICLE_WRITER_SYS` now
  FORBIDS model-drawn figures/mermaid/`Figure N`/`Listing N`/captions/bare-ref-lines. New
  **`repolish_manuscript()`** + **`polish` CLI command** re-fix an EXISTING manuscript with ~0 tokens
  and re-export. **Ran it on the voicebot article**: inline `[N]` 29→0, mid-article ref lines 9→0,
  figure-heading 1→0, redundant SVG embed removed (figure-twice fixed), References rebuilt = 47 ranked/
  dated/scored (DraftKings demoted to #10). Re-exported md/txt/html/epub/docx (pdf was file-locked -
  user had it open; `manuscript.md.bak` saved). +7 tests (`test_polish.py`).
  **Phase 3 (figure render quality) - DONE for the pipeline engine:** Playwright render of the
  section_05 spec proved the **built-in engine ≫ D2** (D2+ELK = 1744px-wide unreadable; built-in =
  compact 592px with title/lane-headers/readable boxes). (1) `nodes.generate_svg_diagram`: **`auto`
  now = built-in** (was: D2 whenever the d2 binary is installed - exactly why the user's runs looked
  bad); D2 is explicit opt-in. (2) built-in **comparison** edge-label **de-dup** (`_edge_label(...,
  seen)`): repeated relations (`provides`×3) render ONCE instead of overlapping in the column gap; gap
  90→120. Flipped local `settings.yaml` `diagram_engine: d2 → auto`. +1 test (`test_diagram.py`).
  **All 305 tests pass; ruff clean.** **Still open (smaller):** the EXISTING voicebot article's figures
  are model **mermaid** (the SVG was deduped out; prose references the mermaid), rendered via
  mermaid.ink (clipped pie title) - only fixable by regenerating that article's diagrams (small
  diagram-node token cost; offered to the user). Going forward every figure is a clean built-in SVG.


- **New (2026-06-13, session 15 - multi-provider model hosts + slash-menu polish):** two
  Hermes-inspired asks, each pruned to what a single-wire-format writing pipeline actually needs.
  **(A) Multi-provider routing** (plan §12.2): new `providers.py` registry (frozen `Provider`
  dataclass; `id`/`name`/`base_url`/key-envs/`*_BASE_URL` override/`reports_cost`/`headers`/`local`)
  with 17 OpenAI-compatible hosts (OpenRouter default + cost; DeepSeek, OpenAI, Gemini-compat, xAI,
  Groq, Mistral, Moonshot, DashScope, Zhipu, NVIDIA, Together/Fireworks/DeepInfra, Ollama + LM Studio
  local, `custom`) and an alias table. `llm.py` rewired: `_get_client` resolves the active provider
  (lazy creds - key-less switch never crashes; clear "set XAI_API_KEY" only on first real call),
  `configure_provider`/`active_provider` added, cost-ask gated per provider. `settings.provider`
  (default `openrouter`) + `WRITINGAGENT_PROVIDER` env; wired at startup (`cli._apply_provider`,
  `api._apply_runtime`). Shell: `/provider [id]` (list with key/local markers · switch · did-you-mean),
  `/set provider` side-effect, completer + `/help` config group. **Deliberately dropped from the spec:**
  the 3 non-OpenAI transports, `NormalizedResponse`, `api_mode` heuristics, OAuth/Bedrock/Codex auth,
  cross-host slug translation. +10 tests (`test_providers.py`). **(B) Slash-menu**: `/features` is now
  an interactive prompt_toolkit **toggle grid** (`_toggle_grid`; ↑↓ · space · ↵ save · esc cancel;
  falls back to the static table off-TTY), and `/help` is **grouped by category** (`_SLASH_HELP` is
  now category-keyed). +3 tests (`test_ui.py`). **(C) Configurable save location** (plan §16.5):
  exports can now be written wherever the writer wants. New `settings.export_dir` (global default,
  `""` = each project's own folder) + per-project override (a `export_dir.txt` sidecar in the project
  root). `brain.resolve_export_dir`/`project_root`/`get|set_project_export_dir`/`move_exports` +
  `EXPORT_DELIVERABLES`; `orchestrator._export_paths_and_title` now also returns `out_dir` and all 6
  exporters write the rendered file there while `base_dir` stays the brain root (so images/diagrams
  still resolve). Shell **`/path`**: no-arg menu (default · or pick an ongoing project → enter folder →
  offer to **move** existing deliverables; the `manuscript.md` SOURCE never moves), plus `/path
  default <dir>`, `/path <project> <dir>`, `/path show`, `/path clear`. Completer + `/help` session
  group + dispatch. +8 tests (`test_export_path.py`). **(D) Export to many formats + NL parsing**:
  `export` now takes one format, a list (`export pdf epub`), or **`all`**; positional arg + dropped the
  argparse `choices` lock; one failing format never aborts the rest (per-format try/except + summary).
  `cli._resolve_formats` understands commas/semicolons/·/&/+, connector words ("pdf, epub **and** word"),
  and synonyms (word→docx, markdown→md, ebook→epub, everything→all). `write` interview returns a list
  too. Centralised the styled prompt in `cmd_export` (removed the duplicate picker in `_execute_cmd`).
  +7 tests (`test_export_formats.py`). **(E) Smart, forgiving input everywhere** (the "make it
  intelligent" sweep): `brain.match_projects`/`resolve_project` (excerpt/typo/word-order tolerant, with
  a clear-leader rule + ambiguous→options) wired into `/use` (numbered picker), `/path`, `/dashboard`,
  and `cli._resolve_book`. New `ui.is_affirmative` (slang yes/no: yeah/yep/sure/nah/"do it") applied to
  all 4 confirm prompts; `ui.smart_match` (alias→exact→prefix→substring→fuzzy) applied to `/theme`,
  `/mode` (+essay/novel synonyms), `/model` agent, `/set` key, `/provider`, `/skill`. **(F) Chat `/use`
  guardrail**: the assistant was inventing a `/use <hallucinated-id>[article]` for "export to epub" and
  erroring; now `_chat_use_project` strips the `[type]` tag and switches only on a STRONG match, else
  keeps the active project silently. Context now lists projects one-per-line (id separated from the
  type tag) + prompt rules: no `/use` when a project is active, never invent ids. +9 tests
  (`test_smart_input.py`). **All 297 tests pass; ruff clean. Nothing committed yet.** Next: optional
  `/theme` list-picker; README/docs-site note; the deferred Hermes-transport tier (user said "wait").
- **Phase:** **Production-ready.** Books and articles both live-validated end-to-end. **263 tests
  pass** (+1 opt-in live skip +1 d2-binary skip); ruff clean on Windows AND Linux (WSL-verified). **CI green on all
  12 matrix jobs** since session 10's `svglib<1.6` pin (1.6.0 pulls pycairo, which has no Linux
  wheels). `gh` is authenticated on this machine (keyring), so CI stays checkable headlessly even
  after the repo goes private again.
- **New (2026-06-13, session 14 - quality machinery II: independence, verification, compounding):**
  four levers breaking the "one model judges its own output" ceiling (plan §15.6). (1) **Tournament
  judge** (`nodes.rank_variants`; `tournament_judge` on) picks the best divergent draft side-by-side
  instead of by isolated 1-5 self-score; scalar `_crit_better` is the fallback; the winner's noted
  weakness feeds the refine. (2) **Claim↔source verification** (`nodes.verify_claims`; `verify_claims`
  on; articles): each `[N]`-cited specific claim checked against its source text (`source_text`
  threaded through `_section_fetch`); unsupported → BLOCKING `evidence` + a revision note. (3)
  **Counterargument engagement** (writer prompt) + **closed table-read loop** (`nodes.reader_report`;
  `table_read_revise` off, autonomous-only): the reader's single top fix applied as a bounded,
  version-snapshotted (`reader-fix`) targeted revision. (4) **Compounding learner**: tournament +
  revision signals logged to `<project>/learning_signals.md` and fed to `learn()` as a secondary
  **candidate-only** signal (efficacy gate unchanged - no auto-promotion). New `judge`/`verifier`
  model slugs (route cross-family for independence; default stays DeepSeek). `verify_claims` is
  depth-gated (blocks on deep full-text, advisory nit on shallow snippets). Wired into the user
  surfaces too (`shell._NODES` for `/model`, `/features` board, chat context, `settings.yaml`).
  +11 tests (`test_quality.py`); ruff clean.
- **New (2026-06-13, session 13 - public Python API):** added `writingagent.api` - a stable
  `Agent` + `Project` facade (plus a one-shot `write()`) over the orchestrator, re-exported from
  the package root with `__version__` and PEP-562 lazy imports, so `from writingagent import Agent,
  write` just works after `pip install -e .`. +14 offline tests (`tests/test_api.py`); README
  "Python API" section + plan.md §18. The internals stay unstable; this is the supported
  embedding surface.
- **New (2026-06-13, session 12 - diagrams + exports):** diagram node → **v4-pro** (16k budget,
  information-design prompt, deterministic `fill="none"` guard, flash fallback); **PDF exports
  render SVG figures as vector art** via svglib (were image-less without cairosvg); the voicebot
  article's 3 diagrams regenerated + re-exported and visually verified; telemetry test-pollution
  fixed (autouse brain/index isolation) and the real `.index/telemetry` scrubbed.
- **New (2026-06-12, session 11 - TUI):** compact welcome (66→33 lines, banner stays on screen),
  `/features` command, bottom toolbar removed, red FAKE-mode launch warning, animated run
  dashboard (live clock + stage spinner between log events).
- **New (2026-06-12, session 10 - review fixes + Linux CI unblocked):** revise-critic parity
  (book + article), chat stream errors no longer masquerade as prose, SSRF/robots/politeness gate
  on the deep fetcher, Wikimedia formatversion=2 parse fix, +55 tests (incl. a coverage pass over
  store/retrieval/skills/cache/search/images/embeddings). Details in the session-log entry.
- **New (2026-06-12, session 9d - live validation + docs sync + tooling):**
  - **LIVE end-to-end validation of the quality+trust machinery** (real DeepSeek, not fake):
    2-section article "Why most RAG evaluation metrics mislead teams". Full chain fired -
    thesis (genuinely contestable, with steelman+rebuttal), divergent drafts (1/2 approved per
    section, best picked), versions saved (v01/v02 variants + v03 committed per section),
    surgical humanizer (only **2** AI-tell sentences left in 3,448 words), table read + eval +
    learner (+4 skills). Critic insight 5/4; eval insight 5 · clarity 5 · structure 5 ·
    evidence 4 · persuasiveness 5; honestly flagged missing named sources (researcher was off).
    **Cost: $0.15 / 15 calls / 84k tokens** for the 2-section run. **Watch item:** v4-pro critic
    (same family as writer) scored 4-5 on first/second variants - one good-topic run can't tell
    if the insight bar is too easy; eval did show critical capacity (evidence 4 + flagged
    sources). Tune `min_insight` once a deliberately-weak topic is run.
  - **Docs synced** (commit e78060e): plan.md §5/§7/§13/§12.1 + new §15.4 (quality machinery)
    and §15.5 (trust machinery); README command/slash tables + self-correction diagram +
    not-slop section; CHANGELOG [Unreleased] Added/Changed.
  - **Tooling:** installed GitHub CLI (`gh` 2.93) and pandoc (3.10) via winget - DOCX export now
    works; `gh` still needs a one-time interactive `gh auth login` before CI status is queryable.
    CI gates reproduced locally (ruff clean + `pytest -q` fake-mode all pass on 3.11; compiles on
    3.12). Repo is private so Actions status couldn't be checked headlessly.
- **New (2026-06-12, session 9c - trust machinery: versions, diffs, brief, eval):**
  Audited the TUI against a 20-point writing-agent framework; built the 5-item cut + eval:
  - **Version snapshots** ("git for writing"): every generated draft (divergent variants
    with temps, revisions, committed finals, revise outputs) saved under
    `<project>/versions/<unit>.vNN.md` with a label header; survives article cleanup.
    `versions [--chapter N]` lists; `read --chapter N --v K` reads one.
  - **Semantic + text diff on `revise`**: flash-model Added/Removed/Improved summary +
    colored unified diff shown BEFORE applying; `[Y/n]` accept/reject in TTY (discard
    touches nothing). `revise_unit(confirm=)` callback keeps orchestrator UI-agnostic.
  - **`brief` command + dashboard goal line**: thesis claim (articles) / premise (books)
    shown in the live run header; `brief` prints thesis/audience/length/intake/voice state.
  - **`tableread [--as "persona"]`**: on-demand skeptical-reader pass, persona-swappable
    (books supported via pseudo-outline); reports saved per-persona.
  - **Scorecard-lite**: Critique gains clarity/structure/evidence (1-5) judged per unit,
    tracked in `state["scores"]`, averaged on the summary card.
  - **`eval` command**: post-hoc quality report - deterministic metrics (words, AI-tell
    scan via the humanizer lexicon, structural metrics, citation/source coverage) + a
    pro-model 5-dimension rubric with quote-backed strengths/weaknesses -> `eval_report.md`
    + a bar scorecard in the TUI. The framework's verdict was right: version comparison
    is where trust is won; deliberately skipped document-first layout / sentence-level
    suggestions as a different product (co-editor, not autonomous pipeline).
- **New (2026-06-12, session 9b - TUI/UX batch + headroom actually installed):**
  - **Escalation picker**: a stalled run now shows the critic's blocking issues and prompts
    `[f]ix · [i]nstruct · [a]pprove as-is · [g]o autonomous · [r]ead draft · [s]top` - one
    keypress instead of `review --chapter N --instruction "..."`. Backed by new
    `orchestrator.approve_escalation()` (commits the stalled draft via the normal commit path).
  - **`revise` command** (post-completion loop): `revise --chapter N --instruction "..."`
    rewrites ONE committed unit of a finished piece (write→critique→optional fix pass→
    humanize), patches the section file AND the assembled manuscript
    (`_replace_manuscript_section`); books re-run production. Canon deliberately not
    re-extracted. NL chat maps "make section 3 more technical" to it.
  - **Outline gate** (manual mode, TTY only): after `new`, the outline + thesis claim are
    shown with `[Enter] write · r regenerate · g regenerate with guidance` (max 3 rounds).
  - **Manual variant pick**: in manual interactive runs the human chooses among divergent
    drafts (glimpse + critic verdict/insight per variant; Enter = critic's pick) via an
    `ask` callback threaded through `run()` (Live display pauses/resumes around input).
  - **Summary card + bell**: finished runs ring the terminal and show words/time/tokens/
    cost/avg-insight (state["insights"] tracked per commit) + table-read pointer.
  - **Table read** (`table_read: true`): whole-article cold read by a skeptical
    target-audience reader -> `table_read.md` report (boredom/trust/unclear/missing),
    report-only, feeds `revise`.
  - **Toolbar turns red** (prompt_toolkit HTML) when a review is pending; dashboard now
    shows a draft-opening glimpse line per attempt.
  - **Headroom fixed**: `headroom-ai` was configured but NOT INSTALLED (silent no-op since
    day one). Installed the Windows pure-Python build (0.10.17 + opentelemetry-api +
    tiktoken); verified through `llm._compress`. Caveat: transforms target long multi-turn
    payloads - expect savings on late-book context, not every call.
- **New (2026-06-12, session 9 - quality machinery: originality over slop-absence):**
  Code review concluded the pipeline guaranteed the floor (no slop symptoms) but had no
  machinery for the ceiling (a thesis, a voice, a risk). Implemented all three tiers:
  - **Thesis node** (`nodes.generate_thesis`, `schemas.Thesis`): contestable claim + stakes +
    arguments + steelmanned counterargument/rebuttal + non-goals, generated at `start_article`,
    persisted as `thesis.json`/`thesis.md`, injected into every section writer + critic call.
    Critic blocks sections that cover the topic without advancing the thesis.
  - **Voice exemplars** (`brain.voice_dir`/`voice_exemplars`): drop admired paragraphs in
    `brain/users/<uid>/voice/`; they're injected into every writer call as register to MATCH.
    New **`/praise [N]`** command saves a committed chapter/section there (falls back to
    manuscript extraction for finished articles) - feeds both the writer and the learner
    (`nodes.learn` now takes `praised=` positive exemplars).
  - **Surgical humanizer** (humanizer.py rewritten): tells detected deterministically
    (lexicon regex), ONLY flagged sentences rewritten (structured `LineEdits`), each rewrite
    guarded (citations/numbers/length/tell-gone) before splicing. No more wholesale
    re-generation of approved prose. "optimize" removed from the lexicon (wrong for technical
    prose - the old ban was leaky anyway).
  - **Divergent first drafts** (`divergent_drafts: 2` setting): attempt 0 samples N drafts at
    temps 0.7/1.0/1.2 in parallel; critic scores all; the winner gets refined. Both loops.
  - **Insight gate** (`Critique.insight` 1-5, `min_insight: 3` setting): approve now requires
    insight >= bar; correct-but-generic drafts get a sharpening revision note. Deterministic
    `structural_report()` (paragraph uniformity, rule-of-three density, specificity density)
    feeds the critic as computed evidence. `_crit_better` prefers higher insight.
  - **Critic = DeepSeek v4-pro** (user decisions: DeepSeek pro/flash only - no other
    providers; then critic upgraded flash→pro since insight scoring + thesis checks need
    real judgment). Writer temp now explicit (0.9); humanizer 0.3.
  - **Researcher default ON** (`use_researcher: true`); critic treats uncited stats as
    fabrication risk when research is off; production logs a warning when [n] citations exist
    with an empty source registry.
  - Earlier same day: `/auto` autonomous↔manual toggle (clears stuck escalations),
    `run --autonomous/--manual`, chat escalation playbook, export fixes (PDF code wrap,
    Mermaid→PNG with disk cache, U+2011 tofu, byline, "Section N:" strip, per-section
    reference consolidation, EPUB code-wrap CSS).
  - **Next:** live-validate a real article run end-to-end with the new machinery (thesis +
    divergent drafts + insight gate + cross-family critic); compare output quality against
    the voice-agent article; tune `min_insight`/`divergent_drafts` from telemetry cost data.
- **New (2026-06-12, sessions 1-8):**
  - **Chat NL flow** - propose abstract → refine with plain English → "run it"/"go ahead"
    creates + starts writing in one turn. Fixed the regex that silently dropped every
    chat-emitted command and the routing that swallowed "run it" as bare `run`.
  - **Hard confirmation gate (session 8):** a chat-emitted `new` now only executes when
    the user's own message was an explicit go-ahead (`shell._is_confirmation`); otherwise
    the whole command batch is held and shown as a proposal. Prompt-only enforcement had
    failed live (model skipped PROPOSE and ran new+run immediately).
  - **`write` one-shot flow** - upfront interview → fully autonomous run → exported file (plan
    §15.3). Fixed the bug that silently ignored `autonomous: true` (runs kept pausing).
  - **10 TUI themes** (`/theme`) - each owns a distinct hue family AND its own wordmark figlet
    face (editorial blue-ink default, kazama flame, supabase, violet-bloom, t3-chat,
    starry-night, vercel, fallout, mimi, astrovista). README banner SVG = the real ANSI Shadow
    wordmark, gradient-filled, centered.
  - **Production guards** (plan §15.1): `max_run_tokens` budget kill-switch (clean resumable
    pause + tokens/budget + USD cost in the live dashboard), per-call JSONL telemetry with
    `/dashboard [<project>]` rollup, and `wrap_untrusted` injection fencing on every
    web→prompt path.
  - Chat-stream scrollback duplication fixed (transient tail preview + single final render).
- **New this session (2026-06-10 session 6 - deep researcher + article tests + craft skills + read fix):**
  - **Deep multi-source researcher** (`deep_research.py`, opt-in `deep_research` setting): LLM query-expansion -> concurrent multi-query fan-out -> URL/domain dedup -> full **page-text** fetch+extract -> cross-source synthesis node that cites sources by number. Wired into both book + article research branches; articles persist the real fetched URLs as references. **Fetch backend is pluggable:** prefers **Scrapo** (`github.com/vikast908/Scrapo`, optional `[deep]` extra - clean markdown + HTTP/browser/stealth escalation) and falls back to a stdlib `urllib`+`html.parser` path so there are still zero *required* deps. **Validated live** (real DuckDuckGo + real Scrapo fetch). Spec in `plan.md` §15.2.
  - **`read --manuscript` works for articles** (`cli._paths_for` picks ArticlePaths vs BookPaths) - fixes the long-standing pre-existing bug.
  - **+4 technical-writing seed skills:** `technical-explanation`, `runnable-code-examples`, `claims-and-evidence`, `information-architecture` (13 seed skills total).
  - **First article-pipeline tests** (`test_article.py`) + deep-researcher tests (`test_deep_research.py`). **62 tests pass** (was 44); ruff clean.
- **Agent name:** **WRITING AGENT**. CLI: `writing-agent` / `python writingagent.py`.
- **Article pipeline:** fully built and live-run - "How to think with AI without offloading your brain to AI" (6 sections, DOCX exported).
- **Book pipeline:** fully built and live-run - *The Misprint File* (3 chapters, 9-page PDF).
- **New this session (2026-06-10 session 5 - reliability/UX/security hardening, branch `hardening-reliability-ux`):**
  - **Headroom fixed:** pinned `headroom-ai==0.10.17` (last pure-Python release; ≥0.21 is a Rust/pyo3 ext with no Windows wheel), installed `--no-deps`; `_compress` counts tokens with a tiktoken model so compression actually runs on DeepSeek slugs.
  - **Reliability:** classified retry + exponential backoff (honors Retry-After), fail-fast on 4xx, request timeout, real structured-output repair retry, token-usage telemetry; atomic `write_json`/`write_text` + corrupt-tolerant `read_json`; resume guards prevent double-commit / canon duplication.
  - **Performance:** independent network steps overlap (research ∥ image/SVG; parallel front/back-matter) via `concurrency.py`; on-disk cache for web search + SVG diagrams (`cache.py`). Chapter chain stays sequential by design (continuity).
  - **Security:** chat assistant can no longer auto-execute `delete` / `/user` / `/set`; path confinement + `is_safe_id` validation; export HTML sanitized; YAML-safe skill frontmatter; non-dict frontmatter guard; `Critique.confidence` clamped.
  - **Richer TUI/CLI:** live `run` dashboard (elapsed + live tokens + stage + event log), arg/value autocomplete, persistent history, `new` spinners, Rich `status` (phase stepper + word count/reading time), Markdown `read`/`memory`, skills efficacy bars, clickable export paths, "did you mean?", `--plain`/`NO_COLOR`.
  - Removed dead `run.py`/`slice.py`; new shared `ui.py` (palette + helpers). 44 tests (added `tests/test_hardening.py`, `tests/test_ui.py`).
- **Source of truth:** `plan.md` (spec + implementation status); `README.md` = how to run.
- **How to run:** `writing-agent` (after `pip install -e .`) or `python writingagent.py` → interactive shell; `python writingagent.py <cmd> ...` for one-shot. Needs `OPENROUTER_API_KEY` in `.env`.
- **Next up (all optional):** (a) live end-to-end deep-research run through the full article/book pipeline (fetch path validated live; full pipeline only run offline); (b) LangGraph wrapper; (c) multi-user / server mode; (d) book↔article dedup refactor in orchestrator/shell (~800 duplicated lines - the revise-critic drift was a symptom). robots.txt/SSRF/rate-limit: **done** (session 10).
- **Stack:** Python; durable on-disk state machine; markdown brain + SQLite/FTS5; OpenRouter + DeepSeek V4 Pro/Flash per-node; Rich TUI + prompt_toolkit.
- **Platforms:** **Linux · macOS · Windows** - all code is portable (pathlib, atomic `os.replace`, `Path.as_uri()` links, OS-aware optional headroom) and CI runs the suite on all three × Python 3.10–3.13.
- **Open-source ready:** MIT `LICENSE`, full `pyproject` metadata (dist renamed `writing-agent`), `CONTRIBUTING.md` / `SECURITY.md` / `CODE_OF_CONDUCT.md` / `CHANGELOG.md`, GitHub Actions CI, issue/PR templates, ruff + pre-commit.
- **Open product calls:** none blocking.

## How to use this file

- **Session start:** read this file top-to-bottom, then `plan.md`.
- **Session end:** prepend a new `### <YYYY-MM-DD> - <summary>` entry below with what changed,
  decisions made, and the concrete next step.
- Keep entries short and factual. Durable decisions go in `plan.md`; this is the journal. Don't
  duplicate.

## Session log

### 2026-06-14 (24) - Repo structure + redundancy review (cleanups; big items flagged)

Reviewed the layout/standards + redundancy. Verdict: the repo is already well-structured (src layout,
tests/, config/, conventional root files, good docs). Applied the safe cleanups; the high-value
redundancy items are large refactors, left as recommendations.

- **Cleanups done:** gitignore `.ruff_cache/` + `.claude/` (were untracked but un-ignored); folded
  `pytest.ini` → `pyproject.toml [tool.pytest.ini_options]` (verified `pytest -q` still works via it);
  removed `requirements-dev.txt` (duplicated pyproject `[dev]`, unused by CI). Suite green.
- **Kept at root deliberately:** `plan.md`/`resume.md` are referenced as "the spec" in dozens of
  source docstrings (`cli`, `orchestrator`, `brain`, `prompts`, …) + the CLAUDE workflow - moving them
  would be high-churn for no gain. `requirements.txt` stays (a documented convenience mirror; pyproject
  is canonical).
- **Book↔article de-dup IN PROGRESS (safe, test-gated; plan.md §20):** mapped it (Explore agent), then
  extracted `_run_learner` (learner tail) and **Tier 1 `_base_run_state`** (shared run-state keys for
  `start_book`/`start_article`; mode-specific keys spread in). Suite green after each. **Deliberately
  did NOT merge `_commit`/`_commit_section`** - the paths differ structurally (canon vs
  citation-renumber), so a shared helper reads worse than the small dup (good judgment ≠ blind DRY).
  Remaining (own PRs): Tier 2 (fetch shell + attempt-loop via callbacks), Tier 3 (defer run-loop).
- **Still flagged:** giant `shell.py` (144KB) / `orchestrator.py` (115KB) - split AFTER the dedup (do
  §20 first, since the dup is intertwined). Optional: consolidate `SampleRun/`→`examples/`;
  collapse `requirements.txt`→pyproject+lock.

Followed up on the A/B run's finding that `cached_tokens: 0` on every OpenRouter call.

- **Root cause (measured live):** OpenRouter load-balances DeepSeek across upstreams; only some
  cache, so default routing never hits. Fix: new **`openrouter_providers`** setting →
  `llm.configure_openrouter_providers` → OpenRouter `provider.order` (fallbacks on). Live 2-call check:
  default routing cached 0 both calls; **pinned DeepSeek cached 768/965 (~80%) at ~3.5x lower cost**
  (call 2 still missed - OpenRouter instance load-balancing isn't 100%, so DeepSeek-direct
  `provider=deepseek` is the reliable path). Enabled `openrouter_providers: DeepSeek` in the local
  (gitignored) settings.yaml.
- **Measurement broadened:** `llm._cached_tokens` now also reads DeepSeek-direct's
  `prompt_cache_hit_tokens` (+ pydantic model_extra), so hits show on any host. +2 tests.
- Wired into both startup paths (`cli.main`, `api._apply_runtime`). Docs: plan §19, CHANGELOG.
- **A/B pilot COMPLETE (3 prompts; `benchmarks/blind_ab/RESULTS.md`):** Writing Agent 2, tie 1, Claude 0
  (win-rate excl ties 100%). The honest signal is the **dimension scores**: WA wins **trust/sources
  4.7 vs 3.7** (15-20 real cited sources + worked examples per piece), Claude wins **readability 5.0 vs
  4.0** (tighter), **insight ~even** (Claude 4.7 vs WA 4.3). **Not independent** - Claude wrote the
  competitor side AND judged, so it's indicative, not proof; needs a human/third-model judge. Real
  defects surfaced: WA repetition, a stray `[N]` in one piece, and resume-template SEO pages padding
  the microservices citations. `cases/` gitignored; RESULTS.md committed.

### 2026-06-14 (22) - Product (PM) review → implemented P0/P1 + PRD + evidence report

User asked for a product-value review (OSS lens, benchmarked vs rivals), then "implement everything +
add PRD.md". Review verdict: the engineering is ahead of the go-to-market; the differentiator
(thesis/critic/claim-verify) is real but *told, not shown*. Implemented the show-don't-tell P0s.
**Full suite green (~329 tests; +2).**

- **Evidence report** (the headline "proof" artifact): `polish.build_evidence_report(manuscript, thesis,
  title)` - deterministic, no LLM - emits the thesis + every source ranked by influence (parsed from the
  References list's 0-100 scores). `orchestrator.build_evidence_report(uid, id)` writes
  `evidence_report.md`; **auto-generated** at article assembly (`_produce_article`), refreshed by
  `repolish_manuscript`, and on-demand via the new **`evidence`** CLI command + `Project.evidence_report()`.
  Verified on the real voicebot article (46 sources, 13 high-influence). +2 tests.
- **README output-first rewrite**: spearhead one-liner ("argues a thesis and cites real sources - not
  slop"), a **"Why not just prompt ChatGPT?"** comparison table, an **Evidence report** section with a
  real sample, leads with articles, links to `examples/`.
- **`examples/` gallery**: ships the real voicebot `manuscript.md` + `evidence_report.md` + its SVG
  figures (copied out of gitignored `brain/`), a `SampleRun` pointer (the book), and a **Colab
  zero-install quickstart** notebook.
- **`PRD.md`**: full product-requirements doc - problem, target/non-users, JTBD, value/differentiation,
  scope, OSS success metrics, roadmap (Now/Next/Later), validation plan, risks, competitive landscape.
- **Blind A/B harness SHIPPED** (`benchmarks/blind_ab/`): `generate.py` (Writing Agent side, real
  run) → paste competitor into `chatgpt.md` → `blind.py` (anonymize A/B, strip format tells, hide key)
  → score `score_sheet.md` → `tally.py` (win-rate + dim scores). Validated offline (synthetic cases:
  blind/tally pipeline + tell-stripping asserted). Run-local artifacts gitignored; `RESULTS.md`
  template committed.
- **Next (need a human/deploy, not code):** actually RUN the A/B (human blind reads) → publish
  RESULTS.md; a hosted/zero-install web demo (HF Space); activation instrumentation
  (install → first finished piece).

### 2026-06-14 (21) - Token/cost-efficiency pass (telemetry-grounded; quality unchanged)

User: review the codebase for token/LLM-cost efficiency, then "implement all of it." Grounded in real
telemetry (241 calls: 843k prompt / 602k completion, p/c=1.40, $1.74; **pro = 98% of cost**; prompt
tokens dominate = repeated prefixes). **Full suite green (~327 tests; +7).** Headline finding: the
codebase is already cache-friendly (stable system prefix, variable user tail) and already disciplined
on max_tokens / verify excerpts - so the real win is **claiming the provider prompt-cache discount**,
not rewriting prompts.

- **F1 cache telemetry** (`llm.py`): capture `prompt_tokens_details.cached_tokens` → `usage_summary`
  ("N cached, X% of prompt") + JSONL. Makes the caching discount measurable.
- **F2 lossless schema shrink** (`llm._strip_schema_noise`): drop pydantic auto `"title"` keys from
  the per-call JSON-Schema dump (~20-30% smaller; lossless).
- **F6 `use_headroom` default OFF** (config.py + settings.yaml): ~no savings on single-turn payloads
  and it can perturb the cacheable prefix.
- **F4 thesis brief** (`nodes.thesis_brief`): critic+judge get claim+arguments only; writer keeps the
  full thesis (must engage the counterargument). Wired in the main article path.
- **F5 per-node `max_tokens`** (`ModelConfig.max_tokens_for` + models.yaml `max_tokens:`): tuning lever,
  defaults unchanged. The codebase already caps tightly (summaries 600-1500, etc.) - ~no savings, just
  configurability.
- **F3 `divergent_skeletons`** (opt-in, **default off**): draft variants short → judge → expand the
  winner. Threaded into run-state + the main article draft loop. Quality-risky, so off by default.
- **F7** already done (format_documents `excerpt_chars=1500` caps the verify payload). **F9** the one
  big shared fragment (`NO_SLOP`) is already a constant; unifying the two critics' (intentionally
  different) rubrics would change prompts for zero token gain - skipped. **F10** chat history 10→8.
- +`tests/test_token_efficiency.py` (6) + an article skeleton e2e. Docs: CHANGELOG, plan §19.
- **Next (the real lever):** verify OpenRouter returns a cache discount on DeepSeek; if not, route the
  hot nodes to DeepSeek-direct (automatic caching). A/B `divergent_skeletons` on a live run.

### 2026-06-14 (20) - TUI UX overhaul (full spec, all P0-P2 implemented)

User asked for a staff-level UX redesign of the TUI (audit-plan → approval gate → build), then
"fix all of it." Captured the real surfaces headlessly first (banner/welcome/help/features/run),
delivered the 10-part spec, then implemented every item. **All tests pass (full suite, fake mode);
+~10 tests in `test_ui.py`.** Standing framework saved to memory [[ux-redesign-framework-default]]
(audit-plan + approval gate before any design work; production-grade bar). **Functionality preserved -
no command/flag removed** (the user's explicit worry); changes are additive + test-backed.

- **P0.1 no command dead-ends** (`shell.run_shell`): reserved words without a slash (`_SLASH_WORDS`)
  run the command + a hint; ambiguous English words (`set/use/model/…`) only route as a single bare
  token (`_STRONG_SLASH`); leading `\` forces chat. Was: bare `help` → canned chat (verified fixed).
- **P0.2 summary settle**: `console.print()` before the Panel kills the `manuscript.md┌─` glue.
- **P0.3 trust chip** (`ui.trust_chip`): `verdict=… blocking=…` → `✓ approved · insight N/5 ·
  confidence ●●●○○`; **blocking>0 never renders as a bare approve** (the captured contradiction).
- **P0.4 recovery**: `_paused_card` (budget-cap vs interrupt + resume/alternatives) in the run loop;
  `cli._export_failed` (locked-file / missing-dep aware) replaces quiet `skip {fmt}` in all 3 export
  loops.
- **P1.5 dashboard**: soft ETA (rolling median per stage via `_enter_stage`/`_durs`), a "Ctrl-C
  pauses · resumable" controls line, stage banking. (True interactive mid-run keys = out of scope,
  noted - synchronous run loop.)
- **P1.6**: "self-edits" summary line (revision/humanizer counts on the dash); persistent prompt
  "done" marker is the status stripe.
- **P2.7 a11y/motion**: `WRITINGAGENT_A11Y` line-mode (no Live; append-only sentences) +
  `WRITINGAGENT_REDUCED_MOTION` (no spinner) + narrow (<60col) one-line wordmark fallback in `_banner`.
- **P2.8 key check**: `_provider_needs_key`/`_key_warning` warn in the banner when the active provider
  has no key. **Latent bug found+fixed**: `_stack_label` called `providers.resolve().name` but
  `resolve()` returns an id string, not a `Provider` (always hit the fallback) - now via `REGISTRY`.
- **P2.9 progressive help**: `/help <topic>` filters commands+slash (`_command_help_rows` extracted as
  the shared source); empty "no projects" state already had the try-it row.
- Docs: CHANGELOG Added/Fixed; this entry.
- **Follow-up (same session) - threaded mid-run controls + LIVE validation (user: "both"):**
  - **Live run controls** built: `orchestrator.run(control=None)` checks a duck-typed control at each
    **unit boundary** (only safe interruption point); `_apply_run_control` handles pause (return
    durable state) + manual (flip autonomous off + restore escalate thresholds). `shell._KeyListener`
    (cross-platform: msvcrt / termios+select) + `_RunControls`: **esc/p pause · m manual**, active only
    for autonomous + real-TTY runs (no-ops in pytest/pipes/a11y, so the suite is unaffected). Dashboard
    shows the controls hint + a live `note`. +4 tests (incl. an end-to-end pause/resume in
    `test_article.py`). **All tests pass.**
  - **Latent bug fixed**: `WRITINGAGENT_PROVIDER` configured the llm client but never synced
    `settings.provider`, so the banner/key-warning read the stale provider. `cli._apply_provider` now
    sets `settings.provider = providers.resolve(choice)`. Verified: banner shows `DeepSeek · … ` +
    `⚠ no API key for DeepSeek` when pointed at a keyless provider.
  - **LIVE (non-fake) run** (real DeepSeek, api path, 2 sections, researcher/images off): trust chip
    rendered correctly on REAL verdicts (`verdict=revise blocking=5` → `↻ revising · … · 5 blocking`;
    `verdict=approve blocking=0` → `✓ approved`); invariant held (no bare-approve-with-blocking). Judge
    picked variants for real. **24 calls / 173k tok / $0.25 / 2,603 words**; learner +4 skills. Demo
    project + `_live.py` deleted afterward. (Note: the api path doesn't auto-load `.env` like the CLI -
    a script must call `load_dotenv` itself.)
- **Next:** soft-ETA + the esc/m keys are interactive-terminal-only (can't capture in a pipe) - the
  user can see them with `writingagent run` on a 2+ section autonomous project; install `ebooklib` in
  `.venv` for epub re-exports.

### 2026-06-14 (19) - Diagram glance-rule + micro-improvements (read time, version, provider banner)

Three threads after the article re-polish. **All tests pass (full suite, fake mode); ruff not in
.venv but new lines match existing style.**

- **Diagrams - confirmed the architecture is already "LLM→spec→layout→SVG"** (the user proposed it;
  it's been the design since session 15). Mapped their proposal to the code (DiagramSpec / `_ranks`
  layering / deterministic render); ELK is already wired as the opt-in D2 backend. Added the user's
  **3-second-glance rule** to `DIAGRAM_SPEC_SYS` (governs pro + `diagram_fallback`), recorded in
  plan.md §16.6 + memory [[diagram-3-second-glance-rule]]. Fixed two stale "auto = D2" comments
  (`nodes.py` docstring, `diagram.py` D2 section) - `auto` = built-in since session 16.
- **Reading time was inflated** (user: voicebot said "22 min" but isn't). Root cause:
  `len(body.split())/200` counted **489 code words + 703-word references list** as prose (4,782
  total → 24 min). Fix: `polish.prose_word_count` / `read_time_min` / `refresh_read_time`
  (`READ_WPM=225`, strips fenced code + the References section + image lines); `ui.reading_time_min`
  now accepts text (prose) or int (legacy); `_assemble_article` uses it; **`repolish` rewrites the
  header**; `cli` status reads the manuscript for a prose-based estimate. Re-polished the voicebot
  article: header **22 → 16 min** (prose 3,568 words). +exports refreshed (epub skipped - `ebooklib`
  not in .venv).
- **Version single-sourced + bumped 0.1.0 → 0.2.0.** `src/writingagent/__init__.py __version__` is now
  the ONE source; `pyproject.toml` uses `dynamic = ["version"]` + `[tool.setuptools.dynamic] version
  = {attr="writingagent.__version__"}`; `shell.py` imports it (was a hardcoded `_VERSION = "0.1.0"`).
- **Banner provider/model now dynamic** (was hardcoded `"OpenRouter · DeepSeek"`). New
  `shell._stack_label(cfg, settings)` shows `providers.resolve(settings.provider).name · <writer
  model> · vX`; `_banner` takes cfg/settings (defaulted, so the theme test's `_banner(c)` still works).
- **New standing instruction:** the user set a staff-level **UX redesign framework** as the default
  for all future design work - **audit-plan + explicit-approval gate before any redesign**, production-
  grade bar (all component states, purposeful motion, AI trust/observability, WCAG 2.2). Saved as
  memory [[ux-redesign-framework-default]] (deliberately overrides the autonomous-flow pref for design
  work). **Next: presented a UX Audit Plan for the TUI; awaiting the user's go/no-go.**

### 2026-06-14 (18) - Re-polished the voicebot article (stale PDF) + CHANGELOG/README sync

User: "go to what we did last and give me improved docs" → clarified they meant the **voicebot
article** (`brain/users/default/articles/from-idea-to-sub-100ms-voicebot-…`). **No code change.**

- **Stale PDF fixed.** The article's `manuscript.pdf` was Jun-13 22:50 (pre-polish - last session it
  was file-locked open, so it never got the §16.6 polish + re-export); every other format was the
  Jun-14 00:16 polished version. Ran **`writingagent.py polish --book-id <id>`** (idempotent, ~0 tokens): it
  rebuilt the References (46 ranked), re-cleaned citations/stray refs, and re-exported pdf/html/docx/
  txt/md. **`epub` skipped** - `ebooklib` is missing from `.venv` (the existing polished `.epub` from
  last session is current, so all 6 formats are now polished). Verified the new PDF with pypdf: 16
  pages, **0 inline `[N]`**, References present, **46 ranked-ref lines**, figure captions 1.1/2.1/5.1
  intact, **0 raster images** (figures are the vector built-in SVGs). Spot-checked the HTML render in
  a browser - figures + ranked References list render clean.
- **Figures note:** the manuscript references the clean **built-in `section_0X_diagram.svg`** figures
  (3: §1/§2/§5), not model mermaid - so the prior open item ("figures are model mermaid, clipped pie")
  is effectively resolved in the current source. Leftover `images/mermaid_*.png` are unused cache.
- **Also (from the first read of the ask):** synced the user-facing project docs to §16.6 -
  **CHANGELOG.md** `[Unreleased]` got a top `### Added` entry for the deterministic polish pass (ranked
  References, `strip_inline_citations`, stray-dump removal, figure de-dup, `ARTICLE_WRITER_SYS` ban,
  `polish` command), and a **now-stale D2 bullet was fixed** (`diagram_engine: auto` is built-in since
  session 16, D2 is opt-in). **README.md** "How it makes good writing" gained a "clean prose, sourced
  at the end" bullet + a `writingagent polish <id>` note.
- **Next:** install `ebooklib` in `.venv` if epub re-exports are wanted here; consider a `rediagram`
  command to regenerate figures from the persisted `versions/*.diagram.spec.json`.

- **CHANGELOG.md** `[Unreleased]`: added a top `### Added` entry for the deterministic polish pass
  (one influence-ranked end References list 0-100 + dated, `strip_inline_citations`, stray-dump
  removal, figure de-dup, `ARTICLE_WRITER_SYS` forbidding model figures/captions/ref-lines, the new
  `polish` command / `repolish_manuscript()`). Also **fixed a now-stale D2 bullet** - it still claimed
  D2 is used automatically when the binary is present, but session 16 flipped `diagram_engine: auto`
  to the built-in engine; rewrote it as built-in-default / D2-opt-in.
- **README.md** "How it makes good writing": new bullet *"clean prose, sourced at the end"* (inline
  `[N]` stripped; one influence-ranked References list), plus a short note that
  `writingagent polish <id>` re-fixes an existing piece with no model call (~0 tokens).
- **Not done:** the export-quality session itself was never given its own dated entry in this Session
  log (it lives only in "Current status" as "session 16"); left as-is to avoid inventing details - the
  §16.6 spec already covers it. No `docs/` source in this repo (docs-writingagent.vercel.app is a
  separate repo).
- **Next:** if the docs site is in scope, port the References/polish material there too
  (`reference/quality/` + a `polish` command page).

### 2026-06-13 (17) - Diagrams: dedicated cycle (ring) + comparison (two-column) layouts + spec audit

User: "finish the diagrams." The built-in renderer degraded `cycle`/`comparison` to `flow`; now
both have dedicated layouts. **263 tests pass** (+3 net); ruff clean. **Verified visually**
(Playwright: a CD-loop cycle and a Monolith-vs-microservices comparison render cleanly).

- **`_render_cycle`** (`diagram.py`): nodes evenly on a ring (radius from `(box_w+gap)/(2·sin(π/n))`
  so adjacent boxes clear), edges as straight chords clipped to box borders (`_box_edge` ray-box
  intersection) with **angle-aware arrowheads** (`_arrow_at`); legend + focus as before. The natural
  shape for a feedback loop instead of a vertical list.
- **`_render_comparison`**: two colour-headed columns from the first two `group`s ("A vs B"),
  headers carry the colour (no separate legend); leftover-group nodes balance into the shorter
  column; cross-column edges drawn if present.
- **Dispatch** (`render_spec`): `cycle` (≥3 nodes) and `comparison` (≥2 groups) now route to their
  own layouts; under those thresholds they still degrade to `flow` (guarded, tested). Added
  `import math` + the two geometry helpers.
- **Spec audit trail**: `generate_svg_diagram` gained an `on_spec` callback; the orchestrator
  persists the `DiagramSpec` to `versions/<unit>.diagram.spec.json` (best-effort, never fatal) for
  both book + article diagram sites — so a figure's structure is inspectable, not just its SVG.
- **Tests** (`test_diagram.py`, +4 / -1): cycle spreads both axes (ring, not a column) + overlap-free;
  comparison renders two distinct column x-positions + headers; both degrade to flow when
  under-specified; `on_spec` receives the built spec. The pre-existing `test_cycle_*` was rewritten.
- **Next:** `timeline` archetype (horizontal spine) is the one common shape still mapped to flow;
  consider a `rediagram [--chapter N]` command now that the spec is persisted (re-render from the
  saved spec without a model call); a live run to see real model-authored cycle/comparison specs.

### 2026-06-13 (16) - `writingagent` npm launcher (global CLI over the Python engine)

User asked for an npm package, globally installable, that runs as a CLI command - named
**`writingagent`** (not `my-agent`), scoped as a **launcher for this Writing Agent** (their pick
over a standalone/LLM CLI). Built under **`writingagent/`** (zero npm deps, Node ≥16, CommonJS).

- **`lib/launcher.js`** resolves how to invoke the agent and forwards args with `stdio: 'inherit'`
  (so the TUI works) + propagates the exit code. Resolution order: `$WRITINGAGENT_CMD` →
  a console script on PATH (`writing-agent`, from `pip install`) →
  `python writingagent.py` (via `$WRITINGAGENT_HOME` or an upward search). Zero-dep cross-platform
  helpers: `whichSync` (honors PATHEXT), `findPython` (`py -3`/python3/python), `findProjectDir`.
  Local commands: `--version`, `--help`, `doctor` (diagnostics); everything else forwards
  (so `writingagent run --help` shows the agent's help). `bin/writingagent.js` is a 1-line shim.
- **Verified end-to-end:** `npm test` (5 Node `--test` cases - parse/which/project-discovery/
  env-override/version) green; `npm install -g .` then `writingagent --version|doctor|list` run
  from a neutral dir ($TEMP) and correctly resolve via the `writing-agent` console script even
  when writingagent.py isn't reachable from cwd; forwarded `list` printed the real projects; exit codes
  propagate (0). The earlier `-1` was just `Select-Object -First` closing the pipe (EPIPE), not a bug.
- **Naming:** npm `writingagent` (no hyphen) deliberately ≠ the pip console script `writing-agent`
  (hyphen) so they don't collide on PATH; the launcher calls the hyphenated one under the hood.
- **Next:** optional `npm publish` (add `repository`/`homepage` first); a `writingagent upgrade`
  that shells `pip install -U`; consider bundling as an `npx writingagent` one-shot.

### 2026-06-13 (15) - Diagrams rebuilt: structured spec → deterministic SVG renderer

User: "diagram is not good, text is still overlapping." Root cause: `generate_svg_diagram` asked
the model for **raw SVG with absolute coordinates** - an LLM can't measure text or verify geometry,
so labels overflow boxes and edge pills collide no matter the prompt (two prior prompt rounds, §12
sessions, didn't fix it). Fixed by removing layout from the model entirely. **260 tests pass**
(+19 across the built-in renderer and the optional D2 backend, new `test_diagram.py`); ruff clean.
**Verified visually** (Playwright screenshots of the rendered specs - flow w/ back-edge, branching
flow, layered stack, fan-out).

- **New `src/writingagent/diagram.py`** - a pure-Python SVG layout engine. The model returns a
  structured **`DiagramSpec`** (`schemas.py`: nodes/edges/labels/group/lane/focus + archetype) via
  the new **`DIAGRAM_SPEC_SYS`** prompt; the engine does the geometry: per-char text measurement →
  boxes sized to fit + labels wrap (never overflow); **uniform-box grid placement** so boxes can't
  overlap by construction; `flow` (column-ranked DAG) and `layered` (stacked lane bands) archetypes
  (`cycle`/`comparison` degrade to `flow`); orthogonal elbow edges (adjacent) or stacked bottom
  channels (spanning/back) that route around boxes; measured white pills for edge labels with
  collision-nudging; one colour per `group` + a bottom legend; `focus` node emphasized.
- **Back-edge bug** (caught in the visual check): a feedback arrow (`spk→mic` "barge-in") dragged
  the start node to the far right and reversed the whole pipeline. `_ranks` now detects back edges
  via **iterative DFS** and excludes them from longest-path layering, so forward order survives.
  Regression test pins it.
- **Explicit arrowheads** (polygons), not `<marker>` - svglib (the PDF path) drops markers, so a
  marker-only arrow vanished in PDF. `_svg_fill_guard` stays as a no-op safety net (the renderer
  already sets `fill="none"`). In fake/offline mode `generate_svg_diagram` returns a placeholder.
- **Flow**: model picks content (good at that); Python owns layout (model is bad at that). The old
  `DIAGRAM_SYS` raw-SVG prompt is gone; `generate_svg_diagram` now does spec → `diagram.render_spec`,
  with a flash-tier `diagram_fallback` retry on a node-less spec, then a placeholder.
**Follow-up (same session, user "use d2 lang with ELK, or compare side-by-side to choose"):**
evaluated [D2](https://d2lang.com) as the renderer. Installed d2 v0.7.1 (GitHub release tarball -
not in winget), wrote a `DiagramSpec → D2` converter, and rendered 4 test specs (flow + back-edge,
branching, layered, dense fan-out) three ways - **built-in vs D2+dagre vs D2+ELK** - screenshotted
side by side in a browser. Verdict: **D2+ELK routes complex graphs (fan-out/fan-in, lane
containers) noticeably better**; the built-in engine wins on zero-dep portability + in-figure
title/legend/metrics. So both ship: **optional D2 backend** (`diagram_engine: auto|d2|builtin`,
default `auto`), `diagram.to_d2` + `render_d2` (temp-file subprocess, ELK, never raises → built-in
fallback), discovered via `$WRITINGAGENT_D2` or `d2` on PATH. **User flagged D2 has no legend** -
fixed: `_inject_d2_legend` extends d2's outer viewBox and appends a colour legend matching the node
borders (verified visually). The built-in engine stays the zero-dep default so CI/unconfigured
users are unaffected. +7 diagram tests (the real-binary one skips without d2). `diagram_engine`
threaded through settings → run-state → both `generate_svg_diagram` call sites; cache key includes
the engine.

- **Next:** dedicated `cycle` (ring) and `comparison` (two-column) built-in layouts instead of
  degrading to flow; consider surfacing the spec in `versions/` for auditability; a `/set
  diagram_engine d2` live run to see real model-authored specs render through D2+ELK.

### 2026-06-13 (14) - Quality machinery II: independence, verification, compounding

**Ask:** "go deeper on logic/quality, suggest something to improve quality exponentially." Diagnosed
the structural ceiling (writer + critic are the same family per §12.1, so `insight`/`evidence` are
one model's self-jittery opinion and the learner converges toward its taste). Proposed five levers;
user picked four, in order 1→2→4→3. All built, tested, documented. Durable spec: **plan.md §15.6**
(+ §5, §8, §12.1 updated). **242 tests pass** (+11); ruff clean.

- **#1 Tournament judge** (`tournament_judge`, default on). New `nodes.rank_variants` + `judge`
  model slug + `VariantRanking` schema + `VARIANT_JUDGE_SYS`. `_pick_variant` now reads the
  divergent drafts **side by side** and returns `(draft, crit, refine_note, pref)`; the scalar
  `_crit_better` is the documented fallback (judge off / errors). The winner's `winner_weakness`
  is injected into the first refinement pass. Wired in **both** loops (book + article). Manual runs
  still let the human override (Enter = recommended).
- **#2 Claim↔source verification** (`verify_claims`, default on; **articles**). New
  `nodes.verify_claims` + `verifier` slug + `ClaimAudit`/`ClaimCheck` schema + `CLAIM_VERIFY_SYS`.
  `_do_research` now returns a 3-tuple `(prefix, sources, source_text)` (deep = full page text,
  shallow = snippets; never persisted). New `_verify_claims_gate` runs after each section critique:
  every `[N]`-cited specific claim is checked against its source; an unsupported one is appended as
  a BLOCKING `evidence` issue, downgrades `approve`→`revise`, and seeds the revision note. No-ops
  without source material / citations / when off. (Books deferred - `[N]` citations are an article
  feature; the node is reusable.)
- **#4 Counterargument + closed table-read loop.** Writer prompt now tells the article writer to
  **engage** the thesis's steelmanned counterargument head-on where a section meets it (not dodge).
  New `nodes.reader_report` (`ReaderReport` schema + `READER_REPORT_SYS`) names the single top fix +
  the section it targets; `table_read_revise` (default **off**, autonomous-only) applies it via the
  new `_targeted_section_revise` (write→critique→fix→humanize→patch section + manuscript),
  version-snapshotted `reader-fix` so it's reversible. Canon-free.
- **#3 Compounding learner.** `_record_preference`/`_read_preferences` log tournament outcomes
  (winner + why + weakness) and revision fixes to `<project>/learning_signals.md`; `nodes.learn`
  gained a `preferences=` arg (new `LEARNER_SYS` clause). Both `_learn`/`_learn_article` feed it.
  Per §8 these are model-judged → **candidate skills only**, efficacy gate unchanged (no
  auto-promotion to user scope). This is the only lever that compounds over runs.

**Cost note:** #1 adds 1 judge call per divergent unit; #2 adds 1 verify call per cited section; the
reader loop adds 1 structured read + ≤1 revision (off by default). All gate cleanly behind settings
and the run-budget kill-switch; telemetry captures the new `judge`/`verifier` calls.

**Follow-up (same session, user "add what you suggest"):** two refinements to the items I flagged.
(a) **Independence stays a deliberate user opt-in** - I did NOT switch `judge`/`verifier` to another
provider (that contradicts the standing DeepSeek-only decision + adds credentials/cost). Instead
both run at **temperature 0.2** (stable, repeatable verdicts) and the cross-family override is a
documented one-liner in `models.yaml`. (b) **`verify_claims` is now depth-gated** so default-on is
safe: with `deep_research` (full page text) an unsupported claim is BLOCKING; with shallow snippets
(a true claim may just be absent from the snippet) it's a non-blocking **nit**. So enforcement wants
`deep_research: true`; shallow mode is advisory. +1 test (shallow-advisory path); the blocking test
now sets `deep_research: True`. **241 tests pass**; ruff clean.

**Surface/consistency pass (user "review other parts to complement"):** the new feature was wired
into the engine but not all user-facing surfaces. Audited and fixed: (1) **`shell._NODES`** was
missing `judge`/`verifier` (and the long-missing `diagram`/`diagram_fallback`), so the documented
`/model judge <slug>` cross-family override would have been rejected as "unknown agent" - now all
models.yaml-routed nodes are selectable, with a **guard test** (`test_models_yaml_nodes_are_
selectable_in_shell`) so the list can't drift again. (2) The **`/features` board** and the **chat
assistant's `features_on` context** now surface the quality toggles (tournament / verify / table
read / reader-loop + the divergent_drafts/min_insight knobs). (3) **`config/settings.yaml`** (a
hand-maintained partial file) gained the quality cluster keys with comments, so they're visible and
editable. Verified the dynamic surfaces need no change: `/set` and `cli.cmd_config` enumerate
`dataclasses.fields(Settings)`, and `api.Agent(**overrides)` validates against them, so the new
settings were already accepted there. The **book** research path still returns a 2-tuple (only the
**article** `_do_research` became a 3-tuple for `source_text`) - no cross-path breakage. **242 tests
pass** (+11 this session); ruff clean.

**Next:** live (non-fake) article run to (a) sight-check the judge actually diverges from the scalar
pick on a real topic, (b) confirm `verify_claims` flags a planted unsupported stat against real
fetched sources (best with `deep_research: true`), and (c) try `table_read_revise: true` end-to-end.
Then tune: is the verify gate too aggressive on common-knowledge claims? Consider extending claim
verification to the book path if bibliography-cited books need it.

### 2026-06-13 (13) - Public Python API (stable `Agent` + `Project` facade)

**Goal:** turn the "internals are importable but unstable" state into a supported import-and-call
interface for embedding the pipeline (the README/plan promised one; now it exists).

**Decision (asked upfront, user picked):** `Agent` + `Project` facade over a bare one-shot - it's
the only shape that reaches the *whole* lifecycle from code (create, run, **resume a paused run**,
revise, evaluate, export). One-shot `write()` layered on top. Sync + `progress` callback (matches
the synchronous, network-bound engine; async is a `to_thread` away and deliberately out of scope).

**What landed:**
- **`src/writingagent/api.py`** (new) - the facade. `Agent(*, user, settings, models, autonomous,
  **overrides)` bundles the `cfg`/`settings`/`uid` plumbing the orchestrator functions otherwise
  demand; `**overrides` validated against `Settings`; `models=` accepts a `ModelConfig` or a slug
  string (→ `set_all`). `Agent.plan/create/write/open/projects`. `Project` is a cheap on-disk
  handle: `run/status/review/revise/evaluate/table_read/read/word_count/memory/consolidate/
  produce/export/delete`. Frozen-dataclass value types (`Approach`, `Status`, `Evaluation`,
  `WriteResult`) so the wire shape is stable and doesn't leak pydantic. `Status` normalizes the
  book/article run-state split. `requirements` (str|dict) feeds the §15.3 intake; `write()` forces
  autonomous (a one-shot can't answer a review).
- **`src/writingagent/__init__.py`** - `__version__ = "0.1.0"` + PEP-562 `__getattr__` lazy exports,
  so `import writingagent` and `from writingagent import brain` stay cheap (don't eagerly pull
  orchestrator/llm/nodes). Public names: `Agent, Project, Approach, Status, Evaluation,
  WriteResult, write, WritingAgentError, ProjectNotFound, EXPORT_FORMATS, MODES, Settings,
  ModelConfig`.
- **`tests/test_api.py`** (new, +14) - all offline via `WRITINGAGENT_FAKE` + the autouse temp-brain
  fixture. Covers lazy exports/version, planning, create→run→status→read, requirements
  persistence, explicit/Approach/int selection + range error, one-shot `write` (with and without
  export), open/projects/not-found, export-format + settings-override validation, delete.
- **Docs:** README "## Python API" section (install one-liner, one-shot, lifecycle,
  human-in-the-loop, method table, stability note); plan.md **§18**.

**Verified:** `231 passed, 1 skipped` (was 218; +14 here, others unchanged); ruff clean on the new
files (autofix dropped redundant quoted forward-refs under `from __future__ import annotations`).

**Context discovered en route (the ModernBERT question):** `use_headroom: true` (default) routes
every LLM call through headroom, whose ContentRouter→**Kompress** compressor loads
`answerdotai/ModernBERT-base` as a bare `ModernBertModel` encoder - hence the "UNEXPECTED keys"
load report (MLM head dropped; harmless). Not our `embeddings.py` (that's `all-MiniLM-L6-v2`). No
code change; noted in case we ever want to gate Kompress off via a `ContentRouterConfig` in
`llm._compress`.

**Next:** keep `__version__` in step with `pyproject` (currently both 0.1.0 - candidate for a
single source later). Optional follow-ups: async wrappers if an integrator needs them; expose a
`ReviewPending`-style signal if callers want exceptions over `Status.pending_review`.

---

### 2026-06-13 (12) - Diagrams to v4-pro + export image fixes + telemetry hygiene

User asked to upgrade the diagram model/prompt to v4-pro, then reported the real
article's exports: PDF had NO images, HTML diagrams had overlapping text, and a
regenerated diagram showed black blobs. All diagnosed live and fixed. **218 tests pass.**

- **Diagram node → DeepSeek V4 Pro** (`models.yaml`), 16k token budget (reasoning shares
  the cap - 6k starved it in 2026-06-09's attempt), plus a rewritten `DIAGRAM_SYS`
  (information-design craft: archetypes, type hierarchy with tspan wrapping, elbow edges
  with labeled pills, lanes, on-figure metric annotations, reserved legend corner, ONE
  focal emphasis). Deliberation explicitly bounded - "plan briefly, budget goes to SVG" -
  after the first version sent v4-pro into reasoning spirals that emptied the budget.
- **Black blobs:** multi-segment connector <path>s without fill="none" render as solid
  black polygons (SVG fills paths by default). `nodes._svg_fill_guard` now forces
  fill="none" onto every connector deterministically on every generated diagram.
- **Flash fallback** (`diagram_fallback` node): when pro emits no SVG, flash draws the
  figure instead of shipping the text-only placeholder.
- **PDF images fixed:** the exporter rasterized SVG via cairosvg-or-DROP; cairosvg isn't
  installed by default → image-less PDFs. xhtml2pdf renders SVG natively via its svglib
  dep (vector!), so the absolute path is passed through instead (cairosvg still preferred
  when present; svglib ignores arrow markers). Verified by rasterizing the real PDF.
- **"Overlapping text on every image" (HTML):** diagram-internal - the old flash diagrams
  printed label pairs on top of each other. All 3 diagrams of the voicebot article
  regenerated with the new prompt (verified visually: lanes, legends clear, no overlaps).
- **Dashboard "26 errors" + model "m" explained (user question):** test_hardening's retry
  tests call the real llm path (stubbed client, model "m", "401 bad key") and were
  appending toy records to the REAL `.index/telemetry` on every local pytest run. Brain +
  index isolation is now an **autouse** conftest fixture; polluted records scrubbed
  (65 real records remain, 0 errors). Blank project "-" in /dashboard = calls outside a
  run (chat, one-off scripts) - expected.
- **Gotcha noted:** a `(model, heading, context)` disk cache means a *prompt* change
  doesn't invalidate cached diagrams; regeneration scripts must not "placeholder-detect"
  by substring (a real diagram legitimately contained height="120" - detect by length).
- **Next:** regenerate diagrams is manual today (one-off script); consider a
  `rediagram [--chapter N]` command if diagram iteration becomes common.

### 2026-06-12 (11) - TUI: compact welcome, /features, toolbar removed, FAKE-mode warning

User feedback from a real launch: the startup screen was so long the wordmark scrolled
off (66 rendered lines vs a ~30-row terminal), and the bottom toolbar strip was "annoying".
Also debugged a live failure: chat kept replying with canned boilerplate - the user had
launched `writing-agent` from the same PowerShell window where a test command had set
`WRITINGAGENT_FAKE=1`, and nothing in the TUI indicated fake mode. **214 tests pass** (+3).

- **Welcome screen 66 → 33 lines** (banner 21 + welcome 12): START (write/new + a try-it
  example when no projects), YOUR PROJECTS (compact), status footer + one-line feature
  status + discovery line. The full COMMANDS table moved under **`/help`** (now renders
  commands + slash list); the FEATURES board moved to a new **`/features`** command.
- **Bottom toolbar removed** (`bottom_toolbar`, `_toolbar`, `_book_progress`, toolbar
  styles): state lives in the prompt prefix and welcome footer; a pending review still
  surfaces via the prompt suffix + escalation picker (the toolbar-turns-red behavior went
  with it - plan §13 updated).
- **FAKE-mode guard:** `_welcome` prints a red warning when `WRITINGAGENT_FAKE` is set
  (rich + plain paths) with the exact `Remove-Item Env:WRITINGAGENT_FAKE` fix - a leftover
  test env var can no longer silently can every model call.
- Guard tests: welcome height budget (≤14 lines, the regression that started this),
  fake-warning presence, /features + /help tables render (`test_ui.py`, +3).
- **Run dashboard animates (user feedback on a live run):** the `Live` previously got a
  static `dash.render()` snapshot, re-rendered only on log events - during one long
  critic call the stage text AND the elapsed clock froze for minutes. The dash object is
  now the renderable (`__rich_console__`), so Live's auto-refresh (8/s) re-renders it
  continuously: clock ticks, and active stages (`…`) get a braille spinner + cycling
  dots (`⠹ critiquing..`). Settled stages (reviewed/committed) stay static. +1 test
  (animation frames differ; dash is print-able). **215 tests pass.**
- **Next step:** user re-runs `writing-agent` in a clean terminal (no WRITINGAGENT_FAKE) and
  retries the live article: chat-propose → "go ahead" → run.

### 2026-06-12 (10) - Review fixes (revise parity, stream errors, fetch gate) + Linux CI unblocked

Full pending/improvable review (resume+plan backlog, code review of the 269192c..9653244 pull,
codebase health scan), then "fix all of it". **211 tests pass** (+55); ruff clean; **CI green on
all 12 matrix jobs** after the fix below. All testing this session is recorded in **`test.md`**.

- **CI was never green on Ubuntu** (every run since the workflow landed 2026-06-10 failed at
  `pip install -e ".[dev]"`, all 4 Python versions; macOS/Windows always passed). Repo went
  public this session → diagnosed headlessly via the Actions API, reproduced in WSL Ubuntu:
  svglib 1.6.0 (transitive via xhtml2pdf) hard-requires rlpycairo→**pycairo, which ships no
  Linux wheels** and fails to build on a bare runner (no pkg-config/libcairo2-dev). Fix: pin
  **`svglib<1.6`** in pyproject (xhtml2pdf only uses svg2rlg, never the cairo rasterizer);
  lockfile updated (svglib 1.5.1; pycairo/rlPyCairo/freetype-py dropped). Verified in WSL:
  install OK + full suite + ruff green on Linux.
- **revise_unit critic parity** (the code-review finding, conf 82): both revise paths critiqued
  with LESS context than the pipeline - no watch-list, no intake requirements, no prior-unit
  context, no length note (book path passed nothing at all) - so a post-completion revision
  violating them could sail through. Both now mirror the pipeline critic call (books open the
  Store for canon context); fix-pass rewrites also carry `requirements`. Regression tests for
  both paths.
- **Chat stream errors no longer masquerade as prose:** `llm.stream_text` used to yield the
  error as a text chunk - it rendered as assistant Markdown, was saved to chat history, and was
  command-parsed. Now it raises; the shell shows partial text + a styled error and discards the
  half-streamed reply from history/command parsing.
- **Deep-fetcher safety gate** (backlog item, now built): every uncached fetch passes an SSRF
  guard (host must resolve only to globally-routable addresses; stdlib path re-validates each
  redirect hop), per-host robots.txt (process-cached; missing/unreachable = allow;
  `WRITINGAGENT_IGNORE_ROBOTS=1` skips), and a 1s per-host politeness interval. Spec row in plan
  §15.2; README hardening section updated.
- **Wikimedia image search was silently dead live:** `_call` requests `formatversion=2` (pages
  = LIST) but `_fetch_info` parsed the v1 dict shape → AttributeError → swallowed by the
  net-error guard → always `[]`. Found by the new-coverage agent; now parses both shapes.
- **Coverage pass (+47 tests):** new `test_store.py`, `test_retrieval.py`, `test_skills.py`,
  `test_support.py` (cache/search/images/embeddings) - previously zero dedicated coverage for
  the learning loop's promotion logic, FTS retrieval, and the support modules.
- **Deliberately deferred** (own session): the ~800-line book↔article duplication in
  orchestrator/shell - a restructuring, not a fix; the revise-parity bug was drift between the
  duplicated paths, which is the argument for doing it.
- **Next step:** push went out with CI watched to green; user flips the repo private again
  (headless Actions checks then stop working - that's fine, CI gates reproduce locally + WSL).
  Then: live weak-topic `min_insight` calibration run + live chat-gate UX check (user-triggered).

### 2026-06-12 (8) - Hard go-ahead gate: chat can no longer create+run without the user's ok

Live run (the session-7 "next step") showed the chat model SKIPPING the PROPOSE step: the
user typed `new --abstract "..." run` (trailing `run` → leftover token → routed to chat) and
the model emitted ```` ```new``` ```` + ```` ```run``` ```` immediately - project created and
writing started with zero confirmation. Prompt rules alone don't hold.

- **Code-level gate in `_chat_respond`:** chat-emitted `new` executes ONLY when the
  triggering user message is an explicit go-ahead (`_is_confirmation`: short message whose
  words all come from a confirm vocabulary - "go ahead", "run it until the end", "ok start
  writing"...). Otherwise the WHOLE batch is held (a trailing `run` would hit the previously
  active project), rendered as "proposed - not run yet" with a confirm hint, and a
  `[shell: ... NOT executed ...]` note is appended to the assistant history message so the
  model re-emits the commands on the next confirming turn.
- **Prompt hardened too:** NEW TOPIC FLOW now covers imperative phrasings ("write an
  article on X", pasted `new ... run` lines) and tells the model the shell enforces the
  gate, so proposing first saves a turn.
- Tests: gate holds without go-ahead / executes with go-ahead / `_is_confirmation`
  positives+negatives (`test_shell_chat.py`, +3). **111 passed, 2 skipped**; ruff clean.
- **Next step:** re-run the live chat flow (topic → refine → "go ahead") to confirm the
  gate's UX feels right in a real terminal.

### 2026-06-12 (7) - Chat NL flow fixed: propose → refine in English → "go ahead" creates + runs

User screenshot showed the chat assistant promising a `new --abstract` it never ran, then
"run it"/"go ahead" failing with "No projects yet." **111 tests pass** (+4); root causes + fixes:

- **`_CODE_BLOCK_RE` bug (root cause):** `[^\n`]*` (info-string skip) greedily ate the entire
  content of single-line fenced blocks (```` ```run``` ````) - exactly the format the chat
  system prompt teaches - so the capture group was empty and every chat-emitted command was
  silently dropped. New regex only consumes the language tag when it ends in a newline:
  `` ```(?:[A-Za-z0-9_+-]*\n)?(.*?)``` ``.
- **"run it" routing bug:** REPL routed any line whose first word is a known command to
  argparse and `parse_known_args` discarded the leftover tokens, so "run it" ran bare `run`.
  Now leftover tokens → the whole line goes to `_chat_respond` instead.
- **New chat flow (system prompt):** no project yet → assistant PROPOSES a short abstract as
  inline code (no execution), the user can REFINE it with plain English (changes merge into a
  revised abstract, still no execution), and on confirmation ("run it"/"go ahead") it emits
  ```` ```new --abstract "..."``` ```` + ```` ```run``` ```` in ONE response - allowed now
  because `_execute_cmd` activates the fresh project between the two commands. (Removed the
  old "NEVER new+run together" rule.)
- Tests: single-line / language-tagged / bare fenced-block extraction in `test_hardening.py`.
- **Next step:** live-validate the flow with a real chat model (topic → refine → "go ahead").

### 2026-06-12 (6) - Production guards: run budget, JSONL telemetry + /dashboard, injection defense

From a production-readiness gap analysis (stack: identity/tools/memory/RAG/planning/guardrails/
approval/observability/eval/reliability/governance/ops), user picked the top 3; /dashboard added
on request mid-build. **107 tests pass** (+10); ruff clean. Spec rows in plan §15.1.

- **Run budget kill-switch:** `max_run_tokens` setting (0 = unlimited), read live at run start.
  `llm._check_budget()` runs before every text/structured call (before fake mode too, so it's
  testable offline) and raises `BudgetExceeded`; both run loops catch it and pause cleanly -
  resumable, nothing lost. Chat streaming is exempt.
- **Telemetry:** new `telemetry.py` - one JSONL record per LLM call (ts, run_id, project, unit,
  kind, model, latency_ms, attempts, tokens, cost, error) under `.index/telemetry/`, never
  raises. Attribution: `llm.set_project` (module-global - prefetch threads inherit) +
  `llm.set_unit` (thread-local; set per chapter/section/phase). Real cost captured via
  OpenRouter `extra_body={"usage":{"include":true}}` -> `usage.cost` (gated on an openrouter
  base URL); `[usage]` line + live dashboard now show $ and `tokens / budget`.
- **`/dashboard [<project>]`:** TUI rollup from the JSONL - totals (calls/tokens/$/avg
  latency/errors), per-model table; bare = all projects + recent runs, with a project name =
  per-chapter/section breakdown. Tab-completes project names.
- **Injection defense:** `prompts.wrap_untrusted` (markers + neutralization of spoofed markers
  + standing data-not-instructions note) applied at all 5 web->prompt choke points: research,
  research_article, deep_research, deep_research_article, interview.
- Next candidates from the same analysis (not built): golden-set eval harness, brain
  auto-git-commit, SSRF/robots guard on the fetcher, PyPI release, dependabot+pip-audit.

### 2026-06-12 (5) - Themes v3: 10 themes, each with its OWN figlet face ("theme changes everything")

User: add 3 tweakcn themes (by URL), revisit old ones, and make a theme change the *font style*
too, not just colors. Theme palettes were scraped from the tweakcn pages (hex values live in the
escaped Next.js flight payload; the `/r/themes/<id>.json` registry endpoint 500s).

- **Theme schema grew:** every theme now defines `FONT` (figlet face), `WORDS` (wordmark words/
  case), `SHEAR` (italic lean) alongside the palette - `apply_theme` rebinds them and
  `shell._wordmark` renders the active theme's face first (generic solid faces as fallback).
  A theme switch now changes palette + wordmark typography + fleuron + gradient + text tint.
- **New themes (tweakcn imports):** `fallout` (pip-boy amber `#ffcc00` + terminal green, pagga
  scanline face, ►), `mimi` (dusky rose/cream/teal pastels, double_blocky tiny face, ♡),
  `astrovista` (mars rust `#c14a24` - shifted from tweakcn's `#df6035` to clear the kazama-
  distance guard - over space navy, delta_corps_priest_1 sci-fi face, ✧).
- **Old themes:** per-theme faces assigned (editorial=ansi_shadow, kazama=ansi_shadow+**shear
  restored**, supabase=ansi_regular, violet-bloom=mono12 mixed-case, t3-chat=smblock,
  starry-night=elite, vercel=smmono9 hairline) + stronger PARCH tints so body text visibly
  shifts per theme.
- New guards: `test_theme_changes_wordmark_face`, `test_every_theme_face_is_available` (font
  must exist in pyfiglet - no silent fallback). **97 tests pass**; ruff clean.

### 2026-06-12 (4) - Theme set v2: distinct hue families + ANSI Shadow + left-aligned banner

User feedback on v1 themes: they all clustered warm (yellow/red/gold) and looked alike; wanted
tweakcn-style presets with completely different colors, the ANSI Shadow figlet for every theme,
and a left-aligned banner.

- **New theme set (each its own hue family):** `editorial` (default - **blue-ink** accent
  `#6f9ed9` + brass secondary, semantic status colors), `kazama` (flame, unchanged),
  `supabase` (emerald `#3ecf8e`, ◆), `violet-bloom` (purple `#8b5cf6`, ✿), `t3-chat` (pink
  `#ec4899` + purple, ♥), `starry-night` (gold stars `#ffd86b` on van Gogh indigo, ✶ - accent
  is the GOLD, indigo is secondary, so it doesn't collide with editorial's blue), `vercel`
  (monochrome white, cyan success, ▲). shakespeare/poe/gatsby dropped (too similar to the warm
  band).
- **Wordmark:** `ansi_shadow` is now the house face for ALL themes (solid █ + dark-outline
  shadow chars), upright (shear off), **left-aligned** with a 2-col indent (banner tagline +
  version too; `Align.center` gone).
- New guard test `test_themes_are_visually_distinct` (pairwise accent RGB distance > 60) -
  caught editorial-vs-starry-night blue clash during dev; fixed by making starry-night's
  accent the gold. **95 tests pass**; ruff clean.

### 2026-06-12 (3) - Theme system: editorial default + /theme switcher (5 themes)

Design review for open-sourcing: the Kazama flame as *default* broke status semantics (red/
yellow/green spent on branding) and collapses for red-green colorblind users. User agreed:
**`editorial` is the new default** (one warm accent `#ff6719`, amber→orange wordmark gradient,
ink-blue secondary, and semantic status colors - green ok / red error preserved); **kazama**
stays as a switchable theme, plus three fun ones: **shakespeare** (violet & old gold, ❦),
**poe** (midnight wine & crimson, ☾), **gatsby** (deco teal & champagne, ✦).

- `ui.THEMES` registry + `ui.apply_theme(name)` (rebinds the module palette constants; unknown
  -> default). Editorial values are also the static module bindings (lint-visible, single
  source). `flame_color()` now samples the *active theme's* `STOPS`.
- Live switching: `shell._sync_palette()` refreshes shell's from-imported names; cli.py reads
  `ui.X` at call time so it needs no sync. `cli.main` applies `settings.theme` BEFORE the shell
  import. prompt_toolkit completion/toolbar styles are built once per session -> refresh on next
  launch (noted in the switch message).
- Surfaces: `/theme` lists themes with gradient swatches, `/theme <name>` or `/set theme <name>`
  switches + persists (`settings.theme`, new Settings field); tab-completion for theme names;
  welcome footer shows the active theme; /help + chat system prompt updated.
- `tests/test_themes.py` (+6: completeness, apply/fallback, gradient sampling, shell sync,
  settings default, banner renders in all 5). **94 tests pass**; ruff clean.

### 2026-06-12 (2) - TUI retheme: "Kazama flame" (Jin Kazama red · orange · yellow on black)

User asked for a Jin Kazama (Tekken) look - red/yellow/black gradient - with a gradient-filled
wordmark. All theming flows through `ui.py` constants, so the swap is centralized.

- **Palette (`ui.py`):** new `FLAME_RED #e8240c` / `FLAME_ORG #ff7a18` / `FLAME_YEL #ffd23f`
  stops + `lerp_hex` / `flame_color(t)` multi-stop gradient sampler. Remapped: `GOLD`=orange,
  `GOLD_HI`=yellow, `INK` slate-blue -> ember red `#d4452f`, `RULE` -> dried-blood `#7a1208`,
  `ERR` -> alarm red `#ff4d3d`, `ON_CLR` green -> flame yellow (no green in the theme), `PARCH`
  -> warm bone. Old "ink & gilt" blue is gone.
- **Wordmark:** `shell._flame_text` renders WRITING/AGENT with a **per-character diagonal
  gradient** (red top-left -> orange -> yellow bottom-right, vertical-weighted 0.72/0.28);
  replaces the old per-line two-color lerp (local `_lerp` deleted - `ui.lerp_hex` is the one
  implementation).
- **Masthead frame:** `_flame_rule` - a mirrored-gradient `━` rule (red edges -> yellow-hot
  core) above and below the banner.
- **Details:** section headers = yellow fleuron + orange title; bottom toolbar fg RULE -> INK
  (dark red on near-black was unreadable); completion menu inherits the remap.
- **Wordmark v3 (user picked the Terminus face):** user pasted a half-block "Terminus" sample;
  matched it to figlet **`mono9`** (the Terminus-derived face). Wordmark is now mixed-case
  "Writing" / "Agent" in mono9 - every stroke is solid `▄▀█`, so the flame gradient fills it
  fully; upright (no shear), like the sample. Faces are now data
  (`_WORDMARK_FACES`: mono9 → ansi_shadow → ansi_regular → line-art fallbacks).
- **Wordmark v2 (user feedback - "hollow dotted outline", wanted Tekken-style fill):** switched
  the figlet font to **`ansi_shadow`** (solid `█` fill + `╔═╝` shadow chars), per-word **shear**
  (`_shear`, 1 col/row) for the Tekken italic lean, and two-layer coloring in `_flame_text`:
  solid blocks get the diagonal flame gradient, shadow chars become a near-black ember outline
  (`_OUTLINE #5c0d04`) like the logo's dark edge. Line-art fonts (slant/small/standard) remain
  fallbacks for terminals without box-drawing glyphs; the old "avoid block fonts" comment is
  superseded (user's terminal renders them fine).
- No test pinned colors; **88 pass**, ruff clean. `--plain`/`NO_COLOR` paths unchanged.
- Not touched: the SVG-diagram accent palette in `prompts.DIAGRAM_SYS` (that styles exported
  *content*, not the TUI).

### 2026-06-12 - Upfront-interview `write` flow + autonomous-flag bug fix

User wanted: "research, ask me everything upfront, then only come back with the end material" -
but the agent kept pausing for input and halting. Two root causes fixed; **86 tests pass** (+5);
ruff clean. Spec rows added to plan §7 and §15.3.

**The bug behind "asks again and again / stops":** `cmd_new` resolved autonomy with
`getattr(args, "autonomous", settings.autonomous)`, but `--autonomous` is an argparse
`store_true` whose default `False` *always exists* - so `settings.autonomous: true` was silently
shadowed and **every project was created non-autonomous**. It then escalated (`pending_review`)
on every low-confidence section and revision cap. Fix: `--autonomous` is now tri-state
(`store_const`/`default=None`) with a `--no-autonomous` override, resolved by
`cli._autonomous_value` (explicit flag wins, else the setting). Verified end-to-end: a plain
`new` now yields `autonomous=True, escalate_below_confidence=0.0, escalate_on_contradiction=False`.

**New one-shot `write` command** (`cli.cmd_write`): topic → quick best-effort web peek →
`nodes.interview` generates a tailored batch of clarifying questions (audience, depth, length,
tone, must-include, avoid) → all asked **once** upfront (`_conduct_interview` + `_ask_batch`,
markup-safe) → forced-autonomous run → **auto-exported finished file** (docx for articles, pdf
for books; chosen in the interview). Blocked from chat auto-exec (interactive). Reuses the live
dashboard via the new `shell.run_with_dashboard` (refactored out of `_cmd_run_rich`).

**Intake threading:** answers ("intake") fold into the planner/outline prompt (`_with_intake`)
AND inject into every writer/critic call as a high-priority `requirements` block (new kwarg on
`write_chapter`/`write_article_section`/`critique_*`). Author name captured upfront →
`user/profile.md` (`_record_author`) so Production fills bylines instead of escalating; article
byline now uses it. `intake` + `author` persisted in `run_state` and `intake.md`.

New: `schemas.Interview`/`InterviewQuestion`, `prompts.INTERVIEW_SYS`, `nodes.interview`,
`tests/test_write_flow.py`. Welcome screen + chat command list now lead with `write`.

**Also fixed - chat streaming duplicated itself in the scrollback** (user saw ~5 copies of a long
reply). `_chat_respond` fed a continuously-growing `Markdown` to a non-transient Rich `Live` with
`vertical_overflow="visible"`; once the reply was taller than the terminal, Live could not
overwrite the prior frame and re-emitted the whole block every refresh. Fix: stream a **transient,
cropped plain-text tail** (bounded to the viewport, erased on exit), then render the complete reply
**once** below. Partial text is still kept on cancel. `tests/test_shell_chat.py` added. The run
dashboard's `Live` was unaffected (its renderable is bounded). **88 tests pass.**

**"Stops after a certain token"** was the escalation halt + the `new`→`run` split, both removed
by the above (one command, no pauses). Per-node `max_tokens` were already generous (writer 8k
article / 16k book) and were not the cause.

**Next:** live (non-fake) `write` run to sight-check the interview questions' quality and that
requirements (length/tone/must-include) actually land in the prose; consider a `--yes`/scripted
intake for non-interactive `write`.

### 2026-06-11 (2) - Logic-review fixes: revision loop, learning loop, citations, length, cohesion, exports

Full-project logic review found 14 gaps; all fixed. **81 tests pass** (+10); ruff clean. Spec rows
added to plan §15.

**Silently-broken loops fixed:**
- Article learner ran AFTER production's cleanup deleted `eval_*.json` -> always saw zero critic
  findings. Cleanup now runs after learn. Plus a produce resume-guard: re-entering production with
  no section files no longer overwrites the manuscript with an empty one.
- Learner watch-list was write-only - now injected into every critic call (books + articles);
  applied skills also shown to the critic.
- Human review instruction was overwritten by the first critique's notes (`_merge_fix_notes`
  keeps it ahead of critique notes every round). Escalation resume now passes the reviewed
  `.draft.md` as the revision base; every revision attempt passes the previous draft (the writer
  was regenerating from notes about text it couldn't see). Draft file deleted on commit.
- Autonomous mode committed the LAST attempt; now commits the best-judged one (`_crit_better`:
  approve > fewer blocking > confidence).
- Article "summaries" were `draft[:800]` - now real `summarize_section` calls (parallel with
  humanize at commit, strict gather).

**Correctness of output:**
- Citations: per-article source registry (`sources.json`, URL-deduped, first-seen order); in-text
  `[N]` renumbered at commit (`_renumber_citations`, two-phase, link-label-safe) so they match the
  final References. Books persist sources too -> production feeds real sources to bibliography
  components (`_BIBLIO_RE`); planner told how many sources exist.
- Timeline events recorded under the actual committing chapter (LLM numbers were unreliable).
- Exports package images: PDF base_dir + cairosvg-or-drop for SVG, EPUB items, pandoc
  `--resource-path`, HTML data-URI inlining; `md` export no longer duplicates the H1.

**Quality additions:**
- `target_words` per chapter/section (planner prompts updated; writer gets target note, critic
  gets actual count, ±40% miss = blocking).
- `article_cohesion` setting (default on): whole-article smoothing pass before References,
  guarded (≥60% length, headings survive) so it can never lose content.
- FTS index finally used: `store.search_excerpts` + `assemble_context` pulls relevant excerpts
  from non-dependency chapters. SVG-diagram fallback gated to non-fiction genres.
- `propose_search_queries` capped at n.

**Next:** live (non-fake) run of an article with researcher on to sight-check citation numbering
and the cohesion pass; consider apportioning targets when outline omits per-section values.

### 2026-06-11 - Performance pass: prefetch pipeline, parallel commit batch, canon cap

Wall-clock optimisation sweep after a full code review. **71 tests pass** (was 67; +strict-gather,
+canon-cap, +incremental-index tests); ruff clean. No behaviour changes to prose/continuity - the
chapter chain stays sequential; only LLM-call *scheduling* changed.

**Pipeline scheduling (`orchestrator.py`):**
- **Unit prefetch:** research/images/skills for chapter (and article section) **n+1** are fetched on
  a 2-worker pool while unit n is written/critiqued (`_chapter_fetch`/`_section_fetch`, prefetch loop
  in `run()`/`_run_article`). They depend only on plan/TOC; results are disk-cached so an escalation
  wastes nothing. Skill retrieval moved into the same gather (its first embeddings call pays the
  model load).
- **Parallel commit batch:** `_commit` (and `_repair_contradictions`) now run humanize ∥ summarize ∥
  extract_canon concurrently via `concurrency.gather(strict=True)` - 3 serial LLM round-trips -> 1.
  Summary/extraction read the pre-humanized draft (humanizer preserves content). strict=True keeps
  the old failure semantics (failed summary/extraction aborts the commit; chapter file written only
  after the batch, which *shrinks* the old partial-commit crash window).
- **Deep research:** query-expansion LLM call now overlaps a warm-up search of the seed query
  (`_deep_docs`); merged pass hits the search disk cache.

**Token/prompt diet:** writer/critic canon block capped at the 12 most recent facts per character
(`retrieval.MAX_CANON_FACTS_PER_CHAR` -> `store.canon_context(max_facts_per_char=...)`).
Consolidation/extraction still see full canon. Also fixes late-chapter prompt growth (was linear).

**Smaller fixes:** `store.index_chapter` (incremental FTS; per-commit full rebuild was O(n²)) +
`render_canon(names=...)` (only touched characters rewritten); `canon_context` N+1 query -> grouped;
Scrapo fetches share one persistent background event loop (was `asyncio.run` per URL per thread);
per-thread DDGS session reuse in `search.py` (reset on error); embeddings import deferred
(`find_spec` - top-level sentence-transformers import pulled torch); numpy cosine when available;
`_json_instruction` cached per schema; embed-cache path now respects `brain.INDEX_DIR` (was
hardcoded `_ROOT/.index`, bypassing redirects).

**New: `WRITINGAGENT_HOME`** env var relocates brain + .index off synced folders (OneDrive sync adds
latency to every atomic write and its locks can break `os.replace`). Documented in README
troubleshooting + plan §15. **Recommended on this machine** (repo lives in OneDrive).

**Stack decision (recorded):** stay on Python - workload is ~95% LLM network latency; threads
release the GIL on socket waits. No asyncio rewrite, no LangGraph for perf. If server/multi-user
mode lands, front this engine with FastAPI; don't rewrite it.

**Next:** unchanged backlog (live deep-research e2e; LangGraph wrapper; multi-user; robots.txt).

### 2026-06-10 - Deep multi-source researcher + article tests + craft skills + read fix

Worked four items off the backlog after fast-forwarding `master` to `origin/master` (the merged hardening branch). All offline; **62 tests pass** (was 44); ruff clean on `src` + `tests`.

**1. `read --manuscript` for articles (`cli.py`):** `cmd_read` hardcoded `BookPaths`, so it never found article manuscripts/sections. Added `cli._paths_for(uid, project_id)` (ArticlePaths if the article `run_state` exists, else BookPaths - both expose `.manuscript`/`.ch`/`.ch_summary`) and routed `cmd_read` through it. The shell's `read` dispatches to the same `cmd_read`, so it's fixed there too.

**2. Article-pipeline tests (`tests/test_article.py`, new):** the book pipeline had e2e tests; the article pipeline had none. Added: fake-mode start_article -> run -> done (manuscript + references assembled, intermediate `section_*` files cleaned up, learner skill emitted), escalate -> review -> resume, `_produce_article` source de-dup by URL, and the `_paths_for` article/book resolution.

**3. Technical-writing seed skills (`seeds/skills/`, +4 -> 13):** `technical-explanation` (concrete-before-abstract, progressive disclosure, worked examples), `runnable-code-examples` (minimal/runnable/tagged + show output), `claims-and-evidence` (every claim sourced; no fabricated stats), `information-architecture` (one idea per section, dependency order, scannable). Same frontmatter+section format as the existing seeds; all `status: trusted`.

**4. Deep multi-source researcher (`src/writingagent/deep_research.py`, new):** the §15 deferred "Deep Researcher", now built. Pipeline: `nodes.propose_search_queries` (query expansion, best-effort) -> `deep_research.gather_documents` (concurrent multi-query search via `concurrency.gather`, dedupe by URL, cap 2/domain, keep top 6) -> concurrent `fetch_text` (stdlib `urllib` + an `html.parser`-based `_TextExtractor` that strips script/style/nav; http(s)-only, byte-capped, non-HTML skipped, 7-day disk cache, all non-fatal) -> `nodes.deep_research` / `deep_research_article` synthesize across the numbered full-text sources and cite by number. Opt-in `deep_research` setting (layers on `use_researcher`), threaded through `start_book`/`start_article` run_state and both `_do_research` branches in the orchestrator. Articles persist the **real fetched URLs** as sources (more reliable than LLM-copied ones) -> References section. New schema `SearchQueries`; new prompts `QUERY_PLANNER_SYS` / `DEEP_RESEARCHER_SYS` / `DEEP_ARTICLE_RESEARCHER_SYS`; reuses the `researcher` model node (no models.yaml change). Surfaced in the shell FEATURES table + `settings.yaml`.

**Fetch backend (added after first pass, at user's suggestion):** the page-fetch step is pluggable. It prefers **Scrapo** (`github.com/vikast908/Scrapo`, v0.7.0, installed from git - not on PyPI) when available: `await scrapo.scrape(url)` returns clean page **markdown** and escalates HTTP -> http+session -> browser -> stealth on real failure signals (403s etc.), reaching pages the naive fetch can't. Bridged from the sync `fetch_text` via a per-call `asyncio.run` (safe: runs on `concurrency.gather` worker threads / the sync orchestrator thread, neither has a live loop). Scrapo leaves logging to the caller and structlog's unconfigured default prints everything, so the loader calls `scrapo.logging.configure_logging("WARNING")` (overridable via `SCRAPO_LOG_LEVEL`) to keep the TUI clean. If Scrapo is absent or returns nothing, it falls back to the stdlib `urllib`+`html.parser` path - so there are still **zero required deps** and CI (py3.10-3.13 x 3 OSes) stays green. `WRITINGAGENT_NO_SCRAPO=1` forces the stdlib path. Optional `[deep]` extra in `pyproject.toml` (git ref + `python_version >= '3.11'` marker). Browser-tier escalation additionally needs `playwright install chromium` (not required; without it Scrapo just stops at the HTTP tiers).

**Validated live:** real `gather_documents` over real DuckDuckGo + real Scrapo fetch returned 4 sources across 4 domains (realpython/docs.python.org/medium/datacamp/dataquest/geeksforgeeks across runs) with full markdown (~6000 chars each) in ~5s concurrently; medium.com's 403 escalated through the tiers; JS-only YouTube returned little text (needs the browser tier).

Tests in `tests/test_deep_research.py` (HTML extraction, cache-hit-without-network, dedup/domain-cap/max-sources, query dedup, format/truncation, **Scrapo-preferred / stdlib-fallback / env-kill-switch backend selection**, offline e2e for both pipelines, query-helper fallback, and an **opt-in live test** gated by `WRITINGAGENT_LIVE=1`). **67 tests** (66 pass + 1 live skipped by default); ruff clean. Spec: `plan.md` §15.2.

**Playwright installed (for Scrapo's browser tier):** `playwright==1.60.0` + `python -m playwright install chromium` (chromium-1223). Verified the browser tier now activates with no `playwright-missing` error (confirmed chromium launches + renders). Note: Scrapo escalates HTTP -> browser on *failure signals* (403/blocks), not merely thin content, so a 200-with-sparse-body page won't auto-escalate; hostile targets (YouTube) still return little even via browser.

**Dependencies recorded:** `requirements.txt` gained a documented optional "deep researcher" section (Scrapo via git + Playwright + `playwright install chromium`), mirroring the headroom/sentence-transformers optional style - not hard deps (Scrapo is py3.11+/git-only/opt-in). `pyproject.toml` `[deep]` extra now lists both `scrapo` and `playwright` (both `; python_version >= '3.11'`). `requirements.lock.txt` surgically updated: +scrapo (commit-pinned) +playwright +their 9 transitive deps (aiosqlite, beautifulsoup4, greenlet, markdownify, platformdirs, pyee, selectolax, soupsieve, structlog) and the editable line bumped b41a20a -> 0d35d3d; deliberately did NOT fold in the unrelated torch/transformers/embeddings stack a blind `pip freeze` would have added.

**Next:** a full deep-research pipeline run live (fetch path is validated live; full pipeline only run offline). The deep fetcher has no `robots.txt`/rate-limit yet (fine at this volume; Scrapo has `SCRAPO_RESPECT_ROBOTS`).

### 2026-06-10 - Reliability / performance / UX / security hardening (branch `hardening-reliability-ux`)

Two commits on a branch off `master` (not pushed): `35bda07` (hardening) + `752f7ee` (richer TUI/CLI). 44 tests pass.

**Headroom (context compression) fixed on Windows:**
- `headroom-ai` ≥0.21 is a Rust/pyo3 extension with **no published Windows wheel**; the sdist build failed (no toolchain + Git-Bash `link.exe` shadowing MSVC). 0.10.17 is the **last pure-Python release**, but its compressor still needs a native `_core`, *and* it routes non-tiktoken models (DeepSeek) to a HuggingFace tokenizer that hard-imports `transformers` → silently no-ops.
- Fix: install `headroom-ai==0.10.17 --no-deps` (skips `litellm`, whose deeply-nested paths break installs without Windows long-path support); `llm._compress` now passes a tiktoken model (`gpt-4o`) to headroom purely for token counting - compression is model-agnostic, so DeepSeek runs really compress (~97% on tool-output JSON). Declared `tiktoken` + `ebooklib`; added `requirements.lock.txt`. `headroom-ai` is now an optional extra in `pyproject.toml`, not a hard dep.

**Reliability / performance (`llm.py`, `orchestrator.py`, new `concurrency.py` / `cache.py`):**
- Classified retry with exponential backoff + jitter (honors `Retry-After`), fail-fast on 4xx, per-request `timeout` (new `request_timeout` setting), SDK retries disabled (we own them). Real structured-output **repair retry** (feeds the bad output + error back). Token-usage telemetry (`[usage]` line at run end + live in the dashboard).
- Overlap independent network steps within a unit (research ∥ image/SVG) and parallelize production components via `concurrency.gather` (thread pool). **The chapter/section chain stays sequential** - each pulls the previous summary for continuity, so it can't be parallelized without breaking canon (correction to an earlier over-estimate).
- On-disk cache (`cache.py`) for web search (7-day TTL) and generated SVG diagrams.

**Durability / security:**
- `brain.write_json`/`write_text` are atomic (temp + `os.replace`); `read_json` tolerates corrupt files (returns `None`) - `run_state.json` can no longer become unresumable. Resume guards in `_process_chapter`/`_process_article_section` skip already-committed units (no double-commit, no duplicate canon facts).
- Chat assistant **cannot auto-execute** `delete` / `/user` / `/set` (data-loss / tenant / config). `is_safe_id` validation + `delete_book` path confinement. Export HTML sanitized (strip script/iframe/handlers/`javascript:`). `retrieval._parse_frontmatter` coerces non-dict → `{}`; `skills.write_skill` emits YAML-safe frontmatter + avoids slug collisions; `Critique.confidence` clamped to [0,1]; `load_config` falls back if `models.yaml` missing.

**UX (`shell.py`, `cli.py`, new `ui.py`):**
- Live `run` dashboard; arg/value autocomplete (`/use`,`/model`,`/set`,`/skill`,`/mode`,`export --format`); persistent `FileHistory`; spinners during `new`; Rich `status` (phase stepper + word count + reading time); Markdown-rendered `read` (paged) / `memory`; skills efficacy bars; clickable export paths + size; "did you mean?"; `--plain` + `NO_COLOR`; richer bottom toolbar.
- `ui.py` centralizes the editorial palette + pure helpers; deleted dead `run.py`/`slice.py` (referenced removed `brain.ensure_book`).

**Removed dead code:** vertical-slice prototype `run.py` + `src/writingagent/slice.py`.

**Next:** push the branch + open PR when ready; the `--manuscript` path in `cmd_read` still uses `BookPaths` (won't find article manuscripts - pre-existing, low priority); consider article-node unit tests.

### 2026-06-09 - Bug fixes, headroom, SVG diagrams, colour update, push to GitHub

**Bugs fixed:**
- `AttributeError: 'ArticlePaths' object has no attribute 'ch_draft'` - added duck-type aliases (`ch`, `ch_draft`, `ch_summary`, `eval_of`) to `ArticlePaths` so shared orchestrator helpers work for both project types.
- `list_projects` type label wrong - now reads `run_state.json` `mode` field first; a project in `books/` created in article mode shows correctly as `(article)`.
- Delete `PermissionError` (WinError 32) - wrapped `shutil.rmtree` to catch `PermissionError` and show a friendly "close the file and try again" message instead of a raw traceback.
- SVG fallback - `generate_svg_diagram` was returning the placeholder because the model wraps SVG in a code fence and adds prose after. Fixed extraction: greedy match first; if no closing `</svg>`, extract from `<svg` to last `>` and auto-close.
- SVG model - was using DeepSeek V4 Pro (reasoning model) which burned all 6000 tokens on thinking. Moved to a dedicated `diagram` node (Flash) so all tokens go to SVG output.

**Headroom integration:**
- `headroom-ai` added as a core dependency (auto-installs with `pip install -e .`).
- `use_headroom: true` by default - compresses messages in `complete_text`, `complete_structured`, `stream_text`.
- `configure_headroom(enabled)` called at startup from both `cli.py` and `shell.py`.

**Colour update:**
- TUI accent `GOLD` → `#ff6719` (brand orange), `GOLD_HI` → `#ff8c4b`, `RULE` → `#8c3a10`.
- SVG diagram accent palette updated: `#f7934f` → `#ff6719`.

**Other:**
- `use_images: true` default in `settings.yaml` - diagrams now generate on every run.
- SVG prompt completely rewritten: 860×520 canvas, `<defs>` arrowhead marker, accent palette, mandatory topic-specific node labels, 6000 token budget.
- README.md fully rewritten with ASCII banner, badges, full pipeline diagrams, architecture table, all commands and slash commands, headroom section, SVG section, design decisions.
- Pushed to https://github.com/vikast908/WritingAgent (temp repo).

**Next:** unit tests for article nodes; more craft skills; LangGraph wrapper (optional).

### 2026-06-09 - Rename to WRITING AGENT, /update command, UX overhaul, docs update

**Rename:** the agent is now **WRITING AGENT** throughout - shell wordmark, tagline, `llm.py` `X-Title`, `pyproject.toml` (`writing-agent` entry point added), `CLAUDE.md`, `README.md`, `resume.md`.

**`/update` slash command:** type `/update [description]` or just `/update` (prompts inline). Reads the active project's `run_state.json` + last 800 chars of manuscript, then asks the chat agent to review and advise. Added to `_SLASH_HELP`, `_SLASH_COMPLETIONS`, and welcome screen.

**`_auto_or_pick_project()` helper:** eliminates all `--book-id` errors in the TUI. Auto-picks if exactly one project exists; shows a numbered picker for multiple; filters by `settings.mode` first (`article` mode only sees articles), falls back to all if no mode match. Called before any command in `_NEEDS_PROJECT`.

**`parse_known_args`:** both `_execute_cmd` and the main shell loop now use `parse_known_args` instead of `parse_args` - filler words (`run it`, `run now`, `run please`) no longer crash.

**`autonomous` bug fixed:** `cmd_new` was hardcoded to `autonomous=False`; changed to `getattr(args, "autonomous", settings.autonomous)` so `settings.yaml` `autonomous: true` is respected.

**BOM fix:** `brain.read_json` uses `encoding="utf-8-sig"` to strip the UTF-8 BOM that PowerShell 5.1's `Set-Content -Encoding utf8` writes.

**DOCX fix:** `export.markdown_to_docx` replaces `\n---\n` with `\n\n* * *\n\n` before pandoc, prepends a YAML front-matter block, and uses `--syntax-highlighting=kate`.

**SVG fallback:** `nodes.generate_svg_diagram()` + `prompts.DIAGRAM_SYS` - when `use_images=True` and Wikimedia returns nothing, the LLM generates a self-contained `<svg>` saved to `images/`. Applies to both books (per-chapter) and articles (per-section).

**Docs:** `README.md` fully rewritten (WRITING AGENT name, article mode, all 6 exports, `/update`, SVG fallback, flat article layout, accurate status). `plan.md` implementation status updated. `resume.md` (this file) current status block updated.

**Next:** unit tests for article nodes; more craft skills for technical writing; LangGraph wrapper (still optional).

### 2026-06-09 - Skills overhaul, 5-format export, ddgs fix, slop rules

**Skills (non-negotiable, always-on):**
- `NO_SLOP` constant added to `prompts.py` - injected into `WRITER_SYS`, `ARTICLE_WRITER_SYS`, `HUMANIZER_SYS`, and referenced in both critic prompts. 24 rules: banned verbs/adjectives/transitions/phrases/openers, no em-dashes, no fabrications, concrete > abstract.
- `HUMANIZER_SYS` fully rewritten with blader/humanizer rules (10 specific actions: inflated significance, symbolic language, weak construction verbs, synonym cycling, filler openers, transition phrases, sentence rhythm, hedging, rule-of-three).
- `ARTICLE_CRITIC_SYS` / `CRITIC_SYS` - both now flag AI slop as BLOCKING (not just a nit).
- 5 new seed skills (all general, no topic references): `no-ai-slop`, `writing-principles`, `prose-craft`, `story-architecture`, `prose-critique`. Updated: `humanize-prose`.
- Removed 5 topic-specific learned skills from user brain (Serendipity Code world-building rules).

**Export (5 formats):**
- Added `export_txt` and `export_md` to `orchestrator.py` and `export.py`.
- `cmd_export` now shows interactive format picker (pdf · epub · html · docx · txt · md) when `--format` omitted.
- Shell intercepts `export` without `--format` and shows Rich-styled picker via `console.input()`.
- CLI parser default changed from `"pdf"` to `None` to trigger interactive path.

**Search fix:** `search.py` now tries `ddgs` first (new package name), falls back to `duckduckgo_search` with warnings suppressed. `ddgs` added to `pyproject.toml`.

**Article pipeline:** Running live for topic "How to think with AI without offloading your brain to AI". 4/6 sections committed, sections 5-6 in progress.

**Next:** Export to DOCX once pipeline finishes (sections 5-6). Then the article is done.

### 2026-06-09 - Fix "new says Book abstract after /mode article"

**What changed (shell.py only - 3 targeted edits):**
1. **Prompt indicator** - `[article]` now shown even when no active book is set, using `global_mode = settings.mode`. Both prompt_toolkit path (`sfx_plain = " [article]"`) and Rich console path (`mode_tag`) updated.
2. **AI system prompt** - `_build_chat_system` appends a `MODE OVERRIDE` block when `settings.mode == "article"`. Block tells the AI: "`new` creates an ARTICLE not a book, never say 'Book abstract', say 'article topic'."
3. **`_CHAT_SYSTEM` static text** - `new` description changed from "Start a book" to "Start a new project - book (default) or article (when mode=article)"; removed old redundant `new (article mode)` line.
4. **`_next_hint` + `_show_post_hint`** - made `settings`-aware so the footer hint says `new --abstract "your topic"` (not "your idea") in article mode.

**Next up:** all previous optional items - unit tests, real article run, LangGraph, more built-in skills.

### 2026-06-09 - Chat UX: streaming, spinner, echo, next-step hints

- **`llm.stream_text()`** (new): generator that yields text chunks from a streaming OpenAI
  call. Falls back to yielding the fake placeholder in fake mode; on error yields an error chunk.
- **`_chat_respond()` rebuilt** with the full 5-step UX flow:
  1. Separator + `you  ›  <message>` echo - immediate acknowledgment before any API call
  2. `console.status("✦ deepseek-v4-flash...", spinner="dots")` - semantic loading state,
     shown while waiting for the first token
  3. Spinner drops the moment the first chunk arrives; remaining chunks stream progressively
     to the terminal with `console.file.flush()` per chunk
  4. ANSI cursor-up clears streamed raw text; Markdown re-renders it with code block styling
  5. Context-aware `_next_hint()` footer (e.g. `next: run` / `next: review --chapter N`)
- **`_next_hint(state)`**: reads `run_state.json` to suggest the most useful next command -
  `new` if no books, `review` if pending escalation, `export` if done, else `run`.
- **Plain-text fallback**: streams chunks directly with `print(chunk, end="", flush=True)`.
- 11 pytest pass; compile clean.

### 2026-06-09 - TUI chat mode + rich onboarding welcome screen

- **Chat mode:** any input that doesn't start with `/` and whose first word isn't a known
  book command is routed to DeepSeek Flash (`chat` node in `models.yaml`). Chat has full
  session context (active book, features, books list) injected into the system prompt.
  In fake/offline mode returns a static helpful hint. Chat response rendered via
  `rich.Markdown` with rule separators in the TUI; plain text in plain mode.
- **Welcome screen rebuilt** (`_welcome()`): now has four named sections:
  - **COMMANDS** - all commands with descriptions (including export EPUB)
  - **SLASH & CHAT** - slash commands + explicit "💬 free chat" tip
  - **GETTING STARTED** (first-time users with no books): 3-step guide + /set tips
  - **YOUR BOOKS** (returning users): live phase/chapter/pending status per book from run_state.json
  - **FEATURES**: colour-coded on/off indicators for humanize, researcher, embeddings, images
  - Footer: model names, skills count, books count, user; hints about chat mode
- **Settings enabled:** `use_researcher: true` (web search is ready), `use_embeddings: true`
  (already on). `use_images` left false (non-fiction opt-in).
- `chat` model node added to `config/models.yaml` (DeepSeek Flash); added to `_NODES` in
  shell so `/model chat <slug>` works.
- 11 pytest pass; compile clean; smoke test green.

### 2026-06-09 - Web search (Researcher), EPUB export, /set command

- **`search.py`** (new): DuckDuckGo web search via `duckduckgo-search` (no API key). Returns
  `[]` in fake mode / on network errors so the pipeline never blocks. `build_query()` derives
  a focused query from plan genre + chapter title + purpose; `format_results()` produces a
  compact context block. Wired into `orchestrator._process_chapter()` before `nodes.research()`.
- **`nodes.research()`** gains `web_results: str | None` param; injected as a "Live web search
  results" block so the LLM cites real sources with URLs.
- **`prompts.RESEARCHER_SYS`** updated: now explicitly instructs the model to prefer fetched
  facts and cite source URLs inline.
- **EPUB export** (`export.markdown_to_epub()`): splits on `---` separators (the assembly
  format), converts each section to XHTML via the `markdown` package, builds a proper
  `ebooklib` EPUB with NCX/Nav TOC and shared CSS. `orchestrator.export_epub()` extracts title
  from `plan.json` and author from `user/profile.md`. CLI: `book export --format epub|pdf`
  (default pdf). Added `duckduckgo-search` + `ebooklib` to `requirements.txt`.
- **`/set <key> <value>` shell command**: live-edits any `Settings` field (bool/int/float/str
  auto-parsed from default type), updates in-memory settings so new books in the same session
  pick them up, persists to `config/settings.yaml` via new `config.save_settings()`. Also added
  to `/help` table.
- **Note:** `save_settings()` rewrites `settings.yaml` without comments (same trade-off as
  `save_config()`); values are preserved correctly.
- 11 pytest still pass; all new modules compile; integration smoke test green.

### 2026-06-09 - Wikimedia image fetch + semantic embeddings for skill retrieval

- **`images.py`** (new): Wikimedia Commons API client (stdlib urllib, no new deps). Searches the
  File namespace, filters by CC/PD license, returns `ImageResult` dataclass with full attribution.
  `to_markdown()` emits the image + italicised attribution line ready for the writer. Network
  errors return `[]` silently so the writer always proceeds. Activated by `use_images: true`.
- **`embeddings.py`** (new): Semantic embeddings via `sentence-transformers` (all-MiniLM-L6-v2,
  ~80 MB download once). Lazy-loaded, disk-cached in `.index/embed_cache.json` (keyed by SHA-256
  so unchanged texts are never re-embedded). `available()` returns False if library is absent →
  `retrieval.py` falls back to Jaccard automatically.
- **`retrieval.py`** updated: `relevant_skills()` gains `use_embeddings` + `embed_cache` params.
  When enabled, embeds both the book's genre/tone/themes profile and each skill's tag list, ranks
  by cosine similarity; falls back to Jaccard on any embedding failure.
- **`nodes.py`** `write_chapter()` gains `images: list[str] | None` param; injected as a
  "Suggested images" block before fix_notes so the writer can embed them with kept attribution.
- **`orchestrator.py`**: `start_book()` saves `use_images` + `use_embeddings` to `run_state.json`;
  `_process_chapter()` fetches Wikimedia images (2 per chapter) and passes `embed_cache` path and
  `use_embeddings` flag to `relevant_skills()`.
- **`config/settings.yaml`** + **`Settings` dataclass** gain `use_images: false` and
  `use_embeddings: false`. Both default off so all existing tests keep passing.
- 11 pytest still pass; all new modules compile; smoke test green.
- **To enable images:** set `use_images: true` in `config/settings.yaml` before `book new`.
- **To enable embeddings:** `pip install sentence-transformers` then `use_embeddings: true`.

### 2026-06-09 - TUI redesign (editorial "ink & gilt") + shell branding

- Rebranded the shell with a distinctive editorial/letterpress look (via the
  frontend-design skill): gilt-gradient figlet wordmark, ink-blue tagline + colophon framed by
  rules, fleuron (❧) section headers, borderless command tables, dim studio footer, `❧ <model>`
  prompt. Deliberately unlike the Hermes orange-block aesthetic. Palette in `shell.py` constants.
- Wired up the console-script entry point; verified it launches from any directory.
- Compiles; 11 tests pass.

### 2026-06-09 - Slash commands + runtime model switching

- Shell now has Hermes-style slash commands: `/help`, `/model` (+ per-agent), `/skills`,
  `/skill <name>`, `/seed-skills`, `/books`, `/use <book>`, `/user <id>`, `/config`, `/clear`,
  `/exit`. Non-slash lines run book commands; `/use` sets the active book for following commands.
- `/model <slug>` routes ALL agents to any OpenRouter model; `/model <agent> <slug>` overrides one
  agent. Changes **persist** to `config/models.yaml` (new `config.save_config` + `ModelConfig`
  setters: `set_default`/`set_node`/`set_all`).
- Verified: `/model critic openai/gpt-4o-mini` persisted; `/skills` lists seed+learned; `/use` +
  typed `status` dispatched to the active book. 11 tests pass; config restored after test.

### 2026-06-08 - Interactive shell (TUI) + pip-installable `book` command

- Added `shell.py`: a Hermes-style REPL (pyfiglet banner + rich command panel showing
  models/skills/books/user + `<model> ›` prompt). Launches when `book`/`python writingagent.py` is run
  with no subcommand. Type commands without the `book` prefix; `help`/`clear`/`exit` built in.
- Refactored `cli.py`: extracted `build_parser()`; `main()` branches to the shell on bare invoke,
  reuses the same parser+`_COMMANDS` for one-shot and REPL.
- Packaging: `pyproject.toml` → `pip install -e .` installs a global `book` console script
  (verified runnable from another directory). `.env` now loads anchored to the project root, so it
  works from any CWD. **Git push is NOT required to run** - it's a local app.
- Deps: rich, pyfiglet (TUI). Smoke-tested (banner + panel render; piped commands dispatch).
  11 pytest still pass.

### 2026-06-08 - Humanizer, both fixes, seed skills, format-aware critic

- **Humanizer:** new `humanizer.py` (LLM rewrite + deterministic typographic clean that skips code
  fences) + `humanizer` model node; runs on each chapter at commit; `humanize` setting (default
  true) + `new --no-humanize`. Strips em-dashes and AI-favored phrasing.
- **Fixed both known nits:** (1) manuscript title no longer duplicated; (2) autonomous mode now
  ACTS on consolidation contradictions - `_repair_contradictions` rewrites the cited chapters
  (bounded, 1 round) then re-consolidates. Human mode still pauses for review.
- **Seed skills:** `seeds/skills/` (humanize-prose, diagrams-as-code, web-image-attribution,
  figure-captions-and-callouts) + `skills.seed_builtin` + `book seed-skills`; auto-seeded on `new`.
- **Critic is format-aware** (heading/code-block/figure checks for non-fiction/technical books).
- Tests +2 (humanizer clean; seed install) -> **11 pass**.
- Feedback-loop validation: a human caught a fate-control-vs-prediction worldbuilding contradiction
  in the sample; our consolidation pass had already flagged the same issue (contradiction #4) + 4
  others. (Autonomous mode reported but didn't act - exactly the gap the new auto-repair closes.)

### 2026-06-08 - LIVE run: bug fixed + first autonomous book + PDF (SampleRun/)

- Validated OpenRouter/DeepSeek live (3-call probe incl. JSON-structured).
- **Bug fixed:** DeepSeek V4 is a reasoning model; the critic's `max_tokens=4000` let internal
  reasoning truncate the JSON to empty content → crash. Fixed: empty/truncation detection + 3×
  retry in `llm`, and higher `max_tokens` on reasoning-heavy nodes (critic/extraction/
  consolidation 8k; production/researcher 4k; learner 6k).
- Built **autonomous mode** (`--autonomous`: never pauses; commits best draft at the revision cap)
  + **PDF export** (`book export`; markdown→PDF via `markdown` + `xhtml2pdf`). Tests → **9 pass**.
- Ran a fully autonomous book end-to-end: *The Misprint File* (dystopian noir, 3 ch, no human in
  loop). Ch2 approved; ch1/ch3 committed best-draft at cap; consolidation flagged 5 contradictions
  / 12 unresolved; production = 5 front + 2 back matter; learner = 5 on-topic skills; **9-page PDF**.
- Captured everything in **`SampleRun/`** (book/, learned/, manuscript.pdf, run-log.txt, README.md).
- Known nits (logged in Next up): manuscript title duplicated at top; autonomous mode reports but
  doesn't act on consolidation contradictions.

### 2026-06-08 - `.env` set up + closed escalation gaps (#1, #2)

- Created real `.env` (OpenRouter key, gitignored); scrubbed `.env.example` back to a placeholder
  (it's committed, so a live key there would leak).
- **#1 Low-confidence escalation gate:** critic `confidence < escalate_below_confidence` (default
  0.5) now escalates as a chapter review (settings + run_state + `_process_chapter`).
- **#2 Consolidation escalation:** when `escalate_on_contradiction` (default true), contradictions
  pause the run with `reviews/consolidation-*.md`; resume via the new `book run --force`.
- Faker gained `WRITINGAGENT_FAKE_CONFIDENCE` + `WRITINGAGENT_FAKE_CONTRADICTION` (default = clean book,
  so autonomous fake runs still complete).
- Added 2 tests (low-confidence escalate; consolidation escalate → force). **8 pytest pass.**
- Remaining spec gaps are now only the two intentional v1 simplifications (canon DB-of-record
  rendered to md; skill `target_failures` always 0) + the deferred §15 items. Live API run still
  pending.

### 2026-06-08 - Provider switch to OpenRouter + DeepSeek; LangGraph confirmed not needed

- Replaced the Anthropic SDK with the **OpenAI SDK against OpenRouter** (`OPENROUTER_API_KEY`).
- Per-node routing (`config/models.yaml`): `deepseek/deepseek-v4-pro` for planner/writer/
  consolidation; `deepseek/deepseek-v4-flash` for toc/critic/summarizer/production/learner/
  researcher. (Verified both slugs exist on OpenRouter.)
- Rewrote structured output: Anthropic `messages.parse` → **JSON mode + Pydantic validation** with
  one repair retry (portable). Dropped the Opus temperature guard (DeepSeek accepts sampling).
- `requirements.txt` → openai (not anthropic); `.env.example` → OPENROUTER_API_KEY.
- Re-verified offline: compile + **6 pytest pass** + fake e2e CLI all green.
- **Decision: LangGraph wrapper NOT required** - the on-disk state machine already gives
  orchestration + resume; LangGraph would only add ecosystem (viz/tracing), not function.

### 2026-06-08 - Researcher, fake-LLM mode, pytest suite

- Added the **Researcher** node (optional, off by default via `use_researcher`) wired into the
  chapter context slice - the last planned node.
- Added an offline **fake-LLM mode** in `llm.py` (`WRITINGAGENT_FAKE`, optional
  `WRITINGAGENT_FAKE_VERDICT`): builds valid Pydantic instances + canned prose so the full pipeline
  runs with no API.
- Added a **pytest suite** (`tests/`, `pytest.ini`, `requirements-dev.txt`): data layer
  (store/FTS5/canon, context slice, skill promote + retire) and end-to-end orchestrator (full
  pipeline; escalation → review → resume). **6 tests pass.**
- Added `book list`. All modules compile; UTF-8 console fix in place.
- Still: not run against the real API.

### 2026-06-08 - Full system built (all 10 components)

- Implemented the whole pipeline in `src/writingagent/`: `brain` (multi-tenant markdown layout +
  `BookPaths`), `store` (per-book SQLite FTS5 index + entity graph + canon, renders canon md),
  `retrieval` (context slice + lexical genre-relevance), `nodes` (planner/toc/writer/critic/
  summarizer/extraction/consolidation/production/learner), `skills` (efficacy counters +
  lift-over-baseline reconcile), `orchestrator` (durable on-disk state machine: chapters →
  consolidate → production → learn, with escalate/review/resume), `cli` + `writingagent.py`
  (new/run/status/review/read/memory/produce/consolidate/skills/config).
- **Two flagged deviations from spec** (both noted in plan.md top status block): orchestrator is a
  durable on-disk state machine, **not** LangGraph (brain on disk = checkpoint; LangGraph stays
  the wrapper target); genre-relevance is **lexical**, not embeddings (Anthropic has no embeddings
  endpoint). Both have clean seams.
- Also fixed: Windows cp1252 console crash → force UTF-8 stdout in `cli`/`slice`.
- **Verified:** all modules `py_compile`; venv install OK; `--help`/`config`/`skills`/`status`
  clean; offline data-layer smoke test passed (FTS5 search, graph, canon render, context slice,
  skills write/record/reconcile/relevance). Smoke artifacts removed. **NOT run vs API.**
- **Next:** end-to-end run with `ANTHROPIC_API_KEY`.

### 2026-06-08 - Vertical slice built (Planner→TOC→Writer→Critic)

- Built the files-only slice under `src/writingagent/` + `run.py` (no orchestrator yet). Nodes:
  planner (directions + expand), TOC, writer (streamed, adaptive thinking), critic
  (approve/revise/escalate + confidence + blocking/nits), summarizer. Revision loop with a
  `--max-revisions` cap → escalate + write a review-queue entry on failure.
- Grounded API usage in the claude-api reference and caught a spec bug: **Opus 4.7/4.8 reject
  `temperature`** (HTTP 400). Fixed `config/models.yaml` + plan §12.1 (critic → Sonnet 4.6) and
  gated sampling to Sonnet/Haiku in `llm.py`.
- Structured output via `messages.parse(output_format=<Pydantic>)`; long prose via
  `messages.stream().get_final_message()`. All modules `py_compile`-clean.
- Added `requirements.txt`, `.env.example`, `.gitignore`, `README.md`.
- **Not yet run** - no API key in this env, and runs make paid external calls.
- **Next:** user runs the slice with a key set, then iterate on prompts / start the memory
  substrate / LangGraph engine.

### 2026-06-08 - Architecture + spec finalized (planning only)

- Reshaped the pasted architecture into a coherent design (discussion, no code).
- Key reframes from the original draft:
  - Collapsed 10 agents → 8 nodes; Continuity/Style/Logic became *Critic checks*.
  - Dropped the 100-point rubric for **blocking/nits + confidence + verdict**.
  - Learning is **per-user across books**, genre-relevance retrieved (freeform tags).
  - Human-in-the-loop = **directed instructions on reject** (no prose edits); checkpoint/resume.
- Reviewed reference repos: **Hermes** (markdown skills, user modeling, FTS recall) and
  **GBrain** (markdown-canonical + synced index, entity graph, Dream-Cycle consolidation).
- Wrote `plan.md`.
- Closed all open questions (§15): notification = markdown review queue; consolidation = fixed
  N=5; skill efficacy = lift over baseline; researcher = shallow v1.
- Added: per-node **model routing** (§12.1), a **Book Production** layer for front/back matter +
  manuscript assembly (§16), and this `resume.md` + `CLAUDE.md` session-continuity convention (§17).
- **Next:** await user's choice - build memory substrate first, or thin vertical slice.
