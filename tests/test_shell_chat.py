"""Guard the streaming chat render path (`_chat_respond`).

The visual "duplicate blocks in the scrollback" bug only reproduces on a real
terminal, but these keep the control flow honest: the complete reply is rendered
and saved exactly once, for both a normal stream and a cancelled one.
"""
import io

from rich.console import Console

from book_agent import shell
from book_agent.config import load_config, load_settings


def _console():
    return Console(file=io.StringIO(), force_terminal=False, width=80)


def _state():
    return {"uid": "u", "book": None, "chat_history": [], "last_chat": None,
            "_known_commands": set()}


def test_chat_stream_renders_and_saves_once(tmp_brain, monkeypatch):
    monkeypatch.delenv("BOOK_AGENT_FAKE", raising=False)

    def fake_stream(model, system, message, *, history=None, max_tokens=400, temperature=0.7):
        yield "Intro paragraph.\n\n"
        yield "SENTINELWORD sits in the body.\n\n"
        yield "Closing line.\n"
    monkeypatch.setattr("book_agent.llm.stream_text", fake_stream)

    cfg, settings = load_config(), load_settings()
    console = _console()
    state = _state()
    shell._chat_respond("hi there", console, cfg, settings, state)

    out = console.file.getvalue()
    # The reply lands in the scrollback exactly once (was 5x with the old Live).
    assert out.count("SENTINELWORD") == 1
    # ...and is saved to history once.
    assert state["chat_history"][-1]["role"] == "assistant"
    assert "SENTINELWORD" in state["chat_history"][-1]["content"]


def test_chat_stream_keeps_partial_on_cancel(tmp_brain, monkeypatch):
    monkeypatch.delenv("BOOK_AGENT_FAKE", raising=False)

    def fake_stream(model, system, message, *, history=None, max_tokens=400, temperature=0.7):
        yield "First chunk kept. "
        raise KeyboardInterrupt
    monkeypatch.setattr("book_agent.llm.stream_text", fake_stream)

    cfg, settings = load_config(), load_settings()
    console = _console()
    state = _state()
    shell._chat_respond("hi", console, cfg, settings, state)

    out = console.file.getvalue()
    assert "First chunk kept." in out      # partial text still shown once


def test_chat_stream_error_is_not_prose(tmp_brain, monkeypatch):
    """A mid-stream error renders as an error (not assistant prose): the partial
    text is shown, history is NOT polluted, and no commands are parsed from it."""
    monkeypatch.delenv("BOOK_AGENT_FAKE", raising=False)

    def fake_stream(model, system, message, *, history=None, max_tokens=400, temperature=0.7):
        yield "Partial reply with a half command: ```ru"
        raise RuntimeError("connection reset")
    monkeypatch.setattr("book_agent.llm.stream_text", fake_stream)
    executed = []
    # _execute_cmd lives in shell.repl now; _chat_respond lazy-imports it from there.
    monkeypatch.setattr("book_agent.shell.repl._execute_cmd", lambda cmd, *a, **k: executed.append(cmd))

    cfg, settings = load_config(), load_settings()
    console = _console()
    state = _state()
    state["_known_commands"] = {"run"}
    shell._chat_respond("hi", console, cfg, settings, state)

    out = console.file.getvalue()
    assert "Partial reply" in out                      # partial text still shown
    assert "assistant unavailable" in out              # error surfaced as an error
    assert state["chat_history"] == []                 # half reply not saved
    assert executed == []                              # nothing command-parsed


def _stream_new_and_run(model, system, message, *, history=None, max_tokens=400,
                        temperature=0.7):
    yield 'On it!\n\n```new --abstract "voice agents"```\n```run```\n'


def test_chat_new_without_goahead_is_held(tmp_brain, monkeypatch):
    """The model jumps straight to new+run on a topic message → nothing executes."""
    monkeypatch.delenv("BOOK_AGENT_FAKE", raising=False)
    monkeypatch.setattr("book_agent.llm.stream_text", _stream_new_and_run)
    executed = []
    # _execute_cmd lives in shell.repl now; _chat_respond lazy-imports it from there.
    monkeypatch.setattr("book_agent.shell.repl._execute_cmd", lambda cmd, *a, **k: executed.append(cmd))

    cfg, settings = load_config(), load_settings()
    console = _console()
    state = _state()
    state["_known_commands"] = {"new", "run"}
    shell._chat_respond("write about voice agents", console, cfg, settings, state)

    assert executed == []                                  # held, not run
    assert "not run yet" in console.file.getvalue()
    # the model is told its commands did not run, so it re-emits on confirmation
    assert "NOT executed" in state["chat_history"][-1]["content"]


def test_chat_new_with_goahead_executes(tmp_brain, monkeypatch):
    """Same response on an explicit go-ahead turn → both commands run in order."""
    monkeypatch.delenv("BOOK_AGENT_FAKE", raising=False)
    monkeypatch.setattr("book_agent.llm.stream_text", _stream_new_and_run)
    executed = []
    # _execute_cmd lives in shell.repl now; _chat_respond lazy-imports it from there.
    monkeypatch.setattr("book_agent.shell.repl._execute_cmd", lambda cmd, *a, **k: executed.append(cmd))

    cfg, settings = load_config(), load_settings()
    console = _console()
    state = _state()
    state["_known_commands"] = {"new", "run"}
    shell._chat_respond("yes, go ahead", console, cfg, settings, state)

    assert executed == ['new --abstract "voice agents"', "run"]


def test_is_confirmation():
    yes = ["go ahead", "run it", "ok", "yes, go ahead and run it",
           "run it until the end", "ok start writing", "looks good, go ahead"]
    no = ["write about voice agents", "go ahead but make it shorter",
          'new --abstract "voice agents" run', "no, don't run it",
          "make it more technical", ""]
    for msg in yes:
        assert shell._is_confirmation(msg), msg
    for msg in no:
        assert not shell._is_confirmation(msg), msg
