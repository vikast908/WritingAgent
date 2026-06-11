# Contributing to WRITING AGENT

Thanks for your interest! This guide covers local setup, tests, and conventions.

## Development setup

WRITING AGENT runs on **Python 3.10+** and is tested on **Linux, macOS, and Windows**.

```bash
git clone https://github.com/vikast908/WritingAgent.git
cd WritingAgent

python -m venv .venv
source .venv/bin/activate          # macOS / Linux
# .venv\Scripts\activate           # Windows (PowerShell)

pip install -e ".[dev]"            # editable install + pytest + ruff
```

### Optional: context compression (headroom)

Headroom is optional - the app runs fine without it.

- **Linux / macOS:** `pip install -e ".[headroom]"` (prebuilt Rust wheels).
- **Windows:** there is no Windows wheel for current versions; install the last
  pure-Python release without its deps:
  ```powershell
  pip install -e ".[headroom]"
  pip install --only-binary=:all: --no-deps "headroom-ai==0.10.17"
  ```

### API key

```bash
cp .env.example .env               # Windows: copy .env.example .env
# add your OPENROUTER_API_KEY
```

You do **not** need a key to develop or run the tests - see fake mode below.

## Running tests

```bash
pytest
```

The suite runs fully offline. Tests that exercise the pipeline use **fake mode**
(`BOOK_AGENT_FAKE=1`), where every LLM node returns deterministic placeholder
output - no network, no key. You can drive the whole app this way too:

```bash
BOOK_AGENT_FAKE=1 python book.py new --abstract "test" --pick 1
BOOK_AGENT_FAKE=1 python book.py run
```

## Linting & formatting

We use [ruff](https://docs.astral.sh/ruff/):

```bash
ruff check .          # lint
ruff format .         # format
```

A `.pre-commit-config.yaml` is provided - run `pre-commit install` to lint on commit.

## Conventions

- **`plan.md`** is the architecture/spec source of truth; **`resume.md`** is the running
  dev journal (newest entry on top). Durable decisions go in `plan.md`, not `resume.md`.
- Keep nodes deterministic LLM calls - see `plan.md` §4. Don't add agentic behavior.
- Network/IO is best-effort: degrade gracefully, never crash the pipeline on a fetch error.
- All numeric thresholds are tunable config (`config/settings.yaml`), not hard-coded.
- Cross-platform: use `pathlib`, avoid shelling out, and don't assume a POSIX or Windows path
  layout. CI runs the suite on all three OSes - keep it green.

## Submitting changes

1. Branch off `master`.
2. Make the change + add/adjust tests.
3. `ruff check . && pytest` locally.
4. Open a PR describing the change and linking any issue. CI must pass.

## Architecture tour

A 60-second map (full detail in `plan.md` and the README's Architecture section):

- `src/book_agent/orchestrator.py` - durable on-disk state machine (the brain *is* the checkpoint).
- `nodes.py` / `prompts.py` / `schemas.py` - the LLM nodes, their prompts (incl. the
  `wrap_untrusted` injection fence), and structured outputs.
- `llm.py` - OpenRouter wrapper (retry/backoff, timeout, repair, headroom compression,
  run token budget, usage/cost tallies).
- `telemetry.py` - per-call JSONL records + the `/dashboard` aggregation.
- `brain.py` / `store.py` - markdown filesystem layout + SQLite/FTS canon & graph.
- `search.py` / `deep_research.py` / `images.py` / `cache.py` - the optional research stack.
- `shell.py` / `cli.py` / `ui.py` - Rich TUI, one-shot CLI, and the theme registry
  (10 themes: palette + wordmark figlet per theme).
- `export.py` - pdf · epub · html · docx · txt · md renderers.
