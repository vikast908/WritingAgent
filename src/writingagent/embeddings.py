"""Semantic embeddings for genre-relevance skill retrieval (plan §10).

Uses sentence-transformers (local; no API cost; no per-call latency after the first run).
Falls back silently to lexical scoring (retrieval.py Jaccard) if the library is absent.

Embeddings are cached by SHA-256 hash in .index/embed_cache.json - computed once per
unique text, reused across process restarts and runs.

Install:  pip install sentence-transformers
          (downloads ~80 MB all-MiniLM-L6-v2 on first use)
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import threading
from pathlib import Path

from . import brain

_MODEL_NAME = "all-MiniLM-L6-v2"   # 80 MB; fast; strong for short genre/tag phrases
_model = None                        # lazy-loaded on first embed call
_cache_lock = threading.Lock()       # serialize the read-modify-write of the shared cache file
#                                      (book prefetch embeds chapters n and n+1 concurrently)


def available() -> bool:
    """True when sentence-transformers is installed and embeddings can be computed.

    Checked via find_spec - actually importing sentence-transformers pulls in torch
    (multi-second); that cost is deferred to the first real embed call.
    """
    return importlib.util.find_spec("sentence_transformers") is not None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer as _ST
        _model = _ST(_MODEL_NAME)
    return _model


def _key(text: str) -> str:
    # Namespaced by model (A-017): a cache built with one embedding model must never serve
    # a vector to another - different models live in different vector spaces, so a bare
    # text hash would silently return incompatible vectors if _MODEL_NAME ever changes.
    return hashlib.sha256(f"{_MODEL_NAME}\x00{text}".encode()).hexdigest()[:20]


def embed_texts(texts: list[str], cache_path: Path | None = None) -> list[list[float]]:
    """Embed a list of texts, reading/writing a disk cache to avoid recomputation.

    Raises ImportError if sentence-transformers is not installed.
    """
    if not available():
        raise ImportError(
            "sentence-transformers is not installed. "
            "Enable embeddings with: pip install sentence-transformers"
        )
    keys = [_key(t) for t in texts]
    # The read, compute, and write run under one lock so concurrent embed calls (the book
    # prefetches adjacent chapters in parallel) can't lose each other's cache entries to a
    # last-writer-wins overwrite; the disk write is atomic (B-005).
    with _cache_lock:
        cache: dict = {}
        if cache_path and cache_path.exists():
            try:
                cache = json.loads(cache_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                cache = {}

        miss = [i for i, k in enumerate(keys) if k not in cache]
        if miss:
            model = _get_model()
            vecs = model.encode([texts[i] for i in miss])
            for j, i in enumerate(miss):
                cache[keys[i]] = vecs[j].tolist()
            if cache_path:
                brain.write_text(cache_path, json.dumps(cache))

        return [cache[k] for k in keys]


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors (numpy when available, else pure Python)."""
    try:
        import numpy as np
        va, vb = np.asarray(a), np.asarray(b)
        na, nb = float(np.linalg.norm(va)), float(np.linalg.norm(vb))
        return float(va @ vb) / (na * nb) if na and nb else 0.0
    except ImportError:
        dot = sum(x * y for x, y in zip(a, b, strict=False))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(x * x for x in b) ** 0.5
        return dot / (na * nb) if na and nb else 0.0
