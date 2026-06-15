<div align="center">

<img src="assets/writing-agent-banner.svg" alt="Writing Agent - a self-correcting, autonomous writing system that turns a topic into a publication-ready manuscript" width="860">

[![Docs](https://img.shields.io/badge/docs-docs--writingagent.vercel.app-6f9ed9?style=flat-square)](https://docs-writingagent.vercel.app/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square)](https://www.python.org/)
[![Platforms](https://img.shields.io/badge/Linux%20%C2%B7%20macOS%20%C2%B7%20Windows-informational?style=flat-square)](#install)
[![License](https://img.shields.io/badge/license-MIT-lightgrey?style=flat-square)](LICENSE)

### The autonomous long-form writer that argues a thesis and cites real sources — not slop.

**One command → a researched, self-critiqued, fact-checked, exported article (or book).** Local-first, on your own model key, for cents.

#### ▶ Try it in your browser — no install, no key
A **[web demo](web/)** runs the whole pipeline behind a simple UI: a **free preview** (placeholder output, $0, no key) shows exactly how a run works, or paste your own key for a real piece. Run it with `pip install -e ".[web]" && python web/app.py`, or deploy it as a Hugging Face Space ([guide](web/README.md)).

[Try in browser](web/) · [Quickstart](#quickstart) · [Install](#install) · [Why not just prompt ChatGPT?](#why-not-just-prompt-chatgpt) · [Examples](examples/) · [**Docs ↗**](https://docs-writingagent.vercel.app/)

</div>

---

## What it does

Most AI writing is **fluent slop** — confident, generic, samey, often unsourced. Writing Agent's bet
is the opposite: from one topic it produces a **long-form piece that takes a defensible position and
backs it with real, ranked sources** — then proves it with an **evidence report**. It's a
**pipeline, not a prompt**: a durable state machine with a *separate critic*, a *thesis* it enforces,
and *claim↔source verification* — not a single API call.

**Best at articles** (a finished, sourced piece for ~$0.25 in a couple of minutes); it does **books**
too (multi-chapter, with continuity audits + a production layer).

- **One command** — `write` asks a few questions upfront, then researches, writes, self-critiques, fact-checks, humanises, and exports the finished file with zero babysitting
- **Argues, doesn't just cover** — a per-piece *thesis* the critic enforces, a side-by-side *judge* that picks the strongest of N drafts, and **claim↔source verification** that blocks unsupported citations
- **Proof, not vibes** — every article ships an [**evidence report**](#evidence-report-proof-not-vibes): the argument it makes + every source ranked by influence (0–100)
- **Figures that lay themselves out** — the model authors a diagram *spec*; a layout engine places it so labels never overflow
- **Use it your way** — interactive TUI, one-shot CLI, an embeddable Python API, or a global `writingagent` npm launcher
- **Self-directing mode (opt-in)** — an optional LLM *controller* decides per unit whether to gather research or read canon *before* drafting, instead of always drafting first; off by default, with the fixed pipeline as the fallback (see [Self-directing mode](#self-directing-mode-opt-in))
- **Local-first** — everything is plain markdown + JSON on disk; your own OpenRouter/DeepSeek key; kill a run and it resumes exactly where it stopped; a global `fallback` model keeps an unattended run alive if a tier has an outage

> 📂 See real output in [**`examples/`**](examples/) · 📚 full manual at [docs-writingagent.vercel.app](https://docs-writingagent.vercel.app/).

## Why not just prompt ChatGPT?

For a quick paragraph, do. For something you'd **put your name on**, the gap is the point:

| | Prompting ChatGPT/Claude | Writing Agent |
|---|---|---|
| **Effort** | prompt → paste → reprompt → edit → format | one command → finished, exported file |
| **Point of view** | whatever the model defaults to | a contestable **thesis** the critic enforces every section |
| **Sources** | often missing or fabricated | researched, and **each cited claim verified against its source** |
| **Slop** | up to you to catch | a surgical **humanizer** + a critic that blocks AI tells |
| **Proof** | none | an **evidence report** (thesis + influence-ranked sources) |
| **Your data / cost** | in someone's cloud | local markdown on disk; your key; cents per piece; resumable |

It won't replace a conversation when you want to *steer every sentence*. It replaces the *grind* of
turning a topic into a sourced, non-generic, finished long-form piece.

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
WRITINGAGENT_FAKE=1 writingagent new --abstract "test" --pick 1 && writingagent run
```

<sub>Windows PowerShell: <code>$env:WRITINGAGENT_FAKE=1; writingagent new --abstract "test" --pick 1; writingagent run</code></sub>

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

**Prefer a browser?** A zero-install **web demo** (`web/app.py`) runs the whole pipeline behind a
Gradio UI — try it free in fake mode with no key, or paste your own key for a real run. Run it with
`pip install -e ".[web]" && python web/app.py`, or deploy it as a Hugging Face Space (see
[`web/README.md`](web/README.md)).

With npm, `setup` is optional — the first run of `writingagent` offers to install the engine for
you. Later, **`writingagent update`** pulls the latest engine. Optional extras (context compression,
deep research, DOCX export, D2 diagrams, embeddings) each degrade gracefully — see the
[**installation guide ↗**](https://docs-writingagent.vercel.app/installation/).

---

## How it makes good writing (not slop)

Every chapter/section runs a **write → critique → revise → humanise → commit** loop that optimizes
for a *take*, not just the absence of tells:

- a contestable **thesis** the critic enforces, and a **side-by-side judge** that picks the strongest of N divergent drafts
- **claim↔source verification** — a cited claim the source doesn't support is blocking
- **clean prose, sourced at the end** — inline `[N]` markers are stripped from the body and every source rolls up into one **References list ranked by how much it actually shaped the piece** (cite count + title relevance, scored 0–100, dated), and **scored for credibility** — a deterministic source-authority check demotes SEO/template padding and promotes gov/standards/primary sources, so citation *quality* counts, not just quantity
- a **surgical humanizer** that rewrites only the sentences with AI tells (citations and numbers preserved)
- it **learns which craft moves actually work** — after each piece it distills reusable "skills", and with `skill_duels` on it *A/B-tests* them (drafts one version with a skill held out, lets the critic compare) so trust is earned by cause-and-effect, not guesswork. This is accumulating memory, not model retraining.
- figures that **lay themselves out** — the model authors a spec; a deterministic engine places it (no overflow, no overlap):

<div align="center">

<img src="assets/diagram-pipeline.svg" alt="The diagram pipeline: a heading and context go to the diagram node, which authors a DiagramSpec; the spec is laid out by the built-in engine or D2+ELK into a self-contained SVG, with the spec saved for auditing." width="820">

<sub><i>↑ this figure was drawn by the system itself — the same engine that figures your books and articles</i></sub>

</div>

Already generated a piece? **`writingagent polish <id>`** re-runs the references, citation, and figure
cleanup and re-exports — with **no model call** (≈0 tokens).

Deep dives: [Quality machinery ↗](https://docs-writingagent.vercel.app/reference/quality/) ·
[How it works ↗](https://docs-writingagent.vercel.app/concepts/how-it-works/) ·
[Architecture ↗](https://docs-writingagent.vercel.app/concepts/architecture/)

---

## Self-directing mode (opt-in)

By default the pipeline is fixed: every unit drafts immediately. **Agentic mode** is an optional layer
that puts an LLM *controller* in charge of each unit — before drafting, it can choose to **gather more
research** or **read the canon** first, then draft. It's **off by default** and the fixed pipeline is
always the fallback, so nothing changes unless you ask for it. Crucially, the `draft` step is the
*same* episode the system already learns from, so turning this on doesn't touch the self-improving
skill-learning loop.

Three policies: `default` (identical to the fixed pipeline), `llm` (a ReAct controller call per unit),
and `trace` (a learned-policy seam for the future). Every controller decision is appended to an
`agent_trace.jsonl` you can inspect.

```bash
/agentic on        # turn it on (uses the llm policy) and flip the active project live
/agentic llm       # explicitly pick the llm controller
/agentic default   # behave exactly like the fixed pipeline
/agentic off       # back to the fixed pipeline
/trace             # print the active project's agent_trace.jsonl (the controller's decisions)
```

From the Python API: `Agent(agentic=True, agentic_policy="llm")` opts in; flip an existing project with
`orchestrator.apply_controller`. Tunables live in `config/settings.yaml` (`agentic`,
`agentic_policy`, `agentic_controller_model`, `agentic_max_unit_steps`, `agentic_factcheck_panel`) and
can be set with `/set <field> <value>`. It's an advanced mode — the fixed pipeline remains the
recommended default for most runs.

---

## Evidence report: proof, not vibes

Every article ships an **`evidence_report.md`** — the receipts behind "argues a thesis, cites real
sources." It's generated deterministically from the finished piece (no model call), so it's cheap and
trustworthy:

```markdown
# Evidence report — Your Voice Assistant's 100ms Problem

## The argument it makes
> Real-time voice AI at sub-100ms is impossible without streaming partial responses and
> decoupling LLM inference from audio generation, rendering sequential pipelines obsolete.

## At a glance
- **46** sources behind the piece
- **13** high-influence (score ≥ 50)
- **31/46** from high-authority domains (gov · standards · primary research · established outlets)
- **71/100** average source authority
- **27/46** carry a date

## Sources, ranked by influence (0–100)
1. **100** · 2026 · [LLM Inference Optimization: Quantization to Speculative Decoding](…)
2. **86**  · 2026 · [LLM Inference Optimization: KV Cache, and Serving at Scale](…)
…
```

Regenerate any time with **`writingagent evidence <id>`** (or `Project.evidence_report()`).

---

## Architecture

A **multi-agent pipeline on a durable state machine**, in layers from the surface down to the
models. Your interface (TUI · CLI · npm · API) drives the **orchestrator**, which runs each unit
through the **agents** — Writer → Critic → Judge → Humanizer — persists to the **markdown brain**
(canon · skills · versions), and feeds the **Learner** so the next piece is better. Every agent
routes to its own model tier on OpenRouter.

<div align="center">

<img src="assets/architecture.svg" alt="Layered architecture and multi-agent workflow: an interface layer (TUI, CLI, npm, API) sends commands to an orchestration layer (the state machine running write→critique→revise→commit); the orchestrator routes every call to the models layer (OpenRouter/DeepSeek) and drives the agents layer, where Writer → Critic → Judge → Humanizer run the per-unit workflow; results commit to the memory layer (the markdown brain of canon, skills, and versions), which feeds the Learner that returns new skills to the orchestrator." width="900">

<sub><i>↑ the layered pipeline, kept compact so it stays legible — see [Architecture ↗](https://docs-writingagent.vercel.app/concepts/architecture/) for the full picture</i></sub>

</div>

---

## Documentation

Everything beyond this tour lives at **[docs-writingagent.vercel.app](https://docs-writingagent.vercel.app/)**:

| | |
|---|---|
| [Quickstart ↗](https://docs-writingagent.vercel.app/quickstart/) | from install to a finished article in one command |
| [The TUI ↗](https://docs-writingagent.vercel.app/guides/tui/) | the interactive shell, live dashboard, 11 themes |
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
