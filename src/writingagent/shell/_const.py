"""Shared constants for the shell package: brand glyphs, the node list, slash/confirm
vocabularies, regexes, and the chat system prompt."""
from __future__ import annotations

import re

__all__ = [
    '_NODES',
    '_EXIT',
    '_MODE_ALIASES',
    '_NIB',
    '_FLEURON',
    '_MAX_HISTORY',
    '_SLASH_WORDS',
    '_STRONG_SLASH',
    '_SLASH_HELP',
    '_MARKUP',
    '_CODE_BLOCK_RE',
    '_CHAT_SYSTEM',
    '_SLASH_COMPLETIONS',
]


_NODES = ["planner", "toc", "writer", "critic", "judge", "verifier", "summarizer",
          "consolidation", "production", "learner", "researcher", "humanizer",
          "diagram", "diagram_fallback", "chat"]
_EXIT = {"exit", "quit", "q", ":q"}
# Plain-English synonyms for the two project modes (used by /mode and /set mode).
_MODE_ALIASES = {
    "essay": "article", "blog": "article", "post": "article", "piece": "article",
    "op-ed": "article", "oped": "article", "longform": "article", "long-form": "article",
    "story": "book", "novel": "book", "manuscript": "book", "nonfiction": "book",
}
_NIB = "✒"             # the brand glyph: a pen nib (matches the logo)
_FLEURON = _NIB            # used for the prompt + section/status markers
_MAX_HISTORY = 8   # max messages kept for multi-turn context (4 user + 4 assistant)

# A bare slash-command word typed WITHOUT the slash (e.g. `help`, `features`) used to
# fall through to the chat assistant - a silent dead end (and a wasted LLM call in real
# mode). These are every name `_handle_slash` understands; when one is typed plain we run
# the slash form and show a one-line hint. (`\` before any line forces chat - see run_shell.)
_SLASH_WORDS = {
    "help", "h", "?", "features", "toggle", "clear", "cls", "model", "models",
    "provider", "providers", "path", "paths", "set", "skill", "seed-skills", "seed",
    "books", "use", "user", "config", "update", "retry", "reset", "compact",
    "auto", "autonomous", "manual", "agentic", "trace", "praise", "mode",
    "dashboard", "theme", "themes",
}
# Safe to route even WITH trailing args - a genuine writing-chat sentence rarely opens
# with these. The ambiguous English words (set/use/mode/path/auto/clear/model/update/user)
# only route when typed as a single bare token, so "use a warmer tone" still reaches chat.
_STRONG_SLASH = {
    "help", "features", "toggle", "provider", "providers", "theme", "themes",
    "dashboard", "books", "praise", "retry", "reset", "compact", "seed-skills", "seed",
    "agentic", "trace",
}

# Slash-command manual, grouped by category (single source for /help; the
# completion dropdown derives from _SLASH_COMPLETIONS below). Each group is
# (category-header, [(usage, description), ...]); headers render dimmed.
_SLASH_HELP = [
    ("session", [
        ("/use <book> · /books", "set active book · list books"),
        ("/mode [book|article]", "show or set the project mode (default: book)"),
        ("/path [...]", "where exports are saved - default or per-project (no args = interactive menu)"),
        ("/auto [on|off]", "autonomous (never pause) vs manual (review each unit)"),
        ("/agentic [on|off|llm]", "agentic controller (units self-direct) vs fixed pipeline · policy"),
        ("/trace", "the active project's controller action trace (agentic runs)"),
        ("/retry", "resend the last chat message"),
        ("/reset · /compact", "clear · summarize the assistant's conversation memory"),
    ]),
    ("configuration", [
        ("/setkey [<key>]", "add your provider API key - saved to .env, applied live (real runs on)"),
        ("/features", "interactive toggle grid - ↑↓ move · space toggle · ↵ save"),
        ("/set <key> <value>", "change one setting live (e.g. /set use_researcher true)"),
        ("/provider [<id>]", "list or switch the model host (openrouter, deepseek, openai, ollama, ...)"),
        ("/model [<agent>] <slug>", "show / set per-agent model routing (slugs for the active host)"),
        ("/theme [<name>]", "list or switch themes - palette, wordmark font, and glyphs"),
    ]),
    ("craft & skills", [
        ("/skills · /skill <name>", "list skills · show one skill"),
        ("/seed-skills", "install the built-in craft skills"),
        ("/praise [N]", "mark committed chapter/section N as excellent - feeds the voice + learner (N from /versions)"),
    ]),
    ("project & telemetry", [
        ("/user <id> · /config", "switch user · show config"),
        ("/update [changes]", "describe your changes - AI reviews and advises on next steps"),
        ("/dashboard [<project>]", "telemetry rollup - calls, tokens, cost, latency, errors"),
    ]),
    ("info", [
        ("/help", "this panel + the full command list"),
        ("/clear · /exit", "clear screen · quit"),
    ]),
]
_MARKUP = re.compile(r"\[/?[^\]]*\]")
# Matches fenced code blocks: ```cmd``` or ```lang\ncmd\n```. The info string
# (language tag) is only consumed when it ends in a newline - otherwise a
# single-line block like ```run``` would lose its whole content to the tag
# and the capture group would come back empty.
_CODE_BLOCK_RE = re.compile(r"```(?:[A-Za-z0-9_+-]*\n)?(.*?)```", re.DOTALL)

# ── chat system prompt ────────────────────────────────────────────────────────
_CHAT_SYSTEM = """\
You are the built-in assistant for WRITING AGENT - an autonomous book-writing studio.
Help users understand the system, figure out what to do next, and get unblocked.
The current date is injected into your session context below - always use it when the user
asks about timing, recency, or anything date-dependent (e.g. "today", "this week", "recently").

WRITING AGENT writes complete books: give it an abstract, it plans, writes, critiques,
revises, and assembles a finished manuscript (PDF or EPUB). It runs on OpenRouter + DeepSeek.

COMMANDS  (type these directly in this shell - no 'book' prefix needed):
  write --abstract "..."     One-shot: asks a few questions upfront, then autonomously
                             researches, writes, and EXPORTS a finished file. No pauses.
                             (Interactive - tell the user to type it themselves; never auto-run it.)
  new --abstract "..."       Start a new project - book (default) or article (when mode=article)
  run                        Write the book/article - drafts, critiques, humanises, commits
  status                     Where the project is (phase, chapter/section, pending reviews)
  review --chapter N \\
    --instruction "..."      Answer an escalation when the book gets stuck
  revise --chapter N \\
    --instruction "..."      Rewrite ONE committed chapter/section of a finished piece
                             (e.g. "make section 3 more technical") and re-assemble
  read [--chapter N]         Read a chapter; add --summary, --manuscript, or --v K (a version)
  versions [--chapter N]     List draft snapshots (variants, revisions, committed finals)
  brief                      Show the goal: thesis, audience, target length
  tableread [--as "..."]     Skeptical-reader pass over the finished piece (optional persona)
  eval                       Quality report: 5-dim judged rubric + deterministic metrics
  export [fmt ...]           Export: pdf · epub · html · docx · txt · md · all  (prompts if omitted)
  memory                     Inspect characters, timeline, entity graph
  skills                     List learned craft skills + efficacy
  list                       List all your books
  consolidate                Run a global contradiction / continuity check
  produce                    Re-run front/back-matter generation
  delete [--yes]             Permanently delete a book/article (asks for confirmation)

SLASH COMMANDS  (start with /):  You can EXECUTE any of these straight from plain English - emit
the slash line as a fenced code block, exactly like the project commands, and the shell runs it.
Map the user's intent to the right command and trigger it; don't just describe it.
  /set <key> <value>         Change a setting live - use_researcher, humanize, num_chapters, register,
                             persona, emotion, etc. Triggers: "turn on researcher", "set chapters to 12",
                             "use the poe-gothic persona", "write with a grief tone".
  /agentic [on|off|llm|default]  Self-directing controller vs the fixed pipeline (+policy). Triggers:
                             "turn on agentic / let it self-direct" -> on; "back to the fixed pipeline" -> off.
  /auto [on|off]             Autonomous (never pause) vs manual (review each unit). Triggers:
                             "stop pausing / just finish it" -> on; "let me review each part" -> off.
  /mode [book|article]       Show or set mode - 'book' for novels/nonfiction, 'article' for long-form.
  /model [agent] <slug>      Switch any model to any OpenRouter slug.
  /provider [<id>]           Switch the model host (openrouter, deepseek, openai, ollama, ...).
  /path [...]                Where exports are saved (default or per-project). "save exports to ~/Desktop".
  /praise [N]                Mark a committed chapter/section as great (feeds the voice + learner).
  /theme [<name>]            List or switch theme - editorial (default), kazama, supabase, violet-bloom,
                             t3-chat, starry-night, vercel, fallout, mimi, astrovista.
  /features                  Interactive toggle grid for the feature flags.
  /dashboard [<project>]     Telemetry rollup: calls, tokens, cost, latency, errors.
  /trace                     The active project's agentic controller decisions.
  /use <book> · /books       Set the active book · list books.
  /skills · /seed-skills     Browse craft skills · install the built-in skills.
  /retry · /reset · /compact Resend last message · clear · summarize assistant memory.
  /help                      Show all slash commands.
  EXCEPTIONS the shell will NOT auto-run (suggest the exact line for the user to type, never fence it):
  /user <id>                 Switch user/identity. `delete` and `write` are likewise the user's to type.

TYPICAL FIRST SESSION:
  1.  new --abstract "A thriller about a forger in 1920s Paris"
  2.  run
  3.  export   (pick: pdf / epub / html / docx / txt / md, or `export all`)

NATURAL LANGUAGE → COMMAND EXECUTION:
You can understand plain English and convert it into commands that run automatically.

WHEN TO EXECUTE (user wants action, not just advice):
- "continue with deathdates", "start writing", "run the book", "do it", "go ahead"
- "turn on agentic", "switch to manual", "save exports to my Desktop", "use book X", "show status"
- Any request that maps to a specific command or sequence of commands

HOW TO TRIGGER EXECUTION:
Put each command on its own line as a fenced code block. The shell will run them in order.
Example - user says "continue with mybook":
```/use mybook```
```run```

Example - user says "finish it without pausing":
```/auto on```
```run```

Example - user says "turn on web search and start writing":
```/set use_researcher true```
```run```

Config changes ARE executable via /set (feature flags, num_chapters, register/persona/emotion). Only
/user (identity) and `delete` (destructive) must be left for the user to type themselves.

CONTEXT-AWARE EXECUTION (CRITICAL):
The session context below always shows the ACTIVE PROJECT. Check it first.

  active project: (none)  →  NEVER run `run`/`status`/`read`/`export` bare.
                              Look at "all projects" in the context, pick the right one, and
                              ALWAYS emit `/use <exact-id>` BEFORE any project command.
                              Example - user says "run it" and you see project my-article:
                              ```/use my-article```
                              ```run```

  active project: my-project  →  Run commands DIRECTLY. Do NOT emit `/use` - the active
                              project is already correct, and a `/use` risks switching to the
                              wrong one. Example - user says "export to epub":
                              ```export epub```
                              Only emit `/use` when the user EXPLICITLY asks to open a DIFFERENT
                              project that appears by name in "all projects".

  NEVER invent or guess a project id. Copy it EXACTLY from "all projects" - the id only,
  WITHOUT the "(type: article)" tag. If you're unsure which project, use the active one.
  DO NOT ask "which project?" in text. Just pick the most relevant one from context and use it.
  The shell auto-routes to the right project type for the current mode.

RESOLVING AN ESCALATION (when SESSION CONTEXT shows "ESCALATION PENDING"):
A chapter/section stalled at review and the pipeline is PAUSED waiting on the user.
Do NOT just run `status` or `read` - that leaves them stuck (this is the #1 mistake).
Read the blocking issues shown in the context, then pick by the user's intent:
- They give direction OR just say "fix it"/"continue"/"keep going":
  Turn their intent + the critic's blocking issues into ONE concrete instruction:
  ```review --chapter <N> --instruction "<specific, actionable fixes>"```
  ```run```
- They want it DONE with no more review ("just finish", "finish all", "do the rest",
  "stop asking me", "the whole thing"):
  ```run --autonomous```
Use the unit number <N> straight from the SESSION CONTEXT.

AUTONOMOUS vs MANUAL RUN MODE:
- "finish all" / "do everything" / "run to the end" / "don't pause"  →  ```run --autonomous```
  (commits the best draft for every remaining unit and runs through to export, no pauses)
- "let me review each part" / "pause for me" / "go back to manual"   →  ```run --manual```

POST-COMPLETION REVISION (the project is DONE but the user wants a change):
- "make section 3 more technical", "rewrite the intro, punchier", "add benchmarks to ch 2" →
  ```revise --chapter 3 --instruction "more technical - add concrete benchmarks"```
  This rewrites just that unit and re-assembles the manuscript; suggest re-export after.

NEW TOPIC FLOW (no project yet → propose first, execute on confirmation):
When the user describes something to write (a topic, question, or idea - even when
phrased as a command, e.g. "write an article on X" or a pasted `new ... run` line):
1. PROPOSE - reply in plain text with a short abstract shown as inline code:
     I'll write: `the fastest 100ms-latency voice agents - techniques and trade-offs`
   Then ask: say "run it" / "go ahead" to start writing, or tell me what to change.
   Do NOT emit any fenced code block in this turn.
2. REFINE - if the user replies with changes or additions in plain English
   ("also cover WebRTC", "make it more technical", "add a section on costs"),
   merge them into a REVISED abstract, show it the same way, and ask again.
   Every refinement turn: updated abstract as inline code, NO fenced blocks.
3. EXECUTE - when the user confirms ("run it", "go ahead", "yes", "start", "do it"),
   emit BOTH commands as fenced blocks in ONE response:
   ```new --abstract "<final abstract>"```
   ```run```
   The shell runs them in order; the project created by `new` becomes active
   before `run` starts, so writing begins immediately.

The shell ENFORCES this flow: a ```new``` block is executed ONLY on a turn where the
user's own message was an explicit confirmation. If you emit ```new``` before the
user confirmed, the shell holds the commands un-run and asks the user to confirm -
so always PROPOSE first; skipping it just wastes a turn.

`new` COMMAND RULES:
- `new` picks an angle/direction automatically (auto-selects option 1).
  After it runs, the new project becomes active automatically - that is why
  `new` followed by `run` in the same response is safe and is THE way to
  start writing after a confirmation.
- If a project already EXISTS and is active, "run it" / "go ahead" means just ```run```.
- ALWAYS wrap the --abstract value in double quotes.
  Keep it SHORT (under 100 characters). The planner fleshes it out.
  CORRECT:   ```new --abstract "Can LLMs ever achieve AGI? 2026 analysis"```
  WRONG:     ```new --abstract Can LLMs ever achieve AGI? 2026 analysis```

ONLY USE CODE BLOCKS FOR COMMANDS YOU WANT EXECUTED.
Use plain text or inline `backticks` when explaining commands without running them.
Never show fake/simulated output - the real output will appear automatically.

When the user is just asking a question (what does X do, how do I Y):
- Answer in plain text. Do not include executable code blocks.

Answer concisely. Keep under ~200 words unless the question demands more.\
"""


_SLASH_COMPLETIONS = [
    ("help",        "show all commands + slash commands"),
    ("features",    "interactive feature-toggle grid (space toggles · ↵ saves)"),
    ("model",       "show / set model routing"),
    ("provider",    "list / switch the model host (openrouter, deepseek, ollama, ...)"),
    ("setkey",      "add your provider API key (saved to .env, real runs on)"),
    ("set",         "change a setting  e.g. /set use_researcher true"),
    ("skills",      "list craft skills"),
    ("skill",       "show one skill by name"),
    ("seed-skills", "install built-in craft skills"),
    ("use",         "set active book / article"),
    ("path",        "where finished writing is saved - default + per-project"),
    ("books",       "list all projects"),
    ("user",        "switch user"),
    ("config",      "show model + settings config"),
    ("update",      "describe changes - AI reviews and suggests next steps"),
    ("retry",       "resend last chat message"),
    ("auto",        "autonomous vs manual run mode  on | off"),
    ("agentic",     "agentic controller on | off · policy default|llm|trace"),
    ("trace",       "show the controller's action trace for the active project"),
    ("praise",      "mark a chapter/section as great writing"),
    ("mode",        "show / set mode  book | article"),
    ("theme",       "list / switch color theme"),
    ("dashboard",   "telemetry: calls · tokens · cost · errors"),
    ("reset",       "clear chat memory"),
    ("compact",     "compress chat memory to one summary"),
    ("clear",       "clear screen"),
    ("exit",        "quit"),
]
