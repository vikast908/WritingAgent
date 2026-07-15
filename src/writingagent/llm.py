"""Thin LLM wrapper over any OpenAI-compatible provider.

- Text: chat.completions -> message content.
- Structured: JSON mode + Pydantic validation, with one repair retry (portable across
  models; DeepSeek has no Anthropic-style messages.parse).
- Fake mode (WRITINGAGENT_FAKE): returns valid placeholder output, no network. Used by tests.

The active provider (OpenRouter by default) comes from `providers.py`; switch it
with `/provider`, the `provider` setting, or WRITINGAGENT_PROVIDER. Each provider
reads its own key env var (OPENROUTER_API_KEY, DEEPSEEK_API_KEY, ...). Models are
configured per node in config/models.yaml.

Process-global state invariant (A-021): the client, usage tally, run-id, and the
per-thread `unit`/`project` tags are MODULE-GLOBAL - the design is one unattended
pipeline run per process. In a long-lived host (the TUI, the web demo) two
overlapping runs would corrupt each other's token accounting and telemetry
attribution. `run_session()` makes the full run() body acquire a process lock so
concurrent runs SERIALIZE instead of interleaving; callers that drive a whole run
(orchestrator.run) wrap it in that context manager.
"""
from __future__ import annotations

import contextlib
import datetime
import functools
import logging
import os
import random
import threading
import time
import types
import uuid
from typing import Literal, TypeVar, Union, get_args, get_origin

from openai import OpenAI
from pydantic import BaseModel

from . import providers

T = TypeVar("T", bound=BaseModel)

_log = logging.getLogger(__name__)

_provider_id = providers.DEFAULT   # active provider id; see configure_provider
_client: OpenAI | None = None
_client_lock = threading.Lock()
_include_cost = False   # ask OpenRouter to report usage.cost (set when client builds)

# Retry/backoff knobs (network calls dominate runtime - a transient 429/5xx must
# not kill a multi-hour book run, and a non-retryable 4xx must not waste attempts).
_MAX_ATTEMPTS = 4
_BACKOFF_BASE = 1.0   # seconds; doubles each attempt
_BACKOFF_CAP = 30.0
_request_timeout: float = 60.0   # per-request timeout (s); see configure_timeout


def configure_timeout(seconds: float) -> None:
    """Set the per-request network timeout (called at startup from settings)."""
    global _request_timeout, _client
    _request_timeout = seconds
    _client = None  # force the client to be rebuilt with the new timeout


# Global fallback model (plan §12.1): after the primary model exhausts its retries on a
# call (persistent outage / content filter / 5xx), the call is retried ONCE on this slug -
# the cheapest reliable tier - so one node's failure degrades instead of killing an
# unattended run. Empty = no fallback. Set at startup from models.yaml `fallback:`.
_fallback_model: str = ""


def configure_fallback(model: str | None) -> None:
    """Set the global fallback model (called at startup from `ModelConfig.fallback`)."""
    global _fallback_model
    _fallback_model = (model or "").strip()


def configure_provider(provider_id: str) -> None:
    """Select the active model host (called at startup and on `/provider`).

    Accepts a canonical id or alias (see providers.py). Rebuilds the client lazily
    on the next call; credentials are only required when a real request is made,
    so switching to a key-less provider never fails here (or in fake mode)."""
    global _provider_id, _client, _include_cost
    pid = providers.resolve(provider_id)
    if pid not in providers.REGISTRY:
        valid = ", ".join(providers.names())
        raise ValueError(f"unknown provider '{provider_id}' - valid: {valid}")
    _provider_id = pid
    _include_cost = providers.REGISTRY[pid].reports_cost
    _client = None  # rebuild against the new base_url/key on next use


def active_provider() -> providers.Provider:
    """The Provider currently in effect."""
    return providers.REGISTRY[_provider_id]




# ── Token-usage telemetry + run budget ────────────────────────────────────────
# Aggregated across every call since the last reset; surfaced at the end of a run.
_usage_lock = threading.Lock()
_usage = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
          "cost": 0.0, "cached_tokens": 0}
_run_id = uuid.uuid4().hex[:12]
_budget_max = 0           # run token budget; 0 = unlimited (see set_run_budget)
_tl_ctx = threading.local()   # .unit - which chapter/section/phase a call belongs to
_run_project: str | None = None   # module-global: one run per process; prefetch
                                  # threads inherit it (thread-locals wouldn't)


class BudgetExceeded(RuntimeError):
    """The run's total token spend reached max_run_tokens - pause, don't burn on."""


def set_run_budget(max_tokens: int) -> None:
    """Set the kill-switch for the current run (0 disables it)."""
    global _budget_max
    _budget_max = max(0, int(max_tokens or 0))


def run_budget() -> int:
    return _budget_max


def set_unit(unit: str | None) -> None:
    """Tag subsequent calls on THIS thread with the unit being processed
    (ch03 / sec02 / consolidate / production / learn) for telemetry attribution."""
    _tl_ctx.unit = unit


def set_project(project: str | None) -> None:
    """Tag all subsequent calls (any thread) with the project being run."""
    global _run_project
    _run_project = project


def set_node(node: str | None) -> None:
    """Tag this thread's next calls with the agent/node name (writer/critic/judge/...).
    Set by ModelConfig.model_for - the seam every call site resolves its model through -
    so telemetry can break cost down per agent."""
    _tl_ctx.node = node


def _check_budget() -> None:
    if _budget_max:
        with _usage_lock:
            total = _usage["total_tokens"]
        if total >= _budget_max:
            raise BudgetExceeded(
                f"run token budget reached ({total:,} >= {_budget_max:,} tokens)")


def reset_usage() -> None:
    global _run_id
    with _usage_lock:
        _usage.update(calls=0, prompt_tokens=0, completion_tokens=0, total_tokens=0,
                      cost=0.0, cached_tokens=0)
    _run_id = uuid.uuid4().hex[:12]


def run_id() -> str:
    """The current run's id - the join key shared by telemetry calls and the agentic
    action trace (so a run's LLM calls and controller decisions line up; D-014)."""
    return _run_id


# Serializes a full pipeline run's use of the module-global accounting state (see the
# module docstring's A-021 invariant). One unattended run per process is the design;
# this lock degrades concurrent runs in a long-lived host to "one at a time" rather
# than letting them corrupt each other's usage tally / run-id / telemetry tags.
_run_lock = threading.Lock()


@contextlib.contextmanager
def run_session(project: str | None = None, *, budget: int = 0):
    """Context manager wrapping one whole pipeline run: acquire the run lock, reset the
    usage tally + run-id, set the project tag and token budget, and clear the per-run
    tags on exit (so a finished run never mis-attributes a later stray call)."""
    with _run_lock:
        reset_usage()
        set_project(project)
        set_run_budget(budget)
        try:
            yield
        finally:
            set_project(None)
            set_unit(None)


def _u(o, name: str) -> int:
    """Read a usage field whether `o` is a dict, a pydantic object with the field defined,
    or a pydantic object carrying it as an extra (model_extra) - the OpenAI client drops
    provider-specific fields like DeepSeek's cache counters into model_extra."""
    if o is None:
        return 0
    if isinstance(o, dict):
        return int(o.get(name) or 0)
    v = getattr(o, name, None)
    if v is None:
        me = getattr(o, "model_extra", None)
        if isinstance(me, dict):
            v = me.get(name)
    return int(v or 0)


def _cached_tokens(u) -> int:
    """Prompt tokens served from the provider's context cache (a cache hit). Conventions
    differ: OpenAI / OpenRouter report `prompt_tokens_details.cached_tokens`; DeepSeek's
    own API reports `prompt_cache_hit_tokens` at the top of usage. We read both, so cache
    hits are visible whichever host (and field) is in play."""
    d = getattr(u, "prompt_tokens_details", None)
    if d is None:
        me = getattr(u, "model_extra", None)
        if isinstance(me, dict):
            d = me.get("prompt_tokens_details")
    return _u(d, "cached_tokens") or _u(u, "prompt_cache_hit_tokens")


def _record_usage(resp) -> None:
    u = getattr(resp, "usage", None)
    if u is None:
        return
    try:
        cost = float(getattr(u, "cost", 0) or 0)   # OpenRouter reports usage.cost (USD)
    except (TypeError, ValueError):
        cost = 0.0
    with _usage_lock:
        _usage["calls"] += 1
        _usage["prompt_tokens"] += getattr(u, "prompt_tokens", 0) or 0
        _usage["completion_tokens"] += getattr(u, "completion_tokens", 0) or 0
        _usage["total_tokens"] += getattr(u, "total_tokens", 0) or 0
        _usage["cost"] += cost
        _usage["cached_tokens"] += _cached_tokens(u)


def current_tokens() -> int:
    """Live total-token tally since the last reset (for progress displays)."""
    with _usage_lock:
        return _usage["total_tokens"]


def current_cost() -> float:
    """Live cost tally (USD) since the last reset; 0.0 if the provider doesn't report it."""
    with _usage_lock:
        return _usage["cost"]


def usage_summary() -> str | None:
    """One-line tally of tokens (and cost when known) since the last reset."""
    with _usage_lock:
        if _usage["calls"] == 0:
            return None
        line = (f"[usage] {_usage['calls']} LLM calls, "
                f"{_usage['prompt_tokens']:,} prompt + "
                f"{_usage['completion_tokens']:,} completion = "
                f"{_usage['total_tokens']:,} tokens")
        if _usage["cached_tokens"] > 0:
            pct = 100 * _usage["cached_tokens"] / max(_usage["prompt_tokens"], 1)
            line += f" ({_usage['cached_tokens']:,} cached, {pct:.0f}% of prompt)"
        if _usage["cost"] > 0:
            line += f" · ${_usage['cost']:.4f}"
        return line


def _log_call(kind: str, model: str, t0: float, attempts: int, resp,
              error: str | None = None) -> None:
    """Emit one structured JSONL record for this call (best-effort)."""
    from . import telemetry
    u = getattr(resp, "usage", None)
    try:
        cost = float(getattr(u, "cost", 0) or 0) if u else 0.0
    except (TypeError, ValueError):
        cost = 0.0
    telemetry.log_call({
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "run_id": _run_id,
        "project": _run_project,
        "unit": getattr(_tl_ctx, "unit", None),
        "node": getattr(_tl_ctx, "node", None),
        "kind": kind,
        "model": model,
        "latency_ms": round((time.time() - t0) * 1000),
        "attempts": attempts,
        "prompt_tokens": (getattr(u, "prompt_tokens", 0) or 0) if u else 0,
        "completion_tokens": (getattr(u, "completion_tokens", 0) or 0) if u else 0,
        "total_tokens": (getattr(u, "total_tokens", 0) or 0) if u else 0,
        "cached_tokens": _cached_tokens(u) if u else 0,
        "cost": cost,
        "error": error,
    })


# ── Retry classification + backoff ─────────────────────────────────────────────
def _is_retryable(exc: Exception) -> bool:
    """True for transient errors worth retrying (timeouts, connection drops, 429,
    5xx). Auth/permission/bad-request (4xx) are fatal - retrying just wastes calls."""
    from openai import (
        APIConnectionError,
        APITimeoutError,
        InternalServerError,
        RateLimitError,
    )
    if isinstance(exc, (APITimeoutError, APIConnectionError, RateLimitError,
                        InternalServerError)):
        return True
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status == 429 or status >= 500
    # Empty/truncated model output (raised by us below) is worth one more shot.
    return isinstance(exc, (_EmptyResponse,))


def _retry_after(exc: Exception) -> float | None:
    """Honour a server-provided Retry-After header when present."""
    resp = getattr(exc, "response", None)
    headers = getattr(resp, "headers", None) or {}
    val = headers.get("retry-after") if hasattr(headers, "get") else None
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def _backoff_sleep(attempt: int, exc: Exception) -> None:
    """Exponential backoff with jitter; respects Retry-After if the server sent one."""
    delay = _retry_after(exc)
    if delay is None:
        delay = min(_BACKOFF_CAP, _BACKOFF_BASE * (2 ** attempt))
        delay += random.uniform(0, delay * 0.25)  # jitter to avoid thundering herd
    _log.warning("LLM call failed (%s), retrying in %.1fs...", type(exc).__name__, delay)
    time.sleep(delay)


class _EmptyResponse(RuntimeError):
    """Model returned no content (e.g. reasoning consumed the whole token budget)."""


# ── Context-window overflow recovery (B-013) ──────────────────────────────────
def _is_context_overflow(exc: Exception) -> bool:
    """True when the provider rejected the request for exceeding the context window.
    Conventions differ (OpenAI: code 'context_length_exceeded'; others put it in the
    message), so we sniff both. Distinct from a generic 400 - this one is recoverable
    by SHRINKING the prompt and retrying, rather than failing the whole node."""
    if getattr(exc, "status_code", None) not in (400, 413, None):
        return False
    code = str(getattr(exc, "code", "") or "")
    msg = str(getattr(exc, "message", "") or exc).lower()
    return (
        "context_length_exceeded" in code
        or "context_length_exceeded" in msg
        or "context length" in msg
        or "maximum context" in msg
        or "too many tokens" in msg
        or "reduce the length" in msg
        or "string too long" in msg
    )


def _shrink_for_context(messages: list[dict], model: str) -> list[dict]:
    """Make an over-long message list fit the window by hard-truncating the single
    longest message to 60%. Best-effort - returns the original on any failure."""
    out = [dict(m) for m in messages]
    if not out:
        return out
    i = max(range(len(out)), key=lambda k: len(str(out[k].get("content") or "")))
    content = str(out[i].get("content") or "")
    keep = int(len(content) * 0.6)
    out[i]["content"] = content[:keep] + "\n\n[...truncated to fit the model context window...]"
    return out


# ── Opt-in prompt/completion debug sink (D-013) ───────────────────────────────
# Set WRITINGAGENT_LLM_DEBUG=1 to record the full prompt + completion of every call
# to .index/llm_debug-YYYYMMDD.jsonl (keyed by the same run_id/unit as telemetry, so
# "why did it produce/escalate this" is answerable without a re-run). Off by default
# (prompts/completions are large and may carry the user's text).
def _llm_debug_enabled() -> bool:
    return os.getenv("WRITINGAGENT_LLM_DEBUG", "").strip().lower() not in ("", "0", "false", "no")


def _debug_dump(kind: str, model: str, messages: list[dict], output: str) -> None:
    if not _llm_debug_enabled():
        return
    from . import telemetry
    telemetry.log_debug({
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "run_id": _run_id,
        "project": _run_project,
        "unit": getattr(_tl_ctx, "unit", None),
        "kind": kind,
        "model": model,
        "messages": messages,
        "output": output,
    })




def _get_client() -> OpenAI:
    global _client, _include_cost
    # Double-checked lock: concurrent first calls (parallel research/image fetch)
    # must not each build a client.
    if _client is None:
        with _client_lock:
            if _client is None:
                p = providers.REGISTRY[_provider_id]
                base_url = providers.base_url_for(p)
                if not base_url:
                    raise RuntimeError(
                        f"provider '{p.id}' has no base URL - set {p.base_url_env}")
                key = providers.api_key_for(p)
                if key is None and not p.local:
                    envs = " or ".join(p.key_env) or "(none)"
                    raise RuntimeError(
                        f"no API key for {p.name} - set {envs} "
                        f"(or switch provider with /provider)")
                # Only OpenRouter reports real USD cost in usage; other hosts may
                # reject the extra body field, so the cost ask is gated per provider.
                _include_cost = p.reports_cost
                _client = OpenAI(
                    base_url=base_url,
                    api_key=key or "not-needed",   # local servers ignore the key
                    default_headers=dict(p.headers) or None,
                    timeout=_request_timeout,   # a hung connection must not block forever
                    max_retries=0,              # we own retries (classified backoff below)
                )
    return _client


# OpenRouter upstream-provider preference. OpenRouter load-balances a model across several
# upstreams (DeepSeek, Together, Fireworks, ...) and only some support prompt caching - so
# DeepSeek's automatic context cache often never engages. Pinning the order (fallbacks kept
# on) routes to a caching-capable backend. Empty = OpenRouter's default routing.
_openrouter_providers: list[str] = []


def configure_openrouter_providers(spec: str | None) -> None:
    """Set preferred OpenRouter upstreams (comma-separated, e.g. 'DeepSeek') so DeepSeek's
    prompt cache engages. Called at startup from settings.openrouter_providers. '' = off."""
    global _openrouter_providers
    _openrouter_providers = [s.strip() for s in (spec or "").split(",") if s.strip()]


def _cost_kwargs() -> dict:
    """Per-request extra body for OpenRouter: ask it to report usage.cost, and (when set)
    pin the upstream provider order so a caching-capable backend is used. Only OpenRouter
    accepts these fields, so they're gated on _include_cost (true only for OpenRouter)."""
    if not _include_cost:
        return {}
    body: dict = {"usage": {"include": True}}
    if _openrouter_providers:
        body["provider"] = {"order": _openrouter_providers, "allow_fallbacks": True}
    return {"extra_body": body}


# ── Fake mode (offline testing/demo; no API calls) ───────────────────────────
def _fake_mode() -> bool:
    return os.getenv("WRITINGAGENT_FAKE", "").lower() in ("1", "true", "yes")


_FAKE_TEXT = (
    "## Chapter - Placeholder\n\n"
    "Placeholder prose generated in fake mode (WRITINGAGENT_FAKE) for offline testing.\n\n"
    "Maya stood at the window and watched the fog roll in.\n"
)
_FAKE_STRINGS = {"title": "Untitled Chapter", "name": "Maya", "premise": "A placeholder premise."}


def _fake_value(annotation, field_name: str = ""):
    origin = get_origin(annotation)
    if annotation is str:
        return _FAKE_STRINGS.get(field_name, "placeholder")
    if annotation is bool:
        return True
    if annotation is int:
        if field_name == "insight":
            # Default fake = a passing insight score so autonomous runs complete;
            # tests force the low-insight path with WRITINGAGENT_FAKE_INSIGHT.
            override = os.getenv("WRITINGAGENT_FAKE_INSIGHT")
            if override:
                try:
                    return int(override)
                except ValueError:
                    pass
            return 5
        if field_name in ("clarity", "structure", "evidence", "persuasiveness"):
            return 5   # quality scores read as passing in offline runs
        return 1
    if annotation is float:
        if field_name == "confidence":
            override = os.getenv("WRITINGAGENT_FAKE_CONFIDENCE")
            if override:
                try:
                    return float(override)
                except ValueError:
                    pass
        return 0.5
    if origin is list:
        (inner,) = get_args(annotation)
        # Default fake = a clean book (no contradictions) so autonomous runs complete.
        if field_name == "contradictions" and not os.getenv("WRITINGAGENT_FAKE_CONTRADICTION"):
            return []
        return [_fake_value(inner, field_name)]
    if origin is Literal:
        opts = get_args(annotation)
        if field_name == "verdict":
            override = os.getenv("WRITINGAGENT_FAKE_VERDICT")
            if override in opts:
                return override
        return opts[0]
    if origin is Union or origin is types.UnionType:
        args = [a for a in get_args(annotation) if a is not type(None)]
        return _fake_value(args[0], field_name)
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return _fake_instance(annotation)
    return "placeholder"


def _fake_instance(model: type[T]) -> T:
    return model(**{n: _fake_value(f.annotation, n) for n, f in model.model_fields.items()})


# ── Real calls ────────────────────────────────────────────────────────────────
def complete_text(
    model: str,
    system: str,
    user: str,
    *,
    max_tokens: int = 16000,
    temperature: float | None = None,
    frequency_penalty: float | None = None,
    presence_penalty: float | None = None,
    _allow_fallback: bool = True,
) -> str:
    _check_budget()   # kill-switch: before fake mode too, so tests exercise it offline
    if _fake_mode():
        return _FAKE_TEXT
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    t0 = time.time()
    last_err: Exception | None = None
    shrunk = False   # context-overflow recovery fires at most once per call
    for attempt in range(_MAX_ATTEMPTS):
        kwargs: dict = {"model": model, "max_tokens": max_tokens, "messages": messages,
                        **_cost_kwargs()}
        if temperature is not None:
            kwargs["temperature"] = temperature
        if frequency_penalty is not None:
            kwargs["frequency_penalty"] = frequency_penalty
        if presence_penalty is not None:
            kwargs["presence_penalty"] = presence_penalty
        try:
            resp = _get_client().chat.completions.create(**kwargs)
            _record_usage(resp)
            content = (resp.choices[0].message.content or "").strip()
            if content:
                _log_call("text", model, t0, attempt + 1, resp)
                _debug_dump("text", model, messages, content)
                return content
            # Empty content (reasoning ate the budget) - retryable, but only a BIGGER
            # budget can help: re-sending the same max_tokens just truncates again
            # (mirrors complete_structured's finish_reason=length recovery).
            if (resp.choices[0].finish_reason or "") == "length" and max_tokens < 16000:
                max_tokens = min(max_tokens * 2, 16000)
                _log.warning("text: empty output (finish_reason=length) - retrying "
                             "with max_tokens=%d", max_tokens)
            raise _EmptyResponse(
                f"empty response (finish_reason={resp.choices[0].finish_reason})")
        except Exception as e:  # noqa: BLE001
            last_err = e
            if attempt < _MAX_ATTEMPTS - 1:
                if _is_retryable(e):
                    _backoff_sleep(attempt, e)
                    continue
                if not shrunk and _is_context_overflow(e):
                    # Prompt too long for the window: shrink and retry instead of
                    # failing the node (B-013).
                    messages = _shrink_for_context(messages, model)
                    shrunk = True
                    _log.warning("text: context overflow - shrinking prompt and retrying")
                    continue
            break  # non-retryable (e.g. 401/400) or out of attempts - fail fast
    _log_call("text", model, t0, attempt + 1, None, error=str(last_err))
    if _allow_fallback and _fallback_model and model != _fallback_model:
        _log.warning("text: %s failed (%s); falling back to %s", model, last_err, _fallback_model)
        return complete_text(_fallback_model, system, user, max_tokens=max_tokens,
                             temperature=temperature, frequency_penalty=frequency_penalty,
                             presence_penalty=presence_penalty, _allow_fallback=False)
    raise RuntimeError(f"Text completion failed for {model}: {last_err}")


def complete_text_with_tools(
    model: str,
    system: str,
    user: str,
    *,
    tools: list[dict],
    tool_runner,
    max_tool_rounds: int = 2,
    max_tool_calls: int = 4,
    max_tokens: int = 16000,
    temperature: float | None = None,
    frequency_penalty: float | None = None,
    presence_penalty: float | None = None,
) -> str:
    """A chat-completions TOOL-USE loop: the model may call tools mid-generation; each call
    is executed via ``tool_runner(name, args_dict) -> str`` and the result fed back, until the
    model returns prose (or the budget is spent, after which a final no-tools turn forces the
    draft). This is true in-generation tool use - the writer gathers WHILE drafting, not via a
    fixed pre/post step. The whole loop is still ONE episode (invariant §21.0).

    BOUNDED two ways so an eager model can't go on a research spree (a live run showed ~12
    tool calls per draft - cost + latency): ``max_tool_rounds`` caps the request/response
    round-trips, and ``max_tool_calls`` caps the TOTAL tools executed - once either is hit,
    tools are dropped and the model must write. Robust: fake mode returns the placeholder;
    any transport error or a provider that rejects ``tools`` falls back to plain
    ``complete_text`` so a draft is always produced. ``tools`` are OpenAI tool schemas."""
    import json
    _check_budget()
    if _fake_mode():
        return _FAKE_TEXT
    messages: list[dict] = [{"role": "system", "content": system},
                            {"role": "user", "content": user}]
    t0 = time.time()
    extra: dict = {}
    if temperature is not None:
        extra["temperature"] = temperature
    if frequency_penalty is not None:
        extra["frequency_penalty"] = frequency_penalty
    if presence_penalty is not None:
        extra["presence_penalty"] = presence_penalty
    calls_used = 0
    try:
        for round_i in range(max_tool_rounds + 1):
            # Offer tools only while BOTH budgets allow it; otherwise the model must return prose.
            offer_tools = round_i < max_tool_rounds and calls_used < max_tool_calls
            kwargs: dict = {"model": model, "max_tokens": max_tokens, "messages": messages,
                            **extra, **_cost_kwargs()}
            if offer_tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
            resp = _get_client().chat.completions.create(**kwargs)
            _record_usage(resp)
            msg = resp.choices[0].message
            calls = list(getattr(msg, "tool_calls", None) or [])
            if not calls:
                content = (getattr(msg, "content", None) or "").strip()
                if content:
                    _log_call("text+tools", model, t0, round_i + 1, resp)
                    _debug_dump("text+tools", model, messages, content)
                    return content
                break   # no content and no calls -> give up the loop, fall back below
            # Echo the assistant's tool-call turn, then run each tool and feed results back.
            # Every echoed call MUST get a tool response (or the next request is malformed), so
            # the whole round runs; the per-call budget then closes tools on the next round.
            messages.append({
                "role": "assistant", "content": msg.content or "",
                "tool_calls": [{"id": tc.id, "type": "function",
                                "function": {"name": tc.function.name,
                                             "arguments": tc.function.arguments or "{}"}}
                               for tc in calls]})
            for tc in calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except (ValueError, TypeError):
                    args = {}
                try:
                    result = tool_runner(tc.function.name, args) or ""
                except Exception:  # noqa: BLE001 - a tool that errors must not kill the draft
                    result = ""
                messages.append({"role": "tool", "tool_call_id": tc.id,
                                 "content": str(result)[:8000] or "(no result)"})
            calls_used += len(calls)
    except Exception as e:  # noqa: BLE001 - tool use is best-effort; never fail the draft
        _log.warning("tool-use loop failed (%s); falling back to a plain draft", type(e).__name__)
    # Fallback: a plain completion (no tools) always yields a draft.
    return complete_text(model, system, user, max_tokens=max_tokens, temperature=temperature,
                         frequency_penalty=frequency_penalty, presence_penalty=presence_penalty)


def stream_text(
    model: str,
    system: str,
    user: str,
    *,
    max_tokens: int = 2000,
    temperature: float | None = None,
    history: list | None = None,
):
    """Yield text chunks from a streaming completion.

    history: optional list of prior {"role": ..., "content": ...} dicts for multi-turn context.
    In fake mode yields the placeholder text as a single chunk (no network).
    Errors (including mid-stream) propagate to the caller, who already holds the
    partial chunks. Yielding the error as a text chunk would let it pass for
    assistant prose - saved to chat history and command-parsed.

    Honors the run token budget and records usage + telemetry from the final stream
    chunk (B-012), so chat calls no longer bypass the kill-switch and accounting.
    (No automatic retry: a stream can't be replayed once chunks are emitted, so a
    mid-stream failure is left to the caller, who holds the partial output.)
    """
    _check_budget()   # kill-switch: chat must not blow past max_run_tokens either
    if _fake_mode():
        yield _FAKE_TEXT
        return
    raw: list[dict] = [{"role": "system", "content": system}]
    if history:
        raw.extend(history)
    raw.append({"role": "user", "content": user})
    messages = raw
    kwargs: dict = {"model": model, "max_tokens": max_tokens, "messages": messages,
                    "stream": True, "stream_options": {"include_usage": True},
                    **_cost_kwargs()}
    if temperature is not None:
        kwargs["temperature"] = temperature
    t0 = time.time()
    final_usage = None
    parts: list[str] = []
    stream = _get_client().chat.completions.create(**kwargs)
    for chunk in stream:
        u = getattr(chunk, "usage", None)
        if u is not None:
            final_usage = u   # arrives on the terminal chunk (stream_options.include_usage)
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta.content
        if delta:
            parts.append(delta)
            yield delta
    if final_usage is not None:
        shim = types.SimpleNamespace(usage=final_usage)
        _record_usage(shim)
        _log_call("chat", model, t0, 1, shim)
    _debug_dump("chat", model, messages, "".join(parts))


def _strip_schema_noise(obj):
    """Drop pydantic's auto-generated 'title' keys from a JSON Schema. Pydantic emits a
    'title' for every model AND every field (e.g. "title": "Confidence") - pure noise the
    model ignores, ~20-30% of the schema text. Lossless: types/required/enums/$defs stay."""
    if isinstance(obj, dict):
        return {k: _strip_schema_noise(v) for k, v in obj.items() if k != "title"}
    if isinstance(obj, list):
        return [_strip_schema_noise(x) for x in obj]
    return obj


@functools.cache
def _json_instruction(schema: type[BaseModel]) -> str:
    # Cached per schema class - model_json_schema() + dumps is pure CPU repeated on
    # every structured call otherwise. The title-strip keeps it lossless but smaller,
    # and the result is identical every call so it sits inside the cacheable prefix.
    import json
    compact = _strip_schema_noise(schema.model_json_schema())
    return ("Respond with ONLY a single JSON object (no markdown, no prose) that conforms to this "
            "JSON Schema:\n" + json.dumps(compact, separators=(",", ":")))


def _extract_json(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1]
        if t.lower().startswith("json"):
            t = t[4:]
        t = t.strip()
    if not t.startswith("{"):
        i, j = t.find("{"), t.rfind("}")
        if i != -1 and j != -1:
            t = t[i:j + 1]
    return t


def complete_structured(
    model: str,
    system: str,
    user: str,
    schema: type[T],
    *,
    max_tokens: int = 8000,
    temperature: float | None = None,
    _allow_fallback: bool = True,
) -> T:
    _check_budget()   # kill-switch: before fake mode too, so tests exercise it offline
    if _fake_mode():
        return _fake_instance(schema)
    system_full = system + "\n\n" + _json_instruction(schema)
    messages = [{"role": "system", "content": system_full}, {"role": "user", "content": user}]
    t0 = time.time()
    last_err: Exception | None = None
    use_response_format = True   # dropped if a model rejects it (BadRequest)
    shrunk = False               # context-overflow recovery fires at most once per call
    # Reasoning models spend tokens THINKING before they emit the JSON; if that thinking
    # fills max_tokens the reply comes back empty (or cut off mid-object) with
    # finish_reason=length. Re-sending the same too-small budget just truncates again, so the
    # node burns its retries and falls back to a weaker model for nothing. Instead, on a
    # length-truncation we RAISE the cap and retry the same prompt (no repair turn - the
    # prompt was fine). Mirrors the diagram node's 16k token budget for the same reason.
    cur_max = max_tokens
    cap = max(16000, max_tokens)
    for attempt in range(_MAX_ATTEMPTS):
        kwargs: dict = {"model": model, "max_tokens": cur_max, "messages": messages,
                        **_cost_kwargs()}
        if temperature is not None:
            kwargs["temperature"] = temperature
        if use_response_format:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            resp = _get_client().chat.completions.create(**kwargs)
        except Exception as e:  # noqa: BLE001 - transport/API error
            last_err = e
            if attempt < _MAX_ATTEMPTS - 1:
                if _is_retryable(e):
                    _backoff_sleep(attempt, e)
                    continue
                if not shrunk and _is_context_overflow(e):
                    # Prompt too long for the window: shrink and retry (B-013). Checked
                    # before the response_format drop so a genuine overflow isn't
                    # misread as a format rejection.
                    messages = _shrink_for_context(messages, model)
                    shrunk = True
                    _log.warning("structured: context overflow - shrinking prompt and retrying")
                    continue
                if use_response_format and getattr(e, "status_code", None) == 400:
                    # This model likely rejects json_object response_format - drop it.
                    use_response_format = False
                    _log.warning("structured: dropping response_format and retrying")
                    continue
            break  # non-retryable, out of attempts

        _record_usage(resp)
        finish = getattr(resp.choices[0], "finish_reason", None)
        raw = resp.choices[0].message.content or ""
        text = _extract_json(raw)
        try:
            if not text.strip():
                raise _EmptyResponse(f"empty model output (finish_reason={finish})")
            out = schema.model_validate_json(text)
            _log_call("structured", model, t0, attempt + 1, resp)
            _debug_dump("structured", model, messages, raw)
            return out
        except Exception as e:  # noqa: BLE001 - parse/validation/empty
            last_err = e
            if attempt < _MAX_ATTEMPTS - 1:
                if finish == "length" and cur_max < cap:
                    # Output ran out of room (reasoning ate the budget, or the JSON was cut
                    # off mid-object): the prompt was fine, so skip the repair turn and just
                    # give the SAME model more room. Keeps the call on its routed (stronger)
                    # tier instead of degrading to the fallback model.
                    cur_max = min(cap, cur_max * 2)
                    _log.warning("structured: output truncated (finish_reason=length) - "
                                 "raising max_tokens to %d and retrying", cur_max)
                    continue
                # Repair turn: show the model its own bad output + the error and ask
                # for a correction (far more reliable than re-sending the same prompt).
                messages = messages + [
                    {"role": "assistant", "content": raw or "(empty response)"},
                    {"role": "user", "content": (
                        f"Your previous reply was not valid for the schema: {e}\n"
                        "Return ONLY a single corrected JSON object - no prose, no code fences.")},
                ]
                continue
            break
    _log_call("structured", model, t0, attempt + 1, None, error=str(last_err))
    if _allow_fallback and _fallback_model and model != _fallback_model:
        _log.warning("structured: %s failed (%s); falling back to %s",
                     model, last_err, _fallback_model)
        return complete_structured(_fallback_model, system, user, schema,
                                   max_tokens=max_tokens, temperature=temperature,
                                   _allow_fallback=False)
    raise RuntimeError(f"Structured parse failed for {schema.__name__}: {last_err}")
