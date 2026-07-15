"""Tests for the deep multi-source researcher: HTML extraction, fetch caching,
multi-query merge/dedup/diversity, the Scrapo/stdlib fetch backends, and the
deep-research pipeline wiring (offline)."""
import os

import pytest

from writingagent import deep_research as dr
from writingagent import orchestrator
from writingagent import schemas as S
from writingagent.brain import ArticlePaths, BookPaths
from writingagent.config import load_config, load_settings
from writingagent.search import SearchResult


# ── HTML -> text ───────────────────────────────────────────────────────────────
def test_html_to_text_strips_chrome_and_decodes_entities():
    html = ("<html><head><title>T</title><style>.x{color:red}</style></head>"
            "<body><nav>menu</nav><h1>Heading</h1>"
            "<p>A fact: 42 widgets &amp; more.</p>"
            "<script>var x=1; bad()</script>"
            "<ul><li>alpha</li><li>beta</li></ul></body></html>")
    txt = dr.html_to_text(html)
    assert "Heading" in txt and "42 widgets" in txt and "alpha" in txt
    assert "&" in txt                          # entity decoded
    assert "color:red" not in txt              # <style> dropped
    assert "bad()" not in txt and "var x" not in txt   # <script> dropped


def test_html_to_text_keeps_paragraph_breaks():
    txt = dr.html_to_text("<p>one</p><p>two</p>")
    assert "one" in txt and "two" in txt
    assert "\n" in txt                         # block tags produce a break


def test_html_to_text_never_raises_on_garbage():
    assert isinstance(dr.html_to_text("<<<not >valid< html"), str)


def test_domain_of():
    assert dr.domain_of("https://www.Example.com/a?q=1") == "example.com"
    assert dr.domain_of("http://sub.host.org/x") == "sub.host.org"
    assert dr.domain_of("not a url") == ""


# ── fetch_text ─────────────────────────────────────────────────────────────────
def test_fetch_text_rejects_non_http():
    assert dr.fetch_text("ftp://host/file") == ""
    assert dr.fetch_text("file:///etc/passwd") == ""


def test_fetch_text_uses_cache_without_network(tmp_brain, monkeypatch):
    from writingagent import cache
    url = "https://example.com/page"
    cache.put("fetch", (url, dr._MAX_DOC_CHARS), "cached body")

    def _boom(*_a, **_k):
        raise AssertionError("network must not be hit on a cache hit")
    monkeypatch.setattr(dr.urllib.request, "urlopen", _boom)
    assert dr.fetch_text(url) == "cached body"


# ── gather_documents: merge / dedup / domain diversity ──────────────────────────
def _sr(url, title=None):
    return SearchResult(title=title or url, url=url, snippet=f"snippet for {url}")


def test_gather_documents_dedup_and_domain_cap(tmp_brain, monkeypatch):
    canned = {
        "q1": [_sr("https://a.com/1"), _sr("https://a.com/2"), _sr("https://a.com/3")],
        "q2": [_sr("https://b.com/1"), _sr("https://a.com/1"), _sr("https://c.com/1")],
    }
    monkeypatch.setattr(dr, "web_search", lambda q, max_results=5: canned.get(q, []))
    monkeypatch.setattr(dr, "fetch_text", lambda u, **k: f"TEXT::{u}")

    docs = dr.gather_documents(["q1", "q2"], max_per_domain=2, max_sources=6)
    urls = [d.url for d in docs]
    assert urls == ["https://a.com/1", "https://a.com/2",
                    "https://b.com/1", "https://c.com/1"]
    assert "https://a.com/3" not in urls                  # per-domain cap (2) for a.com
    assert urls.count("https://a.com/1") == 1             # cross-query URL dedup
    assert all(d.text == f"TEXT::{d.url}" for d in docs)  # page text fetched + attached


def test_gather_documents_respects_max_sources(tmp_brain, monkeypatch):
    canned = {"q": [_sr("https://a.com/1"), _sr("https://b.com/2"), _sr("https://c.com/3")]}
    monkeypatch.setattr(dr, "web_search", lambda q, max_results=5: canned.get(q, []))
    monkeypatch.setattr(dr, "fetch_text", lambda u, **k: "")
    docs = dr.gather_documents(["q"], max_sources=2)
    assert len(docs) == 2


def test_gather_documents_empty_and_dedup_queries(tmp_brain, monkeypatch):
    calls = []
    monkeypatch.setattr(dr, "web_search",
                        lambda q, max_results=5: calls.append(q) or [])
    assert dr.gather_documents([]) == []
    assert dr.gather_documents(["  ", ""]) == []          # all-empty -> no search
    dr.gather_documents(["dup", "dup"])
    assert calls.count("dup") == 1                        # duplicate query collapsed


# ── format_documents ────────────────────────────────────────────────────────────
def test_format_documents_numbered_and_truncated():
    long_body = "word " * 1000
    docs = [
        dr.Document(title="One", url="http://a/1", snippet="s1", domain="a", text=long_body),
        dr.Document(title="Two", url="http://b/2", snippet="snip-two", domain="b", text=""),
    ]
    out = dr.format_documents(docs, excerpt_chars=100)
    assert out.startswith("[1] One")
    assert "[2] Two" in out
    assert "http://a/1" in out and "http://b/2" in out
    assert "snip-two" in out                              # falls back to snippet when no text
    assert "..." in out                                   # long body truncated
    assert dr.format_documents([]) == ""


def test_verifier_source_text_is_full_fetch(tmp_brain, monkeypatch):
    """The claim-verification ground truth must be the FULL fetched page text, not the
    1500-char synthesis excerpt - the gate BLOCKS on 'unsupported', so a true claim
    whose support sits past the synthesis cut must still be visible to the verifier."""
    monkeypatch.setenv("WRITINGAGENT_FAKE", "1")
    from writingagent import nodes
    from writingagent.orchestrator import article as article_mod

    marker = "UNIQUE-LATE-FACT-9317"
    long_text = ("pad " * 800) + marker                    # marker sits past char 1500
    docs = [dr.Document(title="One", url="http://a/1", snippet="s", domain="a",
                        text=long_text)]
    monkeypatch.setattr(article_mod, "_deep_docs", lambda *a, **k: docs)

    cfg = load_config()
    angle = S.ArticleAngle(title="T", angle="a", audience="eng", hook="h")
    outline = nodes.build_article_outline(cfg, "abstract", angle, 1)
    state = {"use_researcher": True, "deep_research": True,
             "verify_excerpt_chars": 6000, "use_images": False}
    out = article_mod._section_fetch(cfg, ArticlePaths("vfx", "u"), outline, state, 1,
                                     lambda *a, **k: None)
    _prefix, _sources, source_text = out["research"]
    assert marker in source_text                           # verifier sees the late fact
    # and the synthesis default alone would have cut it:
    assert marker not in dr.format_documents(docs)


# ── Search providers: duckduckgo (default) | firecrawl ──────────────────────────
def test_search_provider_defaults_and_degrades(monkeypatch):
    from writingagent import search as sm
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    assert sm.provider() == "duckduckgo"                  # shipped default
    # firecrawl selected but no key -> degrade to the free provider, never block
    from writingagent.config import Settings
    monkeypatch.setattr("writingagent.config.load_settings",
                        lambda: Settings(search_provider="firecrawl"))
    assert sm.provider() == "duckduckgo"
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
    assert sm.provider() == "firecrawl"


def test_firecrawl_search_parses_both_response_shapes(monkeypatch):
    import io
    import json

    from writingagent import search as sm
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")

    def _fake_urlopen(payload):
        class _Resp(io.BytesIO):
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False
        return lambda req, timeout=0: _Resp(json.dumps(payload).encode())

    v1 = {"success": True, "data": [
        {"title": "One", "url": "https://a/1", "description": "d1"}]}
    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen(v1))
    out = sm._firecrawl_search("q", 5)
    assert out and out[0].url == "https://a/1" and out[0].snippet == "d1"

    v2 = {"success": True, "data": {"web": [
        {"title": "Two", "url": "https://b/2", "description": "d2"}]}}
    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen(v2))
    out = sm._firecrawl_search("q", 5)
    assert out and out[0].url == "https://b/2"


def test_fetch_text_prefers_firecrawl_when_selected(tmp_brain, monkeypatch):
    monkeypatch.setattr(dr, "_fetch_permitted", lambda u: True)
    monkeypatch.setattr(dr, "_throttle", lambda h, **k: None)
    monkeypatch.setattr(dr, "_fetch_via_firecrawl",
                        lambda url, max_chars, **k: "firecrawl markdown")
    monkeypatch.setattr(dr, "_fetch_via_scrapo", lambda url, **k: "scrapo body")
    assert dr.fetch_text("https://x.test/page") == "firecrawl markdown"


def test_fetch_via_firecrawl_disabled_without_provider(monkeypatch):
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    assert dr._fetch_via_firecrawl("https://x.test/p", max_chars=100) == ""


# ── fetch backends: Scrapo preferred, stdlib fallback ───────────────────────────
def test_scrapo_disabled_via_env(monkeypatch):
    monkeypatch.setenv("WRITINGAGENT_NO_SCRAPO", "1")
    assert dr._scrapo() is None                          # env kill-switch wins


def test_fetch_text_prefers_scrapo_backend(tmp_brain, monkeypatch):
    """When Scrapo is available it's used (markdown), and urllib is not touched."""
    class _Res:
        markdown = "# Scraped\n\nclean markdown body"

    class _FakeScrapo:
        async def scrape(self, url, schema=None):
            return _Res()

    monkeypatch.setattr(dr, "_fetch_permitted", lambda u: True)  # offline: no DNS/robots
    monkeypatch.setattr(dr, "_scrapo", lambda: _FakeScrapo())
    monkeypatch.setattr(dr, "_fetch_via_urllib",
                        lambda *a, **k: pytest.fail("stdlib path must not run when Scrapo succeeds"))
    out = dr.fetch_text("https://example.com/x")
    assert out.startswith("# Scraped")
    # Result is cached (second call returns it even though the backend would now fail).
    monkeypatch.setattr(dr, "_scrapo", lambda: None)
    assert dr.fetch_text("https://example.com/x").startswith("# Scraped")


def test_fetch_text_falls_back_to_urllib(tmp_brain, monkeypatch):
    """If Scrapo yields nothing, the stdlib path is used."""
    monkeypatch.setattr(dr, "_fetch_permitted", lambda u: True)  # offline: no DNS/robots
    monkeypatch.setattr(dr, "_fetch_via_scrapo", lambda *a, **k: "")
    monkeypatch.setattr(dr, "_fetch_via_urllib", lambda *a, **k: "stdlib extracted text")
    assert dr.fetch_text("https://example.com/y") == "stdlib extracted text"


# ── fetch safety: SSRF guard, robots.txt, throttle ──────────────────────────────
def test_url_is_safe_blocks_private_and_loopback(monkeypatch):
    """Hosts resolving to non-global addresses are rejected; public ones pass."""
    resolved = {"internal.example": "10.0.0.5", "public.example": "93.184.216.34",
                "localhost": "127.0.0.1"}

    def fake_getaddrinfo(host, *_a, **_k):
        if host not in resolved:
            raise OSError("unresolvable")
        return [(None, None, None, None, (resolved[host], 0))]

    monkeypatch.setattr(dr.socket, "getaddrinfo", fake_getaddrinfo)
    assert dr.url_is_safe("https://public.example/page")
    assert not dr.url_is_safe("http://internal.example/admin")
    assert not dr.url_is_safe("http://localhost:8080/")
    assert not dr.url_is_safe("http://169.254.169.254/latest/meta-data")  # cloud metadata
    assert not dr.url_is_safe("http://nosuchhost.example/")               # unresolvable
    assert not dr.url_is_safe("ftp://public.example/x")                   # scheme
    assert not dr.url_is_safe("not a url")


def test_fetch_text_blocks_unsafe_url(tmp_brain, monkeypatch):
    monkeypatch.setattr(dr, "url_is_safe", lambda u: False)
    monkeypatch.setattr(dr, "_fetch_via_urllib",
                        lambda *a, **k: pytest.fail("unsafe URL must not be fetched"))
    monkeypatch.setattr(dr, "_fetch_via_scrapo",
                        lambda *a, **k: pytest.fail("unsafe URL must not be fetched"))
    assert dr.fetch_text("https://internal.example/secret") == ""


def test_robots_disallow_blocks_fetch(tmp_brain, monkeypatch):
    """A parsed robots.txt Disallow rule for our UA blocks the page fetch."""
    rp = dr.robotparser.RobotFileParser()
    rp.parse(["User-agent: *", "Disallow: /private/"])
    monkeypatch.setattr(dr, "url_is_safe", lambda u: True)
    monkeypatch.setattr(dr, "_throttle", lambda *a, **k: None)  # no 1s pacing in tests
    monkeypatch.setitem(dr._robots_cache, "https://site.example", rp)
    monkeypatch.setattr(dr, "_fetch_via_urllib",
                        lambda *a, **k: pytest.fail("disallowed URL must not be fetched"))
    monkeypatch.setattr(dr, "_fetch_via_scrapo", lambda *a, **k: "")
    assert dr.fetch_text("https://site.example/private/x") == ""
    # Allowed path on the same host goes through to the backends.
    monkeypatch.setattr(dr, "_fetch_via_urllib", lambda *a, **k: "ok body")
    assert dr.fetch_text("https://site.example/public/x") == "ok body"


def test_robots_ignored_via_env(monkeypatch):
    monkeypatch.setenv("WRITINGAGENT_IGNORE_ROBOTS", "1")
    assert dr._robots_allows("https://anything.example/x")


def test_throttle_spaces_same_host(monkeypatch):
    dr._host_last.clear()
    t0 = dr.time.monotonic()
    dr._throttle("slow.example", min_interval=0.2)   # first hit: no wait
    dr._throttle("other.example", min_interval=0.2)  # different host: no wait
    assert dr.time.monotonic() - t0 < 0.15
    dr._throttle("slow.example", min_interval=0.2)   # same host again: waits
    assert dr.time.monotonic() - t0 >= 0.2
    dr._host_last.clear()


def test_fetch_via_scrapo_returns_empty_when_unavailable(monkeypatch):
    monkeypatch.setattr(dr, "_scrapo", lambda: None)
    assert dr._fetch_via_scrapo("https://example.com", max_chars=100) == ""


# ── pipeline wiring (offline / fake mode) ───────────────────────────────────────
@pytest.fixture
def fake_llm(monkeypatch):
    monkeypatch.setenv("WRITINGAGENT_FAKE", "1")


def _silent(*_a, **_k):
    pass


def test_deep_research_article_pipeline_offline(tmp_brain, fake_llm):
    """deep_research on: the article pipeline still completes with no network."""
    cfg, settings = load_config(), load_settings()
    settings.use_researcher = True
    settings.deep_research = True
    angle = S.ArticleAngle(title="A", angle="analysis", audience="devs", hook="h")
    aid = orchestrator.start_article(cfg, settings, "u", "topic", angle,
                                     "deepart", 1, 1, autonomous=True)
    state = orchestrator.run(cfg, "u", aid, log=_silent)
    assert state["phase"] == "done"
    assert state["deep_research"] is True
    assert ArticlePaths(aid, "u").manuscript.exists()


def test_deep_research_book_pipeline_offline(tmp_brain, fake_llm):
    """deep_research on: the book pipeline still completes with no network."""
    cfg, settings = load_config(), load_settings()
    settings.use_researcher = True
    settings.deep_research = True
    chosen = S.Direction(title="D", premise="p", tone="dark", themes=["x"],
                         hook="h", why_it_works="w")
    bid = orchestrator.start_book(cfg, settings, "u", "abstract", chosen,
                                  "deepbook", 1, 1, autonomous=True)
    state = orchestrator.run(cfg, "u", bid, log=_silent)
    assert state["phase"] == "done"
    assert state["deep_research"] is True
    assert BookPaths(bid, "u").ch(1).exists()


def test_research_queries_helper_falls_back_on_llm_error(tmp_brain, monkeypatch):
    """If query expansion raises, the seed queries are still returned."""
    cfg = load_config()
    from writingagent import nodes
    monkeypatch.setattr(nodes, "propose_search_queries",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    qs = orchestrator._research_queries(cfg, "topic", "focus", "seed query", log=_silent)
    assert qs == ["seed query"]


# ── live network (opt-in) ───────────────────────────────────────────────────────
_LIVE = os.getenv("WRITINGAGENT_LIVE", "").lower() in ("1", "true", "yes")


@pytest.mark.skipif(not _LIVE, reason="live network test; set WRITINGAGENT_LIVE=1 to run")
def test_gather_documents_live(tmp_brain):
    """Real DuckDuckGo discovery + real page fetch (Scrapo if installed, else stdlib).
    Opt-in - hits the network. Asserts we get diverse sources with real page text."""
    docs = dr.gather_documents(["python list comprehension tutorial",
                                "python list comprehension performance"],
                               per_query=4, max_sources=4)
    assert docs, "expected at least one source from a live search"
    assert any(d.text for d in docs), "expected at least one fetched page with text"
    assert len({d.domain for d in docs}) >= 2, "expected sources from multiple domains"
