"""The built-in conversational assistant: system prompt, history compaction, hints,
and a chat turn."""
from __future__ import annotations

import os

from .. import brain
from ..config import ModelConfig, Settings
from ..ui import DIM, ERR, GOLD, INK, PARCH, RULE
from ._const import _CHAT_SYSTEM, _FLEURON, _MAX_HISTORY

__all__ = [
    '_build_chat_system',
    '_next_hint',
    '_show_post_hint',
    '_compact_history',
    '_trim_history',
    '_chat_respond',
]


def _build_chat_system(settings: Settings, state: dict) -> str:
    import datetime
    uid = state["uid"]
    projects = brain.list_projects(uid)
    active = state.get("book")
    features_on = ", ".join(k for k, v in [
        ("humanize", settings.humanize),
        ("researcher", settings.use_researcher),
        ("deep-research", settings.deep_research),
        ("embeddings", settings.use_embeddings),
        ("images", settings.use_images),
        ("tournament-judge", settings.tournament_judge),
        ("verify-claims", settings.verify_claims),
    ] if v) or "none"
    active_line = (
        f"ACTIVE PROJECT: {active}  ← safe to run/status/read/export"
        if active else
        "ACTIVE PROJECT: (none set)  ← DO NOT execute run/status/read without /use <project> first"
    )
    today = datetime.date.today().strftime("%Y-%m-%d")
    # One per line, id clearly separated from its (type) tag - the model must copy
    # the id ONLY (it used to paste "id[article]" straight into commands).
    all_proj = ("\n" + "\n".join(f"    - {p[0]}   (type: {p[1]})" for p in projects)
                if projects else "(none yet)")
    run_mode = ("autonomous (never pauses for review)" if settings.autonomous
                else "manual (pauses for review at each unit)")
    ctx = (
        "\n\nCURRENT SESSION CONTEXT:"
        f"\n  date: {today}"
        f"\n  {active_line}"
        f"\n  all projects: {all_proj}"
        f"\n  mode: {settings.mode}"
        f"\n  run mode: {run_mode}"
        f"\n  features on: {features_on}"
        f"\n  user: {uid}"
    )
    # If the active project is paused at a chapter/section escalation, surface the
    # unit number + the critic's blocking issues so the assistant can resolve it
    # (emit `review --chapter N --instruction ...` or `run --autonomous`) instead of
    # looping on status/read.
    if active:
        from ..brain import ArticlePaths, BookPaths
        ap = ArticlePaths(active, uid)
        paths = ap if ap.run_state.exists() else BookPaths(active, uid)
        st = brain.read_json(paths.run_state) or {}
        if st.get("pending_review") and st.get("review_kind") in ("chapter", "section"):
            unit_key = "current_section" if st.get("mode") == "article" else "current_chapter"
            unit_n = st.get(unit_key)
            review_md = (brain.read_text(paths.review_of(unit_n)) or "").strip()
            ctx += (
                f"\n\n⚠ ESCALATION PENDING: unit {unit_n} stalled at review and is waiting for the user."
                f"\n  Resolve it this turn - emit `review --chapter {unit_n} --instruction \"...\"` then `run`,"
                f"\n  or `run --autonomous` if the user wants it finished without more review."
            )
            if review_md:
                ctx += f"\n  Critic's blocking issues:\n{review_md[:900]}"
    # Tell the AI about article mode + how to handle project selection
    if settings.mode == "article":
        ctx += (
            "\n\nMODE: ARTICLE - important rules:"
            "\n  • `new` creates an ARTICLE, not a book. Say 'article topic', never 'Book abstract'."
            "\n  • When user asks to write/run/continue something, check ACTIVE PROJECT above."
            "\n  • If ACTIVE PROJECT is set → just run: ```run```"
            "\n  • If ACTIVE PROJECT is (none) and there are projects listed above:"
            "\n    ALWAYS execute `/use <exact-id>` first, then ```run```."
            "\n    Pick the most recently created article project."
            "\n  • If user asks to write a BOOK while in article mode, say:"
            "\n    'You are in article mode. Type `/mode book` to switch, or I can write an article instead.'"
        )
    elif not active:
        # Book mode, no active project - instruct AI to set one
        mode_filter = "book"
        matching = [p[0] for p in projects if p[1] == mode_filter]
        if matching:
            ctx += (
                f"\n\nNo active project. To help the user, use:"
                f"\n  ```/use {matching[-1]}```"
                f"\n  then suggest `run` or `status`."
            )
    return _CHAT_SYSTEM + ctx


def _next_hint(state: dict, settings=None) -> str:
    """One-liner prompt of the most useful next action given current state."""
    from ..brain import ArticlePaths, BookPaths
    projects = brain.list_projects(state["uid"])
    active = state.get("book")
    if not projects:
        mode = settings.mode if settings else "book"
        noun = "topic" if mode == "article" else "idea"
        return f'next:  new --abstract "your {noun}"'
    if active:
        art = ArticlePaths(active, state["uid"])
        if art.run_state.exists():
            st = brain.read_json(art.run_state) or {}
        else:
            st = brain.read_json(BookPaths(active, state["uid"]).run_state) or {}
        mode = st.get("mode", "book")
        if st.get("pending_review"):
            key = "current_section" if mode == "article" else "current_chapter"
            return f'next:  review --chapter {st.get(key, "")} --instruction "..."'
        if st.get("phase") == "done":
            return "next:  export  (pdf · epub · html · docx · txt · md)"
        return "next:  run   (or: status  read  /help)"
    # No active project - show actual names
    mode_filter = "article" if (settings.mode if settings else "book") == "article" else "book"
    matching = [p[0] for p in projects if p[1] == mode_filter]
    candidates = matching or [p[0] for p in projects]
    if len(candidates) == 1:
        return f"next:  /use {candidates[0]}   then  run"
    return "next:  type  run  - it will ask you which project"


def _show_post_hint(console, state: dict, settings=None) -> None:
    """Print a dim next-step hint after any book command completes."""
    hint = _next_hint(state, settings)
    if console:
        from rich.rule import Rule
        from rich.text import Text
        console.print(Rule(Text(f"  {_FLEURON}  {hint}", style=DIM), style=RULE))
    else:
        print(f"\n  {hint}")


def _compact_history(history: list, cfg: ModelConfig) -> list:
    """Summarize chat history to a single system message using the chat model."""
    if not history:
        return []
    from ..llm import complete_text
    model = cfg.model_for("chat")
    transcript = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in history)
    summary = complete_text(
        model,
        "You are a concise summarizer.",
        ("Summarize this WRITING AGENT assistant conversation in 3-4 sentences. "
         "Capture: what book(s) were discussed, what was done or decided, "
         "and the current state so the assistant can continue helpfully.\n\n"
         + transcript),
        max_tokens=200,
        temperature=0.0,
    )
    return [{"role": "system", "content": f"[Compacted prior context] {summary}"}]


def _trim_history(history: list, user_msg: dict, asst_msg: dict) -> None:
    """Append a turn and keep at most _MAX_HISTORY messages total."""
    history.append(user_msg)
    history.append(asst_msg)
    if len(history) > _MAX_HISTORY:
        del history[:len(history) - _MAX_HISTORY]


def _chat_respond(message: str, console, cfg: ModelConfig, settings: Settings, state: dict) -> None:
    """Route unrecognised input to the chat model with streaming + spinner UX."""
    from ..llm import stream_text

    # Lazy import: dispatch/slash import chat (for _chat_respond), so the back-edge to
    # the command dispatcher must be deferred to call time to avoid an import cycle.
    from .dispatch import _commands_in_response, _execute_cmd, _is_confirmation

    system = _build_chat_system(settings, state)
    model = cfg.model_for("chat")
    model_slug = model.split("/")[-1]
    fake = os.getenv("WRITINGAGENT_FAKE", "").lower() in ("1", "true", "yes")
    history: list[dict] = state.setdefault("chat_history", [])

    # ── Plain-text (no Rich) - stream chunks directly ─────────────────────────
    if not console:
        print(f"\nyou > {message}")
        print(f"[{model_slug}]", end=" ", flush=True)
        if fake:
            resp = "I'm WRITING AGENT. Try: `new --abstract \"your idea\"` then `run`."
            print(f"\n{resp}\n")
            state["last_chat"] = message
            _trim_history(history, {"role": "user", "content": message},
                          {"role": "assistant", "content": resp})
            return
        try:
            chunks: list[str] = []
            for chunk in stream_text(model, system, message,
                                     history=history, max_tokens=400, temperature=0.7):
                print(chunk, end="", flush=True)
                chunks.append(chunk)
            full = "".join(chunks)
            print(f"\n\n{_next_hint(state, settings)}\n")
            state["last_chat"] = message
            _trim_history(history, {"role": "user", "content": message},
                          {"role": "assistant", "content": full})
        except KeyboardInterrupt:
            print("\n(cancelled)\n")  # stop this response, stay in the shell
        except Exception as e:  # noqa: BLE001
            print(f"\n(unavailable: {e}) - try /help\n")
        return

    # ── Rich TUI - spinner → streaming → Markdown render ─────────────────────
    from rich.markdown import Markdown
    from rich.rule import Rule
    from rich.text import Text

    # 1. Acknowledge immediately - separator + echo user message
    console.print(Rule(style=RULE))
    console.print(Text(f"  you  ›  {message}", style=f"italic {INK}"))

    if fake:
        response = (
            "I'm **WRITING AGENT** - your autonomous book-writing studio.\n\n"
            "**Get started:**  `new --abstract \"your idea\"`  →  `run`  →  `export --format epub`\n\n"
            "Type `/help` for all commands, or just describe what you want to write."
        )
        console.print(Rule(style=RULE))
        console.print(Markdown(response))
        console.print(Rule(Text(f"  {_FLEURON}  {_next_hint(state, settings)}", style=DIM), style=RULE))
        state["last_chat"] = message
        _trim_history(history, {"role": "user", "content": message},
                      {"role": "assistant", "content": response})
        return

    # 2. Spinner until the first token arrives, then Live Markdown streaming
    from rich.live import Live
    from rich.padding import Padding

    chunks: list[str] = []
    error: str = ""
    cancelled = False
    try:
        gen = stream_text(model, system, message,
                          history=history, max_tokens=400, temperature=0.7)

        with console.status(
            f"[dim]✦ {model_slug}[/dim]",
            spinner="dots",
            spinner_style=f"bold {GOLD}",
        ):
            for chunk in gen:
                chunks.append(chunk)
                break  # first chunk received - drop spinner

        # 3. Stream a TRANSIENT, in-place tail preview while tokens arrive; the
        #    complete reply is rendered once, below, after the loop.
        #
        #    Why not Live-update a growing Markdown block: once the reply is taller
        #    than the terminal, a non-transient Live with vertical_overflow="visible"
        #    can't overwrite the previous frame, so it re-emits the WHOLE block on
        #    every refresh - stacking many identical copies in the scrollback (the
        #    "I see 5 duplicates" bug). A transient + cropped plain-text tail is
        #    bounded to the viewport, updates in place, and is erased on exit, so the
        #    single final print is the only thing left on screen.
        console.print(Rule(style=RULE))
        if chunks:
            max_rows = max(6, (console.size.height or 24) - 4)
            with Live(console=console, refresh_per_second=12, transient=True,
                      vertical_overflow="crop") as live:
                for chunk in gen:
                    chunks.append(chunk)
                    tail = "".join(chunks).splitlines()[-max_rows:]
                    live.update(Padding(Text("\n".join(tail) + " ▌", style=PARCH),
                                        pad=(0, 2)))

    except KeyboardInterrupt:
        cancelled = True  # stop streaming, keep partial text, stay in the shell
        console.print(Text("  (cancelled)", style=DIM))
    except Exception as e:  # noqa: BLE001
        error = f"(assistant unavailable: {e}) - type /help to see all commands"

    # The only thing committed to the scrollback: the complete reply, formatted
    # once. (The streaming preview above was transient, so there's nothing to
    # duplicate.) On cancel we still render whatever partial text we collected.
    # An error renders in the error style, clearly apart from assistant prose.
    full = "".join(chunks)
    if full:
        console.print(Padding(Markdown(full), pad=(0, 2)))
    if error:
        console.print(Text(f"  {error}", style=ERR))

    # 4. Save history (not on error - a half-streamed reply would mislead the model)
    if full and not error:
        state["last_chat"] = message
        _trim_history(history, {"role": "user", "content": message},
                      {"role": "assistant", "content": full})

    # 6. Execute any commands the model included in code blocks
    #    (skip when cancelled or errored - a half-streamed response may carry a
    #    partial command)
    cmds = (_commands_in_response(full, state.get("_known_commands", set()))
            if full and not cancelled and not error else [])
    # Hard gate: creating a project from chat needs the user's explicit go-ahead.
    # If the model jumped straight to `new` on a turn where the user didn't confirm,
    # hold the WHOLE batch (a trailing `run` would otherwise hit the previously
    # active project) and ask. The note appended to history tells the model its
    # commands did not run, so it re-emits them once the user confirms.
    if cmds and any(c.split()[0] == "new" for c in cmds) and not _is_confirmation(message):
        console.print(Rule(Text(f"  {_FLEURON}  proposed - not run yet", style=f"bold {GOLD}"), style=RULE))
        for cmd_line in cmds:
            console.print(Text(f"  $ {cmd_line}", style=f"dim {GOLD}"))
        console.print(Text('  say "go ahead" to start writing, or tell me what to change', style=DIM))
        if history and history[-1]["role"] == "assistant":
            history[-1]["content"] += (
                "\n\n[shell: the commands above were NOT executed - the shell is waiting "
                "for the user's explicit go-ahead. Re-emit them when the user confirms.]"
            )
        cmds = []
    if cmds:
        console.print(Rule(Text(f"  {_FLEURON}  running", style=f"bold {GOLD}"), style=RULE))
        for cmd_line in cmds:
            console.print(Text(f"  $ {cmd_line}", style=f"dim {GOLD}"))
            _execute_cmd(cmd_line, console, cfg, settings, state)

    # 7. Actionable hint footer
    console.print(Rule(Text(f"  {_FLEURON}  {_next_hint(state, settings)}", style=DIM), style=RULE))


# ── Prompt state indicator ────────────────────────────────────────────────────
