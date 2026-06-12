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

import asyncio
import ipaddress
import os
import re
import socket
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib import robotparser
from urllib.parse import urlparse

from . import cache, concurrency
from .search import web_search

_FETCH_TTL_S = 7 * 24 * 3600        # fetched page text is stable enough to reuse for a week
_FETCH_TIMEOUT = 12.0               # per-page network timeout (s) for the stdlib path
_SCRAPO_TIMEOUT = 25.0              # Scrapo may escalate to a browser tier - give it more room
_MAX_DOC_CHARS = 6000               # cap extracted text stored per page
_MAX_BYTES = 2_000_000             # never read more than 2 MB off the wire per page
_ROBOTS_TIMEOUT = 5.0               # robots.txt fetch timeout (s)
_HOST_MIN_INTERVAL = 1.0            # politeness: min seconds between requests to one host
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


# All Scrapo coroutines run on one persistent background event loop. The previous
# per-call asyncio.run spun up (and tore down) a fresh loop per URL on every worker
# thread, which defeats any session/browser reuse inside Scrapo and adds loop-churn
# for each of the ~6 concurrent fetches per research pass.
_loop_lock = threading.Lock()
_loop: asyncio.AbstractEventLoop | None = None


def _scrapo_loop() -> asyncio.AbstractEventLoop:
    global _loop
    with _loop_lock:
        if _loop is None or _loop.is_closed():
            loop = asyncio.new_event_loop()
            threading.Thread(target=loop.run_forever, name="scrapo-loop",
                             daemon=True).start()
            _loop = loop
        return _loop


def _fetch_via_scrapo(url: str, *, max_chars: int, timeout: float = _SCRAPO_TIMEOUT) -> str:
    """Fetch page markdown via Scrapo. '' if Scrapo is unavailable or on any failure."""
    mod = _scrapo()
    if mod is None:
        return ""

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
        # Schedule on the shared loop; concurrent fetch_text worker threads each get a
        # future and block only their own thread. The extra margin on .result() guards
        # against a wedged loop (wait_for above is the real per-page timeout).
        fut = asyncio.run_coroutine_threadsafe(_run(), _scrapo_loop())
        text = fut.result(timeout=timeout + 10)
    except Exception:  # noqa: BLE001 - scrape failure is non-fatal; caller falls back to stdlib
        return ""
    return (text or "").strip()[:max_chars]


# ── Fetch safety: SSRF guard, robots.txt, per-host politeness ──────────────────
# Search results (and the LLM's query expansion behind them) decide which URLs get
# fetched, so the fetcher must not be steerable at internal services. The guard
# resolves the host and requires every address to be globally routable; the stdlib
# path re-checks each redirect hop. robots.txt is honored per host (unreachable or
# missing robots = allow, the wide-web convention; BOOK_AGENT_IGNORE_ROBOTS=1 skips
# the check), and requests to one host are spaced at least _HOST_MIN_INTERVAL apart.
# The Scrapo backend does its own fetching - it has SCRAPO_RESPECT_ROBOTS for robots,
# and the initial-URL guard here still applies to it.
def _is_public_host(host: str) -> bool:
    """True when the host resolves and every resolved address is globally routable."""
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False    # unresolvable - a real fetch would fail anyway
    addrs = {info[4][0] for info in infos}
    if not addrs:
        return False
    for a in addrs:
        try:
            if not ipaddress.ip_address(a).is_global:
                return False    # loopback / private / link-local / reserved
        except ValueError:
            return False
    return True


def url_is_safe(url: str) -> bool:
    """http(s) URL whose host resolves only to public addresses (SSRF guard)."""
    try:
        p = urlparse(url)
    except Exception:  # noqa: BLE001
        return False
    if p.scheme not in ("http", "https") or not p.hostname:
        return False
    return _is_public_host(p.hostname)


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Re-validate every redirect target - a public page must not be able to bounce
    the fetcher onto an internal address."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not url_is_safe(newurl):
            raise urllib.error.HTTPError(newurl, code, "unsafe redirect target",
                                         headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(_SafeRedirectHandler)

_ROBOTS_UNSET = object()
_robots_lock = threading.Lock()
_robots_cache: dict[str, robotparser.RobotFileParser | None] = {}


def _robots_allows(url: str, *, timeout: float = _ROBOTS_TIMEOUT) -> bool:
    """robots.txt verdict for `url`, cached per scheme://host for the process.
    No reachable/parsable robots.txt means allow. BOOK_AGENT_IGNORE_ROBOTS=1 skips."""
    if os.getenv("BOOK_AGENT_IGNORE_ROBOTS", "").lower() in ("1", "true", "yes"):
        return True
    try:
        p = urlparse(url)
        base = f"{p.scheme}://{p.netloc}"
    except Exception:  # noqa: BLE001
        return False
    with _robots_lock:
        rp = _robots_cache.get(base, _ROBOTS_UNSET)
    if rp is _ROBOTS_UNSET:
        rp = None
        try:
            req = urllib.request.Request(base + "/robots.txt",
                                         headers={"User-Agent": _UA})
            with _opener.open(req, timeout=timeout) as resp:
                body = resp.read(200_000).decode("utf-8", errors="replace")
            parser = robotparser.RobotFileParser()
            parser.parse(body.splitlines())
            rp = parser
        except Exception:  # noqa: BLE001 - no robots.txt -> allow
            rp = None
        with _robots_lock:
            _robots_cache[base] = rp
    return True if rp is None else rp.can_fetch(_UA, url)


def _fetch_permitted(url: str) -> bool:
    """SSRF guard + robots.txt, the gate every uncached fetch passes through."""
    return url_is_safe(url) and _robots_allows(url)


_host_lock = threading.Lock()
_host_last: dict[str, float] = {}


def _throttle(host: str, *, min_interval: float = _HOST_MIN_INTERVAL) -> None:
    """Block until at least `min_interval` seconds since this host was last fetched."""
    if not host:
        return
    while True:
        with _host_lock:
            now = time.monotonic()
            wait = min_interval - (now - _host_last.get(host, -min_interval))
            if wait <= 0:
                _host_last[host] = now
                return
        time.sleep(min(wait, min_interval))


def _fetch_via_urllib(url: str, *, max_chars: int, timeout: float = _FETCH_TIMEOUT) -> str:
    """Stdlib fetch + HTML->text extraction. '' on any failure or non-HTML response."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": _UA,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en",
        })
        with _opener.open(req, timeout=timeout) as resp:  # noqa: S310 - guarded by _fetch_permitted
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
    html.parser fetch. Only http(s) to publicly-routable hosts is fetched (SSRF
    guard, re-checked per redirect on the stdlib path), robots.txt is honored, and
    per-host requests are rate-limited. Non-empty results are cached on disk so
    resumes and overlapping sections don't refetch.
    """
    if urlparse(url).scheme not in ("http", "https"):
        return ""
    cached = cache.get("fetch", (url, max_chars), max_age_s=_FETCH_TTL_S)
    if cached is not None:
        return cached
    if not _fetch_permitted(url):
        return ""
    _throttle(urlparse(url).hostname or "")
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
