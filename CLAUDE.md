# WRITING AGENT

A self-correcting, autonomous writing system (books, articles, and more). Interactive TUI
(`writing-agent` / `python -m writingagent`) + one-shot CLI, on any OpenAI-compatible model host
(OpenRouter, OpenAI, Anthropic, DeepSeek, Gemini, … — no blessed default). **Cross-platform:
Linux · macOS · Windows** (CI runs the suite on all three × Python 3.10–3.13). Full spec in
`docs/plan.md`; how-to-run in `README.md`.

## Start every session here

1. Read **`docs/dev/resume.md`** - the session log: what happened last time and the next step.
   (maintainer-local, not in the repo; skip if absent)
2. Read **`docs/plan.md`** - the authoritative spec (architecture, memory, nodes, state machine,
   learning, production, model routing, CLI).

## End every session

- Prepend a dated entry to **`docs/dev/resume.md`** (what changed, decisions, concrete next step).
- Put durable decisions in **`docs/plan.md`**; keep `docs/dev/resume.md` as the journal.

## Map of the repo (each thing has ONE home)

- `src/writingagent/` — all code. Entry points: the `writing-agent` console script and
  `python -m writingagent`. There is no launcher script at the repo root.
- `src/writingagent/resources/` — ALL shipped data (models.yaml default routing, seed skills,
  gold corpus, personas). The single source; no repo-root copies exist.
- Runtime state (brain/, .index/, config/*.yaml, .env keys) lives in the **agent home**:
  `$WRITINGAGENT_HOME`, else the OS user-data dir (see `src/writingagent/paths.py`).
  The app never writes into the repo.
- `docs/` — all project docs: `plan.md` (spec), `design.md` (UI system), `prd.md`,
  `learning.md`, `roadmap.md`, `proposals/`, `dev/` (maintainer journals).
- `demo/` — the Gradio Hugging Face Space demo (NOT the package's web dashboard;
  that is `src/writingagent/webui/`).
- `examples/` — real output, including `examples/sample-run/` (a full book run).
- `website/` — the Astro docs site: its OWN nested git repo
  (remote `vikast908/writingagentdocs`, deployed on Vercel), deliberately untracked here.
- `tests/`, `benchmarks/`, `scripts/`, `assets/` — the usual.

## Conventions

- `docs/plan.md` = single source of truth. `docs/dev/resume.md` = running log (with
  `docs/dev/test.md`, the verification log). Don't duplicate between them.
- All numeric thresholds in `docs/plan.md` are **tunable config**, not hard-coded.
- Borrow *patterns* from Hermes/GBrain, not their surface area. This is a narrow writing pipeline.
