"""Thin LLM wrapper over any OpenAI-compatible provider.

- Text: chat.completions -> message content.
- Structured: JSON mode + Pydantic validation, with one repair retry (portable across
  models; DeepSeek has no Anthropic-style messages.parse).
- Fake mode (WRITINGAGENT_FAKE): returns valid placeholder output, no network. Used by tests.

The active provider (OpenRouter by default) comes from `providers.py`; switch it
with `/provider`, the `provider` setting, or WRITINGAGENT_PROVIDER. Each provider
reads its own key env var (OPENROUTER_API_KEY, DEEPSEEK_API_KEY, ...). Models are
configured per node in config/models.yaml.
"""
from __future__ import annotations

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


# ── Headroom context compression (optional) ──────────────────────────────────
_headroom_enabled: bool = False


def configure_headroom(enabled: bool) -> None:
    """Enable/disable headroom compression for all LLM calls (called at startup)."""
    global _headroom_enabled
    _headroom_enabled = enabled


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


# headroom uses the model name only to select a tokenizer for tallying savings;
# its compression transforms (SmartCrusher, ContentRouter, …) are model-agnostic.
# headroom's non-tiktoken (HuggingFace) backends hard-import `transformers` and
# raise instead of falling back to estimation, so any non-OpenAI slug - e.g. the
# DeepSeek models we run on OpenRouter - makes compression silently no-op. We
# therefore count with a tiktoken-native model; the tally is approximate but the
# compressed output is identical.
_HEADROOM_COUNT_MODEL = "gpt-4o"


def _compress(messages: list[dict], model: str) -> list[dict]:
    """Compress messages via headroom before sending to the LLM.

    Falls back to the original list silently if headroom is not installed or
    compression raises any error - the pipeline must never block on this.
    """
    if not _headroom_enabled:
        return messages
    try:
        from headroom import compress as hr_compress
        result = hr_compress(messages, model=_HEADROOM_COUNT_MODEL)
        if result.tokens_saved > 0:
            _log.info(
                "headroom: %d -> %d tokens (saved %d, %.0f%%)",
                result.tokens_before, result.tokens_after,
                result.tokens_saved, result.compression_ratio * 100,
            )
        return result.messages
    except Exception:
        return messages


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
) -> str:
    _check_budget()   # kill-switch: before fake mode too, so tests exercise it offline
    if _fake_mode():
        return _FAKE_TEXT
    messages = _compress(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        model,
    )
    t0 = time.time()
    last_err: Exception | None = None
    for attempt in range(_MAX_ATTEMPTS):
        kwargs: dict = {"model": model, "max_tokens": max_tokens, "messages": messages,
                        **_cost_kwargs()}
        if temperature is not None:
            kwargs["temperature"] = temperature
        try:
            resp = _get_client().chat.completions.create(**kwargs)
            _record_usage(resp)
            content = (resp.choices[0].message.content or "").strip()
            if content:
                _log_call("text", model, t0, attempt + 1, resp)
                return content
            # Empty content (reasoning ate the budget) - retryable.
            raise _EmptyResponse(
                f"empty response (finish_reason={resp.choices[0].finish_reason})")
        except Exception as e:  # noqa: BLE001
            last_err = e
            if attempt < _MAX_ATTEMPTS - 1 and _is_retryable(e):
                _backoff_sleep(attempt, e)
                continue
            break  # non-retryable (e.g. 401/400) or out of attempts - fail fast
    _log_call("text", model, t0, attempt + 1, None, error=str(last_err))
    raise RuntimeError(f"Text completion failed for {model}: {last_err}")


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
    """
    if _fake_mode():
        yield _FAKE_TEXT
        return
    raw: list[dict] = [{"role": "system", "content": system}]
    if history:
        raw.extend(history)
    raw.append({"role": "user", "content": user})
    messages = _compress(raw, model)
    kwargs: dict = {"model": model, "max_tokens": max_tokens, "messages": messages, "stream": True}
    if temperature is not None:
        kwargs["temperature"] = temperature
    stream = _get_client().chat.completions.create(**kwargs)
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


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
) -> T:
    _check_budget()   # kill-switch: before fake mode too, so tests exercise it offline
    if _fake_mode():
        return _fake_instance(schema)
    system_full = system + "\n\n" + _json_instruction(schema)
    messages = _compress(
        [{"role": "system", "content": system_full}, {"role": "user", "content": user}],
        model,
    )
    t0 = time.time()
    last_err: Exception | None = None
    use_response_format = True   # dropped if a model rejects it (BadRequest)
    for attempt in range(_MAX_ATTEMPTS):
        kwargs: dict = {"model": model, "max_tokens": max_tokens, "messages": messages,
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
                if use_response_format and getattr(e, "status_code", None) == 400:
                    # This model likely rejects json_object response_format - drop it.
                    use_response_format = False
                    _log.warning("structured: dropping response_format and retrying")
                    continue
            break  # non-retryable, out of attempts

        _record_usage(resp)
        raw = resp.choices[0].message.content or ""
        text = _extract_json(raw)
        try:
            if not text.strip():
                raise _EmptyResponse(
                    f"empty model output (finish_reason={resp.choices[0].finish_reason})")
            out = schema.model_validate_json(text)
            _log_call("structured", model, t0, attempt + 1, resp)
            return out
        except Exception as e:  # noqa: BLE001 - parse/validation/empty
            last_err = e
            if attempt < _MAX_ATTEMPTS - 1:
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
    raise RuntimeError(f"Structured parse failed for {schema.__name__}: {last_err}")
