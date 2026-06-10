"""Semantic embeddings for genre-relevance skill retrieval (plan §10).

Uses sentence-transformers (local; no API cost; no per-call latency after the first run).
Falls back silently to lexical scoring (retrieval.py Jaccard) if the library is absent.

Embeddings are cached by SHA-256 hash in .index/embed_cache.json — computed once per
unique text, reused across process restarts and runs.

Install:  pip install sentence-transformers
          (downloads ~80 MB all-MiniLM-L6-v2 on first use)
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

try:
    from sentence_transformers import SentenceTransformer as _ST
    _HAS_ST = True
except ImportError:
    _HAS_ST = False

_MODEL_NAME = "all-MiniLM-L6-v2"   # 80 MB; fast; strong for short genre/tag phrases
_model = None                        # lazy-loaded on first embed call


def available() -> bool:
    """True when sentence-transformers is installed and embeddings can be computed."""
    return _HAS_ST


def _get_model():
    global _model
    if _model is None:
        _model = _ST(_MODEL_NAME)
    return _model


def _key(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:20]


def embed_texts(texts: list[str], cache_path: Path | None = None) -> list[list[float]]:
    """Embed a list of texts, reading/writing a disk cache to avoid recomputation.

    Raises ImportError if sentence-transformers is not installed.
    """
    if not _HAS_ST:
        raise ImportError(
            "sentence-transformers is not installed. "
            "Enable embeddings with: pip install sentence-transformers"
        )
    cache: dict = {}
    if cache_path and cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            cache = {}

    keys = [_key(t) for t in texts]
    miss = [i for i, k in enumerate(keys) if k not in cache]
    if miss:
        model = _get_model()
        vecs = model.encode([texts[i] for i in miss])
        for j, i in enumerate(miss):
            cache[keys[i]] = vecs[j].tolist()
        if cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(cache), encoding="utf-8")

    return [cache[k] for k in keys]


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0
