"""Thin LLM wrapper over OpenRouter (OpenAI-compatible API).

- Text: chat.completions -> message content.
- Structured: JSON mode + Pydantic validation, with one repair retry (portable across
  models; DeepSeek has no Anthropic-style messages.parse).
- Fake mode (BOOK_AGENT_FAKE): returns valid placeholder output, no network. Used by tests.

Set OPENROUTER_API_KEY. Models are configured per node in config/models.yaml.
"""
from __future__ import annotations

import logging
import os
import random
import threading
import time
import types
from typing import Literal, TypeVar, Union, get_args, get_origin

from openai import OpenAI
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

_log = logging.getLogger(__name__)

_BASE_URL = "https://openrouter.ai/api/v1"
_client: OpenAI | None = None
_client_lock = threading.Lock()

# Retry/backoff knobs (network calls dominate runtime — a transient 429/5xx must
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


# ── Headroom context compression (optional) ──────────────────────────────────
_headroom_enabled: bool = False


def configure_headroom(enabled: bool) -> None:
    """Enable/disable headroom compression for all LLM calls (called at startup)."""
    global _headroom_enabled
    _headroom_enabled = enabled


# ── Token-usage telemetry ─────────────────────────────────────────────────────
# Aggregated across every call since the last reset; surfaced at the end of a run.
_usage_lock = threading.Lock()
_usage = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def reset_usage() -> None:
    with _usage_lock:
        _usage.update(calls=0, prompt_tokens=0, completion_tokens=0, total_tokens=0)


def _record_usage(resp) -> None:
    u = getattr(resp, "usage", None)
    if u is None:
        return
    with _usage_lock:
        _usage["calls"] += 1
        _usage["prompt_tokens"] += getattr(u, "prompt_tokens", 0) or 0
        _usage["completion_tokens"] += getattr(u, "completion_tokens", 0) or 0
        _usage["total_tokens"] += getattr(u, "total_tokens", 0) or 0


def current_tokens() -> int:
    """Live total-token tally since the last reset (for progress displays)."""
    with _usage_lock:
        return _usage["total_tokens"]


def usage_summary() -> str | None:
    """One-line tally of tokens spent since the last reset, or None if nothing ran."""
    with _usage_lock:
        if _usage["calls"] == 0:
            return None
        return (f"[usage] {_usage['calls']} LLM calls, "
                f"{_usage['prompt_tokens']:,} prompt + "
                f"{_usage['completion_tokens']:,} completion = "
                f"{_usage['total_tokens']:,} tokens")


# ── Retry classification + backoff ─────────────────────────────────────────────
def _is_retryable(exc: Exception) -> bool:
    """True for transient errors worth retrying (timeouts, connection drops, 429,
    5xx). Auth/permission/bad-request (4xx) are fatal — retrying just wastes calls."""
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
# raise instead of falling back to estimation, so any non-OpenAI slug — e.g. the
# DeepSeek models we run on OpenRouter — makes compression silently no-op. We
# therefore count with a tiktoken-native model; the tally is approximate but the
# compressed output is identical.
_HEADROOM_COUNT_MODEL = "gpt-4o"


def _compress(messages: list[dict], model: str) -> list[dict]:
    """Compress messages via headroom before sending to the LLM.

    Falls back to the original list silently if headroom is not installed or
    compression raises any error — the pipeline must never block on this.
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
    global _client
    # Double-checked lock: concurrent first calls (parallel research/image fetch)
    # must not each build a client.
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = OpenAI(
                    base_url=os.getenv("OPENROUTER_BASE_URL", _BASE_URL),
                    api_key=os.environ["OPENROUTER_API_KEY"],
                    default_headers={"X-Title": "Writing Agent"},
                    timeout=_request_timeout,   # a hung connection must not block forever
                    max_retries=0,              # we own retries (classified backoff below)
                )
    return _client


# ── Fake mode (offline testing/demo; no API calls) ───────────────────────────
def _fake_mode() -> bool:
    return os.getenv("BOOK_AGENT_FAKE", "").lower() in ("1", "true", "yes")


_FAKE_TEXT = (
    "## Chapter — Placeholder\n\n"
    "Placeholder prose generated in fake mode (BOOK_AGENT_FAKE) for offline testing.\n\n"
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
        return 1
    if annotation is float:
        if field_name == "confidence":
            override = os.getenv("BOOK_AGENT_FAKE_CONFIDENCE")
            if override:
                try:
                    return float(override)
                except ValueError:
                    pass
        return 0.5
    if origin is list:
        (inner,) = get_args(annotation)
        # Default fake = a clean book (no contradictions) so autonomous runs complete.
        if field_name == "contradictions" and not os.getenv("BOOK_AGENT_FAKE_CONTRADICTION"):
            return []
        return [_fake_value(inner, field_name)]
    if origin is Literal:
        opts = get_args(annotation)
        if field_name == "verdict":
            override = os.getenv("BOOK_AGENT_FAKE_VERDICT")
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
    thinking: bool = False,  # accepted for API parity; reasoning is model-internal
) -> str:
    if _fake_mode():
        return _FAKE_TEXT
    messages = _compress(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        model,
    )
    last_err: Exception | None = None
    for attempt in range(_MAX_ATTEMPTS):
        kwargs: dict = {"model": model, "max_tokens": max_tokens, "messages": messages}
        if temperature is not None:
            kwargs["temperature"] = temperature
        try:
            resp = _get_client().chat.completions.create(**kwargs)
            _record_usage(resp)
            content = (resp.choices[0].message.content or "").strip()
            if content:
                return content
            # Empty content (reasoning ate the budget) — retryable.
            raise _EmptyResponse(
                f"empty response (finish_reason={resp.choices[0].finish_reason})")
        except Exception as e:  # noqa: BLE001
            last_err = e
            if attempt < _MAX_ATTEMPTS - 1 and _is_retryable(e):
                _backoff_sleep(attempt, e)
                continue
            break  # non-retryable (e.g. 401/400) or out of attempts — fail fast
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
    On any error during streaming, yields an error message chunk and stops.
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
    try:
        stream = _get_client().chat.completions.create(**kwargs)
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
    except Exception as e:  # noqa: BLE001
        yield f"\n_(stream error: {e})_"


def _json_instruction(schema: type[BaseModel]) -> str:
    import json
    return ("Respond with ONLY a single JSON object (no markdown, no prose) that conforms to this "
            "JSON Schema:\n" + json.dumps(schema.model_json_schema()))


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
    if _fake_mode():
        return _fake_instance(schema)
    system_full = system + "\n\n" + _json_instruction(schema)
    messages = _compress(
        [{"role": "system", "content": system_full}, {"role": "user", "content": user}],
        model,
    )
    last_err: Exception | None = None
    use_response_format = True   # dropped if a model rejects it (BadRequest)
    for attempt in range(_MAX_ATTEMPTS):
        kwargs: dict = {"model": model, "max_tokens": max_tokens, "messages": messages}
        if temperature is not None:
            kwargs["temperature"] = temperature
        if use_response_format:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            resp = _get_client().chat.completions.create(**kwargs)
        except Exception as e:  # noqa: BLE001 — transport/API error
            last_err = e
            if attempt < _MAX_ATTEMPTS - 1:
                if _is_retryable(e):
                    _backoff_sleep(attempt, e)
                    continue
                if use_response_format and getattr(e, "status_code", None) == 400:
                    # This model likely rejects json_object response_format — drop it.
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
            return schema.model_validate_json(text)
        except Exception as e:  # noqa: BLE001 — parse/validation/empty
            last_err = e
            if attempt < _MAX_ATTEMPTS - 1:
                # Repair turn: show the model its own bad output + the error and ask
                # for a correction (far more reliable than re-sending the same prompt).
                messages = messages + [
                    {"role": "assistant", "content": raw or "(empty response)"},
                    {"role": "user", "content": (
                        f"Your previous reply was not valid for the schema: {e}\n"
                        "Return ONLY a single corrected JSON object — no prose, no code fences.")},
                ]
                continue
            break
    raise RuntimeError(f"Structured parse failed for {schema.__name__}: {last_err}")
