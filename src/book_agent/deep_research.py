"""Deep multi-source researcher (plan §4 / §15 'Deep Researcher').

The shallow researcher (`search.web_search` + `nodes.research`) feeds the writer
DuckDuckGo *snippets* from a single query. This module goes deeper: it fans out
several distinct queries concurrently, dedupes the hits and caps how many come from
any one domain (so the brief isn't six links from the same site), then fetches and
extracts the actual *page text* of the top sources. The LLM synthesis node then reads
across full pages, not snippets - so it can pull specific numbers, quotes, and note
where sources disagree.

This module is LLM-free. Page fetching prefers the optional **Scrapo** backend
(github.com/vikast908/Scrapo) when it's installed - it returns clean markdown and
escalates HTTP -> browser -> stealth, reaching pages a naive fetch can't - and falls
back to a pure-stdlib path (urllib + html.parser) otherwise, so the module stays
portable across Linux/macOS/Windows with zero required deps. The orchestrator composes
it with the query-planner and synthesis nodes. Every network op is best-effort - any
failure degrades to the stdlib path, a snippet, or an empty result, never an exception
(mirrors the pipeline's "network errors are non-fatal" contract).
"""
from __future__ import annotations

import os
import re
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urlparse

from . import cache, concurrency
from .search import web_search

_FETCH_TTL_S = 7 * 24 * 3600        # fetched page text is stable enough to reuse for a week
_FETCH_TIMEOUT = 12.0               # per-page network timeout (s) for the stdlib path
_SCRAPO_TIMEOUT = 25.0              # Scrapo may escalate to a browser tier - give it more room
_MAX_DOC_CHARS = 6000               # cap extracted text stored per page
_MAX_BYTES = 2_000_000             # never read more than 2 MB off the wire per page
_UA = ("Mozilla/5.0 (compatible; WritingAgent/1.0 research; "
       "+https://github.com/vikast908/WritingAgent)")


@dataclass
class Document:
    """One fetched source: search metadata plus extracted page body (may be empty)."""
    title: str
    url: str
    snippet: str
    domain: str
    text: str = ""


# ── HTML -> text ───────────────────────────────────────────────────────────────
class _TextExtractor(HTMLParser):
    """Pull readable text from HTML, dropping script/style/nav chrome.

    HTMLParser delivers <script>/<style> bodies as data while inside those tags, so
    a skip-depth counter is enough to exclude them. Block-level tags emit a newline
    so paragraphs don't run together.
    """
    _SKIP = {"script", "style", "noscript", "head", "svg", "template"}
    _BLOCK = {"p", "br", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6",
              "tr", "section", "article", "header", "footer", "ul", "ol", "blockquote"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip += 1
        elif self._skip == 0 and tag in self._BLOCK:
            self._chunks.append("\n")

    def handle_startendtag(self, tag, attrs):
        if self._skip == 0 and tag in self._BLOCK:
            self._chunks.append("\n")

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if self._skip == 0:
            t = data.strip()
            if t:
                self._chunks.append(t + " ")

    def get_text(self) -> str:
        raw = "".join(self._chunks)
        raw = re.sub(r"[ \t\r\f]+", " ", raw)
        raw = re.sub(r"\n[ ]+", "\n", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def html_to_text(html: str) -> str:
    """Extract readable text from an HTML document. Best-effort, never raises."""
    try:
        p = _TextExtractor()
        p.feed(html)
        out = p.get_text()
        if out:
            return out
    except Exception:  # noqa: BLE001 - malformed HTML must not crash a fetch
        pass
    # Fallback: crude tag strip.
    return re.sub(r"\s+", " ", re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ",
                                      re.sub(r"<[^>]+>", " ", html))).strip()


def domain_of(url: str) -> str:
    """Registrable-ish host for a URL, with a leading 'www.' stripped ('' on error)."""
    try:
        net = urlparse(url).netloc.lower()
        return net[4:] if net.startswith("www.") else net
    except Exception:  # noqa: BLE001
        return ""


# ── Optional Scrapo backend ────────────────────────────────────────────────────
# Scrapo (https://github.com/vikast908/Scrapo) is a richer scraper: it returns clean
# page *markdown* and escalates HTTP -> browser -> stealth on real failure signals, so
# it reaches content the plain urllib + html.parser path can't (JS-rendered pages,
# soft blocks). It's optional - Python 3.11+, heavier deps - so we prefer it when it's
# installed and silently fall back to the stdlib path otherwise. Set
# BOOK_AGENT_NO_SCRAPO=1 to force the stdlib path (deterministic / offline runs).
_SCRAPO_UNSET = object()
_scrapo_mod = _SCRAPO_UNSET


def _scrapo():
    """The scrapo module if importable and not disabled, else None (resolved once)."""
    global _scrapo_mod
    if os.getenv("BOOK_AGENT_NO_SCRAPO", "").lower() in ("1", "true", "yes"):
        return None
    if _scrapo_mod is _SCRAPO_UNSET:
        try:
            import scrapo
            # Scrapo leaves logging to the caller, and structlog's unconfigured default
            # prints every line; quiet it (overridable via SCRAPO_LOG_LEVEL) so its
            # debug/info chatter doesn't pollute the TUI.
            try:
                from scrapo.logging import configure_logging
                configure_logging(os.environ.get("SCRAPO_LOG_LEVEL", "WARNING"))
            except Exception:  # noqa: BLE001 - logging setup is best-effort
                pass
            _scrapo_mod = scrapo
        except Exception:  # noqa: BLE001 - not installed / import failure: fall back
            _scrapo_mod = None
    return _scrapo_mod


def _fetch_via_scrapo(url: str, *, max_chars: int, timeout: float = _SCRAPO_TIMEOUT) -> str:
    """Fetch page markdown via Scrapo. '' if Scrapo is unavailable or on any failure."""
    mod = _scrapo()
    if mod is None:
        return ""
    import asyncio

    async def _run():
        res = await asyncio.wait_for(mod.scrape(url), timeout=timeout)
        md = getattr(res, "markdown", None)
        if md is None:
            try:
                md = res["markdown"]   # dict-style access (backward-compat)
            except Exception:  # noqa: BLE001
                md = None
        return md or ""

    try:
        # fetch_text runs on a concurrency.gather worker thread (or the synchronous
        # orchestrator thread) - neither has a running event loop, so a fresh
        # asyncio.run per call is safe.
        text = asyncio.run(_run())
    except Exception:  # noqa: BLE001 - scrape failure is non-fatal; caller falls back to stdlib
        return ""
    return (text or "").strip()[:max_chars]


def _fetch_via_urllib(url: str, *, max_chars: int, timeout: float = _FETCH_TIMEOUT) -> str:
    """Stdlib fetch + HTML->text extraction. '' on any failure or non-HTML response."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": _UA,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - http(s) enforced by caller
            ctype = (resp.headers.get("Content-Type") or "").lower()
            if ctype and "html" not in ctype and "text" not in ctype:
                return ""   # binary/PDF - nothing useful to extract
            charset = resp.headers.get_content_charset() or "utf-8"
            raw = resp.read(_MAX_BYTES)
        return html_to_text(raw.decode(charset, errors="replace"))[:max_chars]
    except Exception:  # noqa: BLE001 - DNS/timeout/403/decode: non-fatal
        return ""


# ── Page fetch ─────────────────────────────────────────────────────────────────
def fetch_text(url: str, *, timeout: float = _FETCH_TIMEOUT,
               max_chars: int = _MAX_DOC_CHARS) -> str:
    """Fetch a URL and return its page content (markdown or text, capped). '' on failure.

    Prefers the Scrapo backend when installed, falling back to a stdlib urllib +
    html.parser fetch. Only http(s) is followed; non-HTML responses (PDFs, images) are
    skipped by the stdlib path. Non-empty results are cached on disk so resumes and
    overlapping sections don't refetch.
    """
    if urlparse(url).scheme not in ("http", "https"):
        return ""
    cached = cache.get("fetch", (url, max_chars), max_age_s=_FETCH_TTL_S)
    if cached is not None:
        return cached
    text = (_fetch_via_scrapo(url, max_chars=max_chars)
            or _fetch_via_urllib(url, max_chars=max_chars, timeout=timeout))
    if text:
        cache.put("fetch", (url, max_chars), text)
    return text


# ── Multi-query gather ─────────────────────────────────────────────────────────
def gather_documents(
    queries: list[str], *,
    per_query: int = 5,
    max_sources: int = 6,
    max_per_domain: int = 2,
    fetch: bool = True,
    log=None,
) -> list[Document]:
    """Run several searches concurrently, merge + dedupe + diversify, fetch page text.

    - de-dupes queries and drops empties;
    - searches run in parallel (each `web_search` is independent);
    - hits are merged in query order, deduped by URL, and capped at `max_per_domain`
      per host so the source set spans multiple sites;
    - the top `max_sources` then have their full page text fetched concurrently.
    Returns [] if there are no queries or nothing was found.
    """
    queries = [q for q in dict.fromkeys(q.strip() for q in queries) if q]
    if not queries:
        return []

    search_tasks = {
        f"q{i}": (lambda q=q: web_search(q, max_results=per_query))
        for i, q in enumerate(queries)
    }
    results_by_q = concurrency.gather(search_tasks)

    seen_urls: set[str] = set()
    per_domain: dict[str, int] = {}
    merged: list[Document] = []
    for i in range(len(queries)):
        for r in (results_by_q.get(f"q{i}") or []):
            url = (r.url or "").strip()
            if not url or url in seen_urls:
                continue
            dom = domain_of(url)
            if per_domain.get(dom, 0) >= max_per_domain:
                continue
            seen_urls.add(url)
            per_domain[dom] = per_domain.get(dom, 0) + 1
            merged.append(Document(title=r.title, url=url, snippet=r.snippet, domain=dom))
            if len(merged) >= max_sources:
                break
        if len(merged) >= max_sources:
            break

    if fetch and merged:
        fetched = concurrency.gather({d.url: (lambda u=d.url: fetch_text(u)) for d in merged})
        for d in merged:
            d.text = fetched.get(d.url) or ""
        if log:
            got = sum(1 for d in merged if d.text)
            log(f"   deep research: {len(merged)} source(s) across "
                f"{len(per_domain)} domain(s), {got} with full text")
    return merged


def format_documents(docs: list[Document], *, excerpt_chars: int = 1500) -> str:
    """Numbered source block for the synthesis node. Uses page text, falls back to
    the snippet. Numbers ([1], [2]...) match the citation scheme the prompts ask for."""
    if not docs:
        return ""
    blocks = []
    for i, d in enumerate(docs, 1):
        body = (d.text or d.snippet or "").strip()
        if len(body) > excerpt_chars:
            body = body[:excerpt_chars].rsplit(" ", 1)[0] + " ..."
        blocks.append(f"[{i}] {d.title}\n    URL: {d.url}\n    {body}")
    return "\n\n".join(blocks)
