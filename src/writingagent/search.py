"""Web search for the Researcher node (plan §4).

Uses duckduckgo-search (no API key, no cost). Returns an empty list on any failure so
the pipeline never blocks on a network error.

Install: pip install duckduckgo-search  (already in requirements.txt)
"""
from __future__ import annotations

import os
import threading
from dataclasses import dataclass


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


_CACHE_TTL_S = 7 * 24 * 3600   # web results are stable enough to reuse for a week

# One DDGS session per thread: the multi-query fan-out otherwise pays a fresh TLS
# handshake per query. Thread-local (not shared) because DDGS isn't documented as
# thread-safe. Reset on error so a broken session can't poison later searches.
_tl = threading.local()


def _ddgs():
    inst = getattr(_tl, "ddgs", None)
    if inst is None:
        try:
            # Try the new package name first (renamed from duckduckgo_search to ddgs)
            from ddgs import DDGS
        except ImportError:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                from duckduckgo_search import DDGS
        inst = _tl.ddgs = DDGS()
    return inst


def web_search(query: str, max_results: int = 5) -> list[SearchResult]:
    """Search the web via DuckDuckGo. Returns [] in fake mode or on any error.

    Non-empty results are cached on disk (keyed by query + count) so resumes and
    near-identical sections don't re-hit the network or burn rate-limit budget.
    """
    if os.getenv("WRITINGAGENT_FAKE", "").lower() in ("1", "true", "yes"):
        return []

    from . import cache
    cached = cache.get("search", (query, max_results), max_age_s=_CACHE_TTL_S)
    if cached is not None:
        return [SearchResult(**r) for r in cached]

    try:
        raw = list(_ddgs().text(query, max_results=max_results))
        results = [SearchResult(title=r["title"], url=r["href"], snippet=r["body"]) for r in raw]
    except Exception:  # noqa: BLE001 - network/rate-limit errors are non-fatal
        _tl.ddgs = None   # drop a possibly-broken session; rebuild on next call
        return []

    if results:
        cache.put("search", (query, max_results), [r.__dict__ for r in results])
    return results


def format_results(results: list[SearchResult]) -> str:
    """Compact context block for injecting results into the researcher prompt."""
    if not results:
        return ""
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"[{i}] {r.title}\n    {r.url}\n    {r.snippet}")
    return "\n\n".join(lines)


def build_query(plan, blueprint) -> str:
    """Build a focused search query from the book plan + chapter blueprint."""
    parts = [plan.genre, blueprint.title, blueprint.purpose.split(".")[0]]
    return " ".join(p for p in parts if p)[:200]
