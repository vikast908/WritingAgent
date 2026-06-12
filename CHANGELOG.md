# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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
  and a red warning fires at launch when `BOOK_AGENT_FAKE` is set so test mode can't
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
  honors robots.txt per host (`BOOK_AGENT_IGNORE_ROBOTS=1` to skip), and rate-limits
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

### Fixed
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

### Changed
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

### Security
- The conversational assistant can no longer auto-execute `delete` / `/user` /
  `/set`; project/user ids are validated and deletes are confined to the brain dir.
- Exported HTML is sanitized (script/iframe/event handlers stripped).
- Deep-research fetches are SSRF-guarded (public-address-only hosts, redirect
  re-validation), robots.txt-respecting, and per-host rate-limited.

### Removed
- Dead vertical-slice prototype (`run.py`, `src/book_agent/slice.py`).

## [0.1.0]
- Initial book + article pipelines: plan → write → critique → revise → humanise →
  commit, with canon/consolidation, learned craft skills, and six export formats.
