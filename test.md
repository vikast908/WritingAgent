# Test record - WRITING AGENT

Verification log for recent sessions (newest first). The living suite is `tests/`
(run `pytest -q` with `BOOK_AGENT_FAKE=1`); this file records what was executed,
where, and what it proved.

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
| robots.txt honored per host (+ `BOOK_AGENT_IGNORE_ROBOTS=1` escape hatch) | `test_deep_research.py::test_robots_disallow_blocks_fetch`, `::test_robots_ignored_via_env` |
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
