"""Web search for the Researcher node (plan §4).

Pluggable backends, selected by the `search_provider` setting. DuckDuckGo is the
keyless default and also the universal fallback; the rest need an API key (read from
the environment, following providers.py's convention) and are model-host-agnostic -
none of them are tied to the LLM provider:

  duckduckgo  ddgs           no key         free, default
  firecrawl   FIRECRAWL_API_KEY             paid; pairs with Firecrawl page scraping
  tavily      TAVILY_API_KEY               built for LLM agents (clean snippets)
  brave       BRAVE_API_KEY                independent index
  serpapi     SERPAPI_API_KEY              Google results via SerpAPI
  exa         EXA_API_KEY                  neural/semantic search
  parallel    PARALLEL_API_KEY             Parallel web search (beta)

Contract: search NEVER blocks a run. Any backend error (or a selected provider whose
key is absent) degrades to DuckDuckGo, and DuckDuckGo failing returns []. Non-empty
results are cached on disk (keyed by provider + query + count) so resumes and near-
identical sections don't re-hit the network.
"""
from __future__ import annotations

import json
import os
import threading
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


_CACHE_TTL_S = 7 * 24 * 3600   # web results are stable enough to reuse for a week
_SNIPPET_CAP = 400             # keep snippets short so N results don't blow the prompt

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


# ── Keyed backend registry ──────────────────────────────────────────────────────
@dataclass
class _Backend:
    fn: Callable[[str, int], list[SearchResult]]
    key_env: str


_BACKENDS: dict[str, _Backend] = {}


def _register(name: str, key_env: str):
    def deco(fn):
        _BACKENDS[name] = _Backend(fn, key_env)
        return fn
    return deco


def _key(env: str) -> str:
    return os.getenv(env, "").strip()


def _http_json(url: str, *, method: str = "GET", headers: dict | None = None,
               body: dict | None = None, timeout: int = 20) -> dict:
    """Minimal stdlib JSON HTTP call (no extra deps). Raises on any error; every
    caller runs under web_search's try/except, so a raise degrades to the fallback."""
    data = json.dumps(body).encode() if body is not None else None
    hdrs = {"Accept": "application/json", **(headers or {})}
    if data is not None:
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, method=method, headers=hdrs)
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed https hosts
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _mk(title: str, url: str, snippet: str) -> SearchResult | None:
    url = (url or "").strip()
    if not url:
        return None
    return SearchResult(title=(title or url).strip(),
                        url=url, snippet=(snippet or "")[:_SNIPPET_CAP].strip())


FIRECRAWL_BASE = "https://api.firecrawl.dev"


def firecrawl_key() -> str:
    return _key("FIRECRAWL_API_KEY")


@_register("firecrawl", "FIRECRAWL_API_KEY")
def _firecrawl_search(query: str, max_results: int) -> list[SearchResult]:
    """Firecrawl search API -> SearchResults. [] on any failure (caller falls back)."""
    key = firecrawl_key()
    if not key:
        return []
    data = _http_json(FIRECRAWL_BASE + "/v1/search", method="POST",
                      headers={"Authorization": f"Bearer {key}"},
                      body={"query": query, "limit": max_results})
    items = data.get("data") or []
    if isinstance(items, dict):                # v2 response shape: {"web": [...]}
        items = items.get("web") or []
    out = [_mk(r.get("title"), r.get("url"), r.get("description")) for r in items[:max_results]]
    return [r for r in out if r]


@_register("tavily", "TAVILY_API_KEY")
def _tavily_search(query: str, max_results: int) -> list[SearchResult]:
    key = _key("TAVILY_API_KEY")
    if not key:
        return []
    data = _http_json("https://api.tavily.com/search", method="POST",
                      headers={"Authorization": f"Bearer {key}"},
                      body={"query": query, "max_results": max_results,
                            "search_depth": "basic"})
    out = [_mk(r.get("title"), r.get("url"), r.get("content"))
           for r in (data.get("results") or [])[:max_results]]
    return [r for r in out if r]


@_register("brave", "BRAVE_API_KEY")
def _brave_search(query: str, max_results: int) -> list[SearchResult]:
    import urllib.parse
    key = _key("BRAVE_API_KEY")
    if not key:
        return []
    qs = urllib.parse.urlencode({"q": query, "count": max_results})
    data = _http_json(f"https://api.search.brave.com/res/v1/web/search?{qs}",
                      headers={"X-Subscription-Token": key})
    items = ((data.get("web") or {}).get("results")) or []
    out = [_mk(r.get("title"), r.get("url"), r.get("description")) for r in items[:max_results]]
    return [r for r in out if r]


@_register("serpapi", "SERPAPI_API_KEY")
def _serpapi_search(query: str, max_results: int) -> list[SearchResult]:
    import urllib.parse
    key = _key("SERPAPI_API_KEY")
    if not key:
        return []
    qs = urllib.parse.urlencode({"engine": "google", "q": query,
                                 "num": max_results, "api_key": key})
    data = _http_json(f"https://serpapi.com/search.json?{qs}")
    out = [_mk(r.get("title"), r.get("link"), r.get("snippet"))
           for r in (data.get("organic_results") or [])[:max_results]]
    return [r for r in out if r]


@_register("exa", "EXA_API_KEY")
def _exa_search(query: str, max_results: int) -> list[SearchResult]:
    key = _key("EXA_API_KEY")
    if not key:
        return []
    data = _http_json("https://api.exa.ai/search", method="POST",
                      headers={"x-api-key": key},
                      body={"query": query, "numResults": max_results,
                            "contents": {"text": {"maxCharacters": _SNIPPET_CAP}}})
    out = [_mk(r.get("title"), r.get("url"), r.get("text") or r.get("snippet"))
           for r in (data.get("results") or [])[:max_results]]
    return [r for r in out if r]


@_register("parallel", "PARALLEL_API_KEY")
def _parallel_search(query: str, max_results: int) -> list[SearchResult]:
    """Parallel web search (beta endpoint). Excerpts join into the snippet."""
    key = _key("PARALLEL_API_KEY")
    if not key:
        return []
    data = _http_json("https://api.parallel.ai/v1beta/search", method="POST",
                      headers={"x-api-key": key},
                      body={"objective": query, "search_queries": [query],
                            "processor": "base", "max_results": max_results})
    out = []
    for r in (data.get("results") or [])[:max_results]:
        exc = r.get("excerpts") or []
        snippet = " ".join(exc) if isinstance(exc, list) else str(exc)
        out.append(_mk(r.get("title"), r.get("url"), snippet or r.get("snippet", "")))
    return [r for r in out if r]


# The selectable providers: duckduckgo (keyless, also the universal fallback) + the keyed set.
PROVIDERS: tuple[str, ...] = ("duckduckgo", *_BACKENDS.keys())


def provider() -> str:
    """The active, USABLE search provider. A keyed provider whose key is absent (or an
    unknown name) degrades to duckduckgo - the module contract: search never blocks."""
    try:
        from .config import load_settings
        p = (getattr(load_settings(), "search_provider", "") or "duckduckgo").lower()
    except Exception:  # noqa: BLE001 - unreadable settings must not kill a search
        p = "duckduckgo"
    if p == "duckduckgo":
        return p
    b = _BACKENDS.get(p)
    if b and _key(b.key_env):
        return p
    return "duckduckgo"


def _ddg_results(query: str, max_results: int) -> list[SearchResult]:
    """DuckDuckGo via the thread-local session. Resets the session on error so a
    broken one can't poison later calls; returns [] on failure."""
    try:
        raw = list(_ddgs().text(query, max_results=max_results))
        out = [_mk(r.get("title"), r.get("href"), r.get("body")) for r in raw]
        return [r for r in out if r]
    except Exception:  # noqa: BLE001 - network/rate-limit errors are non-fatal
        _tl.ddgs = None   # drop a possibly-broken session; rebuild on next call
        return []


def web_search(query: str, max_results: int = 5) -> list[SearchResult]:
    """Search the web via the configured provider. Returns [] in fake mode or on error.

    A keyed provider that errors or returns nothing falls back to DuckDuckGo before
    giving up. Non-empty results are cached (keyed by provider + query + count).
    """
    if os.getenv("WRITINGAGENT_FAKE", "").lower() in ("1", "true", "yes"):
        return []

    from . import cache
    prov = provider()
    cached = cache.get("search", (prov, query, max_results), max_age_s=_CACHE_TTL_S)
    if cached is not None:
        return [SearchResult(**r) for r in cached]

    results: list[SearchResult] = []
    backend = _BACKENDS.get(prov)
    if backend is not None:
        try:
            results = backend.fn(query, max_results)
        except Exception:  # noqa: BLE001 - fall back to the free provider
            results = []
    if not results:
        results = _ddg_results(query, max_results)
        if not results:
            return []

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
