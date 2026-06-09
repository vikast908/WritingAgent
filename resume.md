# Resume — WRITING AGENT

> **Read this first, then `plan.md`.** This is the session log: what happened last time and
> where to pick up. Newest entry on top. **Update it at the end of every working session.**

## Current status

- **Phase:** **Production-ready.** Books and articles both live-validated end-to-end.
- **Agent name:** **WRITING AGENT** (was BOOKWRITER). CLI: `writing-agent` / `bookwriter` / `book` / `python book.py`.
- **Article pipeline:** fully built and live-run — "How to think with AI without offloading your brain to AI" (6 sections, DOCX exported).
- **Book pipeline:** fully built and live-run — *The Misprint File* (3 chapters, 9-page PDF).
- **New this session (2026-06-09 session 4):**
  - Agent renamed WRITING AGENT throughout (shell wordmark, tagline, llm.py `X-Title`, cli.py, pyproject.toml `writing-agent` entry point).
  - `/update` slash command: describe changes → AI reads active project state + manuscript tail → review + advice.
  - `_auto_or_pick_project()`: smart auto-selection (single match auto-picked, multiple → clean numbered picker, mode-filtered). Eliminates `--book-id` errors entirely in TUI.
  - `parse_known_args` replaces `parse_args` everywhere — filler words like "run it" no longer crash.
  - `autonomous` default in `cmd_new` fixed: reads from `settings.autonomous` not hardcoded `False`.
  - `brain.read_json` uses `utf-8-sig` to strip PowerShell 5.1 BOM from JSON files.
  - DOCX export: `---` → `* * *` before pandoc, explicit YAML front-matter block, `--syntax-highlighting=kate`.
  - SVG fallback: LLM-generated `<svg>` saved to `images/` when Wikimedia returns nothing (both books and articles).
  - 6 export formats: pdf · epub · html · docx · txt · md (interactive picker).
  - `NO_SLOP` guardrails injected into all writer/humanizer/critic prompts.
  - README.md and plan.md fully updated.
- **Source of truth:** `plan.md` (spec + implementation status); `README.md` = how to run.
- **How to run:** `writing-agent` (after `pip install -e .`) or `python book.py` → interactive shell; `python book.py <cmd> ...` for one-shot. Needs `OPENROUTER_API_KEY` in `.env`.
- **Next up (all optional):** (a) unit tests for article nodes; (b) more built-in craft skills for technical writing; (c) LangGraph wrapper; (d) multi-user / server mode.
- **Stack:** Python; durable on-disk state machine; markdown brain + SQLite/FTS5; OpenRouter + DeepSeek V4 Pro/Flash per-node; Rich TUI + prompt_toolkit.
- **Open product calls:** none blocking.

## How to use this file

- **Session start:** read this file top-to-bottom, then `plan.md`.
- **Session end:** prepend a new `### <YYYY-MM-DD> — <summary>` entry below with what changed,
  decisions made, and the concrete next step.
- Keep entries short and factual. Durable decisions go in `plan.md`; this is the journal. Don't
  duplicate.

## Session log

### 2026-06-09 — Bug fixes, headroom, SVG diagrams, colour update, push to GitHub

**Bugs fixed:**
- `AttributeError: 'ArticlePaths' object has no attribute 'ch_draft'` — added duck-type aliases (`ch`, `ch_draft`, `ch_summary`, `eval_of`) to `ArticlePaths` so shared orchestrator helpers work for both project types.
- `list_projects` type label wrong — now reads `run_state.json` `mode` field first; a project in `books/` created in article mode shows correctly as `(article)`.
- Delete `PermissionError` (WinError 32) — wrapped `shutil.rmtree` to catch `PermissionError` and show a friendly "close the file and try again" message instead of a raw traceback.
- SVG fallback — `generate_svg_diagram` was returning the placeholder because the model wraps SVG in a code fence and adds prose after. Fixed extraction: greedy match first; if no closing `</svg>`, extract from `<svg` to last `>` and auto-close.
- SVG model — was using DeepSeek V4 Pro (reasoning model) which burned all 6000 tokens on thinking. Moved to a dedicated `diagram` node (Flash) so all tokens go to SVG output.

**Headroom integration:**
- `headroom-ai` added as a core dependency (auto-installs with `pip install -e .`).
- `use_headroom: true` by default — compresses messages in `complete_text`, `complete_structured`, `stream_text`.
- `configure_headroom(enabled)` called at startup from both `cli.py` and `shell.py`.

**Colour update:**
- TUI accent `GOLD` → `#ff6719` (brand orange), `GOLD_HI` → `#ff8c4b`, `RULE` → `#8c3a10`.
- SVG diagram accent palette updated: `#f7934f` → `#ff6719`.

**Other:**
- `use_images: true` default in `settings.yaml` — diagrams now generate on every run.
- SVG prompt completely rewritten: 860×520 canvas, `<defs>` arrowhead marker, accent palette, mandatory topic-specific node labels, 6000 token budget.
- README.md fully rewritten with ASCII banner, badges, full pipeline diagrams, architecture table, all commands and slash commands, headroom section, SVG section, design decisions.
- Pushed to https://github.com/vikast908/WritingAgent (temp repo).

**Next:** unit tests for article nodes; more craft skills; LangGraph wrapper (optional).

### 2026-06-09 — Rename to WRITING AGENT, /update command, UX overhaul, docs update

**Rename:** `BOOKWRITER` → `WRITING AGENT` throughout — shell wordmark, tagline, `llm.py` `X-Title`, `pyproject.toml` (`writing-agent` entry point added), `CLAUDE.md`, `README.md`, `resume.md`.

**`/update` slash command:** type `/update [description]` or just `/update` (prompts inline). Reads the active project's `run_state.json` + last 800 chars of manuscript, then asks the chat agent to review and advise. Added to `_SLASH_HELP`, `_SLASH_COMPLETIONS`, and welcome screen.

**`_auto_or_pick_project()` helper:** eliminates all `--book-id` errors in the TUI. Auto-picks if exactly one project exists; shows a numbered picker for multiple; filters by `settings.mode` first (`article` mode only sees articles), falls back to all if no mode match. Called before any command in `_NEEDS_PROJECT`.

**`parse_known_args`:** both `_execute_cmd` and the main shell loop now use `parse_known_args` instead of `parse_args` — filler words (`run it`, `run now`, `run please`) no longer crash.

**`autonomous` bug fixed:** `cmd_new` was hardcoded to `autonomous=False`; changed to `getattr(args, "autonomous", settings.autonomous)` so `settings.yaml` `autonomous: true` is respected.

**BOM fix:** `brain.read_json` uses `encoding="utf-8-sig"` to strip the UTF-8 BOM that PowerShell 5.1's `Set-Content -Encoding utf8` writes.

**DOCX fix:** `export.markdown_to_docx` replaces `\n---\n` with `\n\n* * *\n\n` before pandoc, prepends a YAML front-matter block, and uses `--syntax-highlighting=kate`.

**SVG fallback:** `nodes.generate_svg_diagram()` + `prompts.DIAGRAM_SYS` — when `use_images=True` and Wikimedia returns nothing, the LLM generates a self-contained `<svg>` saved to `images/`. Applies to both books (per-chapter) and articles (per-section).

**Docs:** `README.md` fully rewritten (WRITING AGENT name, article mode, all 6 exports, `/update`, SVG fallback, flat article layout, accurate status). `plan.md` implementation status updated. `resume.md` (this file) current status block updated.

**Next:** unit tests for article nodes; more craft skills for technical writing; LangGraph wrapper (still optional).

### 2026-06-09 — Skills overhaul, 5-format export, ddgs fix, slop rules

**Skills (non-negotiable, always-on):**
- `NO_SLOP` constant added to `prompts.py` — injected into `WRITER_SYS`, `ARTICLE_WRITER_SYS`, `HUMANIZER_SYS`, and referenced in both critic prompts. 24 rules: banned verbs/adjectives/transitions/phrases/openers, no em-dashes, no fabrications, concrete > abstract.
- `HUMANIZER_SYS` fully rewritten with blader/humanizer rules (10 specific actions: inflated significance, symbolic language, weak construction verbs, synonym cycling, filler openers, transition phrases, sentence rhythm, hedging, rule-of-three).
- `ARTICLE_CRITIC_SYS` / `CRITIC_SYS` — both now flag AI slop as BLOCKING (not just a nit).
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

### 2026-06-09 — Fix "new says Book abstract after /mode article"

**What changed (shell.py only — 3 targeted edits):**
1. **Prompt indicator** — `[article]` now shown even when no active book is set, using `global_mode = settings.mode`. Both prompt_toolkit path (`sfx_plain = " [article]"`) and Rich console path (`mode_tag`) updated.
2. **AI system prompt** — `_build_chat_system` appends a `MODE OVERRIDE` block when `settings.mode == "article"`. Block tells the AI: "`new` creates an ARTICLE not a book, never say 'Book abstract', say 'article topic'."
3. **`_CHAT_SYSTEM` static text** — `new` description changed from "Start a book" to "Start a new project — book (default) or article (when mode=article)"; removed old redundant `new (article mode)` line.
4. **`_next_hint` + `_show_post_hint`** — made `settings`-aware so the footer hint says `new --abstract "your topic"` (not "your idea") in article mode.

**Next up:** all previous optional items — unit tests, real article run, LangGraph, more built-in skills.

### 2026-06-09 — Chat UX: streaming, spinner, echo, next-step hints

- **`llm.stream_text()`** (new): generator that yields text chunks from a streaming OpenAI
  call. Falls back to yielding the fake placeholder in fake mode; on error yields an error chunk.
- **`_chat_respond()` rebuilt** with the full 5-step UX flow:
  1. Separator + `you  ›  <message>` echo — immediate acknowledgment before any API call
  2. `console.status("✦ deepseek-v4-flash...", spinner="dots")` — semantic loading state,
     shown while waiting for the first token
  3. Spinner drops the moment the first chunk arrives; remaining chunks stream progressively
     to the terminal with `console.file.flush()` per chunk
  4. ANSI cursor-up clears streamed raw text; Markdown re-renders it with code block styling
  5. Context-aware `_next_hint()` footer (e.g. `next: run` / `next: review --chapter N`)
- **`_next_hint(state)`**: reads `run_state.json` to suggest the most useful next command —
  `new` if no books, `review` if pending escalation, `export` if done, else `run`.
- **Plain-text fallback**: streams chunks directly with `print(chunk, end="", flush=True)`.
- 11 pytest pass; compile clean.

### 2026-06-09 — TUI chat mode + rich onboarding welcome screen

- **Chat mode:** any input that doesn't start with `/` and whose first word isn't a known
  book command is routed to DeepSeek Flash (`chat` node in `models.yaml`). Chat has full
  session context (active book, features, books list) injected into the system prompt.
  In fake/offline mode returns a static helpful hint. Chat response rendered via
  `rich.Markdown` with rule separators in the TUI; plain text in plain mode.
- **Welcome screen rebuilt** (`_welcome()`): now has four named sections:
  - **COMMANDS** — all commands with descriptions (including export EPUB)
  - **SLASH & CHAT** — slash commands + explicit "💬 free chat" tip
  - **GETTING STARTED** (first-time users with no books): 3-step guide + /set tips
  - **YOUR BOOKS** (returning users): live phase/chapter/pending status per book from run_state.json
  - **FEATURES**: colour-coded on/off indicators for humanize, researcher, embeddings, images
  - Footer: model names, skills count, books count, user; hints about chat mode
- **Settings enabled:** `use_researcher: true` (web search is ready), `use_embeddings: true`
  (already on). `use_images` left false (non-fiction opt-in).
- `chat` model node added to `config/models.yaml` (DeepSeek Flash); added to `_NODES` in
  shell so `/model chat <slug>` works.
- 11 pytest pass; compile clean; smoke test green.

### 2026-06-09 — Web search (Researcher), EPUB export, /set command

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

### 2026-06-09 — Wikimedia image fetch + semantic embeddings for skill retrieval

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

### 2026-06-09 — TUI redesign (editorial "ink & gilt") + BOOKWRITER branding

- Rebranded the shell to **BOOKWRITER** with a distinctive editorial/letterpress look (via the
  frontend-design skill): gilt-gradient figlet wordmark, ink-blue tagline + colophon framed by
  rules, fleuron (❧) section headers, borderless command tables, dim studio footer, `❧ <model>`
  prompt. Deliberately unlike the Hermes orange-block aesthetic. Palette in `shell.py` constants.
- Added a `bookwriter` console-script alias (kept `book`); verified it launches from any directory.
- Compiles; 11 tests pass.

### 2026-06-09 — Slash commands + runtime model switching

- Shell now has Hermes-style slash commands: `/help`, `/model` (+ per-agent), `/skills`,
  `/skill <name>`, `/seed-skills`, `/books`, `/use <book>`, `/user <id>`, `/config`, `/clear`,
  `/exit`. Non-slash lines run book commands; `/use` sets the active book for following commands.
- `/model <slug>` routes ALL agents to any OpenRouter model; `/model <agent> <slug>` overrides one
  agent. Changes **persist** to `config/models.yaml` (new `config.save_config` + `ModelConfig`
  setters: `set_default`/`set_node`/`set_all`).
- Verified: `/model critic openai/gpt-4o-mini` persisted; `/skills` lists seed+learned; `/use` +
  typed `status` dispatched to the active book. 11 tests pass; config restored after test.

### 2026-06-08 — Interactive shell (TUI) + pip-installable `book` command

- Added `shell.py`: a Hermes-style REPL (pyfiglet banner + rich command panel showing
  models/skills/books/user + `<model> ›` prompt). Launches when `book`/`python book.py` is run
  with no subcommand. Type commands without the `book` prefix; `help`/`clear`/`exit` built in.
- Refactored `cli.py`: extracted `build_parser()`; `main()` branches to the shell on bare invoke,
  reuses the same parser+`_COMMANDS` for one-shot and REPL.
- Packaging: `pyproject.toml` → `pip install -e .` installs a global `book` console script
  (verified runnable from another directory). `.env` now loads anchored to the project root, so it
  works from any CWD. **Git push is NOT required to run** — it's a local app.
- Deps: rich, pyfiglet (TUI). Smoke-tested (banner + panel render; piped commands dispatch).
  11 pytest still pass.

### 2026-06-08 — Humanizer, both fixes, seed skills, format-aware critic

- **Humanizer:** new `humanizer.py` (LLM rewrite + deterministic typographic clean that skips code
  fences) + `humanizer` model node; runs on each chapter at commit; `humanize` setting (default
  true) + `new --no-humanize`. Strips em-dashes and AI-favored phrasing.
- **Fixed both known nits:** (1) manuscript title no longer duplicated; (2) autonomous mode now
  ACTS on consolidation contradictions — `_repair_contradictions` rewrites the cited chapters
  (bounded, 1 round) then re-consolidates. Human mode still pauses for review.
- **Seed skills:** `seeds/skills/` (humanize-prose, diagrams-as-code, web-image-attribution,
  figure-captions-and-callouts) + `skills.seed_builtin` + `book seed-skills`; auto-seeded on `new`.
- **Critic is format-aware** (heading/code-block/figure checks for non-fiction/technical books).
- Tests +2 (humanizer clean; seed install) -> **11 pass**.
- Feedback-loop validation: a human caught a fate-control-vs-prediction worldbuilding contradiction
  in the sample; our consolidation pass had already flagged the same issue (contradiction #4) + 4
  others. (Autonomous mode reported but didn't act — exactly the gap the new auto-repair closes.)

### 2026-06-08 — LIVE run: bug fixed + first autonomous book + PDF (SampleRun/)

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

### 2026-06-08 — `.env` set up + closed escalation gaps (#1, #2)

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

### 2026-06-08 — Provider switch to OpenRouter + DeepSeek; LangGraph confirmed not needed

- Replaced the Anthropic SDK with the **OpenAI SDK against OpenRouter** (`OPENROUTER_API_KEY`).
- Per-node routing (`config/models.yaml`): `deepseek/deepseek-v4-pro` for planner/writer/
  consolidation; `deepseek/deepseek-v4-flash` for toc/critic/summarizer/production/learner/
  researcher. (Verified both slugs exist on OpenRouter.)
- Rewrote structured output: Anthropic `messages.parse` → **JSON mode + Pydantic validation** with
  one repair retry (portable). Dropped the Opus temperature guard (DeepSeek accepts sampling).
- `requirements.txt` → openai (not anthropic); `.env.example` → OPENROUTER_API_KEY.
- Re-verified offline: compile + **6 pytest pass** + fake e2e CLI all green.
- **Decision: LangGraph wrapper NOT required** — the on-disk state machine already gives
  orchestration + resume; LangGraph would only add ecosystem (viz/tracing), not function.

### 2026-06-08 — Researcher, fake-LLM mode, pytest suite

- Added the **Researcher** node (optional, off by default via `use_researcher`) wired into the
  chapter context slice — the last planned node.
- Added an offline **fake-LLM mode** in `llm.py` (`BOOK_AGENT_FAKE`, optional
  `BOOK_AGENT_FAKE_VERDICT`): builds valid Pydantic instances + canned prose so the full pipeline
  runs with no API.
- Added a **pytest suite** (`tests/`, `pytest.ini`, `requirements-dev.txt`): data layer
  (store/FTS5/canon, context slice, skill promote + retire) and end-to-end orchestrator (full
  pipeline; escalation → review → resume). **6 tests pass.**
- Added `book list`. All modules compile; UTF-8 console fix in place.
- Still: not run against the real API.

### 2026-06-08 — Full system built (all 10 components)

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

### 2026-06-08 — Vertical slice built (Planner→TOC→Writer→Critic)

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
- **Not yet run** — no API key in this env, and runs make paid external calls.
- **Next:** user runs the slice with a key set, then iterate on prompts / start the memory
  substrate / LangGraph engine.

### 2026-06-08 — Architecture + spec finalized (planning only)

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
- **Next:** await user's choice — build memory substrate first, or thin vertical slice.
