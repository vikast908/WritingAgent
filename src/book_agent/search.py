"""Web search for the Researcher node (plan §4).

Uses duckduckgo-search (no API key, no cost). Returns an empty list on any failure so
the pipeline never blocks on a network error.

Install: pip install duckduckgo-search  (already in requirements.txt)
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


def web_search(query: str, max_results: int = 5) -> list[SearchResult]:
    """Search the web via DuckDuckGo. Returns [] in fake mode or on any error."""
    if os.getenv("BOOK_AGENT_FAKE", "").lower() in ("1", "true", "yes"):
        return []
    try:
        # Try the new package name first (renamed from duckduckgo_search to ddgs)
        try:
            from ddgs import DDGS
        except ImportError:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            raw = list(ddgs.text(query, max_results=max_results))
        return [SearchResult(title=r["title"], url=r["href"], snippet=r["body"]) for r in raw]
    except Exception:  # noqa: BLE001 — network/rate-limit errors are non-fatal
        return []


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
