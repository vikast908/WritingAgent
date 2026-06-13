<div align="center">

<img src="assets/writing-agent-banner.svg" alt="Writing Agent - a self-correcting, autonomous writing system that turns a topic into a publication-ready manuscript" width="820">

### an autonomous writing studio - books, articles & more

[![CI](https://github.com/vikast908/WritingAgent/actions/workflows/ci.yml/badge.svg)](https://github.com/vikast908/WritingAgent/actions/workflows/ci.yml)
[![Docs](https://img.shields.io/badge/docs-writingagent.vercel.app-6f9ed9?style=flat-square)](https://docs-writingagent.vercel.app/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square)](https://www.python.org/)
[![Platforms](https://img.shields.io/badge/Linux%20%C2%B7%20macOS%20%C2%B7%20Windows-informational?style=flat-square)](#install)
[![License](https://img.shields.io/badge/license-MIT-lightgrey?style=flat-square)](LICENSE)

**self-correcting pipeline · books + articles · 6 export formats · cost guardrails · resumable · local-first**

[Quickstart](#quickstart) · [Install](#install) · [**Documentation ↗**](https://docs-writingagent.vercel.app/) · [Contributing](#contributing)

</div>

---

## What it does

Writing Agent takes a topic and produces a **publication-ready manuscript** — drafting, critiquing,
humanising, and revising in a loop until the work meets quality standards. It's a **pipeline, not a
prompt**: a durable state machine with a separate critic in the loop, not a single API call.

- **Books & articles** — multi-chapter narratives with continuity audits, or long-form pieces with research, citations, and editorial angles
- **One command** — `write` interviews you once upfront, then researches, writes, self-edits, and exports the finished file with zero interruptions
- **Originality, not just slop-absence** — a per-piece thesis the critic enforces, a side-by-side judge that picks the strongest of N drafts, and claim↔source verification that blocks unsupported citations
- **Figures that lay themselves out** — the model authors a diagram *spec*; a layout engine (built-in, or D2 + ELK) places it so labels never overflow or collide
- **Use it your way** — interactive TUI, one-shot CLI, an embeddable Python API, or a global `writingagent` npm launcher
- **Local-first** — everything is plain markdown + JSON on disk; kill a run and it resumes exactly where it stopped

> 📚 **The full manual lives at [docs-writingagent.vercel.app](https://docs-writingagent.vercel.app/).** This README is just the quick tour.

---

## Quickstart

```bash
npm install -g writingagent          # the CLI   (needs Node ≥ 16)
writingagent setup                   # one-time: installs the Python engine (Python 3.10+ & pip)
```

Point it at your [OpenRouter](https://openrouter.ai/) key and give it a topic:

```bash
export OPENROUTER_API_KEY=sk-or-...   # or drop it in a .env in your working directory
writingagent write "How stoicism applies to modern burnout"
```

`write` asks a few questions upfront (audience, depth, tone, must-includes), then runs fully
autonomously and hands you an exported file. Prefer to drive each step? `writingagent new → run →
export` — every command is in the [**command reference ↗**](https://docs-writingagent.vercel.app/reference/commands/).

**Try it with no API key.** *Fake mode* returns deterministic placeholder output, so you can
exercise the whole pipeline and exports for free:

```bash
BOOK_AGENT_FAKE=1 writingagent new --abstract "test" --pick 1 && writingagent run
```

<sub>Windows PowerShell: <code>$env:BOOK_AGENT_FAKE=1; writingagent new --abstract "test" --pick 1; writingagent run</code></sub>

---

## Install

**Requirements:** Node ≥ 16 (for the CLI) · Python 3.10+ with pip (the engine) · Linux / macOS /
Windows · an [OpenRouter API key](https://openrouter.ai/) for real runs (free tier works; none needed for fake mode).

```bash
# npm (recommended)
npm install -g writingagent          # the CLI
writingagent setup                   # installs the Python engine from source; `writingagent doctor` verifies

# …or from source with pip
git clone https://github.com/vikast908/WritingAgent && cd WritingAgent
pip install -e .                     # gives you the `writing-agent` command (hyphen) directly
```

Optional extras (context compression, deep research, DOCX export, D2 diagrams, embeddings) each
degrade gracefully — see the [**installation guide ↗**](https://docs-writingagent.vercel.app/installation/).

---

## How it makes good writing (not slop)

Every chapter/section runs a **write → critique → revise → humanise → commit** loop that optimizes
for a *take*, not just the absence of tells:

- a contestable **thesis** the critic enforces, and a **side-by-side judge** that picks the strongest of N divergent drafts
- **claim↔source verification** — a cited claim the source doesn't support is blocking
- a **surgical humanizer** that rewrites only the sentences with AI tells (citations and numbers preserved)
- figures that **lay themselves out** — the model authors a spec; a deterministic engine places it (no overflow, no overlap):

<div align="center">

<img src="assets/diagram-pipeline.svg" alt="The diagram pipeline: a heading and context go to the diagram node, which authors a DiagramSpec; the spec is laid out by the built-in engine or D2+ELK into a self-contained SVG, with the spec saved for auditing." width="820">

<sub><i>↑ this figure was drawn by the system itself — the same engine that figures your books and articles</i></sub>

</div>

Deep dives: [Quality machinery ↗](https://docs-writingagent.vercel.app/reference/quality/) ·
[How it works ↗](https://docs-writingagent.vercel.app/concepts/how-it-works/) ·
[Architecture ↗](https://docs-writingagent.vercel.app/concepts/architecture/)

---

## Documentation

Everything beyond this tour lives at **[docs-writingagent.vercel.app](https://docs-writingagent.vercel.app/)**:

| | |
|---|---|
| [Quickstart ↗](https://docs-writingagent.vercel.app/quickstart/) | from install to a finished article in one command |
| [The TUI ↗](https://docs-writingagent.vercel.app/guides/tui/) | the interactive shell, live dashboard, 10 themes |
| [Commands ↗](https://docs-writingagent.vercel.app/reference/commands/) · [Slash commands ↗](https://docs-writingagent.vercel.app/reference/slash-commands/) | every command and flag |
| [Quality machinery ↗](https://docs-writingagent.vercel.app/reference/quality/) | thesis, judge, claim checks, the learning loop |
| [Model routing ↗](https://docs-writingagent.vercel.app/reference/models/) · [Settings ↗](https://docs-writingagent.vercel.app/reference/settings/) | per-node models; every tunable |
| [Python API ↗](https://docs-writingagent.vercel.app/project/api/) | embed the engine — `Agent` / `Project` |
| [Architecture ↗](https://docs-writingagent.vercel.app/concepts/architecture/) | the markdown memory substrate + state machine |

---

## Contributing

```bash
git clone https://github.com/vikast908/WritingAgent && cd WritingAgent
pip install -e ".[dev]"
ruff check .        # lint
pytest              # the suite runs fully offline (no API key)
```

Issues and PRs welcome — see **[CONTRIBUTING.md](CONTRIBUTING.md)**. The design spec is in
[`plan.md`](plan.md); also [`SECURITY.md`](SECURITY.md) and [`CHANGELOG.md`](CHANGELOG.md).

## Author

Built and maintained by [**@vikast908**](https://github.com/vikast908). Questions, ideas, or bugs?
[Open an issue](https://github.com/vikast908/WritingAgent/issues) — feedback is welcome.

## License

[MIT](LICENSE).

<div align="center">
  <sub>Built with DeepSeek V4 on OpenRouter · context compression by <a href="https://github.com/chopratejas/headroom">headroom-ai</a> · runs on Linux · macOS · Windows</sub>
</div>
