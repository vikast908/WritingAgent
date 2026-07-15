"""Web search for the Researcher node (plan §4).

Two providers, selected by the `search_provider` setting:
- **duckduckgo** (default): duckduckgo-search - no API key, no cost.
- **firecrawl**: the Firecrawl search API (needs FIRECRAWL_API_KEY) - paid, but
  more reliable under volume and pairs with Firecrawl page scraping in deep_research.

Either way, returns an empty list on any failure so the pipeline never blocks on a
network error; firecrawl additionally falls back to duckduckgo before giving up.
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


FIRECRAWL_BASE = "https://api.firecrawl.dev"


def firecrawl_key() -> str:
    return os.getenv("FIRECRAWL_API_KEY", "").strip()


def provider() -> str:
    """The active search provider ('duckduckgo' | 'firecrawl'), validated.

    Selecting firecrawl without FIRECRAWL_API_KEY degrades to duckduckgo (the
    module contract: search never blocks a run)."""
    try:
        from .config import load_settings
        p = (getattr(load_settings(), "search_provider", "") or "duckduckgo").lower()
    except Exception:  # noqa: BLE001 - unreadable settings must not kill a search
        p = "duckduckgo"
    if p == "firecrawl" and not firecrawl_key():
        return "duckduckgo"
    return p if p in ("duckduckgo", "firecrawl") else "duckduckgo"


def _firecrawl_search(query: str, max_results: int) -> list[SearchResult]:
    """Firecrawl search API -> SearchResults. [] on any failure (caller falls back)."""
    import json
    import urllib.request
    key = firecrawl_key()
    if not key:
        return []
    body = json.dumps({"query": query, "limit": max_results}).encode()
    req = urllib.request.Request(
        FIRECRAWL_BASE + "/v1/search", data=body, method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310 - fixed https host
        data = json.loads(resp.read().decode("utf-8", errors="replace"))
    items = data.get("data") or []
    if isinstance(items, dict):                # v2 response shape: {"web": [...]}
        items = items.get("web") or []
    out: list[SearchResult] = []
    for r in items[:max_results]:
        url = (r.get("url") or "").strip()
        if url:
            out.append(SearchResult(title=r.get("title") or url,
                                    url=url, snippet=r.get("description") or ""))
    return out


def web_search(query: str, max_results: int = 5) -> list[SearchResult]:
    """Search the web via the configured provider. Returns [] in fake mode or on error.

    Non-empty results are cached on disk (keyed by provider + query + count) so resumes
    and near-identical sections don't re-hit the network or burn rate-limit budget.
    A firecrawl failure falls back to duckduckgo before returning [].
    """
    if os.getenv("WRITINGAGENT_FAKE", "").lower() in ("1", "true", "yes"):
        return []

    from . import cache
    prov = provider()
    cached = cache.get("search", (prov, query, max_results), max_age_s=_CACHE_TTL_S)
    if cached is not None:
        return [SearchResult(**r) for r in cached]

    results: list[SearchResult] = []
    if prov == "firecrawl":
        try:
            results = _firecrawl_search(query, max_results)
        except Exception:  # noqa: BLE001 - fall back to the free provider
            results = []
    if not results:
        try:
            raw = list(_ddgs().text(query, max_results=max_results))
            results = [SearchResult(title=r["title"], url=r["href"], snippet=r["body"])
                       for r in raw]
        except Exception:  # noqa: BLE001 - network/rate-limit errors are non-fatal
            _tl.ddgs = None   # drop a possibly-broken session; rebuild on next call
            return []

    if results:
        cache.put("search", (prov, query, max_results), [r.__dict__ for r in results])
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
