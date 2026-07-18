<div align="center">

<img src="assets/writing-agent-banner.svg" alt="Writing Agent - a self-correcting, autonomous writing system that turns a topic into a publication-ready manuscript" width="860">

[![Docs](https://img.shields.io/badge/docs-docs--writingagent.vercel.app-6f9ed9?style=flat-square)](https://docs-writingagent.vercel.app/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square)](https://www.python.org/)
[![Platforms](https://img.shields.io/badge/Linux%20%C2%B7%20macOS%20%C2%B7%20Windows-informational?style=flat-square)](https://docs-writingagent.vercel.app/installation/)
[![License](https://img.shields.io/badge/license-MIT-lightgrey?style=flat-square)](LICENSE)

### The autonomous long-form writer that argues a thesis and cites real sources - not slop.

**One command → a researched, self-critiqued, fact-checked, exported article (or book).**
Local-first and **model-agnostic** (any OpenAI-compatible host), on your own key, for cents.

[Quickstart](#try-it-in-30-seconds) · [What you get](#what-you-get) · [Examples](examples/) · [**Docs ↗**](https://docs-writingagent.vercel.app/)

</div>

---

## Why it's different

Most AI writing is fluent slop - confident, generic, unsourced. Writing Agent is a
**pipeline, not a prompt**: a durable state machine with a *separate critic*, an enforced
*thesis*, and *claim↔source verification*. Every article ships an **evidence report** -
the argument it makes plus every source, ranked by influence. It won't replace a chat
when you want to steer every sentence; it replaces the grind of turning a topic into a
sourced, non-generic, finished piece. [How it works ↗](https://docs-writingagent.vercel.app/concepts/how-it-works/)

## Try it in 30 seconds

```bash
pip install writing-agent                # Python 3.10+ · or: pipx install writing-agent
export OPENROUTER_API_KEY=sk-or-...      # or any OpenAI-compatible host's key - your choice
writing-agent write --abstract "How stoicism applies to modern burnout"
```

`write` asks a few questions upfront, then researches, drafts, critiques, verifies,
humanizes, and exports the finished file with zero babysitting.

**No API key?** `WRITINGAGENT_FAKE=1 writing-agent write --abstract "test"` runs the whole
pipeline offline with placeholder output. **No terminal?** The [web demo](demo/) is a
Gradio try-it page you can run from a clone or deploy as a Hugging Face Space.
Extras, from-source installs, and host setup: [installation guide ↗](https://docs-writingagent.vercel.app/installation/).

## What you get

- **Argues, doesn't just cover** - a contestable thesis a separate critic enforces in
  every section, and a side-by-side judge that picks the strongest of N drafts
- **Real sources, verified** - web-grounded research, and each cited claim is checked
  against its source; unsupported citations are blocked, not shipped
- **Proof, not vibes** - the [evidence report](examples/) shows the thesis + every
  source ranked by influence (0-100), built from the finished piece
- **Any field, any voice** - registers (fiction → academic → copy), 46 selectable
  personas, and emotion targets; the craft engine holds up even on cheap models
- **Self-correcting, optionally self-directing** - fixed quality gates by default; an
  opt-in agentic controller that chooses its own next move when you want it
- **Cheap when you want it** - `cost_mode: budget` targets a finished article for
  ~$0.10-0.25 depending on the model
- **Durable** - plain markdown + JSON on disk; kill a run mid-flight and `run` resumes
  exactly where it stopped
- **Ships, not just writes** - 6 export formats (pdf · epub · html · docx · txt · md),
  self-laying-out diagrams, free-licensed or AI-generated images, an on-page SEO audit, a
  promo pack (X thread, LinkedIn, headlines), and one-paste **Copy for Medium / Substack / X**

## Four ways to use it

| Surface | What it is |
|---|---|
| **TUI** - `writing-agent` | The interactive studio: chat in plain English, slash commands, live run view, 11 themes |
| **CLI** - `writing-agent <cmd>` | One-shot commands (`write`, `run`, `export`, `seo`, `promote`, ...) for scripting |
| **Dashboard** - `writing-agent web` | Local control room on `127.0.0.1:8787` - commission runs, live logs, per-agent cost, evals, memory, copy-to-publish |
| **Web demo** - [`demo/`](demo/) | Standalone Gradio page (`:7860`) to try or host - free fake-mode preview, or bring a key |

There's also an embeddable Python API - see [docs ↗](https://docs-writingagent.vercel.app/project/api/).

## See real output

Judge it before you install it: [`examples/`](examples/) has finished articles with
their evidence reports, an A/B pilot against a plain chatbot, and
[`examples/sample-run/`](examples/sample-run/) - a complete autonomous book run with
every working file the agent produced.

## Learn more

Everything else lives in the **[docs ↗](https://docs-writingagent.vercel.app/)**:
[guides](https://docs-writingagent.vercel.app/guides/articles/) (articles, books,
research, exporting), the full [command](https://docs-writingagent.vercel.app/reference/commands/)
and [settings](https://docs-writingagent.vercel.app/reference/settings/) reference,
[model routing](https://docs-writingagent.vercel.app/reference/models/),
[cost & performance](https://docs-writingagent.vercel.app/reference/cost/), and the
[FAQ](https://docs-writingagent.vercel.app/reference/faq/). The engineering spec is
[`docs/plan.md`](docs/plan.md); the UI system is [`docs/design.md`](docs/design.md).

## Contributing

```bash
git clone https://github.com/vikast908/WritingAgent && cd WritingAgent
pip install -e ".[dev]"
ruff check . && pytest        # the suite runs fully offline - no API key
```

Issues and PRs welcome - see [CONTRIBUTING.md](CONTRIBUTING.md), plus
[SECURITY.md](SECURITY.md) and the [CHANGELOG](CHANGELOG.md).

## Author

Built and maintained by [**@vikast908**](https://github.com/vikast908). Questions, ideas,
or bugs? [Open an issue](https://github.com/vikast908/WritingAgent/issues).

## License

[MIT](LICENSE).

<div align="center">
  <sub>Model-agnostic · runs on any OpenAI-compatible host · Linux · macOS · Windows</sub>
</div>
