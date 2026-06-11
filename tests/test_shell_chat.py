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
