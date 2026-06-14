# Learning Guide — Understanding the Writing Agent from Scratch

> **Who this is for:** someone with little or no coding background who wants to *truly understand*
> what this project is, how it works, and why it was built the way it was. No prior knowledge is
> assumed. Every technical word is explained the first time it appears. Read it top to bottom — it's
> written as a story, in the order things actually happen.
>
> (For the precise engineering spec, see `plan.md`. For the running history of changes, see
> `resume.md`. This file is the friendly tour that sits in front of both.)

---

## 1. The one-sentence version

**This software writes long, well-researched articles and books on its own — and, crucially, it
*criticises and corrects its own work* before showing it to you.**

You give it a topic ("How vector databases work", or "a short detective novel set in a print shop").
It thinks up an angle, researches, writes a draft, grades that draft against a quality bar, rewrites
the weak parts, fact-checks its own claims against real sources, removes the tell-tale "this was
written by a robot" phrasing, and finally exports a finished file (PDF, Word, EPUB, web page, etc.).

It does all of this **autonomously** (without you babysitting it) but can also **pause and ask you**
at key moments if you prefer to stay in control.

---

## 2. The mental model: it's a small writing studio, not a single robot

The most important idea in the whole project is this:

> **One AI writing one draft in one shot is mediocre. A *team* of specialised AIs that draft, critique,
> and revise — like a real editorial team — produces far better work.**

So instead of one big "write me an article" command, the project simulates a **studio of specialists**.
Each specialist is a small, focused job handed to an AI model with very specific instructions. Here is
the cast of characters (in the code these are called **nodes** — think "workers" or "stations on an
assembly line"):

| The worker | What it does | Why it exists (the "why") |
|---|---|---|
| **Planner** | Turns your rough idea into a concrete plan: title, premise, angle, audience. | A vague idea produces a vague article. Forcing a sharp plan up front sets the quality ceiling. |
| **Outline / TOC builder** | Breaks the plan into sections (article) or chapters (book). | You can't write 5,000 good words at once; you write good *sections* and stitch them. |
| **Thesis generator** | Writes the single *contestable argument* the piece will make. | Most AI writing just "covers a topic". A real article *argues a point*. This is the project's headline differentiator. |
| **Researcher** | Searches the web (optionally deeply) and gathers facts + sources. | So the writing is grounded in reality, not the model's vague memory. |
| **Writer** | Writes the actual prose for one section/chapter. | The craftsman. Everything else exists to make this output better. |
| **Critic** | Grades the draft: clarity, structure, evidence, insight; flags "blocking" problems. | A writer who never gets edited plateaus. The critic is the in-house editor. |
| **Judge** | When several drafts are written, picks the best one side-by-side. | Choosing the best of several attempts beats polishing one mediocre attempt. |
| **Verifier** | Checks each cited claim against the actual source text. | Stops the AI from "confidently making things up" (the famous *hallucination* problem). |
| **Humanizer** | Rewrites approved prose to strip robotic tells, keeping the meaning. | AI prose has a recognisable smell. This removes it without changing facts. |
| **Summarizer** | Condenses each finished chapter so later chapters stay consistent. | The model can't hold a whole book in its head; summaries are its short-term memory. |
| **Consolidator** | Checks the whole book for contradictions (a character's eyes change colour, etc.). | Long works drift. This catches the drift before publication. |
| **Learner** | After a piece is done, distils reusable "craft skills" from what worked. | The studio gets *better over time* instead of starting from zero every run. |

**Why a team instead of one prompt?** Because quality in writing comes from *iteration and selection*:
draft → critique → revise → choose the best. A single prompt can't critique itself honestly mid-sentence.
Splitting the work into specialists lets each one be given a narrow, expert instruction and lets the
system loop (draft, grade, redo) until a real quality bar is met.

---

## 3. The journey of one article, start to finish (the chronological story)

This is what actually happens, in order, when you ask for a piece. Follow this and you understand 80%
of the system.

1. **You give a topic.** Either by typing in the interactive console, or a one-line command, or the
   Python interface.

2. **A short interview (optional).** The system may ask you a few upfront questions (audience, depth,
   tone) — *all at once*, never nagging you mid-job. This is deliberate: gather everything up front,
   then go quiet and deliver.

3. **Planning.** The Planner proposes a few *angles* (distinct takes on your topic). One is chosen
   (you pick, or it auto-picks in autonomous mode).

4. **Thesis + outline.** The system writes the **thesis** (the one arguable claim) and an **outline**
   of sections. The thesis is then injected into *every* later step so the whole piece pulls in one
   direction instead of wandering.

5. **A durable "save file" is created.** Everything about this run — the plan, outline, thesis, which
   section we're on — is written to disk immediately as plain files (this is the **brain**, explained
   in §5). *Why:* if your laptop dies or you close the program, you lose nothing; re-running picks up
   exactly where it stopped. The program treats the files on disk as the single source of truth.

6. **For each section, in order:**
   - **Fetch inputs** (research, images, relevant past "skills") — and it *pre-fetches the next
     section's inputs while the current one is being written*, to save wall-clock time.
   - **Draft.** Often it writes **several drafts at different "creativity" settings in parallel**
     (called *divergent drafts*), then the **Judge** picks the strongest. *Why:* selecting the best of
     three is more reliable than iterating one.
   - **Critique.** The Critic grades it and lists "blocking" issues (things that *must* be fixed).
   - **Verify claims.** Any factual claim with a citation is checked against the real source text. If a
     source doesn't support the claim, that becomes a blocking issue.
   - **Decide.** If the draft passes the bar → commit it. If not → revise using the critic's notes and
     try again, up to a limit. If it still can't pass and you're in manual mode → it **escalates**
     (pauses and asks you). In autonomous mode it commits the best attempt and moves on.
   - **Commit.** The approved draft is humanised, summarised (for continuity), and saved.

7. **Assemble + polish.** All sections are stitched into one manuscript. A deterministic (non-AI)
   **polish** pass cleans up citations and references, builds a single ordered reference list, and
   removes duplicate figures. *Why non-AI here:* this is mechanical clean-up; using fixed rules makes
   it free, instant, and perfectly repeatable.

8. **Evidence report.** It generates a short report showing the thesis it argued **and every source
   ranked by how much it influenced the piece**. This is the "show your receipts" feature — most AI
   writing can't tell you *why* it said what it said.

9. **Learn.** The Learner looks at what the critic praised/flagged and saves reusable craft lessons
   for next time.

10. **Export.** The finished manuscript is rendered to the formats you want: Markdown, plain text,
    HTML web page, PDF, Word (.docx), EPUB e-book.

A **book** follows the same arc but with chapters instead of sections, plus two extra concerns: a
**canon** (the tracked facts of the story — characters, timeline, world rules) and periodic
**consolidation** checks for contradictions across chapters.

---

## 4. The folder map (the building, room by room)

Here is the whole project laid out. Top level first, then we go into the important rooms.

```
WritingAgent/
├── writingagent.py                ← the "start button" for the command-line version
├── src/writingagent/        ← ALL the actual program lives here (see §4.2)
├── config/                ← settings you can tweak (which AI model, defaults)
├── brain/                 ← the program's MEMORY — everything it produces (see §5)
├── seeds/                 ← starter "craft skills" shipped with the project
├── tests/                 ← ~330 automated checks that prove the code works
├── examples/              ← real finished pieces, so you can judge output before installing
├── benchmarks/            ← a blind A/B kit to compare quality vs other tools
├── SampleRun/             ← a complete sample book (manuscript + its working files)
├── assets/                ← brand images (logo, banner)
├── writingagent/          ← a small Node/npm launcher (alternative way to install/run)
├── README.md              ← the front-door "what is this / how to run" doc
├── plan.md                ← the authoritative engineering spec (the "law")
├── resume.md              ← the running session log ("what changed last time")
├── learning.md            ← THIS file
├── PRD.md, CHANGELOG.md, CONTRIBUTING.md, ...  ← supporting docs
└── pyproject.toml         ← the project's "ingredients list" (dependencies, how to install)
```

**Why is the code under `src/writingagent/` and not just loose in the folder?** This "src layout" is a
standard professional convention: it keeps the *program* cleanly separated from the *project's other
stuff* (tests, docs, data), and prevents a whole class of "it worked on my machine" import bugs.

### 4.1 The two doors in (how you talk to it) and the engine room

The program has a clean separation between **how you interact with it** (the "faces") and **the engine
that does the work**. This separation is the single most important structural idea, so hold onto it:

- **The faces** never contain the writing logic. They just collect your request and show results.
- **The engine** never knows or cares whether the request came from the console, a script, or a web app.

*Why:* you can completely redesign the console without touching the writing brain, and vice versa. This
is why the project could be safely reorganised many times without breaking anything.

### 4.2 Inside `src/writingagent/` — the program itself

Files are grouped here by their job. (Line counts are rough, to show relative size.)

#### Group A — The two faces (how you talk to it)

| File / folder | Plain-English job | Why it's separate |
|---|---|---|
| `shell/` (a folder) | The **interactive console** (TUI = Text User Interface): the pretty themed prompt, banner, live progress dashboard, the built-in chat assistant, slash-commands like `/help`. | The console is big and visual; it lives in its own folder split into small parts (see §4.3). |
| `cli.py` | The **one-shot command line**: `book new ...`, `book run`, `book export ...`. Type one command, it does one thing, it ends. | Good for scripts, automation, and power users who don't want a live session. |
| `api.py` | The **Python interface** for other programs: `Project(...).run()`, `.export()`. | So developers can embed the writing engine in *their* software. |

#### Group B — The conductor (the orchestrator)

| File / folder | Plain-English job |
|---|---|
| `orchestrator/` (a folder) | The **conductor of the whole orchestra**. It runs the step-by-step process from §3: which worker goes next, what to do if a draft fails, when to save, when to pause. It is the "state machine" — the thing that knows *where in the process we are* and can resume after an interruption. Split into focused parts (see §4.4). |

Think of the orchestrator as the **director on a film set**: it doesn't act, write, or film — it decides
*what happens next and in what order*, and it keeps the master schedule.

#### Group C — The thinking parts (talking to the AI)

| File | Plain-English job | The "why" |
|---|---|---|
| `nodes.py` | Defines **each worker** (planner, writer, critic, judge, verifier, etc.) as a function. Each one bundles "here's the instruction + here's the input + here's the exact shape of answer I want". | One place that lists every specialist, so the orchestrator just calls `nodes.write_article_section(...)` etc. |
| `prompts.py` | The **actual instructions** given to the AI for each worker (the "system prompts"). This is where the design intent is encoded in English. | Keeping the wording in one file makes the system's "personality" and standards easy to read and tune. |
| `schemas.py` | The **exact shape** each worker's answer must take (e.g. a critique must have a verdict, a confidence number, a list of blocking issues). | Forcing structured answers (not free text) means the program can *act on* the answer reliably instead of guessing. |
| `llm.py` | The **universal adapter** that actually sends a request to an AI model and gets the answer back. Handles retries, cost tracking, caching, and fixing malformed answers. | "LLM" = Large Language Model = the AI (like the engine behind ChatGPT). One adapter means the rest of the code never worries about provider details. |
| `providers.py` | The **registry of AI hosts** it can talk to (OpenRouter, DeepSeek, local Ollama, etc.). | So you can switch which company's AI powers the system with one setting. |
| `config.py` + `config/models.yaml` + `config/settings.yaml` | Which **AI model** each worker uses, and all the tunable knobs (revision limits, whether research is on, etc.). | Different jobs need different muscle: see §6. Putting it in editable files means no coding to change behaviour. |

#### Group D — The memory (what it remembers and produces)

| File | Plain-English job |
|---|---|
| `brain.py` | Defines **where every file lives on disk** and how to read/write it safely (per-user, per-project). The "filing cabinet" rules. |
| `store.py` | A small **database** per book for fast search and for tracking the story's *canon* (characters, timeline, world rules) and how they connect. |
| `skills.py` | The **craft-skill library**: lessons learned from past runs, plus tracking which ones actually helped. |
| `retrieval.py` | **Fetches the right slices of memory** at the right moment (e.g. "give the writer the summaries of the last 3 sections, and the most relevant learned skills"). |
| `embeddings.py` | A smarter (meaning-based) way to find relevant skills, when enabled. |

"On disk" simply means saved as ordinary files in folders (the `brain/` directory) — see §5 for why
that choice matters so much.

#### Group E — Research & illustration (grounding in reality)

| File | Plain-English job |
|---|---|
| `search.py` | A quick **web search** to gather facts for a section. |
| `deep_research.py` | A **deeper researcher** that fetches and reads full pages from multiple sources. |
| `images.py` | Fetches relevant **photos** from Wikimedia Commons (free, properly licensed). |
| `diagram.py` | **Draws diagrams** as clean SVG vector images when no good photo exists (for technical pieces). |
| `cache.py` | Remembers expensive results (searches, etc.) so it doesn't pay for the same thing twice. |

#### Group F — Quality & finishing (making it good, then making it pretty)

| File | Plain-English job |
|---|---|
| `humanizer.py` | Rewrites approved prose to **strip AI tells** while preserving meaning (and never touching code blocks). |
| `polish.py` | **Deterministic clean-up** (no AI): fixes citations, builds one reference list, removes duplicate figures, computes reading time. Free and perfectly repeatable. |
| `render.py` | Turns plans/outlines into nicely formatted Markdown for display. |
| `export.py` | Turns the finished manuscript into **PDF and EPUB** (and the orchestrator adds HTML/Word/text/Markdown). |
| `telemetry.py` | Logs **every AI call** (tokens used, cost, time) so you can see exactly what a run cost. |

#### Group G — Small shared helpers

| File | Plain-English job |
|---|---|
| `concurrency.py` | Runs several independent jobs **at the same time** (e.g. fetch research + images + skills together) to save time. |
| `ui.py` | Shared **visual helpers**: colour themes, the console, reading-time formatting. Used by both faces. |
| `__init__.py` | Marks `writingagent` as a package and holds the **version number** (single source of truth). |

### 4.3 Inside `shell/` (the interactive console, broken into small rooms)

The console was once one enormous ~2,900-line file. It is now split into focused pieces (a *facade* —
explained in §7 — keeps everything working as before):

| Piece | Job |
|---|---|
| `_const.py` | Shared bits and pieces: brand glyphs (the pen-nib logo ✒), the list of worker names, the vocabulary for recognising commands, and the chat assistant's instructions. |
| `branding.py` | The banner, the gradient wordmark, colour-theme handling, the welcome screen, and the table-drawing helpers. |
| `help.py` | The `/help` screen, the feature toggle grid, and the model catalogue. |
| `commands.py` | The handlers for slash-commands like `/model`, `/provider`, `/set`, `/auto`, `/praise`, `/skills`, plus choosing the active project. |
| `dashboard.py` | The **live progress dashboard** you watch while it writes (stages, a trust indicator, controls to pause), and the run controls. |
| `chat.py` | The **built-in conversational assistant** — you can just talk to it ("write me an article about X") and it figures out the commands. |
| `dispatch.py` | The "what did the user mean?" logic: is this line a command, a slash-command, or chat? |
| `slash.py` | The actual router that runs whichever slash-command you typed. |
| `session.py` | The smart input box (tab-completion of commands, history). |
| `repl.py` | The **main loop**: show prompt → read your line → route it → repeat. ("REPL" = Read-Eval-Print-Loop, the classic name for an interactive prompt.) |

### 4.4 Inside `orchestrator/` (the conductor, broken into small rooms)

Also once one giant file, now split by responsibility:

| Piece | Job |
|---|---|
| `common.py` | Shared building blocks used by *both* books and articles: research helpers, the divergent-draft + best-pick logic, claim verification, citation tools, the save/resume scaffolding, and the learning step. |
| `book.py` | The **chapter pipeline** *and* `run()` — the single public "go" function that detects whether you have a book or an article and drives the right one. |
| `article.py` | The **section pipeline** for articles. |
| `export.py` | Turning a finished manuscript into all the file formats, plus re-polishing an existing manuscript and building the evidence report. |
| `manage.py` | Housekeeping: delete a project, read its status, record your review instruction, switch a run between autonomous and manual. |
| `review.py` | The human-in-the-loop parts: approve a paused draft, revise a committed section, run a "table read" critique, score a finished project. |

---

## 5. The "brain" — why everything is saved as plain files

The `brain/` folder is where the program keeps **everything it produces and remembers**. Its layout:

```
brain/
└── users/<your-user-id>/
    ├── articles/<project-name>/      ← one folder per article
    │   ├── run_state.json            ← the "save file": what phase we're in, which section
    │   ├── outline.json / outline.md ← the plan of sections
    │   ├── thesis.json / thesis.md   ← the one arguable claim
    │   ├── section_01.md, ...        ← each committed section
    │   ├── manuscript.md             ← the stitched-together finished piece
    │   ├── manuscript.pdf/.docx/...  ← exported formats
    │   ├── evidence_report.md        ← the thesis + ranked sources ("receipts")
    │   ├── sources.json              ← the bibliography registry
    │   ├── revision_log.md           ← a diary of what happened
    │   └── versions/                 ← every draft of every section, kept for inspection
    ├── books/<project-name>/         ← same idea, but chapters + a "canon"
    ├── skills/                       ← learned craft lessons
    └── prefs/                        ← your preferences and author voice samples
```

**Why save everything as ordinary files (Markdown + JSON) instead of hiding it in a database?**
This is one of the project's deepest design choices, and there are several reasons:

1. **Resumability.** Because the current state is *always* on disk, you can close the program, lose
   power, or hit an error — and re-running continues from exactly where it stopped. Nothing is held
   only in memory.
2. **Transparency.** You can open any file and read it. The drafts, the critiques, the sources — it's
   all there in plain text. Nothing is a black box.
3. **Portability.** Because it's just files, you can sync them across computers (the author works from
   several laptops), back them up, or hand them to someone else.
4. **No lock-in.** Markdown and JSON are universal formats that will open anywhere, forever.

("JSON" is a simple text format for structured data. "Markdown" is the lightweight format this very
file is written in — plain text with `#` for headings and `*` for emphasis.)

The one place a real **database** is used is `store.py` — a small per-book file that makes *searching*
the text fast and tracks the story's canon and entity relationships. Think of it as an *index* built
on top of the plain files, not a replacement for them.

---

## 6. Why different jobs use different AI models (and what that saves you)

Look at `config/models.yaml` and you'll see each worker is assigned a model "tier":

- **Pro (high-power) models** go to the jobs that need real judgment: the **Planner** (sets the whole
  piece's DNA), the **Writer** (prose quality), the **Critic/Judge/Verifier** (honest evaluation), the
  **Consolidator** (reasoning across a whole book), and the **Diagram** planner.
- **Flash (fast, cheap) models** go to the mechanical jobs: summaries, assembly, the chat assistant,
  the learner, optional research.

**Why not use the best model for everything?** Cost and speed. Using a top-tier model to write a
one-line chapter summary is like hiring a master novelist to address envelopes — wasteful. Routing each
job to the right tier gives you most of the quality at a fraction of the cost. And because it's just a
settings file, *you* can change any of it without touching code.

A related money-saver: **prompt caching**. The AI charges less when it re-reads text it has seen before
(the same instructions, the same thesis injected into every section). The system is set up to take
advantage of this, which can make a run several times cheaper.

---

## 7. A few clever ideas worth understanding (and why they matter)

These are the techniques that make the output noticeably better than "ask ChatGPT once". You now have
enough context to appreciate each.

- **The thesis.** Every piece argues *one contestable claim*, generated up front and fed into every
  worker. *Why:* it's the difference between an article that *says something* and a Wikipedia-style
  summary that just covers a topic.

- **Divergent drafts + a tournament judge.** For a first draft it often writes **several versions at
  different creativity levels in parallel**, then a separate Judge picks the best. *Why:* selecting the
  strongest of several genuine attempts beats endlessly polishing one weak attempt.

- **Claim verification.** Cited facts are checked against the actual fetched source text; unsupported
  claims become *blocking* problems. *Why:* this directly attacks **hallucination** — the AI's tendency
  to state false things confidently.

- **The insight gate.** A draft can be "correct but boring". The critic scores *insight*, and a draft
  that's below the bar gets sent back to be sharpened even if nothing is technically wrong. *Why:*
  correctness isn't the same as being worth reading.

- **The humanizer.** A final surgical rewrite removes robotic phrasing while leaving meaning (and any
  code) intact. *Why:* AI prose has a recognisable, slightly hollow rhythm; readers trust human-sounding
  writing more.

- **The learning loop.** After each finished piece, lessons are distilled into reusable "skills" that
  inform future runs, and skills that don't help are retired. *Why:* the studio should get better with
  experience, not start from zero every time. **Two important honesty notes:** (1) this is *memory*,
  not retraining — the underlying AI model never changes; the system accumulates a personal, self-pruning
  library of lessons that it feeds back as context. (2) To know which lessons *actually* help, it can run
  an **ablation duel** (turn on `skill_duels`): when writing, it occasionally drafts one extra version
  with a candidate skill removed and lets the critic compare — if the version *with* the skill keeps
  winning, the skill earns trust; if not, it's retired. This is a genuine cause-and-effect test (the only
  thing that differs is that one skill), not a guess. It's off by default because it costs one extra draft
  on the units where it's still learning a skill's worth.

- **The evidence report.** The piece ships with its thesis and **every source ranked by influence**.
  *Why:* it makes the work *auditable* — you can see exactly what carried the argument. Most AI writing
  can show you neither.

- **The facade / package split.** Two of the biggest files (the orchestrator and the console) were each
  split from one giant file into a folder of small, focused files, with a thin "facade" that re-exports
  everything so nothing else had to change. *Why:* a 2,000-line file is hard to read, navigate, and
  modify safely. Small focused files are easier to understand and change — exactly the goal of *this*
  document. (A "facade" here is a friendly front desk: callers still knock on the same door and ask for
  the same things; behind the desk the work has been reorganised into specialised back offices.)

---

## 8. How you actually run it

There are three ways in, all backed by the same engine:

1. **Interactive console (most fun):**
   ```
   writing-agent           # or: python writingagent.py
   ```
   You get a themed prompt; type a topic or chat with it; watch the live dashboard as it writes.

2. **One-shot commands (good for automation):**
   ```
   book new --abstract "How vector databases work" --pick 1
   book run
   book export pdf
   ```

3. **Fake mode (free, no AI key, to see the whole flow):**
   ```
   WRITINGAGENT_FAKE=1 writing-agent
   ```
   This runs the *entire* process with placeholder text instead of real AI calls — perfect for
   understanding the machinery without spending anything. (It's also how the ~330 automated tests run.)

To do real runs you need a free **API key** from an AI host (e.g. OpenRouter), placed in a file named
`.env`. An API key is just a password that lets the program use the AI service on your account. If you
launch without one, the console *tells you* — and offers the free fake-mode path above — rather than
failing on the first command.

**Comfort + accessibility, briefly.** Type `/theme` to switch the look (11 themes, including a
**colourblind-safe** high-contrast one); `/features` toggles capabilities live. For screen readers set
`WRITINGAGENT_A11Y=1` (plain line-by-line output, no animated redraw); for less motion set
`WRITINGAGENT_REDUCED_MOTION=1`; set `NO_COLOR=1` (or run with `--plain`) for monochrome. If something
goes wrong (bad key, rate-limit, network blip, a file open in another program), it shows a plain-English
fix — and your progress is always saved, so you just run again.

---

## 9. Mini-glossary (every jargon word, in plain English)

- **AI model / LLM (Large Language Model):** the text-generating AI, like the engine behind ChatGPT.
- **Node:** in this project, one specialised AI "worker" (planner, writer, critic, …).
- **Orchestrator:** the conductor that runs the workers in the right order and handles save/resume.
- **Prompt:** the instruction text given to an AI model.
- **Token:** the unit AI providers measure and bill by — roughly ¾ of a word. "1,000 tokens" ≈ 750 words.
- **Schema:** a strict template for an answer's shape, so the program can rely on the structure.
- **Hallucination:** when an AI states something false but sounds confident. The verifier fights this.
- **Autonomous vs manual mode:** run start-to-finish without stopping, vs. pause for your review at each unit.
- **Escalation:** when a draft can't pass the quality bar, the run pauses and asks you (in manual mode).
- **Canon (books):** the tracked facts of a story — characters, timeline, world rules — kept consistent.
- **Brain:** the `brain/` folder where all state and output is stored as plain files.
- **TUI / REPL:** the interactive text console / its read-evaluate-print loop.
- **CLI:** the one-shot command-line interface.
- **Markdown / JSON:** plain-text formats for documents / structured data.
- **SQLite:** a tiny self-contained database stored in a single file (used by `store.py`).
- **Facade:** a thin front layer that keeps the old, simple way of calling things working after the
  code behind it has been reorganised.
- **Deterministic:** always produces the same result from the same input (e.g. `polish.py`), as opposed
  to AI steps, which can vary.
- **Fake mode:** a free, offline mode that swaps real AI calls for placeholders to exercise the flow.

---

## 10. The shortest possible summary

> You type a topic. A **conductor** (the orchestrator) walks it through a **studio of AI specialists**
> — plan, research, write several drafts, judge the best, critique, fact-check, revise, humanise — and
> saves **every step as plain files** so it can resume anytime and show its receipts. Cheap models do
> the grunt work, powerful models do the judgment, and the system **learns** from each finished piece.
> Two friendly front doors (a pretty console and a plain command line) sit in front of one engine. The
> whole thing is built to be **transparent, resumable, and self-correcting** — that's the entire point.

*Want the exact rules and thresholds behind any of this? They live in `plan.md`. Want to see real
output? Look in `examples/` and `SampleRun/`.*
