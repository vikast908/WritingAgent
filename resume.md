# Resume - WRITING AGENT

> **Read this first, then `plan.md`.** This is the session log: what happened last time and
> where to pick up. Newest entry on top. **Update it at the end of every working session.**

## Current status

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
- **New (2026-06-13, session 13 - public Python API):** added `book_agent.api` - a stable
  `Agent` + `Project` facade (plus a one-shot `write()`) over the orchestrator, re-exported from
  the package root with `__version__` and PEP-562 lazy imports, so `from book_agent import Agent,
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
- **Agent name:** **WRITING AGENT** (was BOOKWRITER). CLI: `writing-agent` / `bookwriter` / `book` / `python book.py`.
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
- **How to run:** `writing-agent` (after `pip install -e .`) or `python book.py` → interactive shell; `python book.py <cmd> ...` for one-shot. Needs `OPENROUTER_API_KEY` in `.env`.
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
  a console script on PATH (`writing-agent`/`bookwriter`/`book`, from `pip install`) →
  `python book.py` (via `$WRITING_AGENT_HOME` or an upward search). Zero-dep cross-platform
  helpers: `whichSync` (honors PATHEXT), `findPython` (`py -3`/python3/python), `findProjectDir`.
  Local commands: `--version`, `--help`, `doctor` (diagnostics); everything else forwards
  (so `writingagent run --help` shows the agent's help). `bin/writingagent.js` is a 1-line shim.
- **Verified end-to-end:** `npm test` (5 Node `--test` cases - parse/which/project-discovery/
  env-override/version) green; `npm install -g .` then `writingagent --version|doctor|list` run
  from a neutral dir ($TEMP) and correctly resolve via the `writing-agent` console script even
  when book.py isn't reachable from cwd; forwarded `list` printed the real projects; exit codes
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

- **New `src/book_agent/diagram.py`** - a pure-Python SVG layout engine. The model returns a
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
fallback), discovered via `$BOOK_AGENT_D2` or `d2` on PATH. **User flagged D2 has no legend** -
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
- **`src/book_agent/api.py`** (new) - the facade. `Agent(*, user, settings, models, autonomous,
  **overrides)` bundles the `cfg`/`settings`/`uid` plumbing the orchestrator functions otherwise
  demand; `**overrides` validated against `Settings`; `models=` accepts a `ModelConfig` or a slug
  string (→ `set_all`). `Agent.plan/create/write/open/projects`. `Project` is a cheap on-disk
  handle: `run/status/review/revise/evaluate/table_read/read/word_count/memory/consolidate/
  produce/export/delete`. Frozen-dataclass value types (`Approach`, `Status`, `Evaluation`,
  `WriteResult`) so the wire shape is stable and doesn't leak pydantic. `Status` normalizes the
  book/article run-state split. `requirements` (str|dict) feeds the §15.3 intake; `write()` forces
  autonomous (a one-shot can't answer a review).
- **`src/book_agent/__init__.py`** - `__version__ = "0.1.0"` + PEP-562 `__getattr__` lazy exports,
  so `import book_agent` and `from book_agent import brain` stay cheap (don't eagerly pull
  orchestrator/llm/nodes). Public names: `Agent, Project, Approach, Status, Evaluation,
  WriteResult, write, BookAgentError, ProjectNotFound, EXPORT_FORMATS, MODES, Settings,
  ModelConfig`.
- **`tests/test_api.py`** (new, +14) - all offline via `BOOK_AGENT_FAKE` + the autouse temp-brain
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
`BOOK_AGENT_FAKE=1`, and nothing in the TUI indicated fake mode. **214 tests pass** (+3).

- **Welcome screen 66 → 33 lines** (banner 21 + welcome 12): START (write/new + a try-it
  example when no projects), YOUR PROJECTS (compact), status footer + one-line feature
  status + discovery line. The full COMMANDS table moved under **`/help`** (now renders
  commands + slash list); the FEATURES board moved to a new **`/features`** command.
- **Bottom toolbar removed** (`bottom_toolbar`, `_toolbar`, `_book_progress`, toolbar
  styles): state lives in the prompt prefix and welcome footer; a pending review still
  surfaces via the prompt suffix + escalation picker (the toolbar-turns-red behavior went
  with it - plan §13 updated).
- **FAKE-mode guard:** `_welcome` prints a red warning when `BOOK_AGENT_FAKE` is set
  (rich + plain paths) with the exact `Remove-Item Env:BOOK_AGENT_FAKE` fix - a leftover
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
- **Next step:** user re-runs `writing-agent` in a clean terminal (no BOOK_AGENT_FAKE) and
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
  `BOOK_AGENT_IGNORE_ROBOTS=1` skips), and a 1s per-host politeness interval. Spec row in plan
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

**New: `BOOK_AGENT_HOME`** env var relocates brain + .index off synced folders (OneDrive sync adds
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

**4. Deep multi-source researcher (`src/book_agent/deep_research.py`, new):** the §15 deferred "Deep Researcher", now built. Pipeline: `nodes.propose_search_queries` (query expansion, best-effort) -> `deep_research.gather_documents` (concurrent multi-query search via `concurrency.gather`, dedupe by URL, cap 2/domain, keep top 6) -> concurrent `fetch_text` (stdlib `urllib` + an `html.parser`-based `_TextExtractor` that strips script/style/nav; http(s)-only, byte-capped, non-HTML skipped, 7-day disk cache, all non-fatal) -> `nodes.deep_research` / `deep_research_article` synthesize across the numbered full-text sources and cite by number. Opt-in `deep_research` setting (layers on `use_researcher`), threaded through `start_book`/`start_article` run_state and both `_do_research` branches in the orchestrator. Articles persist the **real fetched URLs** as sources (more reliable than LLM-copied ones) -> References section. New schema `SearchQueries`; new prompts `QUERY_PLANNER_SYS` / `DEEP_RESEARCHER_SYS` / `DEEP_ARTICLE_RESEARCHER_SYS`; reuses the `researcher` model node (no models.yaml change). Surfaced in the shell FEATURES table + `settings.yaml`.

**Fetch backend (added after first pass, at user's suggestion):** the page-fetch step is pluggable. It prefers **Scrapo** (`github.com/vikast908/Scrapo`, v0.7.0, installed from git - not on PyPI) when available: `await scrapo.scrape(url)` returns clean page **markdown** and escalates HTTP -> http+session -> browser -> stealth on real failure signals (403s etc.), reaching pages the naive fetch can't. Bridged from the sync `fetch_text` via a per-call `asyncio.run` (safe: runs on `concurrency.gather` worker threads / the sync orchestrator thread, neither has a live loop). Scrapo leaves logging to the caller and structlog's unconfigured default prints everything, so the loader calls `scrapo.logging.configure_logging("WARNING")` (overridable via `SCRAPO_LOG_LEVEL`) to keep the TUI clean. If Scrapo is absent or returns nothing, it falls back to the stdlib `urllib`+`html.parser` path - so there are still **zero required deps** and CI (py3.10-3.13 x 3 OSes) stays green. `BOOK_AGENT_NO_SCRAPO=1` forces the stdlib path. Optional `[deep]` extra in `pyproject.toml` (git ref + `python_version >= '3.11'` marker). Browser-tier escalation additionally needs `playwright install chromium` (not required; without it Scrapo just stops at the HTTP tiers).

**Validated live:** real `gather_documents` over real DuckDuckGo + real Scrapo fetch returned 4 sources across 4 domains (realpython/docs.python.org/medium/datacamp/dataquest/geeksforgeeks across runs) with full markdown (~6000 chars each) in ~5s concurrently; medium.com's 403 escalated through the tiers; JS-only YouTube returned little text (needs the browser tier).

Tests in `tests/test_deep_research.py` (HTML extraction, cache-hit-without-network, dedup/domain-cap/max-sources, query dedup, format/truncation, **Scrapo-preferred / stdlib-fallback / env-kill-switch backend selection**, offline e2e for both pipelines, query-helper fallback, and an **opt-in live test** gated by `BOOK_AGENT_LIVE=1`). **67 tests** (66 pass + 1 live skipped by default); ruff clean. Spec: `plan.md` §15.2.

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

**Removed dead code:** vertical-slice prototype `run.py` + `src/book_agent/slice.py`.

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

**Rename:** `BOOKWRITER` → `WRITING AGENT` throughout - shell wordmark, tagline, `llm.py` `X-Title`, `pyproject.toml` (`writing-agent` entry point added), `CLAUDE.md`, `README.md`, `resume.md`.

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

### 2026-06-09 - TUI redesign (editorial "ink & gilt") + BOOKWRITER branding

- Rebranded the shell to **BOOKWRITER** with a distinctive editorial/letterpress look (via the
  frontend-design skill): gilt-gradient figlet wordmark, ink-blue tagline + colophon framed by
  rules, fleuron (❧) section headers, borderless command tables, dim studio footer, `❧ <model>`
  prompt. Deliberately unlike the Hermes orange-block aesthetic. Palette in `shell.py` constants.
- Added a `bookwriter` console-script alias (kept `book`); verified it launches from any directory.
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
  models/skills/books/user + `<model> ›` prompt). Launches when `book`/`python book.py` is run
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
- Faker gained `BOOK_AGENT_FAKE_CONFIDENCE` + `BOOK_AGENT_FAKE_CONTRADICTION` (default = clean book,
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
- Added an offline **fake-LLM mode** in `llm.py` (`BOOK_AGENT_FAKE`, optional
  `BOOK_AGENT_FAKE_VERDICT`): builds valid Pydantic instances + canned prose so the full pipeline
  runs with no API.
- Added a **pytest suite** (`tests/`, `pytest.ini`, `requirements-dev.txt`): data layer
  (store/FTS5/canon, context slice, skill promote + retire) and end-to-end orchestrator (full
  pipeline; escalation → review → resume). **6 tests pass.**
- Added `book list`. All modules compile; UTF-8 console fix in place.
- Still: not run against the real API.

### 2026-06-08 - Full system built (all 10 components)

- Implemented the whole pipeline in `src/book_agent/`: `brain` (multi-tenant markdown layout +
  `BookPaths`), `store` (per-book SQLite FTS5 index + entity graph + canon, renders canon md),
  `retrieval` (context slice + lexical genre-relevance), `nodes` (planner/toc/writer/critic/
  summarizer/extraction/consolidation/production/learner), `skills` (efficacy counters +
  lift-over-baseline reconcile), `orchestrator` (durable on-disk state machine: chapters →
  consolidate → production → learn, with escalate/review/resume), `cli` + `book.py`
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

- Built the files-only slice under `src/book_agent/` + `run.py` (no orchestrator yet). Nodes:
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
