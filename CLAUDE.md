# WRITING AGENT

A self-correcting, autonomous writing system (books, articles, and more). Interactive TUI (`writing-agent` / `python writingagent.py`)
+ one-shot CLI, on any OpenAI-compatible model host (OpenRouter, OpenAI, Anthropic, DeepSeek, Gemini, … — no blessed default). **Cross-platform: Linux · macOS · Windows** (CI runs the suite on all three × Python 3.10–3.13). Full spec in `plan.md`; how-to-run in `README.md`.

## Start every session here

1. Read **`docs/dev/resume.md`** - the session log: what happened last time and the next step.
2. Read **`plan.md`** - the authoritative spec (architecture, memory, nodes, state machine,
   learning, production, model routing, CLI).

## End every session

- Prepend a dated entry to **`docs/dev/resume.md`** (what changed, decisions, concrete next step).
- Put durable decisions in **`plan.md`**; keep `docs/dev/resume.md` as the journal.

## Conventions

- `plan.md` = single source of truth. `docs/dev/resume.md` = running log (with `docs/dev/test.md`,
  the verification log). Don't duplicate between them.
- All numeric thresholds in `plan.md` are **tunable config**, not hard-coded.
- Borrow *patterns* from Hermes/GBrain, not their surface area. This is a narrow book pipeline.
