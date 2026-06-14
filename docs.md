# docs.md — documentation-agent brief

**Purpose.** This is the working file for the documentation agent ("agentdoc"). On each docs
pass the agent **reviews the ENTIRE repo** and updates the published documentation
(docs-writingagent.vercel.app) so it matches the current code and behavior. This file is the
brief **plus** a running ledger of what changed and still needs documenting. It is **tracked in
git** for now (the author syncs `plan.md`, `resume.md`, `learning.md`, and this file across
machines); they move to gitignore only at open-source time.

---

## How to run a docs pass

1. **Read the ground truth, in this order:**
   - `README.md` (the quick tour) and `CHANGELOG.md` (the `[Unreleased]` section = newest behavior).
   - `learning.md` (the plain-English, layman's tour of the whole codebase — good orientation).
   - `plan.md` (the spec / source of truth) — especially §8 (the Learner: skills, watch-list,
     **ablation duels**), §13.1 (TUI interaction & accessibility), §15.x (quality/production),
     §16.5/§16.6 (export paths, references/figures), §19 (token & cost efficiency), §20/§20.1
     (book↔article dedup + the orchestrator/shell **package split**).
   - `src/book_agent/config.py` `Settings` (every tunable + its default) and `config/models.yaml`
     (per-node model routing, temperatures, `max_tokens`).
   - `src/book_agent/` — note the two former god-modules are now **packages** with facades:
     - `shell/` (TUI) — `branding · help · commands · dashboard · chat · dispatch · slash · session
       · repl`, behind `shell/__init__.py`.
     - `orchestrator/` (pipeline + durable state machine) — `common · book · article · export ·
       manage · review`, behind `orchestrator/__init__.py`.
     - plus `cli.py` (commands + flags), `nodes.py` + `prompts.py` (the agents/nodes),
       `skills.py` (the learning loop + duel efficacy), `polish.py`, `diagram.py`, `llm.py`,
       `ui.py` (themes, trust chip, error explainer), `api.py` (the public Python API).
2. **Diff** current behavior against the docs site; update any page that has drifted.
3. Keep **examples runnable**; keep the **command / slash / settings / model tables** in sync with
   `cli.py`, `shell/` (commands, slash, help), `config.py`, and `models.yaml`.
4. Record what you changed, and anything still pending, in the ledger below.

## Doc-site surface to keep covered

- Quickstart + install (npm `writingagent` launcher · pip `writing-agent`) + **fake mode**
  (`BOOK_AGENT_FAKE=1`) to try the whole flow free.
- Commands: `write · new · run · status · review · revise · read · versions · brief · tableread ·
  eval · export · polish · evidence · memory · skills · list · delete · produce · consolidate`.
- Slash commands: `/help [topic] · /provider · /model · /features · /theme · /path · /auto · /set ·
  /use · /books · /praise · /dashboard · /skill(s) · /user · /config · /update · /reset · /compact`.
- TUI guide: live dashboard (stage + soft ETA + **whole-run ETA** + tokens/cost), escalation picker,
  **live run controls (esc/p pause · m manual; all interrupts resumable)**, accessibility
  (`BOOK_AGENT_A11Y`, `BOOK_AGENT_REDUCED_MOTION`), narrow-terminal fallback, **11 themes incl. the
  colourblind-safe `highcontrast`**, the masthead (provider · model · version), no-key warning +
  **first-run onboarding** (set key / try fake mode), **friendly recoverable errors**
  (`ui.explain_error`: bad key / rate-limit / network / locked file).
- Quality machinery: thesis, divergent drafts (+ opt-in `divergent_skeletons`), tournament judge,
  claim verification, insight gate, surgical humanizer, references/citations/figures polish,
  diagrams (built-in engine default + the 3-second-glance rule).
- **Learning loop:** skill library + watch-list; **ablation duels** (`skill_duels`) as the causal
  efficacy signal; `skill_distill` (de-dup); `watch_blocking` (guarded enforcement); `/skills` shows
  the duel win-rate. "It improves with use" = accumulating memory, **not** model retraining.
- Reference: Settings (`config.py`), model routing (`models.yaml`, incl. `max_tokens`), Python API
  (`Agent`/`Project`), Architecture, Token & cost efficiency (`plan.md` §19).

---

## Ledger — recently changed / pending docs (update every pass; newest on top)

### 2026-06-14 (pass 2)
- **Two god-modules split into packages** (behind facades; `orchestrator.X` / `shell.X` unchanged for
  callers): `orchestrator/` (common/book/article/export/manage/review) and `shell/`
  (branding/help/commands/dashboard/chat/dispatch/slash/session/repl). `plan.md` §20.1. Doc-site
  architecture page + any file-path references must be updated to the package layout.
- **Book↔article de-duplication** (`plan.md` §20): shared `_run_learner`, `_base_run_state`,
  `_divergent_first_draft`, `_finalize_unit`, `_mark_escalated`, `_log_run_complete`.
- **Learning loop v2 — ablation duels** (`plan.md` §8). New settings: **`skill_duels`** (causal A/B
  efficacy; off), **`skill_distill`** (de-dup near-duplicate skills; off), **`watch_blocking`**
  (guarded watch-list enforcement; on). `/skills` now shows duel win-rate. Document "improves with
  use = memory, not retraining."
- **UX audit P1–P3:** duel-aware `/skills`; first-run no-key onboarding (+ try-fake-mode nudge);
  new toggles in `/features`; **whole-run ETA** on the dashboard; friendly recoverable errors
  (`ui.explain_error`); **`highcontrast`** colourblind-safe theme (now 11 themes); clearer
  pause/stop wording (all resumable).
- **`learning.md` added** — a layman's guided tour of the whole codebase; link it from the docs site
  as an orientation/onboarding page.

### 2026-06-14 (pass 1)
- **v0.2.0** — version single-sourced from `book_agent.__version__` (pyproject derives it).
- **Token/cost efficiency** (`plan.md` §19): cache-hit telemetry in `usage_summary`; lossless schema
  shrink; `use_headroom` default **OFF**; thesis brief to critic/judge; per-node `max_tokens`
  (`models.yaml`); **`divergent_skeletons`** (opt-in, default off); chat history 8. Also
  **`openrouter_providers`** pin so the DeepSeek prompt-cache engages.
- **TUI UX overhaul**: no command dead-ends (`help`→`/help`; `\` forces chat), **trust chip**,
  **live run controls** (esc/p pause · m manual), paused card, structured export errors,
  `BOOK_AGENT_A11Y` line-mode, `BOOK_AGENT_REDUCED_MOTION`, narrow-terminal wordmark, proactive
  provider key-warning, **`/help <topic>`**.
- **Reading time is prose-only** (code blocks + the references list excluded).
- **Diagrams**: built-in engine is the default (`diagram_engine: auto`); **3-second-glance rule**.
- **References/citations/figures polish** + the **`polish`** command (`repolish_manuscript`).
- **Multi-provider hosts** via `/provider`; `BOOK_AGENT_PROVIDER` now syncs `settings.provider`.

> Note: `plan.md`, `resume.md`, `learning.md`, `docs.md` are currently **tracked** (not gitignored) so
> the author can sync them across machines. They will move to gitignore at open-source time — at that
> point, stop deep-linking `plan.md` from the README/site and describe the design inline / in the docs.
