# Writing Agent — Product Requirements Document

> **Status:** living doc · **Type:** open-source project (success = installs, activation,
> retention, contributors, word-of-mouth — not revenue) · **Owner:** @vikast908
> Companion docs: `README.md` (the pitch), `plan.md` (the engineering spec), `CHANGELOG.md`.

## 1. One-line product definition (the spearhead)

**The autonomous long-form writer that argues a thesis and cites real sources — not slop.**
You give it a topic; it researches, drafts, critiques itself, verifies its citations, strips AI
tells, and hands you a finished, exported article (or book) — local-first, on your own model key,
for cents.

Lead with **articles** (fast, cheap, shareable, large audience); books are the "it also does that."

## 2. The problem

Generic AI writing is **fluent slop**: confident, samey, structurally identical, often unsourced or
fabricated. For people who *publish* long-form, that's not a finished product — it's a first draft
they must fact-check, de-cliché, and give a point of view. The pain is **frequent** (every piece),
**real** (reputation + time), and **rising** (readers increasingly recognize and discount AI prose).

The unmet need: **"draft me something publication-ready that has a defensible take and real
sources, without me babysitting the model."**

## 3. Target users

| Persona | Who | Why it's (near) must-have | Notes |
|---|---|---|---|
| **P1 — Burned technical long-form creator** | DevRel, technical-content writers, indie hackers, solo founders/consultants who publish explainers + thought-leadership *regularly* | Sick of slop; values a *take*; comfortable in a terminal + an API key; doesn't blink at ~$0.25/article | **The bullseye.** |
| **P2 — Developer-integrator** | Builds a product/pipeline and embeds generation via the `Agent`/`Project` Python API | Stable, scriptable, local-first generation primitive | Smallest, stickiest. |
| **P3 — Technical novelist / self-publisher** | Drafts books with canon/continuity tracking | Continuity audits + production layer | Smaller, taste-driven; book quality least-proven. |

### Non-users / poor fit (say so explicitly)
- **Non-technical writers** wanting a polished web GUI — the terminal + API-key + Python/Node setup is a wall.
- **Teams** needing collaboration, review queues, shared accounts (single-user, local-first).
- **Short-form** needs — tweets, emails, ad copy, SEO snippets (Jasper/Copy.ai own this; the pipeline is overkill).
- **Hosted-SaaS / compliance** seekers (no hosted option, SSO, SOC2).
- **Sentence-level co-writers** who want to steer every line (this is autonomous-first).

## 4. Jobs To Be Done & top use cases

**Core JTBD:** *"Turn a topic into a publication-ready, non-generic, sourced long-form piece I'd be
willing to put my name on — in one command, without supervising it."*

Top use cases (highest value first):
1. **Technical blog post / explainer** with real citations and diagrams. *(Primary wedge.)*
2. **Thought-leadership / opinion article** that takes a contestable position.
3. **Embed generation** in another app via the Python API.
4. **Book / novel draft** with continuity + front/back matter.
5. **Re-fix an existing piece** for free (`polish`) — clean references, citations, figures.

Essential actions: `write` (one-shot) / `new → run → export`; the live dashboard; `evidence`.
Optional/power: themes, `revise`, `tableread`, `eval`, `praise`, model routing, deep research.

## 5. Value proposition & differentiation

**Core value:** not "AI writes," but **"AI writes something with a point of view and real evidence,
and self-corrects until it isn't slop"** — and you own the data and the spend.

| Differentiator | What it is | Who else has it |
|---|---|---|
| **Anti-slop machinery** | Per-piece *thesis* the critic enforces, a side-by-side *judge*, an *insight gate*, a surgical *humanizer* | Rare — ChatGPT/Claude don't self-critique; Jasper/Sudowrite don't enforce a thesis; STORM is neutral/encyclopedic |
| **Self-directing *and* self-improving** | Opt-in **agentic controller** (plan §21): instead of a fixed order, an agent *chooses its next move* — gather research / read canon / draft / re-outline / revise / consolidate / repair / table-read / produce / learn / escalate — and the writer can call tools (research, canon lookup, fact-verify) *mid-draft*. A **learned policy**, distilled from the agent's own action trace, improves the choices with use. The fixed pipeline remains the safety floor (default-off). | Few OSS writers are self-directing; fewer pair it with a self-improving loop *and* a deterministic fallback |
| **Claim↔source verification** | Cited claims checked against the actual source; unsupported = blocking; opt-in **multi-agent panels** (majority-vote fact-check, diverse-lens critique) | Almost no one |
| **Evidence report** | A shareable artifact: thesis + every source ranked by influence (0–100) | Unique |
| **Autonomy → finished file** | One command → researched, written, self-edited, exported, resumable | Few do end-to-end-to-file |
| **Local-first + BYO model** | Plain markdown on disk; your OpenRouter/DeepSeek key; cost guardrails | OSS-aligned; SaaS rivals can't match |

## 6. Scope

**In scope (now):** long-form articles + books; research (shallow + deep); the quality machinery;
6 export formats; diagrams; TUI + CLI + npm launcher + Python API; the markdown brain + learning loop;
an opt-in self-directing (agentic) controller atop the fixed pipeline — a run-level macro-action
controller, in-generation tool use, a learned (trace-distilled) policy, and multi-agent panels, all
default-off and bounded by call-caps + a token budget.

**Out of scope (deliberate):** short-form/marketing copy; real-time collaboration; a hosted SaaS;
a full GUI (revisit only if demand is proven); non-text media.

**Watch (scope risk):** "books + articles + diagrams + themes + API" dilutes the one-line pitch.
Resolution: **lead with articles**; present everything else as secondary.

## 7. Success metrics (open-source)

- **Activation (north star):** install → **first finished piece** conversion. Instrument; expect the
  biggest drop at "get an API key."
- **Try-without-install:** demo runs (Colab/HF Space) per week.
- **Retention:** % of installers who generate ≥3 pieces in 30 days.
- **Virality:** shares of generated artifacts + evidence reports; GitHub stars/forks trend.
- **Contribution:** external PRs; good-first-issues closed.
- **Quality proof:** blind-A/B win-rate vs ChatGPT long-form (target: clearly >50%).
- **Agentic efficacy (when opt-in):** does the self-directing controller *beat its own fixed pipeline*?
  Measure first-pass rate, insight-gate pass rate, and cost/latency for `agentic` runs vs `default`,
  at equal token budget — the agentic mode has to *earn* its caps. Learned-policy uplift only becomes
  measurable once the action-trace corpus is large enough to bite (see roadmap/Next).

## 8. Roadmap

### Now (shipped this session)
- **Self-directing (agentic) controller — opt-in** (`agentic`, plan §21): the system is now optionally
  an *agent that chooses its next move*, not only a fixed pipeline with quality gates. **Off by default**
  (`Settings.agentic`); when off, behavior is byte-identical to the fixed pipeline, which remains the
  agent's fallback. What shipped:
  - **Run-level macro controller** (`agentic/runner.py`, `run_loop`): replaces the hardcoded
    `while phase != done` loop with a policy that picks the next *macro-action* over the whole piece —
    `draft` / `reoutline` / `revise` / `consolidate` / `repair` / `table_read` / `produce` / `learn` /
    `escalate` / `done` — so the agent can re-plan structure, fix the weakest committed unit, audit
    continuity early, or defer to a human.
  - **Three policies behind one seam:** `default` (== the fixed pipeline, the deterministic equivalence
    floor), `llm` (a ReAct controller over a compact state view + tool schemas), `trace` (a learned,
    trace-conditioned policy). Any illegal/parse-failed pick falls back to `default`.
  - **In-generation tool use:** the writer can call `research` / `read_canon` / `verify_fact`
    *mid-draft* (a real OpenAI tool-use loop), bounded by a per-round cap *and* a total-call cap, falling
    back to a plain draft on any provider/tool error.
  - **A learned policy** (`agentic/learn.py`): distilled from the agent's *own* action trace
    (context-conditioned, book vs. article; reward = first-pass + insight). It is **never
    auto-promoted** — the efficacy gate still owns promotion — and it needs run volume before it bites
    (it correctly stays undecided on thin data).
  - **Multi-agent panels:** majority-vote fact-check + diverse-lens critique (opt-in).
  - **Safety by construction:** the `WRITE → CRITIQUE` episode stays atomic (the self-improving loop is
    untouched — agency lives *between* episodes, never inside them); every decision is logged to an
    append-only `agent_trace.jsonl`; the whole thing is bounded by call/action caps + a token budget.
    New `/agentic on|off|llm|default` and `/trace` shell commands, a dashboard controller line, and
    `Agent(agentic=True, agentic_policy="llm")` / `/set agentic true` opt in.

  *Live-validated 2026-06-16: one real OpenRouter run produced a finished article (~$0.15); the writer
  did call tools mid-draft, and the run surfaced tool over-calling — now fixed with a total-call cap.*
  Suite: 433 passed / 2 skipped, ruff clean. *(Advanced mode; the fixed pipeline stays the recommended
  default. Maturity caveat: live validation is a single run and the learned policy is corpus-hungry —
  see Next.)*
- **Resilience + safety hardening** (from an exhaustive code review): a global **`fallback` model**
  (any node whose primary exhausts its retries degrades once onto a cheaper tier rather than killing an
  unattended run); a **context budget** (`max_context_chars`, default 24000) that priority-bounds the
  assembled canon+summaries+excerpts so a long book can't silently overflow the window;
  **crash-safety** (canon is committed to the store *before* the chapter `.md` resume marker, so a
  mid-commit crash re-runs the chapter idempotently instead of skipping it with missing canon); a
  hardened **web demo** (serialized runs + per-visitor key isolation so there's no cross-visitor key /
  billing leak; topic length capped); a **single-source anti-slop lexicon** (`slop.py` — the writer's
  NO_SLOP block and the humanizer are generated from / cross-checked against one module, so they can't
  drift); and **config validation** that clamps out-of-range settings to sane bounds.
- **Learning loop v2 — ablation duels** (`skill_duels`): the system now earns skill-trust by a true
  cause-and-effect A/B test (draft with vs without a skill, critic compares), not a confounded proxy.
  Plus `skill_distill` (de-dup) and a guarded `watch_blocking`. *(Makes "it improves with use" real —
  and honest: memory, not retraining.)*
- **UX audit P1–P3**: first-run onboarding (no-key → set key or try fake mode free), friendly
  recoverable errors, whole-run ETA, a colourblind-safe theme, duel-aware `/skills`.
- **Internals hardened**: book↔article de-duplication + the orchestrator & shell god-modules split into
  packages (behavior-preserving) — lowers contributor friction (no file >~1k lines).
- **`learning.md`** — a layman's guided tour of the whole codebase (onboarding for non-experts).
- Earlier this session: **Evidence report** (`evidence_report.md` + `evidence` command +
  `Project.evidence_report()`), **output-first README**, **`examples/` gallery** + **Colab quickstart**.
- Prior session: token/cost-efficiency pass, TUI UX overhaul, prose read-time, v0.2.0.

### Next (P1 — weeks)
- **Hosted/zero-install demo** (HF Space or rate-limited web) — the single biggest acquisition lever.
- **Blind A/B harness** — 5 prompts, this vs ChatGPT/Claude long-form, blind reads; publish results.
- **Activation instrumentation** — measure install → first-finished-piece.
- **First-run cliff** reduction — *partly shipped* (no-key onboarding + fake-mode nudge); still want a
  60-sec asciinema/GIF.
- **Agentic controller — prove it at scale** (the code is done; what's left is *volume*, not features):
  (a) **live tool-call validation at volume** — many real runs on tool-capable providers, not one, to
  confirm the in-generation loop + caps hold up and that agentic beats `default` at equal budget;
  (b) **a learned-policy trace corpus large enough to bite** — accumulate enough labelled action traces
  that `train_policy` produces a decided, net-positive policy (today it correctly abstains on thin data).

### Later (P2 — only if pull is proven)
- A thin **web UI** or **VS Code extension** to break the terminal ceiling.
- Community: examples-of-the-week, Discord, good-first-issues.
- Book-length coherence hardening (10+ chapters) + public proof.

## 9. Validation plan (assumptions to test BEFORE building more)

1. **Quality claim:** does output beat ChatGPT/Claude long-form on blind reads? → 5-prompt blind A/B
   (**harness shipped:** `benchmarks/blind_ab/` — generate → paste competitor → blind score → tally).
2. **Segment pull:** do 5 DevRel/technical writers call it must-have after one real run? → interviews.
3. **Funnel:** what's install → first-finished-piece conversion, and where do people drop? → telemetry.
4. **Book coherence** at 10+ chapters (the riskiest, least-proven claim). → one long live run, read end-to-end.
5. **Agentic efficacy:** does the opt-in self-directing controller beat its own fixed pipeline at equal
   token budget (first-pass / insight / cost-latency)? → many real `agentic` vs `default` runs at volume
   (today: a single live run validated the loop end-to-end, not its uplift).

## 10. Risks & mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| Terminal-only caps the audience | High | Zero-install demo; later GUI/extension — but only after artifact pull |
| Differentiator is *told*, not *shown* | High | Evidence report (done) + ChatGPT side-by-side + examples gallery |
| Setup/cost friction (key, Python+Node) | Med | Fake mode (done) + clear cost expectation + npm `setup` |
| Book quality unproven | Med | Validate before promoting; lead with articles |
| **Agentic mode adds cost/latency or loops** (extra controller + tool calls; an eager model over-researches) | Med | **Default-off** (opt-in only); per-round + total tool-call caps; a token budget that drops optional polish actions under pressure; the fixed pipeline is the always-legal fallback. *(A live run did surface tool over-calling — caught and capped.)* |
| **Agentic mode unproven at scale** (single live run; learned policy needs corpus volume) | Med | Frame honestly as advanced/opt-in; the deterministic `default` pipeline stays recommended; learned policy never auto-promoted (efficacy gate owns promotion); validate at volume before promoting (roadmap/Next) |
| Scope dilutes the pitch | Med | One-line spearhead; articles first; agentic mode is opt-in, not the headline |

## 11. Verdict (from the product review)

**Solving a real problem? Yes** — for a specific niche (slop fatigue at long-form), narrowed by the
terminal + API-key gate. **The engineering is ahead of the go-to-market.** As an OSS project it will
win a small loyal niche as-is; it spreads only once there's a zero-install try and the output is
*shown* beating ChatGPT. Those two moves — not more features — unlock adoption.

**Keep:** quality machinery, autonomy, local-first, cost guardrails, the API.
**Rework:** positioning → output-first + a sharp one-liner (in progress).
**Add:** demo, examples, the evidence report (done).
**Don't add:** more pipeline surface area yet.

---

### Appendix — competitive landscape

- **ChatGPT / Claude (Projects/Canvas)** — the real default. *Their edge:* zero install, GUI,
  conversational control. *Our edge:* autonomy (one command vs much prompting), the
  thesis/critic/claim-verify anti-slop loop, an opt-in self-directing controller that re-plans / revises /
  audits *and* learns from its own trace (with a deterministic fallback floor), local-first, repeatable,
  cheap.
- **Sudowrite / NovelCrafter** — fiction, polished web UI, subscription. *Our edge:* autonomy, cost,
  local-first, verification, articles too. *Their edge:* UX, fiction tooling, community.
- **Jasper / Copy.ai** — marketing/short-form SaaS. Different segment; not a real competitor.
- **Stanford STORM (OSS)** — the closest analog for researched articles; very popular. *Their edge:*
  hosted demo, mindshare. *Our edge:* a *thesis/stance* (STORM is neutral/encyclopedic), the quality
  machinery, books, export formats, the learning loop, an opt-in self-directing controller, local-first.
- **GPT-Researcher (OSS)** — research reports. *Our edge:* publication-ready prose with a take, not a
  report dump; export + production layer. *Their edge:* simpler pitch, demo, stars.
