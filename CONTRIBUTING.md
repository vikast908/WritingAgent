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

### Optional: research & distribution extras

Optional - the app runs fine without them (imported lazily, degrade gracefully).

- **Deep-research fetch backend:** `pip install -e ".[deep]"` (Scrapo + Playwright, Python 3.11+),
  then `python -m playwright install chromium`.
- **Firecrawl search:** set `FIRECRAWL_API_KEY` in `.env` and `search_provider: firecrawl` to swap
  the default DuckDuckGo backend (a missing key falls back to DuckDuckGo).

> The old `[headroom]` context-compression extra has been **removed** - it saved ~nothing on
> single-turn payloads and perturbed the DeepSeek prompt cache. Cost is handled by prompt-cache
> pinning (`openrouter_providers`) and `cost_mode: budget`.

### Dependency lock (optional)

`pyproject.toml` is the canonical dependency declaration; there is no checked-in lock
file. To pin an exact, reproducible set for a deploy, generate one in a **clean venv
installed from public PyPI**:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"                      # add deep,web to lock those extras too
python scripts/gen_lock.py > requirements.lock.txt
```

`scripts/gen_lock.py` resolves the closure of the project's declared dependencies against
the installed environment (so an unrelated package in the venv can't pollute the lock).
Don't commit a lock generated in a non-clean environment - the pins are only as resolvable
as the environment they're read from.

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
(`WRITINGAGENT_FAKE=1`), where every LLM node returns deterministic placeholder
output - no network, no key. You can drive the whole app this way too:

```bash
WRITINGAGENT_FAKE=1 python writingagent.py new --abstract "test" --pick 1
WRITINGAGENT_FAKE=1 python writingagent.py run
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
- Keep nodes as deterministic, single-purpose LLM calls - see `plan.md` §4. (Self-directing
  behavior is the **opt-in** agentic controller in `agentic/` (`plan.md` §21), a separate layer -
  don't bake it into a node.)
- Network/IO is best-effort: degrade gracefully, never crash the pipeline on a fetch error.
- All numeric thresholds are tunable config (`config/settings.yaml`), not hard-coded.
- **Editorial design system:** the web dashboard and the TUI both follow `design.md` (repo root) -
  ink on warm paper, one accent (manuscript red `#a3341f`), the Fraunces display serif, WCAG-AA
  verified. Every value is a token: port to CSS vars for the web app or to a `ui.THEMES` palette for
  the TUI (default `editorial`, "ink & brass"). Named themes recolor, never restructure - match
  `design.md` rather than hand-picking colors.
- Cross-platform: use `pathlib`, avoid shelling out, and don't assume a POSIX or Windows path
  layout. CI runs the suite on all three OSes - keep it green.

## Submitting changes

1. Branch off `master`.
2. Make the change + add/adjust tests.
3. `ruff check . && pytest` locally.
4. Open a PR describing the change and linking any issue. CI must pass.

## Architecture tour

A 60-second map (full detail in `plan.md` and the README's Architecture section):

- `src/writingagent/orchestrator/` - durable on-disk state machine (the brain *is* the checkpoint);
  a package (`common`/`book`/`article`/`review`/`export`/`manage`). `agentic/` is the opt-in
  self-directing controller layered over it (`plan.md` §21).
- `nodes.py` / `prompts.py` / `schemas.py` - the LLM nodes, their prompts (incl. the
  `wrap_untrusted` injection fence), and structured outputs.
- `llm.py` - OpenRouter wrapper (retry/backoff, timeout, repair, run token budget, usage/cost
  tallies; `cost_mode: budget` routes the judgment nodes to the flash tier).
- `telemetry.py` - per-call JSONL records + the `/dashboard` aggregation (per-node / per-unit cost
  attribution behind the web Telemetry / Cost views).
- `brain.py` / `store.py` - markdown filesystem layout + SQLite/FTS canon & graph.
- `search.py` / `deep_research.py` / `images.py` / `cache.py` - the optional research stack
  (`search_provider`: DuckDuckGo default, Firecrawl opt-in via `FIRECRAWL_API_KEY`).
- `seo.py` / `promote.py` - the local distribution layer: a deterministic on-page SEO audit +
  keyword pack, and platform variants / headline variants / restyle. **Local artifacts only** -
  neither posts or schedules anything.
- `webui/` - the local web dashboard (`server.py`: stdlib `ThreadingHTTPServer` + SSE, `static/`:
  the single-page app). `writing-agent web` serves it on `127.0.0.1` only, no auth, one job at a
  time; no build step and no npm dependency. It calls the same engine facade as the TUI/CLI.
- `registers.py` / `craft.py` / `exemplars.py` / `surgery.py` / `fields.py` - the craft engine:
  genre/register profiles, deterministic craft metrics, few-shot exemplars, surgical
  show-don't-tell / passive passes, and structural templates (`plan.md` §22).
- `compositor.py` / `personas.py` (+ `personas/*.md`) / `emotions.py` - the layer cascade that
  selects one voice from register ⊃ field ⊃ persona ⊃ emotion ⊃ skills: selectable personas
  (manner) and anti-cliché emotion deny-lists (`plan.md` §23).
- `gold/*.md` - the per-register genre style corpus (the default "match this" voice exemplar).
  The gold/persona corpora and the register profiles are **tunable data**, not hard-code.
- `shell/` / `cli/` / `ui.py` - Rich TUI, one-shot CLI (both packages), and the theme registry
  (11 themes: palette + wordmark figlet per theme).
- `export.py` - pdf · epub · html · docx · txt · md renderers.
