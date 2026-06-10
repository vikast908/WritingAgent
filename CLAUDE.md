# WRITING AGENT

A self-correcting, autonomous writing system (books, articles, and more). Interactive TUI (`writing-agent` / `python book.py`)
+ one-shot CLI, on OpenRouter + DeepSeek. **Cross-platform: Linux · macOS · Windows** (CI runs the suite on all three × Python 3.10–3.13). Full spec in `plan.md`; how-to-run in `README.md`.

## Start every session here

1. Read **`resume.md`** — the session log: what happened last time and the next step.
2. Read **`plan.md`** — the authoritative spec (architecture, memory, nodes, state machine,
   learning, production, model routing, CLI).

## End every session

- Prepend a dated entry to **`resume.md`** (what changed, decisions, concrete next step).
- Put durable decisions in **`plan.md`**; keep `resume.md` as the journal.

## Conventions

- `plan.md` = single source of truth. `resume.md` = running log. Don't duplicate between them.
- All numeric thresholds in `plan.md` are **tunable config**, not hard-coded.
- Borrow *patterns* from Hermes/GBrain, not their surface area. This is a narrow book pipeline.
