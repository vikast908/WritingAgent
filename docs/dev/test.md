# Test record - WRITING AGENT

Verification log for recent sessions (newest first). The living suite is `tests/`
(run `pytest -q` with `WRITINGAGENT_FAKE=1`); this file records what was executed,
where, and what it proved.

## 2026-07-16 (session 16): review-driven fix sweep

A full-codebase review (redundancy · mismatches · optimization) across every subsystem, then a
fix batch on branch `fix/review-sweep-2026-07-16`. See `CHANGELOG.md` (Unreleased → Fixed) and
`plan.md` §15.1 (review-sweep invariants row) for the decisions.

| Check | How | Result |
|---|---|---|
| Full offline suite | `python -m pytest -q` (Windows, py3.13) + `ruff check src tests` | **523 passed, 1 skipped** (opt-in live-net test); ruff clean (baseline was 521/1) |
| Dead config keys | scripted scan of all 55 `Settings` fields vs. repo usage | **none** - every field is read outside `config.py` |
| Escalation score alignment (Tier-1 bug) | new `tests/test_pipeline.py::test_record_escalated_score_keeps_arrays_aligned` | `approve_escalation` re-appends the stashed crit's scores so `scores`/`insights` stay 1:1 with `committed` (was silently desyncing → wrong `revise` target / `IndexError`) |
| N-style citation guard (Tier-1 bug) | new `tests/test_quality.py::test_rewrite_ok_preserves_n_style_citations` | the humanizer/surgery guard now preserves `[N12]`, not just `[12]` |
| Whole-word emotion resolution | extended `tests/test_compositor.py::test_emotion_resolution_with_aliases` | `hopeless` no longer resolves to its opposite `hope`; phrase roles ("a sense of dread") still resolve |
| Everything else | existing suite (unchanged) | book critique-panel wiring, register-aware surgery guard, `max_context_chars=0`, `Store.open` safety, webui raster/job-pruning, `export` src-swap, shell `_NEEDS_PROJECT`, dead-code removals - all covered by the green suite; no regressions |

**Deliberately deferred** (not bugs; high-risk refactors whose concrete harms were already fixed in
both pipelines): the full `book.py`/`article.py` `_revise`/`_reoutline`/`_draft`/tool-runner dedup,
and unifying the legacy-vs-agentic consolidation-cadence state keys. *[Update 2026-07-17: the
`_revise`/`_reoutline`/tool-runner extraction has since landed - `_revise_weakest_unit`,
`_reoutline_units`, `_writer_tool_runner` now live in `orchestrator/common.py`; see plan.md §20.]*

## 2026-06-17 (session 15): craft engine (§22) + compositor (§23)

Built and verified two layers: the **craft engine** (plan §22, branch `feat/craft-engine-all-tiers`)
- register-parameterized writing - and the **compositor** (plan §23, branch
`feat/compositor-personas-emotions`) - personas/emotions/voice-layer composition.

| Check | How | Result |
|---|---|---|
| Full offline suite | `python -m pytest -q` (Windows, `WRITINGAGENT_FAKE=1`) + `ruff check src tests` | **250 passed, 1 skipped** (opt-in live-net test); ruff clean *[editorial note, 2026-07-17: this figure is inconsistent with the adjacent sessions (433 in session 14, 523 in session 16) - treat it as a partial-run record]* |
| Craft engine (plan §22) | new `tests/test_craft_engine.py` | registers, register-aware anti-slop, craft metrics, few-shot exemplars, surgical passes, field templates, citation styles, voice-drift report |
| Compositor (plan §23) | new `tests/test_compositor.py` | personas, emotions, the voice-layer precedence + conflict resolution |
| Byte-for-byte back-compat | `tests/test_craft_engine.py` | `register=None`/`nonfiction` reproduces the old `slop.render_constraints()` / `tell_pattern()` **byte-for-byte** - every pre-existing run is unchanged |
| Offline/key-less safety | `tests/test_craft_engine.py`, `tests/test_compositor.py` | surgical + compositor passes are **no-ops in fake mode**, so offline/key-less runs and the suite are unaffected |
| Register/persona conflict resolution | `tests/test_compositor.py` | a persona incompatible with the register is **dropped + logged** (the register wins; compositor never silently concatenates) |

Cross-platform target unchanged: Linux · macOS · Windows × py3.10-3.13. Both branches are
deterministic-test-only (no live spend this session).

## 2026-06-16 (session 14): fully-agentic controller build-out + LIVE validation

| Check | How | Result |
|---|---|---|
| Full offline suite | `pytest` (Windows, `WRITINGAGENT_FAKE=1`) | **433 passed, 2 skipped** (opt-in live-net test + d2 binary not installed); ruff clean |
| Run-level agentic controller | `agentic/runner.py` macro loop; `tests/test_agentic.py` | macro actions (draft/reoutline/revise/consolidate/repair/table_read/produce/learn/escalate/done); `default` policy proven byte-identical to the fixed pipeline (equivalence guarantee); only `llm`/`trace` engage the run loop |
| In-generation tool use | `llm.complete_text_with_tools`; `tests/test_hardening.py` | tool-loop runs a tool then returns prose; fake-mode skips tools; falls back to a plain draft on error; double-bounded by `max_tool_rounds` (2) + total `max_tool_calls` (4) |
| Learned policy | `agentic/learn.py` `train_policy`; `tests/test_agentic.py` | context-conditioned model fit + persisted; consulted by `TracePolicy`; stays undecided on thin data |
| The 8 "fully agentic" gaps | `tests/test_agentic.py` | rich perception, reoutline, revise, escalate, learned policy, `verify_fact` tool + critique panel, budget self-monitoring — caps enforced, escalate pauses, budget-pressure drops optional actions, critique-panel majority |
| LIVE validation (real OpenRouter, key from `.env`) | one full agentic article, `agentic_policy=llm` + `agentic_inline_tools`, ran to `done` | **1,547 words, 61 LLM calls, 186k tokens (35% cached), $0.15, ~18 min.** Confirmed: writer called `research` + `verify_fact` mid-draft; run controller decided; fallback model engaged (pro length-limit → flash); claim-check + critique + revision loop ran; unit outcomes labelled into the trace |

Finding from the live run: the writer over-called `verify_fact` (~12/draft) → fixed with the
total-call cap (`max_tool_calls=4`). Throwaway run artifacts cleaned up + telemetry scrubbed.

## 2026-06-16 (session 13): agentic controller + resilience hardening

| Check | How | Result |
|---|---|---|
| Full suite | `pytest -q` (Windows, fake mode) | **390 passed, 1 skipped** (opt-in live test); ruff clean |
| Agentic controller (opt-in, plan §21) | new `tests/test_agentic.py` | `default`/`llm`/`trace` policies; controller chooses research/canon before drafting; `draft` step is the unchanged episode (learning loop untouched); `agent_trace.jsonl` append-only contract |
| Agentic shell/TUI surface | new `tests/test_agentic_tui.py` | `/agentic on\|off\|llm\|default` toggles the setting *and* flips the active project's controller live; `/trace` prints the project's trace; dashboard shows the latest decision |
| Config validation | new `tests/test_config.py` | `load_settings` clamps out-of-range values (`min_insight: 99`, negative `max_revisions`, etc.) to sane bounds instead of baffling runtime behavior |
| Fallback model on primary exhaustion | `tests/test_hardening.py` | a node whose primary exhausts retries (outage / 5xx / content filter) degrades once onto the global `fallback` tier instead of killing the run |
| Context budget | `tests/test_retrieval.py` | assembled canon+summaries+excerpts block is priority-bounded by `max_context_chars` (default 24000), so a long book can't silently overflow the window |
| Anti-slop lexicon single-source | `tests/test_quality.py` | the writer's `NO_SLOP` block and the deterministic humanizer are cross-checked against the one `slop.py` lexicon, so they can't drift (incl. the documented `optimize` TECHNICAL_EXCEPTION) |

Live-validation: a real 1-section article on OpenRouter (~$0.10) with the `llm` controller —
it chose research→research→draft, recorded in `agent_trace.jsonl`.

## 2026-06-13 (session 12): diagrams + export images

| Check | How | Result |
|---|---|---|
| Full suite | `pytest -q` (Windows) | **218 passed, 1 skipped**; ruff clean |
| v4-pro emits SVG with 16k budget | live call, real DeepSeek | 9.4k-char valid SVG (34 labels, 11 arrows) |
| Black-blob root cause | rendered the SVG in a browser | connector `<path>` without `fill="none"` fills solid black; fixed by deterministic `_svg_fill_guard` (+ unit test) |
| Flash fallback when pro emits no SVG | monkeypatched unit test | fallback model called, figure returned (`test_quality.py`) |
| PDF was image-less | counted `/Subtype /Image` in the exported PDF | 0 images → cairosvg-or-drop path confirmed; after fix, figure renders as vector art (verified by rasterizing the PDF with pypdfium2) |
| HTML "overlapping text" | Edge headless screenshots of the article's SVGs | overlap was diagram-internal (old flash diagrams); all 3 regenerated with the new prompt and re-verified visually - lanes, legends, no overlaps |
| Dashboard "26 errors" / model `m` | inspected `.index/telemetry` JSONL | all test fixtures leaked by retry tests (no `tmp_brain`); autouse isolation added, real telemetry scrubbed → 65 real records, 0 errors |

Live-call spend for the session's diagram validation: a handful of v4 calls (~$0.05).

## 2026-06-12 (session 10): review fixes + Linux CI unblock

## Summary

| Check | Platform | Result |
|---|---|---|
| Full suite (`pytest -q`, fake mode) | Windows 11 · py3.11 | **211 passed, 1 skipped** (opt-in live test) |
| Full suite (`pytest -q`, fake mode) | WSL Ubuntu 24.04 · py3.12 | **211 passed, 1 skipped** |
| Lint (`ruff check src tests`) | Windows + WSL Ubuntu | clean on both |
| `pip install -e ".[dev]"` | WSL Ubuntu (bare, no system packages) | **OK after `svglib<1.6` pin** (failed before) |
| GitHub Actions (matrix: 3 OS × py3.10-3.13) | push of this work | watched to completion after push |

Suite growth this session: **156 → 211 tests** (+55).

## 1. CI failure: diagnosis and reproduction

**Symptom:** every CI run since the workflow landed (2026-06-10, first run `4263476`) concluded
`failure`. Queried headlessly via the public Actions API once the repo went public:
all 4 **ubuntu-latest** jobs failed at the **Install** step (~16s, i.e. dependency resolution /
build, not tests); all macOS and Windows jobs passed. CI had **never** been green on Ubuntu.

**Reproduction (WSL Ubuntu 24.04, python 3.12.3):**

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
# → pycairo metadata generation failed:
#   "Dependency lookup for cairo with method 'pkg-config' failed" (no pkg-config, no libcairo2-dev)
```

**Root cause chain:** `xhtml2pdf` → `svglib>=1.2.1` (resolves 1.6.0) → `rlpycairo` → **pycairo**,
which publishes Windows/macOS wheels but **no manylinux wheels** - on Linux pip builds it from
source and fails on a bare machine/runner.

**Fix:** pin `svglib<1.6` in `pyproject.toml` (svglib 1.5.1 has no cairo chain; xhtml2pdf only
uses `svg2rlg`, never the cairo rasterizer). `requirements.lock.txt` updated to match
(svglib 1.5.1; pycairo / rlPyCairo / freetype-py removed). Local Windows env downgraded to
svglib 1.5.1 to match the lock.

**Verification:** fresh venv in WSL → `pip install -e '.[dev]'` succeeds with **no system
packages**, then the full suite + ruff pass on Linux (211 passed, 1 skipped; ruff clean).

## 2. Fix verification (new regression tests)

| Fix | Tests |
|---|---|
| `revise_unit` critic parity - revise-path critics now receive watch-list, intake requirements, prior-unit context (Store canon for books, section summaries for articles), and length note, matching the pipeline critic | `test_ux.py::test_revise_unit_article_critic_gets_pipeline_context`, `::test_revise_unit_book_critic_gets_pipeline_context` |
| Chat stream errors render as errors, not assistant prose - partial text kept on screen, half-streamed reply NOT saved to history, NOT command-parsed | `test_shell_chat.py::test_chat_stream_error_is_not_prose` |
| Deep-fetcher SSRF guard - public-only resolved addresses (loopback/private/link-local/cloud-metadata blocked), unsafe URLs never reach a fetch backend | `test_deep_research.py::test_url_is_safe_blocks_private_and_loopback`, `::test_fetch_text_blocks_unsafe_url` |
| robots.txt honored per host (+ `WRITINGAGENT_IGNORE_ROBOTS=1` escape hatch) | `test_deep_research.py::test_robots_disallow_blocks_fetch`, `::test_robots_ignored_via_env` |
| Per-host politeness throttle (1s between same-host requests; different hosts unthrottled) | `test_deep_research.py::test_throttle_spaces_same_host` |
| Wikimedia `formatversion=2` parse (live API returns `pages` as a list; the dict-only parse made every live image search silently return `[]`) | `test_support.py::test_search_wikimedia_parses_formatversion2_list` |

Two pre-existing fetch-backend tests (`test_fetch_text_prefers_scrapo_backend`,
`test_fetch_text_falls_back_to_urllib`) now monkeypatch `deep_research._fetch_permitted` so they
stay offline (the gate would otherwise do DNS/robots lookups).

## 3. Coverage pass over previously-untested modules (+47 tests)

Modules that had **zero dedicated tests** before this session, now covered (offline, no optional
deps required, CI-safe on all 3 OSes × py3.10-3.13):

- **`tests/test_store.py`** (9) - open/close persistence across reopen, FTS LIKE-fallback paths,
  `search_excerpts` `[]`-on-error contract, draft exclusion from indexing, canon status upsert
  semantics, `memory_summary`, `render_canon` name filtering.
- **`tests/test_retrieval.py`** (9) - `assemble_context` composition (canon + dependency
  summaries + FTS excerpts from outside the dependency set), `MAX_CANON_FACTS_PER_CHAR` cap
  wiring, `relevant_skills` filtering/ranking (lexical + semantic with faked embeddings,
  fallback on embed error), `_parse_frontmatter` YAMLError → `{}`.
- **`tests/test_skills.py`** (10) - skill index shape, per-skill efficacy counters,
  same-name overwrite (no slug-collision copies), candidate→retired promotion rules
  (MIN_SAMPLE, RETIRE_GAP, `target_failures>=2`, retired-is-terminal), `list_skills`.
- **`tests/test_support.py`** (19+1) - cache (corrupt-file miss, TTL expiry, unserialisable put
  never raises, key hashing under redirected `INDEX_DIR`); search (fake-mode `[]`, disk-cache
  reuse without network, error → `[]` + session reset, ddgs-first/duckduckgo_search-fallback
  import order); images (license + extension filtering, HTML stripping, net-error → `[]`,
  v1 + v2 API shapes); embeddings (unavailable-without-sentence-transformers contract,
  full-cache-hit never loads the model, cosine incl. zero-vector guard).

## 4. Known watch items (not regressions)

- The job-level Actions **log download API requires repo admin auth** (`gh auth login`) even on
  public repos; the web UI requires sign-in too. Diagnosis here used the runs/jobs APIs
  (statuses + step conclusions) + local reproduction, which is repeatable after the repo goes
  private again: CI gates reproduce locally (Windows) and in WSL Ubuntu.
- `min_insight` calibration and the chat-gate UX check still need **live** (paid) runs -
  user-triggered.
