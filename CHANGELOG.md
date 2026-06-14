# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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
  flow free with `BOOK_AGENT_FAKE=1`, instead of suggesting a command that would fail.

### Changed
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
  auto-selected just because the `d2` binary is present ($BOOK_AGENT_D2 / PATH still locates it when
  opted in). The zero-dependency built-in engine stays the default and the fallback.

### Added
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
  optional dep) instead of a quiet skip. (5) **Accessibility** - `BOOK_AGENT_A11Y` line-mode (no Live
  redraw; append-only full-sentence status for screen readers), `BOOK_AGENT_REDUCED_MOTION` (static
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
- **Typing a command word without its slash** (e.g. `help`, `features`) silently went to the chat
  assistant - a dead end (and a wasted LLM call in real mode). It now runs the command.
- **The run summary card's border glued onto the last log line** (`manuscript.md┌─ ✓ complete`) - the
  Live region had no trailing newline before the Panel; a settle newline is now printed first.
- **The critic verdict could read as a contradiction** (`verdict=approve … blocking=1`); the
  normalized trust chip never shows a blocking issue as a bare "approve".
- **The banner hardcoded "OpenRouter · DeepSeek"** regardless of the active provider/model, and (a
  latent bug) `providers.resolve()` returns an id string, not a `Provider`, so the provider name was
  always the fallback - both fixed; the masthead now reflects the real provider, writer model, and
  version (single-sourced from `book_agent.__version__`, bumped 0.1.0 → 0.2.0).
- **`BOOK_AGENT_PROVIDER` configured the model client but never synced `settings.provider`**, so the
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
