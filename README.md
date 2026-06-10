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

[![Python](https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square)](https://www.python.org/)
[![OpenRouter](https://img.shields.io/badge/powered%20by-OpenRouter-orange?style=flat-square)](https://openrouter.ai/)
[![DeepSeek](https://img.shields.io/badge/model-DeepSeek%20V4-blueviolet?style=flat-square)](https://deepseek.com/)
[![Headroom](https://img.shields.io/badge/compression-headroom--ai-green?style=flat-square)](https://github.com/chopratejas/headroom)
[![License](https://img.shields.io/badge/license-MIT-lightgrey?style=flat-square)](LICENSE)

**60–95% token savings · self-correcting pipeline · books + articles · 6 export formats · local-first**

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

```bash
# 1 — Clone
git clone https://github.com/vikast908/WritingAgent.git
cd WritingAgent

# 2 — Virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

# 3 — Install
pip install -e .

# 3b — (optional) context compression via headroom
#   headroom is optional and the app runs fine without it. Pin 0.10.17 (the last
#   pure-Python release) and install WITHOUT deps — newer versions are a Rust
#   extension with no Windows wheel, and headroom's `litellm` dep has paths long
#   enough to break installs on Windows without long-path support.
pip install -e ".[headroom]"
pip install --only-binary=:all: --no-deps "headroom-ai==0.10.17"

# 4 — API key
copy .env.example .env          # Windows
# cp .env.example .env          # macOS / Linux
# → add your OPENROUTER_API_KEY inside .env
```

**Requirements:** Python 3.10+ · [OpenRouter API key](https://openrouter.ai/) (free tier works)

---

## Quick Start

```bash
writing-agent          # launch the interactive TUI
```

```
❧ deepseek-v4-pro article ›  new --abstract "How stoicism applies to modern burnout"
❧ deepseek-v4-pro article ›  run
❧ deepseek-v4-pro article ›  export
❧ deepseek-v4-pro article ›  read --manuscript
```

Or one-shot from the terminal:

```bash
python book.py new --abstract "The psychology of decision fatigue" --pick 1
python book.py run
python book.py export --format pdf
```

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

Toggle any feature live in the TUI: `/set use_researcher false`

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
  export.py       ← pdf, epub, html, docx, txt, md renderers
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

## Contributing

```bash
git clone https://github.com/vikast908/WritingAgent.git && cd WritingAgent
pip install -e ".[dev]"
pytest
```

Full spec in [`plan.md`](plan.md) · session log in [`resume.md`](resume.md)

---

<div align="center">
  <sub>Built with DeepSeek V4 on OpenRouter · Context compression by <a href="https://github.com/chopratejas/headroom">headroom-ai</a></sub>
</div>
