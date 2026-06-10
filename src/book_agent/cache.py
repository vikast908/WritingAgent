"""Small on-disk cache for expensive, repeatable network/LLM results.

Used for web-search results and generated SVG diagrams: both are slow (network /
LLM) and frequently re-requested across resumes and near-identical sections.
Entries live under .index/cache/ (derived, gitignored) and carry a timestamp so
stale results can expire. Any cache error is swallowed — caching must never be
able to break the pipeline.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from . import brain


def _dir():
    # Resolved per-call (not at import) so tests can redirect brain.INDEX_DIR.
    return brain.INDEX_DIR / "cache"


def _path(namespace: str, key_parts):
    raw = "::".join(str(p) for p in key_parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
    return _dir() / f"{namespace}_{digest}.json"


def get(namespace: str, key_parts, *, max_age_s: float | None = None) -> Any | None:
    """Return the cached value, or None if absent/expired/unreadable."""
    p = _path(namespace, key_parts)
    if not p.exists():
        return None
    try:
        entry = json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — corrupt cache file: treat as a miss
        return None
    if max_age_s is not None and (time.time() - entry.get("ts", 0)) > max_age_s:
        return None
    return entry.get("value")


def put(namespace: str, key_parts, value: Any) -> None:
    """Store a JSON-serialisable value; never raises."""
    try:
        _dir().mkdir(parents=True, exist_ok=True)
        _path(namespace, key_parts).write_text(
            json.dumps({"ts": time.time(), "value": value}, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:  # noqa: BLE001 — caching is best-effort
        pass
