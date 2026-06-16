"""Tests for the reliability/perf hardening: retry+backoff, repair, usage
telemetry, the concurrency helper, and the on-disk cache."""
from __future__ import annotations

import time

import pytest
from pydantic import BaseModel

from writingagent import brain, cache, concurrency, llm


# ── concurrency.gather ─────────────────────────────────────────────────────────
def test_gather_runs_all_and_maps_results():
    out = concurrency.gather({"a": lambda: 1, "b": lambda: 2, "c": lambda: 3})
    assert out == {"a": 1, "b": 2, "c": 3}


def test_gather_isolates_failures():
    def boom():
        raise RuntimeError("nope")
    out = concurrency.gather({"ok": lambda: "fine", "bad": boom})
    assert out["ok"] == "fine"
    assert out["bad"] is None  # a failed task must not sink the others


def test_gather_actually_overlaps():
    # Three 0.2s sleeps should finish in well under the 0.6s a serial run would take.
    start = time.time()
    concurrency.gather({str(i): (lambda: time.sleep(0.2)) for i in range(3)})
    assert time.time() - start < 0.5


def test_merge_fix_notes_keeps_instruction():
    """The human instruction must survive every revision round (it used to be
    overwritten by the first critique's notes)."""
    from writingagent import schemas as S
    from writingagent.orchestrator import _merge_fix_notes
    crit = S.Critique(verdict="revise", confidence=0.7, blocking=[], nits=["tighten"])
    out = _merge_fix_notes("keep the ending exactly as is", crit)
    assert "keep the ending exactly as is" in out
    assert "tighten" in out
    assert "tighten" in _merge_fix_notes(None, crit)


def test_crit_better_ordering():
    from writingagent import schemas as S
    from writingagent.orchestrator import _crit_better
    def c(verdict, conf, nblock):
        blocking = [S.BlockingIssue(type="style", where="w", detail="d", fix="f")] * nblock
        return S.Critique(verdict=verdict, confidence=conf, blocking=blocking, nits=[])
    assert _crit_better(c("approve", 0.5, 0), c("revise", 0.9, 0))   # approve wins
    assert _crit_better(c("revise", 0.5, 1), c("revise", 0.9, 3))    # fewer blocking wins
    assert _crit_better(c("revise", 0.9, 2), c("revise", 0.5, 2))    # then confidence


def test_export_md_no_duplicate_title(tmp_path):
    from writingagent.export import markdown_to_md
    out = markdown_to_md("# Already Titled\n\nbody", tmp_path / "a.md", title="Other")
    text = out.read_text(encoding="utf-8")
    assert text.count("# Already Titled") == 1 and "# Other" not in text
    out2 = markdown_to_md("no heading body", tmp_path / "b.md", title="Added")
    assert out2.read_text(encoding="utf-8").startswith("# Added")


def test_export_inline_images_data_uri(tmp_path):
    from writingagent.export import _inline_images
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "x.png").write_bytes(b"\x89PNG fake")
    html = '<p><img src="images/x.png"/> and <img src="https://remote/x.png"/></p>'
    out = _inline_images(html, tmp_path)
    assert "data:image/png;base64," in out
    assert 'src="https://remote/x.png"' in out            # remote srcs untouched


def test_gather_strict_reraises_failure():
    # strict=True: commit-critical batches (summary/extraction) must not silently
    # degrade to None - the failure propagates after all tasks finish.
    def boom():
        raise RuntimeError("nope")
    with pytest.raises(RuntimeError, match="nope"):
        concurrency.gather({"ok": lambda: "fine", "bad": boom}, strict=True)
    with pytest.raises(RuntimeError, match="nope"):
        concurrency.gather({"bad": boom}, strict=True)   # single-task fast path too


# ── cache ──────────────────────────────────────────────────────────────────────
def test_cache_roundtrip(tmp_brain):
    assert cache.get("ns", ("k", 1)) is None
    cache.put("ns", ("k", 1), {"hello": "world"})
    assert cache.get("ns", ("k", 1)) == {"hello": "world"}


def test_cache_respects_ttl(tmp_brain):
    cache.put("ns", ("k",), "v")
    assert cache.get("ns", ("k",), max_age_s=100) == "v"
    assert cache.get("ns", ("k",), max_age_s=-1) is None  # already older than -1s


def test_cache_key_isolation(tmp_brain):
    cache.put("ns", ("a",), 1)
    cache.put("ns", ("b",), 2)
    assert cache.get("ns", ("a",)) == 1
    assert cache.get("ns", ("b",)) == 2


# ── retry classification ───────────────────────────────────────────────────────
def test_retryable_vs_fatal():
    from openai import APITimeoutError, RateLimitError

    class _FakeResp:
        status_code = 429
        headers: dict = {}

    # Build minimal instances without hitting the network.
    rate = RateLimitError.__new__(RateLimitError)
    timeout = APITimeoutError.__new__(APITimeoutError)
    assert llm._is_retryable(rate) is True
    assert llm._is_retryable(timeout) is True
    assert llm._is_retryable(llm._EmptyResponse("empty")) is True
    # A plain auth-style error with no retryable signal is fatal.
    assert llm._is_retryable(ValueError("bad key")) is False


# ── fake OpenAI client harness ─────────────────────────────────────────────────
class _Usage:
    def __init__(self, p, c):
        self.prompt_tokens, self.completion_tokens, self.total_tokens = p, c, p + c


class _Msg:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.message = _Msg(content)
        self.finish_reason = "stop"


class _Resp:
    def __init__(self, content, usage=(10, 5)):
        self.choices = [_Choice(content)]
        self.usage = _Usage(*usage)


class _FakeCompletions:
    def __init__(self, script):
        self._script = list(script)   # each item: a string (content) or an Exception to raise
        self.calls = 0

    def create(self, **kwargs):
        item = self._script[self.calls]
        self.calls += 1
        if isinstance(item, Exception):
            raise item
        return _Resp(item)


class _FakeClient:
    def __init__(self, script):
        self.chat = type("C", (), {"completions": _FakeCompletions(script)})()


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda *_: None)   # don't actually back off
    monkeypatch.setattr(llm, "_fake_mode", lambda: False)     # exercise the real call path
    llm.reset_usage()


def _install(monkeypatch, script):
    client = _FakeClient(script)
    monkeypatch.setattr(llm, "_get_client", lambda: client)
    return client


# ── In-generation tool use (plan §21 Phase 3): a tool_call turn then prose ───────
import types as _types  # noqa: E402


class _ToolCall:
    def __init__(self, cid, name, args):
        self.id, self.type = cid, "function"
        self.function = _types.SimpleNamespace(name=name, arguments=args)


class _ToolMsg:
    def __init__(self, content=None, tool_calls=None):
        self.content, self.tool_calls = content, tool_calls


class _ToolResp:
    def __init__(self, msg):
        self.choices = [_types.SimpleNamespace(message=msg, finish_reason="stop")]
        self.usage = _Usage(5, 5)


class _ToolCompletions:
    def __init__(self, script):
        self._script = list(script)
        self.calls = 0
        self.seen_tools = []

    def create(self, **kw):
        self.seen_tools.append("tools" in kw)
        msg = self._script[self.calls]
        self.calls += 1
        return _ToolResp(msg)


class _ToolClient:
    def __init__(self, script):
        self.completions = _ToolCompletions(script)
        self.chat = self


def test_tool_loop_executes_tool_then_returns_prose(no_sleep, monkeypatch):
    ran = []

    def runner(name, args):
        ran.append((name, args.get("query")))
        return "TOOL RESULT"
    client = _ToolClient([
        _ToolMsg(content=None, tool_calls=[_ToolCall("c1", "research", '{"query":"q"}')]),
        _ToolMsg(content="FINAL DRAFT", tool_calls=None),
    ])
    monkeypatch.setattr(llm, "_get_client", lambda: client)
    out = llm.complete_text_with_tools(
        "m", "sys", "user",
        tools=[{"type": "function", "function": {"name": "research", "parameters": {}}}],
        tool_runner=runner, max_tool_rounds=3)
    assert out == "FINAL DRAFT"
    assert ran == [("research", "q")]        # the tool actually ran mid-generation
    assert client.completions.calls == 2     # tool-call turn + prose turn


def test_tool_loop_fake_mode_skips_tools(monkeypatch):
    monkeypatch.setattr(llm, "_fake_mode", lambda: True)

    def boom(*_a, **_k):
        raise AssertionError("tool_runner must not run in fake mode")
    out = llm.complete_text_with_tools("m", "sys", "u", tools=[{"x": 1}], tool_runner=boom)
    assert out == llm._FAKE_TEXT


def test_tool_loop_falls_back_to_plain_draft_on_error(no_sleep, monkeypatch):
    # A provider that rejects `tools` (or any transport error) must still yield a draft.
    client = _FakeClient([ValueError("tools unsupported"), "PLAIN DRAFT"])
    monkeypatch.setattr(llm, "_get_client", lambda: client)
    out = llm.complete_text_with_tools("m", "sys", "u", tools=[{"x": 1}],
                                       tool_runner=lambda *_a: "", max_tool_rounds=2)
    assert out == "PLAIN DRAFT"              # fell back to complete_text


def test_complete_text_retries_then_succeeds(no_sleep, monkeypatch):
    from openai import APITimeoutError
    client = _install(monkeypatch, [APITimeoutError.__new__(APITimeoutError), "the prose"])
    out = llm.complete_text("m", "sys", "user")
    assert out == "the prose"
    assert client.chat.completions.calls == 2


def test_complete_text_gives_up_on_fatal(no_sleep, monkeypatch):
    _install(monkeypatch, [ValueError("401 bad key"), "unused"])
    with pytest.raises(RuntimeError):
        llm.complete_text("m", "sys", "user")  # fatal error → no retry, no fallback, raises


def test_complete_text_falls_back_after_primary_fails(no_sleep, monkeypatch):
    # With a fallback configured, a primary failure retries ONCE on the fallback model and
    # succeeds, so one node's outage degrades instead of killing the run (plan §12.1).
    monkeypatch.setattr(llm, "_fallback_model", "flash")
    client = _install(monkeypatch, [ValueError("503 model down"), "fallback prose"])
    out = llm.complete_text("m", "sys", "user")
    assert out == "fallback prose" and client.chat.completions.calls == 2


def test_structured_falls_back_after_primary_fails(no_sleep, monkeypatch):
    from writingagent.schemas import SearchQueries
    monkeypatch.setattr(llm, "_fallback_model", "flash")
    _install(monkeypatch, [ValueError("503 model down"), '{"queries": ["q1", "q2"]}'])
    out = llm.complete_structured("m", "sys", "user", SearchQueries)
    assert out.queries == ["q1", "q2"]


def test_fallback_not_retried_on_itself(no_sleep, monkeypatch):
    # The fallback call sets _allow_fallback=False, so a model that IS the fallback fails
    # straight through (no infinite recursion).
    monkeypatch.setattr(llm, "_fallback_model", "flash")
    _install(monkeypatch, [ValueError("401 bad key")])
    with pytest.raises(RuntimeError):
        llm.complete_text("flash", "sys", "user")


def test_usage_is_recorded(no_sleep, monkeypatch):
    _install(monkeypatch, ["hello"])
    llm.complete_text("m", "sys", "user")
    summary = llm.usage_summary()
    assert summary is not None and "15 tokens" in summary  # 10 prompt + 5 completion


# ── B-013: context-window overflow recovery ────────────────────────────────────
def test_complete_text_recovers_from_context_overflow(no_sleep, monkeypatch):
    # A context-length rejection is NOT a fatal 4xx: the prompt is shrunk and retried
    # once instead of failing the whole node.
    client = _install(
        monkeypatch,
        [ValueError("This model's maximum context length is 8192 tokens"), "trimmed prose"])
    out = llm.complete_text("m", "sys", "x " * 4000)
    assert out == "trimmed prose" and client.chat.completions.calls == 2


def test_context_overflow_detection():
    assert llm._is_context_overflow(ValueError("maximum context length exceeded"))
    assert llm._is_context_overflow(ValueError("context_length_exceeded"))
    assert not llm._is_context_overflow(ValueError("401 unauthorized"))


def test_shrink_truncates_longest_message():
    msgs = [{"role": "system", "content": "short"},
            {"role": "user", "content": "y" * 1000}]
    out = llm._shrink_for_context(msgs, "m")
    assert len(out[1]["content"]) < 1000 and "truncated" in out[1]["content"]


# ── B-012: stream_text honors the run budget ────────────────────────────────────
def test_stream_text_honors_budget(monkeypatch):
    monkeypatch.setattr(llm, "_fake_mode", lambda: False)
    llm.reset_usage()
    with llm._usage_lock:
        llm._usage["total_tokens"] = 100
    llm.set_run_budget(1)
    try:
        with pytest.raises(llm.BudgetExceeded):
            next(llm.stream_text("m", "sys", "user"))
    finally:
        llm.set_run_budget(0)
        llm.reset_usage()


# ── A-021: run_session serializes + clears per-run tags ─────────────────────────
def test_run_session_resets_and_clears_tags():
    llm.set_project("stale")
    llm.set_unit("stale-unit")
    with llm.run_session("proj", budget=123):
        assert llm._run_project == "proj"
        assert llm.run_budget() == 123
    assert llm._run_project is None
    assert getattr(llm._tl_ctx, "unit", None) is None
    llm.set_run_budget(0)


# ── D-013: opt-in prompt/completion debug sink ──────────────────────────────────
def test_llm_debug_sink_writes_when_enabled(tmp_brain, no_sleep, monkeypatch):
    monkeypatch.setenv("WRITINGAGENT_LLM_DEBUG", "1")
    _install(monkeypatch, ["debug prose"])
    llm.complete_text("m", "sys", "the prompt")
    files = list(brain.INDEX_DIR.glob("llm_debug-*.jsonl"))
    assert files and "debug prose" in files[0].read_text(encoding="utf-8")


def test_llm_debug_sink_silent_when_disabled(tmp_brain, no_sleep, monkeypatch):
    monkeypatch.delenv("WRITINGAGENT_LLM_DEBUG", raising=False)
    _install(monkeypatch, ["quiet prose"])
    llm.complete_text("m", "sys", "the prompt")
    assert not list(brain.INDEX_DIR.glob("llm_debug-*.jsonl"))


def test_structured_repair_retry(no_sleep, monkeypatch):
    class Thing(BaseModel):
        name: str
        count: int
    # First reply is invalid JSON; repair turn returns valid JSON.
    client = _install(monkeypatch, ["not json at all", '{"name": "ok", "count": 2}'])
    got = llm.complete_structured("m", "sys", "user", Thing)
    assert got.name == "ok" and got.count == 2
    assert client.chat.completions.calls == 2


# ── export escaping (#1) ────────────────────────────────────────────────────────
def test_html_export_escapes_title(tmp_path):
    from writingagent import export
    out = export.markdown_to_html("# Body\n\ntext", tmp_path / "a.html",
                                  title='Crime & Punishment <x>')
    html = out.read_text(encoding="utf-8")
    assert "<title>Crime &amp; Punishment &lt;x&gt;</title>" in html


def test_epub_export_wellformed_with_special_chars(tmp_path):
    import pytest
    epub = pytest.importorskip("ebooklib.epub")
    from writingagent import export
    md = "# A & B\n\nPara with <angle> & ampersand.\n\n---\n\n## Sec & Two\n\nMore."
    out = export.markdown_to_epub(md, tmp_path / "b.epub", title="A & B <x>", author="Me & Co")
    # Round-trip: a corrupt/ill-formed EPUB would raise here.
    book = epub.read_epub(str(out))
    assert book is not None


# ── image markdown escaping (#2) ────────────────────────────────────────────────
def test_image_to_markdown_escapes_caption_and_url():
    from writingagent.images import ImageResult
    r = ImageResult(
        url="https://x.org/wiki/File:Foo (bar) baz.jpg",
        title="File:Foo (bar).jpg",
        author="Jane *Doe*",
        license="CC BY 2.0",
        description="Portrait (1923) *study* [draft]",
    )
    md = r.to_markdown("1")
    # URL parens/spaces are percent-encoded so the (...) can't terminate early.
    url_part = md[md.index("](") + 2: md.index(")\n")]
    assert " " not in url_part and "(" not in url_part and ")" not in url_part
    assert "%20" in url_part
    # Italic/link-breaking chars in text are backslash-escaped.
    assert r"\*study\*" in md and r"\[draft\]" in md


# ── confidence clamp (#low) ─────────────────────────────────────────────────────
def test_confidence_clamp():
    from writingagent.schemas import Critique
    assert Critique(verdict="approve", confidence=95, blocking=[], nits=[]).confidence == 0.95
    assert Critique(verdict="approve", confidence=0.8, blocking=[], nits=[]).confidence == 0.8
    assert Critique(verdict="approve", confidence=-0.2, blocking=[], nits=[]).confidence == 0.0


# ── humanizer (#4) ──────────────────────────────────────────────────────────────
def test_humanizer_dash_does_not_merge_lines():
    from writingagent.humanizer import mechanical_clean
    out = mechanical_clean("first line ends—\nsecond line")
    assert "\n" in out                     # newline preserved (lines not merged)
    assert out.count("\n") == 1


def test_humanizer_leaves_code_fences_untouched():
    from writingagent.humanizer import mechanical_clean
    src = 'prose with “smart quotes”\n```\ncode = a—b  # keep this\n```\nmore “prose”'
    out = mechanical_clean(src)
    assert '"smart quotes"' in out          # prose normalized
    assert "code = a—b" in out              # code fence left exactly as-is (em-dash kept)
    assert 'more "prose"' in out


def test_humanizer_handles_unbalanced_fence():
    from writingagent.humanizer import mechanical_clean
    # Odd number of fences must not raise or mangle - just don't crash.
    out = mechanical_clean("intro “q”\n```\nunterminated code—block")
    assert "intro \"q\"" in out


# ── brain: atomic writes, corrupt-read resilience, safe ids (#2, #7) ────────────
def test_read_json_corrupt_returns_none(tmp_brain):
    from writingagent import brain
    p = tmp_brain / "x.json"
    p.write_text("{ truncated", encoding="utf-8")
    assert brain.read_json(p) is None          # no crash, treated as absent


def test_write_json_atomic_roundtrip_no_temp_left(tmp_brain):
    from writingagent import brain
    p = tmp_brain / "sub" / "s.json"
    brain.write_json(p, {"a": 1})
    assert brain.read_json(p) == {"a": 1}
    assert not list((tmp_brain / "sub").glob(".tmp-*"))   # temp cleaned up


def test_is_safe_id():
    from writingagent import brain
    assert brain.is_safe_id("my-book_1.2")
    assert not brain.is_safe_id("../etc")
    assert not brain.is_safe_id("C:\\x")
    assert not brain.is_safe_id("a/b")
    assert not brain.is_safe_id("")


def test_delete_book_refuses_unsafe_id(tmp_brain):
    import pytest

    from writingagent import orchestrator
    with pytest.raises(ValueError):
        orchestrator.delete_book("default", "../evil")
    with pytest.raises(ValueError):
        orchestrator.delete_book("..", "book")


# ── retrieval frontmatter (#4) ──────────────────────────────────────────────────
def test_parse_frontmatter_coerces_non_dict():
    from writingagent.retrieval import _parse_frontmatter
    assert _parse_frontmatter("---\njust a bare string\n---\nbody") == {}
    assert _parse_frontmatter("---\nname: ok\n---\n").get("name") == "ok"


# ── skills frontmatter escaping + no clobber (#5, low) ──────────────────────────
def test_write_skill_yaml_safe_roundtrip(tmp_brain):
    from writingagent import brain, retrieval, skills
    from writingagent.schemas import SkillProposal
    prop = SkillProposal(name="show: don't tell, really",
                         genre_tags=["a: b", "c, d", "e]f"],
                         when_to_apply="x", technique=["t1"], anti_pattern="ap")
    skills.write_skill("u1", prop)
    f = next(brain.skills_dir("u1").glob("*.md"))
    fm = retrieval._parse_frontmatter(f.read_text(encoding="utf-8"))
    assert fm.get("name") == "show: don't tell, really"      # special chars survive
    assert fm.get("genre_tags") == ["a: b", "c, d", "e]f"]


def test_write_skill_does_not_clobber_distinct_name(tmp_brain):
    from writingagent import brain, skills
    from writingagent.schemas import SkillProposal
    mk = lambda nm: SkillProposal(name=nm, genre_tags=["x"], when_to_apply="a",
                                  technique=["t"], anti_pattern="p")
    skills.write_skill("u2", mk("Show Tell"))
    skills.write_skill("u2", mk("show tell"))   # slugs identically
    assert len(list(brain.skills_dir("u2").glob("show-tell*.md"))) == 2


# ── chat command auto-exec allow/deny (#1, #8) ──────────────────────────────────
def test_chat_command_filter_blocks_destructive():
    from writingagent import shell
    known = {"run", "delete", "new", "status"}
    blk = lambda c: f"```\n{c}\n```"
    text = "\n".join(blk(c) for c in
                     ["run", "delete --yes", "/use mybook", "/set autonomous true", "/user bob"])
    cmds = shell._commands_in_response(text, known)
    assert "run" in cmds
    assert "/use mybook" in cmds
    assert all(not c.startswith("delete") for c in cmds)   # delete never auto-runs
    assert all("/set" not in c for c in cmds)              # /set blocked
    assert all("/user" not in c for c in cmds)             # /user blocked


def test_chat_command_extractor_single_line_blocks():
    """Single-line fenced blocks (```run```) - the format the chat system prompt
    teaches - must be extracted, not swallowed as an info string."""
    from writingagent import shell
    known = {"run", "new", "status"}
    text = ('Starting now:\n'
            '```new --abstract "How to build the fastest voice agent"```\n'
            '```run```\n'
            'Sit back while I write.')
    cmds = shell._commands_in_response(text, known)
    assert cmds == ['new --abstract "How to build the fastest voice agent"', "run"]


def test_chat_command_extractor_language_tagged_blocks():
    from writingagent import shell
    known = {"run"}
    assert shell._commands_in_response("```bash\nrun\n```", known) == ["run"]
    assert shell._commands_in_response("```run```", known) == ["run"]
    assert shell._commands_in_response("```\nrun\n```", known) == ["run"]


# ── export HTML sanitization (#6) ───────────────────────────────────────────────
def test_sanitize_html_strips_active_content():
    from writingagent.export import _sanitize_html
    dirty = ('<p>safe</p><script>alert(1)</script>'
             '<a href="javascript:steal()">x</a><img src=q onerror="evil()">'
             '<iframe src="//x"></iframe>')
    clean = _sanitize_html(dirty).lower()
    assert "<p>safe</p>" in clean
    assert "<script" not in clean
    assert "javascript:" not in clean
    assert "onerror" not in clean
    assert "<iframe" not in clean
