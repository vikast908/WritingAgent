# Learning Guide - Understanding the Writing Agent from Scratch

> **Who this is for:** someone with little or no coding background who wants to *truly understand*
> what this project is, how it works, and why it was built the way it was. No prior knowledge is
> assumed. Every technical word is explained the first time it appears. Read it top to bottom - it's
> written as a story, in the order things actually happen.
>
> (For the precise engineering spec, see `plan.md`. For the running history of changes, see
> `docs/dev/resume.md`. This file is the friendly tour that sits in front of both.)

---

## 1. The one-sentence version

**This software writes long, well-researched articles and books on its own - and, crucially, it
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
> and revise - like a real editorial team - produces far better work.**

So instead of one big "write me an article" command, the project simulates a **studio of specialists**.
Each specialist is a small, focused job handed to an AI model with very specific instructions. Here is
the cast of characters (in the code these are called **nodes** - think "workers" or "stations on an
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
   tone) - *all at once*, never nagging you mid-job. This is deliberate: gather everything up front,
   then go quiet and deliver.

3. **Planning.** The Planner proposes a few *angles* (distinct takes on your topic). One is chosen
   (you pick, or it auto-picks in autonomous mode).

4. **Thesis + outline.** The system writes the **thesis** (the one arguable claim) and an **outline**
   of sections. The thesis is then injected into *every* later step so the whole piece pulls in one
   direction instead of wandering.

5. **A durable "save file" is created.** Everything about this run - the plan, outline, thesis, which
   section we're on - is written to disk immediately as plain files (this is the **brain**, explained
   in §5). *Why:* if your laptop dies or you close the program, you lose nothing; re-running picks up
   exactly where it stopped. The program treats the files on disk as the single source of truth.

6. **For each section, in order:**
   - **Fetch inputs** (research, images, relevant past "skills") - and it *pre-fetches the next
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
   ranked by how much it influenced the piece**. This is the "show your receipts" feature - most AI
   writing can't tell you *why* it said what it said.

9. **Learn.** The Learner looks at what the critic praised/flagged and saves reusable craft lessons
   for next time.

10. **Export.** The finished manuscript is rendered to the formats you want: Markdown, plain text,
    HTML web page, PDF, Word (.docx), EPUB e-book.

A **book** follows the same arc but with chapters instead of sections, plus two extra concerns: a
**canon** (the tracked facts of the story - characters, timeline, world rules) and periodic
**consolidation** checks for contradictions across chapters.

---

## 4. The folder map (the building, room by room)

Here is the whole project laid out. Top level first, then we go into the important rooms.

```
WritingAgent/
├── src/writingagent/              ← the program itself (run it: writing-agent, or python -m writingagent)
├── src/writingagent/        ← ALL the actual program lives here (see §4.2)
├── config/                ← settings you can tweak (which AI model, defaults)
├── brain/                 ← the program's MEMORY — everything it produces (see §5)
├── seeds/                 ← starter "craft skills" shipped with the project
├── tests/                 ← ~525 automated checks that prove the code works
├── examples/              ← real finished pieces, so you can judge output before installing
├── benchmarks/            ← a blind A/B kit to compare quality vs other tools
├── examples/sample-run/             ← a complete sample book (manuscript + its working files)
├── assets/                ← brand images (logo, banner)
├── README.md              ← the front-door "what is this / how to run" doc
├── plan.md                ← the authoritative engineering spec (the "law")
├── learning.md            ← THIS file
├── docs/dev/              ← maintainer journals: resume.md (session log) + test.md (verification log)
├── PRD.md, CHANGELOG.md, CONTRIBUTING.md, ROADMAP.md, ...  ← supporting docs
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

### 4.2 Inside `src/writingagent/` - the program itself

Files are grouped here by their job. (Line counts are rough, to show relative size.)

#### Group A - The two faces (how you talk to it)

| File / folder | Plain-English job | Why it's separate |
|---|---|---|
| `shell/` (a folder) | The **interactive console** (TUI = Text User Interface): the pretty themed prompt, banner, live progress dashboard, the built-in chat assistant, slash-commands like `/help`. | The console is big and visual; it lives in its own folder split into small parts (see §4.3). |
| `cli/` (a folder) | The **one-shot command line**: `writing-agent new ...`, `writing-agent run`, `writing-agent export ...`. Type one command, it does one thing, it ends. | Good for scripts, automation, and power users who don't want a live session. |
| `api.py` | The **Python interface** for other programs: `Project(...).run()`, `.export()`. | So developers can embed the writing engine in *their* software. |

#### Group B - The conductor (the orchestrator)

| File / folder | Plain-English job |
|---|---|
| `orchestrator/` (a folder) | The **conductor of the whole orchestra**. It runs the step-by-step process from §3: which worker goes next, what to do if a draft fails, when to save, when to pause. It is the "state machine" - the thing that knows *where in the process we are* and can resume after an interruption. Split into focused parts (see §4.4). |

Think of the orchestrator as the **director on a film set**: it doesn't act, write, or film - it decides
*what happens next and in what order*, and it keeps the master schedule.

#### Group C - The thinking parts (talking to the AI)

| File | Plain-English job | The "why" |
|---|---|---|
| `nodes.py` | Defines **each worker** (planner, writer, critic, judge, verifier, etc.) as a function. Each one bundles "here's the instruction + here's the input + here's the exact shape of answer I want". | One place that lists every specialist, so the orchestrator just calls `nodes.write_article_section(...)` etc. |
| `prompts.py` | The **actual instructions** given to the AI for each worker (the "system prompts"). This is where the design intent is encoded in English. | Keeping the wording in one file makes the system's "personality" and standards easy to read and tune. |
| `schemas.py` | The **exact shape** each worker's answer must take (e.g. a critique must have a verdict, a confidence number, a list of blocking issues). | Forcing structured answers (not free text) means the program can *act on* the answer reliably instead of guessing. |
| `llm.py` | The **universal adapter** that actually sends a request to an AI model and gets the answer back. Handles retries, cost tracking, caching, and fixing malformed answers. | "LLM" = Large Language Model = the AI (like the engine behind ChatGPT). One adapter means the rest of the code never worries about provider details. |
| `providers.py` | The **registry of AI hosts** it can talk to (OpenRouter, DeepSeek, local Ollama, etc.). | So you can switch which company's AI powers the system with one setting. |
| `config.py` + `config/models.yaml` + `config/settings.yaml` | Which **AI model** each worker uses, and all the tunable knobs (revision limits, whether research is on, etc.). | Different jobs need different muscle: see §6. Putting it in editable files means no coding to change behaviour. |

#### Group D - The memory (what it remembers and produces)

| File | Plain-English job |
|---|---|
| `brain.py` | Defines **where every file lives on disk** and how to read/write it safely (per-user, per-project). The "filing cabinet" rules. |
| `store.py` | A small **database** per book for fast search and for tracking the story's *canon* (characters, timeline, world rules) and how they connect. |
| `skills.py` | The **craft-skill library**: lessons learned from past runs, plus tracking which ones actually helped. |
| `retrieval.py` | **Fetches the right slices of memory** at the right moment (e.g. "give the writer the summaries of the last 3 sections, and the most relevant learned skills"). |
| `embeddings.py` | A smarter (meaning-based) way to find relevant skills, when enabled. |

"On disk" simply means saved as ordinary files in folders (the `brain/` directory) - see §5 for why
that choice matters so much.

#### Group E - Research & illustration (grounding in reality)

| File | Plain-English job |
|---|---|
| `search.py` | A quick **web search** to gather facts for a section. |
| `deep_research.py` | A **deeper researcher** that fetches and reads full pages from multiple sources. |
| `images.py` | Fetches relevant **photos** from Wikimedia Commons (free, properly licensed). |
| `diagram.py` | **Draws diagrams** as clean SVG vector images when no good photo exists (for technical pieces). |
| `cache.py` | Remembers expensive results (searches, etc.) so it doesn't pay for the same thing twice. |

#### Group F - Quality & finishing (making it good, then making it pretty)

| File | Plain-English job |
|---|---|
| `humanizer.py` | Rewrites approved prose to **strip AI tells** while preserving meaning (and never touching code blocks). |
| `polish.py` | **Deterministic clean-up** (no AI): fixes citations, builds one reference list, removes duplicate figures, computes reading time. Free and perfectly repeatable. |
| `render.py` | Turns plans/outlines into nicely formatted Markdown for display. |
| `export.py` | Turns the finished manuscript into **PDF and EPUB** (and the orchestrator adds HTML/Word/text/Markdown). |
| `telemetry.py` | Logs **every AI call** (tokens used, cost, time) so you can see exactly what a run cost. |

#### Group G - Small shared helpers

| File | Plain-English job |
|---|---|
| `concurrency.py` | Runs several independent jobs **at the same time** (e.g. fetch research + images + skills together) to save time. |
| `ui.py` | Shared **visual helpers**: colour themes, the console, reading-time formatting. Used by both faces. |
| `__init__.py` | Marks `writingagent` as a package and holds the **version number** (single source of truth). |

### 4.3 Inside `shell/` (the interactive console, broken into small rooms)

The console was once one enormous ~2,900-line file. It is now split into focused pieces (a *facade* -
explained in §7 - keeps everything working as before):

| Piece | Job |
|---|---|
| `_const.py` | Shared bits and pieces: brand glyphs (the pen-nib logo ✒), the list of worker names, the vocabulary for recognising commands, and the chat assistant's instructions. |
| `branding.py` | The banner, the gradient wordmark, colour-theme handling, the welcome screen, and the table-drawing helpers. |
| `help.py` | The `/help` screen, the feature toggle grid, and the model catalogue. |
| `commands.py` | The handlers for slash-commands like `/model`, `/provider`, `/set`, `/auto`, `/praise`, `/skills`, plus choosing the active project. |
| `dashboard.py` | The **live progress dashboard** you watch while it writes (stages, a trust indicator, controls to pause), and the run controls. |
| `chat.py` | The **built-in conversational assistant** - you can just talk to it ("write me an article about X") and it figures out the commands. |
| `dispatch.py` | The "what did the user mean?" logic: is this line a command, a slash-command, or chat? |
| `slash.py` | The actual router that runs whichever slash-command you typed. |
| `session.py` | The smart input box (tab-completion of commands, history). |
| `repl.py` | The **main loop**: show prompt → read your line → route it → repeat. ("REPL" = Read-Eval-Print-Loop, the classic name for an interactive prompt.) |

### 4.4 Inside `orchestrator/` (the conductor, broken into small rooms)

Also once one giant file, now split by responsibility:

| Piece | Job |
|---|---|
| `common.py` | Shared building blocks used by *both* books and articles: research helpers, the divergent-draft + best-pick logic, claim verification, citation tools, the save/resume scaffolding, and the learning step. |
| `book.py` | The **chapter pipeline** *and* `run()` - the single public "go" function that detects whether you have a book or an article and drives the right one. |
| `article.py` | The **section pipeline** for articles. |
| `export.py` | Turning a finished manuscript into all the file formats, plus re-polishing an existing manuscript and building the evidence report. |
| `manage.py` | Housekeeping: delete a project, read its status, record your review instruction, switch a run between autonomous and manual. |
| `review.py` | The human-in-the-loop parts: approve a paused draft, revise a committed section, run a "table read" critique, score a finished project. |

---

## 5. The "brain" - why everything is saved as plain files

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
   power, or hit an error - and re-running continues from exactly where it stopped. Nothing is held
   only in memory.
2. **Transparency.** You can open any file and read it. The drafts, the critiques, the sources - it's
   all there in plain text. Nothing is a black box.
3. **Portability.** Because it's just files, you can sync them across computers (the author works from
   several laptops), back them up, or hand them to someone else.
4. **No lock-in.** Markdown and JSON are universal formats that will open anywhere, forever.

("JSON" is a simple text format for structured data. "Markdown" is the lightweight format this very
file is written in - plain text with `#` for headings and `*` for emphasis.)

The one place a real **database** is used is `store.py` - a small per-book file that makes *searching*
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
one-line chapter summary is like hiring a master novelist to address envelopes - wasteful. Routing each
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
  claims become *blocking* problems. *Why:* this directly attacks **hallucination** - the AI's tendency
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
  not retraining - the underlying AI model never changes; the system accumulates a personal, self-pruning
  library of lessons that it feeds back as context. (2) To know which lessons *actually* help, it can run
  an **ablation duel** (turn on `skill_duels`): when writing, it occasionally drafts one extra version
  with a candidate skill removed and lets the critic compare - if the version *with* the skill keeps
  winning, the skill earns trust; if not, it's retired. This is a genuine cause-and-effect test (the only
  thing that differs is that one skill), not a guess. It's off by default because it costs one extra draft
  on the units where it's still learning a skill's worth.

- **Self-directing (agentic) mode - and why it leaves the learning loop alone.** Normally the pipeline
  always drafts a unit immediately, in a fixed order. There's an optional, *off-by-default* mode where
  a small AI **controller** gets to *decide its own next move* instead - closer to how a person works.
  This is a big enough idea that it has its own chapter below (§8); the one thing to carry forward
  *here* is **why it doesn't disturb the self-improvement story above.** When the controller finally
  says "draft this unit now", that drafting step is the **exact same step the learner already trains
  on** - same divergent drafts, same critic, same skill duels, same efficacy gate. The controller only
  chooses *what to do before and around* drafting, never *how* a draft is judged. So you can turn the
  mode on without any worry that it weakens or games the learning. (See §8 for the full tour.)

- **The evidence report.** The piece ships with its thesis and **every source ranked by influence**.
  *Why:* it makes the work *auditable* - you can see exactly what carried the argument. Most AI writing
  can show you neither.

- **The facade / package split.** Two of the biggest files (the orchestrator and the console) were each
  split from one giant file into a folder of small, focused files, with a thin "facade" that re-exports
  everything so nothing else had to change. *Why:* a 2,000-line file is hard to read, navigate, and
  modify safely. Small focused files are easier to understand and change - exactly the goal of *this*
  document. (A "facade" here is a friendly front desk: callers still knock on the same door and ask for
  the same things; behind the desk the work has been reorganised into specialised back offices.)

---

## 8. Self-correcting vs. self-directing: the agentic mode (the new part)

Everything up to now described a **self-correcting** writer: a fixed assembly line. The conductor
always walks the same path - plan, then draft, then critique, then revise, then assemble, then learn -
and the only cleverness is the *quality gates* along the way (the critic, the fact-checker, the insight
bar). That assembly line is proven, predictable, and it is still exactly what you get by default.

The new idea, added recently, is to *optionally* let the system become **self-directing** as well - an
agent that, instead of blindly following the assembly line, looks at where things stand and **decides
its own next move**. ("Agentic" is just the jargon for software that chooses its own actions toward a
goal, rather than running a fixed script.)

### 8.1 The single most important fact: it's off by default

This new mode is **opt-in and switched off out of the box.** With it off, *nothing whatsoever changes*
- you get the same fixed assembly line, byte for byte, that this guide has described all along.

Why labour this point? **Safety and trust.** The fixed pipeline is the part that has been tested on
hundreds of runs and that the whole quality story rests on. Rather than replace it with something newer
and less proven, the project keeps it as both the **default** *and* the **fallback**: even when you
*do* turn the agent loose, the moment it gets confused or hits a limit, it quietly drops back to "just
do the next thing the assembly line would have done". You are never forced onto the experimental path,
and the experimental path can never strand you. New capability, zero risk to the old behaviour.

### 8.2 Two levels of decisions

When the mode is on, the agent makes choices at two different scales. It helps to picture a writer at a
desk.

**Level one - before writing any single chapter or section.** A disciplined writer doesn't always just
start typing. Sometimes they think, "I don't actually know enough here - let me look a few things up
first," or "wait, what did I already establish about this character three chapters ago? - let me
re-read my notes," and *then* they write. The agent can now do the same: before drafting one unit it
may choose to **gather research**, or to **recall what's already been written** (pull the relevant
facts out of its own memory/canon), and only then **draft**. The fixed pipeline, by contrast, always
jumps straight to drafting.

**Level two - over the whole piece.** Stepping back to the bird's-eye view of the entire book or
article, the agent can also choose what to tackle *next* from a menu of moves, rather than marching the
fixed order. Its options, in plain terms:

- **write the next part** (draft the next chapter/section),
- **re-plan the outline** - decide the structure itself is wrong and regenerate the plan for the parts
  not yet written,
- **rewrite a weak part it already wrote** - go back and improve the shakiest committed section,
- **check the whole book for contradictions** (the consistency audit from §2's "Consolidator"),
- **fix those contradictions** when it finds them,
- **assemble** the finished manuscript,
- **learn** the craft lessons from the run,
- **finish**, or
- **hand back to the human** - deliberately stop and ask you, if it judges that wiser than pressing on.

So instead of "do step 1, then step 2, then step 3…", the agent repeatedly asks "given where I am, what
is the smartest thing to do right now?" - and the menu above is everything it's allowed to pick from.
(It can never invent a move that skips the critic; the menu is the whole of its power, by design.)

### 8.3 The three "drivers" (who actually decides)

Who makes those decisions? You choose one of three **drivers** - the project calls them *policies*, a
policy being simply "the rule the agent uses to pick its next move." Think of them as three different
people you could put in the driver's seat:

1. **The default driver.** Doesn't really decide anything - it just follows the old assembly line, in
   the old order. This exists precisely so that "agentic mode with the default driver" is *provably
   identical* to the original pipeline. It's the safety floor everything else falls back to.

2. **The LLM driver.** Asks the AI model itself, at each step, "here's the situation - what should I do
   next?" The model reads a short summary of the current state (which part we're on, how the last draft
   scored, whether there are open contradictions, how much budget is left) and picks a move from the
   menu. If it ever picks something nonsensical or illegal, the choice is quietly swapped for what the
   default driver would have done. So even the adventurous driver has the safe driver riding shotgun.

3. **The learned driver.** Uses what the agent has figured out *from its own past runs* (explained in
   §8.5). This is the most ambitious of the three, and the most honest caveat applies to it: it only
   has anything useful to say once the agent has built up enough history. Until then it simply defers
   to the safer drivers.

### 8.4 Pausing mid-sentence to look something up (in-generation tools)

There's a second, finer-grained kind of agency worth understanding, because it's the closest thing to
watching a careful human write.

The **writer** itself - the worker actually producing prose - can now *pause in the middle of writing*
to use a tool, then carry on. Mid-paragraph it might think "I should double-check that figure," go
**look something up** or **fact-check a specific claim** against a real source, get the answer, and
keep writing the very same draft. (These mid-draft helpers are nicknamed *in-generation tools* -
"in-generation" meaning "while the text is still being generated.")

This is powerful but has an obvious failure mode: a writer who keeps stopping to check *one more thing*
never finishes the paragraph. That isn't hypothetical - a real test run showed the model doing exactly
that, going down a research rabbit-hole and over-checking. So a **strict limit** was added: there's a
hard cap on how many times the writer may pause to use a tool within one draft. Once it hits the cap,
no more detours - finish the sentence. (Like every part of this mode, the mid-draft tools are off
unless you opt in, and if the tool machinery ever errors, the writer simply falls back to writing a
plain draft with no detours - never a crash.)

### 8.5 The learned controller policy (the agent learning to direct itself)

This is the deepest new idea, so here's the plain-English version.

Recall from §7 that the studio already keeps a *library of craft skills* - lessons about good writing,
distilled from finished pieces. The **learned controller policy** is the same spirit applied one level
up: instead of learning *how to write well*, the agent learns *how to direct itself well* - which of
those "next moves" tend to pay off.

How? Every decision the controller makes is written to a plain diary file (`agent_trace.jsonl` - a
simple line-by-line log). Crucially, each entry is later stamped with *how it turned out* - for
instance, "before this section I chose to gather research first" gets paired with "…and the draft then
passed on the first try" (or didn't). Over many runs this diary becomes a record of choices and their
consequences.

The learned driver studies that diary and distils a rule of thumb - for example, "for articles,
gathering facts *before* drafting tends to lift the chance the first draft passes," or "when a past run
hit a contradiction, it pays to run the consistency audit early." Then, on future runs, the learned
driver leans on those rules.

Three honesty notes, in keeping with the rest of this guide:

- **It needs many runs before it helps.** With only a handful of entries the diary is too thin to draw
  conclusions from, and the learned driver correctly *stays undecided* - falling back to the safer
  drivers rather than guessing. It earns its influence only once the evidence is real.
- **A human is never forced onto it.** Like the whole mode, the learned driver is opt-in. And what it
  learns is kept walled off from the writing-quality learning loop of §7 - it informs *what to do next*,
  never *how a draft is graded*. The two learning systems don't contaminate each other.
- **This is new.** The plumbing is built and tested, but the learned driver only becomes genuinely
  smart once a large history has accumulated. Today, in practice, the **LLM driver** is the one doing
  the interesting on-the-fly deciding, with the **default driver** always underneath as the floor.

### 8.6 The one-line takeaway for this chapter

> The writer used to be **self-correcting** (a fixed assembly line with quality gates). It can now
> *optionally* be **self-directing** too - an agent that picks its own next move and can even pause
> mid-sentence to look things up. It's **off by default**, the proven pipeline stays the default and
> the fallback, and over many runs it can *learn* which of its own choices tend to work. New power,
> bolted on without putting the trustworthy old behaviour at risk.

---

## 9. Writing *well*, in *many* fields, on a *cheap* model - the craft engine + compositor

Everything so far made the writer **trustworthy**: it won't produce slop, it won't contradict itself,
it backs up its claims, and it argues a real point. But trustworthy is not the same as *good*, and
there were two honest gaps left over.

**Gap one: it spoke in one voice for everything.** The same "clear, plain researcher" voice was baked
into every instruction. That voice is *right* for a blog post - and *wrong* for a novel, a journal
paper, or an advertisement. A rule like "never use an em-dash" or "cut all hedging words" is sensible
for punchy nonfiction and actively *harmful* in literary fiction (where the em-dash is a tool) or
academic writing (where careful hedging - "this *suggests*", "*may* indicate" - is the whole point).
The agent was, in the project's word, **monovocal**: one voice, applied everywhere.

**Gap two: most of the craft lived inside the model's head.** Recall the difference from §3 and §7
between things done by *plain code* (mechanical, free, always the same) and things done by *the AI*
(smart but variable). The agent's quality **floor** - no slop, no contradictions - was enforced by
code, so it held up no matter how clever the model was. But the higher craft - *write vividly*, *vary
your rhythm*, *show, don't tell* - was just **instructions in English** and a hope that the model was
clever enough to obey them. On a top-tier model, fine. On the **cheap, basic model** this project is
meant to run well on, "write vivid prose" mostly produces… prose, blandly. The good stuff was
*prompt-hope*, and prompt-hope is exactly what a weak model can't deliver.

This chapter is the layer that closes both gaps. It comes in two parts that work together: the **craft
engine** (genre-specific rulebooks + ways to coach a weak model) and the **compositor** (the thing
that lets you also pick a *voice* and an *emotion*, and that keeps them from piling up into mush).

### 9.1 Registers - a rulebook *and* a voice, per genre

The cornerstone idea is the **register**. Think of a register as **the rulebook plus the house voice
for one kind of writing**. (In everyday English, "register" already means the way you adjust your
speech for the occasion - you don't talk to a judge the way you text a friend. Same word, same idea.)

Crucially, a register isn't buried in code as a fixed set of rules - it's stored as plain **data** you
can read and tweak. Each register says, for *its* genre:

- which anti-slop bans apply - and, importantly, **which ones flip**. Academic writing *requires* the
  hedging that blog-writing bans; advertising *keeps* the exclamation mark and the rule-of-three
  ("faster, simpler, cheaper") that nonfiction cuts; fiction *keeps* the em-dash as a voice tool.
- the voice and concreteness it wants, and guidance on rhythm and word choice;
- which **citation style** to use (a journal uses APA; an article just credits sources inline);
- the target **reading grade** (children's writing aims low on purpose; a journal paper aims high);
- and **which of the code-based craft measurements actually matter** for that genre.

**Eleven registers ship.** `nonfiction` is the default; the others are `technical`, `literary-fiction`,
`genre-fiction`, `academic`, `journalism`, `copywriting`, `business`, `poetry`, `screenplay`, and
`children`. The system **infers** the right one from your topic and angle, unless you pin one yourself
in settings.

> **The single most important safety promise here** (and it mirrors the one in §8): if you *don't* pick
> a register, the system behaves **exactly** as it always did - the old nonfiction rules, byte for
> byte. There's even an automated test that proves it. So this whole layer is pure addition: every
> existing run is untouched, and you only opt into the new genres when you want them.

### 9.2 How you actually coach a *weak* model (the key idea)

This is the heart of the chapter, and it rests on one plain truth about cheap AI models:

> **A weak model is a far better *imitator* than it is a *rule-follower*.** Tell it "write vividly" (an
> abstraction) and it shrugs. *Show* it a great paragraph and say "match this", and it can rise toward
> it. So the craft engine replaces *abstract instructions* with *concrete things to copy and concrete
> things to measure.*

It does this three ways:

1. **Show, don't tell - to the model itself (examples, not adjectives).** Instead of describing good
   writing, the system hands the model **before-and-after pairs** (here's a flat sentence; here's the
   fixed one) so it can pattern-match the fix. And it gives the **critic** "anchors" - a worked example
   of what a *5-out-of-5* looks like next to what a *2* looks like, on each thing it grades. A weak
   critic told to "rate the rhythm 1–5" guesses; a critic shown a real 5 and a real 2 can *compare*.

2. **A "gold" paragraph to match, per genre.** Each register ships one shipped-quality example
   paragraph - its **gold corpus** - and that paragraph is quietly handed to the writer as the "this is
   the bar, write like this" sample. (If *you've* marked your own writing as good with `/praise`, your
   voice is used instead - see §9.5.) A weak model imitating a strong paragraph beats the same model
   told to "be excellent."

3. **Measure craft with plain code, not opinion.** This is the part that doesn't care how smart the
   model is. Ordinary, deterministic code now reads each draft and reports hard numbers: how much the
   **sentence rhythm** varies (all-same-length sentences are a robotic tell), how many sentences start
   with the same word in a row, the **passive-voice** ratio, **adverb** density, the **reading grade**
   (the Flesch-Kincaid score you may have seen in word processors), **cliché** hits, and whether the
   opening and closing are weak. For *fiction* it swaps in the measurements that matter there instead:
   **filter words** ("she saw", "he felt" - words that put a pane of glass between the reader and the
   scene), how much is dialogue, tired dialogue tags, and whether the point-of-view and tense stay
   consistent. These numbers are handed to the critic as **evidence** - facts it can act on, computed
   the same way every time, free of charge, on any model.

Put together: the model is *shown* what good looks like (gold + before/after), the critic is *shown*
how to score (anchors), and the result is *measured* by code (metrics). None of those three depend on
the model being clever - which is precisely why they lift a cheap model.

### 9.3 Surgical fixes - repair one flaw, never rewrite the whole thing

Back in §7 you met the **humanizer**: it strips robotic phrasing from approved prose *without* changing
the meaning. The craft engine generalises that same careful trick to other flaws. The pattern is
always: **find the specific flaw → rewrite only that one bit → check the repair → splice it back in.**

Two new surgical passes join the humanizer:

- **Show-don't-tell:** it spots a sentence that *names* a feeling ("she was afraid") and rewrites just
  that sentence into the thing that *shows* it (what her hands do, what she stops noticing) - for
  fiction registers.
- **Passive → active:** it turns "mistakes were made" into "the team made mistakes" - for prose
  registers.

The word **surgical** is doing real work. The system never regenerates an approved passage from
scratch, because a fresh full rewrite - especially by a cheap model - is exactly when facts quietly
drift, numbers change, and citations break. Instead it edits the **one offending sentence** and runs
**guards** before accepting the change: the facts and numbers must be unchanged, the specific flaw must
actually be reduced, no new slop may sneak in, and the length must stay sane. If a guard fails, the
edit is thrown away. So even a weak model doing a tiny touch-up *cannot* corrupt the meaning. (Like the
rest of this layer it's on by default but does nothing in the free fake mode.)

### 9.4 The compositor - and why *more* is *worse*

So far we can set the **genre** (the register). The second half of this layer lets you also choose a
**voice** and an **emotion** to write in. But the moment you allow several of those at once, you hit a
trap that's specific to weak models:

> **Pile three different voices onto a cheap model and it doesn't blend them - it *averages* them into
> grey mush.** Tell it to be witty *and* lyrical *and* hard-boiled *and* to follow ten craft skills,
> and it does none of them well. More instructions make a weak model write *worse*, not better.

The fix is a small traffic-controller called the **compositor**, and its job is the opposite of what
you'd expect: it's about **choosing and dropping**, not adding. It arranges every voice-shaping layer
into a fixed pecking order - a **cascade**:

```
register  →  field  →  persona  →  emotion  →  skills
(the genre)  (structure) (the voice) (the feeling) (learned tricks)
```

The rule is simple: **outer layers win.** A genre's rules outrank a chosen voice; the voice outranks
the emotion; and so on. An inner layer is only allowed to fill the freedom the outer layer leaves
open - it can never break the outer layer's rules. And - this is the anti-mush part - the system picks
**exactly one** of each upper layer: one genre, one structure, one voice, one emotion. (Only the
"learned skills" can be plural, and those were already capped at a handful and proven useful back in
§7.) The compositor is the single place that decides what's kept, what's dropped, and it **writes down
why** - it never silently staples instructions together.

### 9.5 Personas - pick a voice to write in

A **persona** is a *manner* - a way of speaking - that flavours the writing *within* whatever the genre
already allows. It changes the diction, the rhythm, how often it reaches for a rhetorical flourish, and
its stance - but it can never overrule the genre's rules (that's the cascade from §9.4).

**Forty-six personas ship**, in two families:

- **Eighteen archetypes** - invented voices you can name: the **wry skeptic**, the **warm mentor**, the
  **hard-boiled minimalist** (short, flat, unsentimental), the **lyrical maximalist** (rich, musical,
  long-lined), the **deadpan technical**, the **firebrand essayist**, and a dozen more (the
  **lucid explainer**, **cultural critic**, **investigative long-form**, **epic-fantasy**, and so on).
- **Twenty-eight public-domain *manners*** - written in the *spirit* of long-dead, out-of-copyright
  authors: **Shakespearean**, **Nietzschean**, **Austen-ironic**, **Twain-vernacular**, **Wildean**
  (epigram and paradox), **Poe-gothic** (slow-tightening dread), **Dickensian** (comic, teeming with
  character), **Whitmanesque** (expansive free-verse cataloguing), **Chekhovian**, **Kafkaesque**,
  **Dostoevskian**, **Tolstoyan**, and many more.

Two boundaries are drawn firmly and on purpose. First, these are the *manner* only - the writing stays
in plain modern language; a "Shakespearean" piece doesn't invent fake-archaic words or pretend to be
from 1600, it just borrows the cadence and wit. Second, and importantly: **no living or in-copyright
authors, ever**, and even the examples that ship are **original homage written fresh for this project -
never the real authors' text.** So there is no copying and no copyright problem. (If you genuinely want
a specific *modern* voice, that's what the `/praise` path is for - you feed it your *own* writing.)

Each persona declares which genres it suits. Ask for a voice that doesn't fit the genre - a Nietzschean
software manual, say - and the compositor politely **drops it and notes why**. The genre wins; you're
never handed a contradiction.

### 9.6 Emotions - done the *opposite* of how you'd guess

You'd think "write this scene with *fear*" would work by handing the model a list like *fear = racing
heart, sweaty palms, cold sweat*. The project tried that idea and **rejected it outright**, because
that list is precisely a **cliché generator** - "her heart raced" and "blood ran cold" are the *worn-
out* phrases that mark amateur writing. Feeding the model the clichés guarantees you get the clichés.

So emotions are built **inside-out**. For each emotion, the system ships:

- a **deny-list of the clichés to ban** - the tired phrases are wired straight into the code-based
  cliché detector (from §9.2), so "her heart raced" gets *flagged* wherever it appears, deterministically;
- and **one plain craft cue** on how to *actually* land the feeling - almost always a version of *show
  it, don't name it* (for fear: "render what the body does without permission, and the small thing that
  stops mattering"). That one tip is handed to the writer; the believable emotion is then carried by
  the deny-list plus the show-don't-tell surgical pass from §9.3 - not by a glossary of symptoms.

**Twelve emotions ship:** fear, anger, grief, joy, love, shame, tension, hope, disgust, surprise,
jealousy, and pride (the basic-emotion canon - disgust and surprise complete the classic set of six,
and jealousy and pride are the two most common dramatic drivers that don't reduce to the others). And
because you might type the *feeling* rather than the exact label, there's gentle synonym-matching - ask
for "dread", "fury", "envy", or "awe" and it resolves to fear, anger, jealousy, and surprise respectively.

### 9.7 The one-line takeaway for this chapter

> The writer used to speak in **one voice** and lean on the model being **clever**. This layer gives it
> **eleven genre rulebooks** (registers) that bend the rules per field; coaches even a **cheap** model
> by *showing* it gold examples and *measuring* craft with plain code instead of just *telling* it to
> be good; **surgically** repairs one flaw at a time without ever risking the facts; and lets you pick
> a **voice** (persona) and a **feeling** (emotion) - while a **compositor** keeps those from piling
> into mush by choosing exactly one of each and dropping whatever clashes. Off-the-shelf, with no
> register chosen, it behaves exactly as before.

---

## 10. How you actually run it

First install it (Python 3.10+): `pip install writing-agent` (or `pipx install writing-agent` to
keep it isolated). That gives you the `writing-agent` command. Then there are three ways in, all
backed by the same engine:

1. **Interactive console (most fun):**
   ```
   writing-agent           # or: python -m writingagent
   ```
   You get a themed prompt; type a topic or chat with it; watch the live dashboard as it writes.

2. **One-shot commands (good for automation):**
   ```
   writing-agent new --abstract "How vector databases work" --pick 1
   writing-agent run
   writing-agent export pdf
   ```

3. **Fake mode (free, no AI key, to see the whole flow):**
   ```
   WRITINGAGENT_FAKE=1 writing-agent
   ```
   This runs the *entire* process with placeholder text instead of real AI calls - perfect for
   understanding the machinery without spending anything. (It's also how the ~525 automated tests run.)

To do real runs you need a free **API key** from an AI host (e.g. OpenRouter), placed in a file named
`.env`. An API key is just a password that lets the program use the AI service on your account. If you
launch without one, the console *tells you* - and offers the free fake-mode path above - rather than
failing on the first command.

**Comfort + accessibility, briefly.** Type `/theme` to switch the look (11 themes, including a
**colourblind-safe** high-contrast one); `/features` toggles capabilities live. For screen readers set
`WRITINGAGENT_A11Y=1` (plain line-by-line output, no animated redraw); for less motion set
`WRITINGAGENT_REDUCED_MOTION=1`; set `NO_COLOR=1` (or run with `--plain`) for monochrome. If something
goes wrong (bad key, rate-limit, network blip, a file open in another program), it shows a plain-English
fix - and your progress is always saved, so you just run again.

---

## 11. Mini-glossary (every jargon word, in plain English)

- **AI model / LLM (Large Language Model):** the text-generating AI, like the engine behind ChatGPT.
- **Node:** in this project, one specialised AI "worker" (planner, writer, critic, …).
- **Orchestrator:** the conductor that runs the workers in the right order and handles save/resume.
- **Prompt:** the instruction text given to an AI model.
- **Token:** the unit AI providers measure and bill by - roughly ¾ of a word. "1,000 tokens" ≈ 750 words.
- **Schema:** a strict template for an answer's shape, so the program can rely on the structure.
- **Hallucination:** when an AI states something false but sounds confident. The verifier fights this.
- **Autonomous vs manual mode:** run start-to-finish without stopping, vs. pause for your review at each unit.
- **Self-correcting vs self-directing:** the fixed assembly line with quality gates (the default), vs.
  the opt-in *agentic* mode where the system chooses its own next move.
- **Agentic / agent:** software that decides its own next action toward a goal, rather than running a
  fixed script. The agentic mode here is off by default.
- **Policy / driver:** the rule the agent uses to pick its next move. Three exist: **default** (follow
  the old assembly line), **LLM** (ask the model), and **learned** (use lessons from past runs).
- **Controller:** the small decision-maker that, in agentic mode, picks the next move from a fixed menu.
- **In-generation tools:** helpers the writer can use *mid-draft* (look something up, fact-check a
  claim) before carrying on - capped so it can't go down a research rabbit-hole.
- **Register:** the rulebook *plus* the house voice for one genre, stored as editable data. Eleven ship
  (nonfiction default, technical, literary-fiction, genre-fiction, academic, journalism, copywriting,
  business, poetry, screenplay, children). Rules *bend* per genre - academic keeps hedging, fiction
  keeps the em-dash, ads keep the exclamation mark.
- **Monovocal:** the old limitation - one writing voice applied to *every* genre. The registers fixed it.
- **Gold corpus:** one shipped, genre-tagged "match this" example paragraph per register, handed to the
  writer so a weak model imitates a strong sample instead of being told to "write well."
- **Score anchors:** worked examples of a 5-out-of-5 vs a 2-out-of-5 given to the critic so it can
  *compare* rather than guess when scoring a draft.
- **Craft metrics:** plain-code measurements of a draft (sentence-rhythm variance, passive-voice ratio,
  reading grade, clichés, filter words, etc.) - model-independent evidence fed to the critic.
- **Surgical pass:** a fix that repairs *one* flawed sentence (e.g. show-don't-tell, passive→active)
  with guards so facts, numbers, and citations can't change - never a full rewrite of approved prose.
- **Compositor:** the traffic-controller that arranges voice-shaping layers into a fixed cascade
  (register → field → persona → emotion → skills), picks exactly **one** of each upper layer, drops
  whatever clashes, and logs why. Its job is *selection*, not accumulation - because piling instructions
  on a weak model produces mush.
- **Persona:** a chosen *voice/manner* (e.g. the wry skeptic, the lyrical maximalist, a Shakespearean
  cadence) that flavours the writing within the register's rules. Forty-six ship - 18 archetypes + 28
  public-domain manners; never living/in-copyright authors, and examples are original homage, not the
  real authors' text.
- **Emotion (craft):** writing a passage with a target feeling, done *inside-out* - a deny-list of the
  emotion's clichés (banned via the cliché detector) plus one "show it, don't name it" cue. Twelve ship
  (fear, anger, grief, joy, love, shame, tension, hope, disgust, surprise, jealousy, pride), with
  synonym-matching for free-text feelings.
- **Escalation:** when a draft can't pass the quality bar, the run pauses and asks you (in manual mode).
- **Canon (books):** the tracked facts of a story - characters, timeline, world rules - kept consistent.
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

## 12. The shortest possible summary

> You type a topic. A **conductor** (the orchestrator) walks it through a **studio of AI specialists**
> - plan, research, write several drafts, judge the best, critique, fact-check, revise, humanise - and
> saves **every step as plain files** so it can resume anytime and show its receipts. Cheap models do
> the grunt work, powerful models do the judgment, and the system **learns** from each finished piece.
> Two friendly front doors (a pretty console and a plain command line) sit in front of one engine. The
> whole thing is built to be **transparent, resumable, and self-correcting** - that's the entire point.

*Want the exact rules and thresholds behind any of this? They live in `plan.md`. Want to see real
output? Look in `examples/` and `examples/sample-run/`.*
