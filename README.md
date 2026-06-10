<div align="center">

<pre>
 _    _______ _____ _____ _____ _   _ _____    ___  _____  _____ _   _ _____ 
| |  | | ___ \_   _|_   _|_   _| \ | |  __ \  / _ \|  __ \|  ___| \ | |_   _|
| |  | | |_/ / | |   | |   | | |  \| | |  \/ / /_\ \ |  \/| |__ |  \| | | |  
| |/\| |    /  | |   | |   | | | . ` | | __  |  _  | | __ |  __|| . ` | | |  
\  /\  / |\ \ _| |_  | |  _| |_| |\  | |_\ \ | | | | |_\ \| |___| |\  | | |  
 \/  \/\_| \_|\___/  \_/  \___/\_| \_/\____/ \_| |_/\____/\____/\_| \_/ \_/  
</pre>

### an autonomous writing studio — books, articles & more

[![CI](https://github.com/vikast908/WritingAgent/actions/workflows/ci.yml/badge.svg)](https://github.com/vikast908/WritingAgent/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square)](https://www.python.org/)
[![Platforms](https://img.shields.io/badge/platforms-Linux%20%C2%B7%20macOS%20%C2%B7%20Windows-informational?style=flat-square)](#setup)
[![OpenRouter](https://img.shields.io/badge/powered%20by-OpenRouter-orange?style=flat-square)](https://openrouter.ai/)
[![DeepSeek](https://img.shields.io/badge/model-DeepSeek%20V4-blueviolet?style=flat-square)](https://deepseek.com/)
[![Headroom](https://img.shields.io/badge/compression-headroom--ai-green?style=flat-square)](https://github.com/chopratejas/headroom)
[![License](https://img.shields.io/badge/license-MIT-lightgrey?style=flat-square)](LICENSE)

**60–95% token savings · self-correcting pipeline · books + articles · 6 export formats · resilient (retry + resumable) · local-first**

[Setup](#setup) · [Quick Start](#quick-start) · [How It Works](#how-it-works) · [Commands](#commands) · [Export](#export-formats) · [Features](#features) · [Architecture](#architecture)

</div>

---

## What it does

Writing Agent is a self-correcting, autonomous writing system that takes a topic and produces a publication-ready manuscript — drafting, critiquing, humanising, and revising in a loop until the work meets quality standards.

- **Books** — multi-chapter narratives with memory, continuity audits, and front/back matter
- **Articles** — long-form editorial pieces with research, citations, and editorial angles
- **Self-correction** — write → critique → revise → humanise → commit, up to a cap, then escalate
- **Quality guardrails** — hard rules against AI slop baked into every prompt
- **Context compression** — [headroom-ai](https://github.com/chopratejas/headroom) runs by default; 60–95% fewer tokens, same output quality

---

## Setup

**Requirements:** Python 3.10+ · runs on **Linux · macOS · Windows** · an [OpenRouter API key](https://openrouter.ai/) (free tier works). No API key is needed to install, run the tests, or try the offline demo.

### 1 — Clone

```bash
git clone https://github.com/vikast908/WritingAgent.git
cd WritingAgent
```

### 2 — Create & activate a virtualenv

<table>
<tr><th>Linux / macOS</th><th>Windows (PowerShell)</th></tr>
<tr><td>

```bash
python3 -m venv .venv
source .venv/bin/activate
```

</td><td>

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

</td></tr>
</table>

> **Windows note:** if PowerShell blocks the activate script, run once:
> `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then re-activate.

### 3 — Install

```bash
pip install -e .                 # core (all platforms)
pip install -e ".[dev]"          # + pytest + ruff (for development)
```

### 4 — (optional) context compression via headroom

Headroom is optional — the app runs fine without it and degrades gracefully.

| Platform | Command |
|---|---|
| **Linux / macOS** | `pip install -e ".[headroom]"` — prebuilt Rust wheels, installs cleanly |
| **Windows** | `pip install -e ".[headroom]"` then `pip install --only-binary=:all: --no-deps "headroom-ai==0.10.17"` — current versions have no Windows wheel, so we use the last pure-Python release (skips the `litellm` dep, whose long paths break installs without long-path support) |

### 5 — Add your API key

<table>
<tr><th>Linux / macOS</th><th>Windows (PowerShell)</th></tr>
<tr><td>

```bash
cp .env.example .env
```

</td><td>

```powershell
copy .env.example .env
```

</td></tr>
</table>

Then edit `.env` and set `OPENROUTER_API_KEY=sk-or-...`.

---

## Quick Start

Launch the interactive TUI (works the same on every OS once the venv is active):

```bash
writing-agent          # or:  python book.py
```

Then drive it from the `❧` prompt:

```
❧ deepseek-v4-flash ›  new --abstract "How stoicism applies to modern burnout"
❧ deepseek-v4-flash ›  run
❧ deepseek-v4-flash ›  export
❧ deepseek-v4-flash ›  read --manuscript
```

Or one-shot from the terminal:

```bash
python book.py new --abstract "The psychology of decision fatigue" --pick 1
python book.py run
python book.py export --format pdf
```

The TUI shows a **live dashboard** while writing (progress, current stage, elapsed time, live token count), **tab-autocompletes** commands and arguments, and remembers history across sessions. Add `--plain` (or set `NO_COLOR`) for unstyled output.

### Try it offline first — no API key (fake mode)

Every node returns deterministic placeholder output, so you can verify the full pipeline, state machine, and exports without a key or any token spend.

<table>
<tr><th>Linux / macOS</th><th>Windows (PowerShell)</th></tr>
<tr><td>

```bash
export BOOK_AGENT_FAKE=1
python book.py new --abstract "test" --pick 1
python book.py run
python book.py export --format pdf
unset BOOK_AGENT_FAKE
```

</td><td>

```powershell
$env:BOOK_AGENT_FAKE = "1"
python book.py new --abstract "test" --pick 1
python book.py run
python book.py export --format pdf
$env:BOOK_AGENT_FAKE = $null
```

</td></tr>
</table>

---

## How It Works

### Article mode

```
topic
  └─▶ 3 editorial angles  (you pick, or --pick N)
        └─▶ outline  (4–8 sections)
              └─▶ per section ──────────────────────────────────────────────┐
                    web research  →  write  →  critique  →  revise (×N)    │
                    →  humanise  →  commit                                  │
              └─▶ assemble manuscript  →  learn skills  →  done ◀──────────┘
```

Output: `brain/users/<user>/articles/<id>/manuscript.md` + `images/`

### Book mode

```
abstract
  └─▶ 3 directions  (you pick, or --pick N)
        └─▶ plan + chapter blueprints  (TOC)
              └─▶ per chapter ─────────────────────────────────────────────┐
                    context slice + skills  →  write  →  critique          │
                    →  revise (×N)  →  humanise  →  commit                 │
              └─▶ periodic consolidation  (contradiction audit)            │
              └─▶ production  (front/back matter, assembly)                │
              └─▶ learn skills  →  done ◀──────────────────────────────────┘
```

Output: `brain/users/<user>/books/<id>/manuscript.md` + front/back matter

### Self-correction loop

Every drafted section/chapter goes through:

```
Draft  →  Critic (approve | revise | escalate)
              │
         revise ──▶ up to max_revisions (default 2)
              │
         cap reached ──▶ escalate to human (pending_review = true)
              │
         approved ──▶ Humanizer ──▶ commit
```

---

## Commands

### Modes

| Command | Effect |
|---|---|
| `/mode article` | Write a long-form article — sections, angles, citations |
| `/mode book` | Write a full book — chapters, canon, consolidation (default) |

### Core commands

| Command | What it does |
|---|---|
| `new --abstract "..."` | Start a project — picks angles/directions, builds outline/TOC |
| `run` | Drive the pipeline: draft → critique → humanise → commit |
| `status` | Show phase, section/chapter progress, pending escalations |
| `review --chapter N --instruction "..."` | Answer an escalation; `run` resumes from that point |
| `read [--chapter N] [--summary] [--manuscript]` | Read any section, summary, or the full manuscript |
| `export [--format <fmt>]` | Export (interactive picker if format omitted) |
| `memory` | Inspect canon — characters, timeline, entity graph |
| `skills` | Browse learned craft skills and efficacy scores |
| `list` | All projects with type and phase |
| `delete [--yes]` | Permanently delete a project |
| `consolidate` · `produce` | Continuity audit · front/back matter on demand |

### Slash commands

| Slash | What it does |
|---|---|
| `/update [description]` | Describe your changes — AI reviews and advises on next steps |
| `/mode [book\|article]` | Show or set writing mode |
| `/use <project>` | Set active project (no `--book-id` needed on follow-up commands) |
| `/books` · `/list` | List all projects with type and phase |
| `/model [agent] <slug>` | Switch any agent to any OpenRouter model slug |
| `/set <key> <value>` | Toggle any setting live (`use_researcher`, `humanize`, `autonomous` …) |
| `/skills` · `/skill <name>` · `/seed-skills` | Browse / view / install built-in craft skills |
| `/retry` · `/reset` · `/compact` | Retry last response · clear memory · compress history |
| `/help` · `/clear` · `/exit` | Full slash list · clear screen · quit |

---

## Export Formats

```bash
export --format pdf      # paginated A5 PDF  (via xhtml2pdf)
export --format epub     # EPUB with NCX/Nav TOC  (via ebooklib)
export --format docx     # Word document  (via pandoc — must be on PATH)
export --format html     # self-contained HTML with embedded CSS
export --format txt      # clean plain text (Markdown stripped)
export --format md       # raw Markdown with title header
```

Just type `export` for an interactive picker.

---

## Features

| Feature | Setting | Default |
|---|---|:---:|
| Web research per section (DuckDuckGo) | `use_researcher` | ✅ on |
| Humanizer — strips AI tells | `humanize` | ✅ on |
| Headroom context compression | `use_headroom` | ✅ on |
| SVG diagram generation (per section) | `use_images` | ✅ on |
| Semantic skill retrieval (embeddings) | `use_embeddings` | off |
| Fully autonomous (no pauses) | `autonomous` | off |
| Per-request network timeout (seconds) | `request_timeout` | 60 |

Toggle any feature live in the TUI: `/set use_researcher false`

**Reliability:** every LLM call retries transient errors (429/5xx/timeouts) with exponential backoff and a request timeout, and fails fast on auth/bad-request. Run state is written atomically and is **resumable** — a crash mid-run never double-commits a chapter or corrupts the project. Token usage is reported at the end of each run.

---

## Writing Quality Guardrails

Hard rules baked into **every** writer, humaniser, and critic prompt — not optional:

**No AI slop** — 24 explicit bans:
- Verbs: `delve`, `leverage`, `utilize`, `foster`, `elevate`, `transform`, `unlock`
- Adjectives: `robust`, `pivotal`, `comprehensive`, `nuanced`, `groundbreaking`
- Transitions: `furthermore`, `moreover`, `in conclusion`, `it's worth noting`
- Structure: no em-dashes, no scare quotes, no bullet-point padding

**No fabrications** — no invented stats, quotes, or attributions

**Humanizer pass** — 11 specific rewrite rules applied after every commit:
removes inflated significance, symbolic language, weak construction verbs, synonym cycling, filler openers, AI transition phrases; varies sentence rhythm

**Critic blocks on slop** — the critic returns `revise` (not `approve`) if any banned pattern appears, forcing a rewrite before commit

---

## Context Compression (Headroom)

[Headroom](https://github.com/chopratejas/headroom) is installed automatically and runs by default on every LLM call.

```
Tool outputs, research results, skill context, conversation history
  ↓
headroom (CacheAligner → ContentRouter → SmartCrusher / CodeCompressor)
  ↓
LLM  (60–95% fewer tokens — same answers)
```

Disable if needed: `/set use_headroom false`

---

## SVG Diagrams

When `use_images` is on, every section/chapter gets a generated diagram saved to `images/` and embedded in the manuscript.

- **860 × 520 px** canvas, publication-quality
- Flowcharts, concept maps, timelines, comparison tables, process loops
- Accent palette: `#4f8ef7` (blue) · `#34c98a` (green) · `#ff6719` (orange) · `#a78bfa` (purple)
- Arrowhead markers, labelled nodes with actual topic concepts — not placeholders
- Routed to DeepSeek Flash (not the reasoning model) so all tokens go to SVG output

---

## Architecture

```
brain/users/<user>/
  profile.md  prefs/  skills/
  books/<book-id>/
    plan.json  book_plan.md  toc.json  run_state.json  manuscript.md
    chapters/  eval/  reviews/  instructions/
    canon/characters/  world_rules.md  timeline.md
    frontmatter/  backmatter/  consolidation/
  articles/<article-id>/
    outline.json  run_state.json  manuscript.md  sources.json
    images/                         ← SVG diagrams

config/
  models.yaml                       ← per-agent model routing
  settings.yaml                     ← all tunable knobs

seeds/skills/                       ← 9 built-in craft skills
src/book_agent/
  llm.py          ← OpenRouter wrapper + headroom compression
  nodes.py        ← all LLM node functions (planner, writer, critic, …)
  orchestrator.py ← durable on-disk state machine
  brain.py        ← BookPaths, ArticlePaths, IO helpers
  shell.py        ← Rich TUI + prompt_toolkit REPL
  cli.py          ← one-shot CLI entry points
  prompts.py      ← all system prompts (NO_SLOP, DIAGRAM_SYS, …)
  export.py       ← pdf, epub, html, docx, txt, md renderers (HTML sanitized)
  ui.py           ← shared palette + Rich helpers (stepper, bars, console)
  concurrency.py  ← thread-pool helper for overlapping independent I/O
  cache.py        ← on-disk cache for web search + SVG diagrams
```

### Model routing

| Node | Model | Why |
|---|---|---|
| planner, writer, consolidation | DeepSeek V4 Pro | Highest prose quality |
| critic, summarizer, humanizer, researcher, toc, chat, diagram | DeepSeek V4 Flash | Fast, cost-efficient, no reasoning overhead |

Override any node live: `/model writer openai/gpt-4o`

---

## Offline / Fake Mode

Test the full pipeline without any API calls:

```bash
# PowerShell
$env:BOOK_AGENT_FAKE=1; python book.py new --abstract "test" --pick 1; python book.py run
```

Every node returns valid placeholder output — lets you verify the pipeline loop, state machine, and exports locally.

---

## Design Decisions

| Decision | What we chose | Why |
|---|---|---|
| Orchestration | Durable on-disk state machine | Brain on disk = checkpoint; resumable runs without LangGraph overhead |
| Skill retrieval | Lexical (BM25) by default | No dependency on embeddings; clean seam to swap in `use_embeddings: true` |
| Article layout | Flat `articles/<id>/` | No subdirs; `manuscript.md` + `images/` only after cleanup |
| Compression | headroom-ai on by default | 60–95% fewer tokens with zero accuracy loss |
| Diagram model | Flash (not Pro/reasoning) | Reasoning tokens don't produce SVG; Flash puts all budget into output |

---

## Platform support

WRITING AGENT is **cross-platform** — Linux, macOS, and Windows — and CI runs the full
test suite on all three (Ubuntu · macOS · Windows) across Python 3.10–3.13 on every push.

| Concern | How it stays portable |
|---|---|
| Filesystem | `pathlib` everywhere; atomic writes via `os.replace`; ids validated/confined |
| Console | Rich auto-detects the terminal and degrades; `--plain` / `NO_COLOR` for no styling; UTF-8 is forced on legacy Windows code pages |
| Export links | clickable `file://` URIs built with `Path.as_uri()` (valid on Windows too) |
| Compression | `headroom` is an optional extra with a platform marker — real wheels on Linux/macOS, the pure-Python fallback on Windows |
| External tools | `pandoc` is only needed for **DOCX** export (install separately and put on `PATH`); a clear error is shown if it's missing. All other formats are pure-Python. |

Per-OS install, activation, and offline-demo commands are in [Setup](#setup) and [Quick Start](#quick-start) above.

---

## Troubleshooting

- **PowerShell won't run the activate script** → `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then re-activate.
- **`headroom-ai` fails to build on Windows** → that's expected; install the pure-Python fallback: `pip install --only-binary=:all: --no-deps "headroom-ai==0.10.17"`. Headroom is optional and the app runs without it.
- **`export --format docx` fails** → install [pandoc](https://pandoc.org/installing.html) and ensure it's on your `PATH`. Other formats (pdf/epub/html/txt/md) need no external tools.
- **Garbled box-drawing / colors** → run with `--plain` or set `NO_COLOR=1`; on Windows use Windows Terminal for best results.
- **`401 Unauthorized` on a real run** → check `OPENROUTER_API_KEY` in `.env`. To verify everything else without a key, use [fake mode](#try-it-offline-first--no-api-key-fake-mode).
- **A run was interrupted** → just run again; state is written atomically and resumes where it left off (no double-committed chapters).

---

## Contributing

Contributions welcome — see **[CONTRIBUTING.md](CONTRIBUTING.md)** for the full guide.

```bash
git clone https://github.com/vikast908/WritingAgent.git && cd WritingAgent
pip install -e ".[dev]"     # Linux · macOS · Windows
ruff check .                # lint
pytest                      # tests (run fully offline)
```

Full spec in [`plan.md`](plan.md) · session log in [`resume.md`](resume.md) · also see
[`SECURITY.md`](SECURITY.md) and [`CHANGELOG.md`](CHANGELOG.md).

---

<div align="center">
  <sub>Built with DeepSeek V4 on OpenRouter · Context compression by <a href="https://github.com/chopratejas/headroom">headroom-ai</a> · Runs on Linux · macOS · Windows</sub>
</div>
