# docs.md — documentation-agent brief (local-only, gitignored)

**Purpose.** This is the working file for the documentation agent ("agentdoc"). On each docs
pass the agent **reviews the ENTIRE repo** and updates the published documentation
(docs-writingagent.vercel.app) so it matches the current code and behavior. This file is the
brief **plus** a running ledger of what changed and still needs documenting. It is gitignored
(a local working doc, not shipped).

---

## How to run a docs pass

1. **Read the ground truth, in this order:**
   - `README.md` (the quick tour) and `CHANGELOG.md` (the `[Unreleased]` section = newest behavior).
   - `plan.md` (the spec / source of truth) — especially §13.1 (TUI interaction & accessibility),
     §15.x (quality/production machinery), §16.5/§16.6 (export paths, references/figures), §19
     (token & cost efficiency).
   - `src/book_agent/config.py` `Settings` (every tunable + its default) and `config/models.yaml`
     (per-node model routing, temperatures, `max_tokens`).
   - `src/book_agent/`: `shell.py` (TUI, commands, slash commands), `cli.py` (commands + flags),
     `orchestrator.py` (pipeline + state machine), `nodes.py` + `prompts.py` (the agents),
     `polish.py`, `diagram.py`, `llm.py`, `api.py` (the public Python API).
2. **Diff** current behavior against the docs site; update any page that has drifted.
3. Keep **examples runnable**; keep the **command / slash / settings / model tables** in sync with
   `cli.py`, `shell.py`, `config.py`, and `models.yaml`.
4. Record what you changed, and anything still pending, in the ledger below.

## Doc-site surface to keep covered

- Quickstart + install (npm `writingagent` launcher · pip `writing-agent`).
- Commands: `write · new · run · status · review · revise · read · versions · brief · tableread ·
  eval · export · polish · memory · skills · list · delete · produce · consolidate`.
- Slash commands: `/help [topic] · /provider · /model · /features · /theme · /path · /auto · /set ·
  /use · /books · /praise · /dashboard · /skill(s) · /user · /config · /update · /reset · /compact`.
- TUI guide: live dashboard (stage + soft ETA + tokens/cost), escalation picker, **live run
  controls (esc/p pause · m manual)**, accessibility (`BOOK_AGENT_A11Y`, `BOOK_AGENT_REDUCED_MOTION`),
  narrow-terminal fallback, 10 themes, the masthead (provider · model · version), no-key warning.
- Quality machinery: thesis, divergent drafts (+ opt-in `divergent_skeletons`), tournament judge,
  claim verification, insight gate, surgical humanizer, references/citations/figures polish,
  diagrams (built-in engine default + the 3-second-glance rule).
- Reference: Settings (`config.py`), model routing (`models.yaml`, incl. `max_tokens`), Python API
  (`Agent`/`Project`), Architecture, Token & cost efficiency (`plan.md` §19).

---

## Ledger — recently changed / pending docs (update every pass; newest on top)

### 2026-06-14
- **v0.2.0** — version single-sourced from `book_agent.__version__` (pyproject derives it).
- **Token/cost efficiency** (`plan.md` §19): cache-hit telemetry in `usage_summary`; lossless schema
  shrink; `use_headroom` default **OFF**; thesis brief to critic/judge; per-node `max_tokens`
  (`models.yaml`); **`divergent_skeletons`** (opt-in, default off); chat history 8.
- **TUI UX overhaul**: no command dead-ends (`help`→`/help`; `\` forces chat), **trust chip**,
  **live run controls** (esc/p pause · m manual), paused card, structured export errors,
  `BOOK_AGENT_A11Y` line-mode, `BOOK_AGENT_REDUCED_MOTION`, narrow-terminal wordmark, proactive
  provider key-warning, **`/help <topic>`**.
- **Reading time is prose-only** (code blocks + the references list excluded).
- **Diagrams**: built-in engine is the default (`diagram_engine: auto`); **3-second-glance rule**.
- **References/citations/figures polish** + the **`polish`** command (`repolish_manuscript`).
- **Multi-provider hosts** via `/provider`; `BOOK_AGENT_PROVIDER` now syncs `settings.provider`.

> Note for the doc site itself: `plan.md` and `resume.md` are now gitignored (local-only), so the
> public repo no longer ships them — don't deep-link to `plan.md` from the README/site; describe the
> design inline or in the docs instead.
