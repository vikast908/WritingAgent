"""Thin LLM wrapper over OpenRouter (OpenAI-compatible API).

- Text: chat.completions -> message content.
- Structured: JSON mode + Pydantic validation, with one repair retry (portable across
  models; DeepSeek has no Anthropic-style messages.parse).
- Fake mode (BOOK_AGENT_FAKE): returns valid placeholder output, no network. Used by tests.

Set OPENROUTER_API_KEY. Models are configured per node in config/models.yaml.
"""
from __future__ import annotations

import os
import types
from typing import Literal, Type, TypeVar, Union, get_args, get_origin

from openai import OpenAI
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

_BASE_URL = "https://openrouter.ai/api/v1"
_client: OpenAI | None = None

# ── Headroom context compression (optional) ──────────────────────────────────
_headroom_enabled: bool = False


def configure_headroom(enabled: bool) -> None:
    """Enable/disable headroom compression for all LLM calls (called at startup)."""
    global _headroom_enabled
    _headroom_enabled = enabled


def _compress(messages: list[dict], model: str) -> list[dict]:
    """Compress messages via headroom before sending to the LLM.

    Falls back to the original list silently if headroom is not installed or
    compression raises any error — the pipeline must never block on this.
    """
    if not _headroom_enabled:
        return messages
    try:
        from headroom import compress as hr_compress
        result = hr_compress(messages, model=model)
        if result.tokens_saved > 0:
            import logging
            logging.getLogger(__name__).info(
                "headroom: %d → %d tokens (saved %d, %.0f%%)",
                result.tokens_before, result.tokens_after,
                result.tokens_saved, result.compression_ratio * 100,
            )
        return result.messages
    except Exception:
        return messages


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            base_url=os.getenv("OPENROUTER_BASE_URL", _BASE_URL),
            api_key=os.environ["OPENROUTER_API_KEY"],
            default_headers={"X-Title": "Writing Agent"},
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


def _fake_instance(model: Type[T]) -> T:
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
    for _ in range(3):  # reasoning models can return empty content on a truncated turn
        kwargs: dict = {"model": model, "max_tokens": max_tokens, "messages": messages}
        if temperature is not None:
            kwargs["temperature"] = temperature
        try:
            resp = _get_client().chat.completions.create(**kwargs)
            content = (resp.choices[0].message.content or "").strip()
            if content:
                return content
            last_err = RuntimeError(
                f"empty response (finish_reason={resp.choices[0].finish_reason})")
        except Exception as e:  # noqa: BLE001
            last_err = e
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


def _json_instruction(schema: Type[BaseModel]) -> str:
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
    schema: Type[T],
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
    for attempt in range(3):
        kwargs: dict = {"model": model, "max_tokens": max_tokens, "messages": messages}
        if temperature is not None:
            kwargs["temperature"] = temperature
        if attempt == 0:
            kwargs["response_format"] = {"type": "json_object"}  # dropped on retry if unsupported
        try:
            resp = _get_client().chat.completions.create(**kwargs)
            text = _extract_json(resp.choices[0].message.content or "")
            if not text.strip():  # truncated/empty (e.g. reasoning ate the token budget)
                raise ValueError(
                    f"empty model output (finish_reason={resp.choices[0].finish_reason})")
            return schema.model_validate_json(text)
        except Exception as e:  # noqa: BLE001 — parse error / empty / unsupported response_format
            last_err = e
    raise RuntimeError(f"Structured parse failed for {schema.__name__}: {last_err}")
