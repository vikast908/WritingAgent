"""Offline tests for the support modules: cache, search, images, embeddings."""
from __future__ import annotations

import importlib.util
import json
import sys
import types

import pytest

from writingagent import cache, embeddings, images, search


# ── cache ──────────────────────────────────────────────────────────────────────
def test_cache_corrupt_file_is_a_miss(tmp_brain):
    """A garbled cache file is treated as absent, never raised to the caller."""
    cache.put("ns", ("k",), "v")
    p = cache._path("ns", ("k",))
    p.write_text("{ not json", encoding="utf-8")
    assert cache.get("ns", ("k",)) is None


def test_cache_put_unserialisable_never_raises(tmp_brain):
    """put() swallows JSON-serialisation errors - caching is best-effort."""
    cache.put("ns", ("k",), object())   # not JSON-serialisable
    assert cache.get("ns", ("k",)) is None


def test_cache_ttl_expiry_with_clock(tmp_brain, monkeypatch):
    """Entries older than max_age_s expire; younger ones survive."""
    cache.put("ns", ("k",), "v")
    real = cache.time.time()
    monkeypatch.setattr(cache.time, "time", lambda: real + 1000)
    assert cache.get("ns", ("k",), max_age_s=2000) == "v"
    assert cache.get("ns", ("k",), max_age_s=500) is None
    assert cache.get("ns", ("k",)) == "v"   # no TTL -> never expires


def test_cache_path_hashing(tmp_brain):
    """Keys hash deterministically, differ per key, and are namespaced on disk."""
    a1, a2 = cache._path("ns", ("a", 1)), cache._path("ns", ("a", 1))
    b = cache._path("ns", ("b", 1))
    other = cache._path("other", ("a", 1))
    assert a1 == a2 and a1 != b
    assert a1.name.startswith("ns_") and other.name.startswith("other_")
    assert a1.parent == cache._dir()    # lives under the (redirected) INDEX_DIR


# ── search ─────────────────────────────────────────────────────────────────────
@pytest.fixture
def online(tmp_brain, monkeypatch):
    """Pretend to be online (no FAKE flag) with a clean per-thread DDGS slot."""
    monkeypatch.delenv("WRITINGAGENT_FAKE", raising=False)
    monkeypatch.setattr(search._tl, "ddgs", None, raising=False)
    return tmp_brain


class _FakeDDGS:
    def __init__(self, rows=None, exc=None):
        self.rows, self.exc, self.calls = rows or [], exc, 0

    def text(self, query, max_results=5):
        self.calls += 1
        if self.exc:
            raise self.exc
        return self.rows


def test_web_search_fake_mode_returns_empty(monkeypatch):
    monkeypatch.setenv("WRITINGAGENT_FAKE", "1")
    assert search.web_search("anything") == []


def test_web_search_result_shape_and_cache(online, monkeypatch):
    """Results map title/href/body -> SearchResult; non-empty hits are disk-cached."""
    fake = _FakeDDGS(rows=[{"title": "T", "href": "https://u", "body": "B"}])
    monkeypatch.setattr(search, "_ddgs", lambda: fake)
    out = search.web_search("maya lighthouse", max_results=3)
    assert out == [search.SearchResult(title="T", url="https://u", snippet="B")]
    # Second identical query is served from cache - the network is not touched.
    monkeypatch.setattr(search, "_ddgs", lambda: _FakeDDGS(exc=RuntimeError("offline")))
    assert search.web_search("maya lighthouse", max_results=3) == out
    assert fake.calls == 1


def test_web_search_error_returns_empty_and_resets_session(online, monkeypatch):
    """Any backend error yields [] and drops the per-thread session for rebuild."""
    monkeypatch.setattr(search, "_ddgs", lambda: _FakeDDGS(exc=RuntimeError("rate limit")))
    monkeypatch.setattr(search._tl, "ddgs", "stale-session", raising=False)
    assert search.web_search("unique-failing-query") == []
    assert search._tl.ddgs is None


def test_ddgs_prefers_new_package(online, monkeypatch):
    """_ddgs() imports the renamed `ddgs` package first."""
    mod = types.ModuleType("ddgs")

    class NewDDGS:
        pass
    mod.DDGS = NewDDGS
    monkeypatch.setitem(sys.modules, "ddgs", mod)
    assert isinstance(search._ddgs(), NewDDGS)


def test_ddgs_falls_back_to_duckduckgo_search(online, monkeypatch):
    """When `ddgs` is missing, the legacy duckduckgo_search package is used."""
    mod = types.ModuleType("duckduckgo_search")

    class OldDDGS:
        pass
    mod.DDGS = OldDDGS
    monkeypatch.setitem(sys.modules, "ddgs", None)            # forces ImportError
    monkeypatch.setitem(sys.modules, "duckduckgo_search", mod)
    assert isinstance(search._ddgs(), OldDDGS)


def test_format_results_block():
    rs = [search.SearchResult(title="A", url="u1", snippet="s1"),
          search.SearchResult(title="B", url="u2", snippet="s2")]
    block = search.format_results(rs)
    assert "[1] A" in block and "[2] B" in block and "u2" in block
    assert search.format_results([]) == ""


def test_build_query_truncates_to_200():
    plan = types.SimpleNamespace(genre="sci-fi " * 40)
    bp = types.SimpleNamespace(title="t " * 40, purpose="first sentence. second")
    q = search.build_query(plan, bp)
    assert len(q) <= 200
    assert "second" not in q   # only the first sentence of purpose is used


# ── images ─────────────────────────────────────────────────────────────────────
class _FakeHTTPResponse:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


_SEARCH_PAYLOAD = {"query": {"search": [
    {"title": "File:Good.jpg"}, {"title": "File:Closed.jpg"}, {"title": "File:Doc.pdf"},
]}}
_INFO_PAYLOAD = {"query": {"pages": {
    "1": {"title": "File:Good.jpg", "imageinfo": [{
        "url": "https://up.wikimedia.org/Good.jpg",
        "extmetadata": {
            "LicenseShortName": {"value": "CC BY-SA 4.0"},
            "Artist": {"value": "<a href='x'>Jane Doe</a>"},
            "ImageDescription": {"value": "A <b>good</b> photo"},
            "LicenseUrl": {"value": "https://creativecommons.org/licenses/by-sa/4.0"},
        }}]},
    "2": {"title": "File:Closed.jpg", "imageinfo": [{
        "url": "https://up.wikimedia.org/Closed.jpg",
        "extmetadata": {"LicenseShortName": {"value": "All rights reserved"}}}]},
    "3": {"title": "File:Doc.pdf", "imageinfo": [{
        "url": "https://up.wikimedia.org/Doc.pdf",
        "extmetadata": {"LicenseShortName": {"value": "CC0"}}}]},
}}}


def test_search_wikimedia_filters_license_and_extension(monkeypatch):
    """Only freely-licensed real image files come back; HTML in metadata is stripped."""
    def fake_urlopen(req, timeout=0):
        payload = _SEARCH_PAYLOAD if "list=search" in req.full_url else _INFO_PAYLOAD
        return _FakeHTTPResponse(payload)
    monkeypatch.setattr(images.urllib.request, "urlopen", fake_urlopen)
    out = images.search_wikimedia("lighthouse", max_results=3)
    assert [r.title for r in out] == ["File:Good.jpg"]   # closed license + .pdf dropped
    r = out[0]
    assert r.author == "Jane Doe" and "<" not in r.description
    assert r.license == "CC BY-SA 4.0" and r.url.endswith("Good.jpg")


def test_search_wikimedia_parses_formatversion2_list(monkeypatch):
    """The real API (formatversion=2) returns `pages` as a LIST - the dict-only parse
    raised, and the net-error guard silently turned every live image search into []."""
    v2_info = {"query": {"pages": list(_INFO_PAYLOAD["query"]["pages"].values())}}

    def fake_urlopen(req, timeout=0):
        payload = _SEARCH_PAYLOAD if "list=search" in req.full_url else v2_info
        return _FakeHTTPResponse(payload)
    monkeypatch.setattr(images.urllib.request, "urlopen", fake_urlopen)
    out = images.search_wikimedia("lighthouse", max_results=3)
    assert [r.title for r in out] == ["File:Good.jpg"]


def test_search_wikimedia_network_error_returns_empty(monkeypatch):
    """Any urllib failure is swallowed: [] instead of an exception."""
    def boom(req, timeout=0):
        raise OSError("no network")
    monkeypatch.setattr(images.urllib.request, "urlopen", boom)
    assert images.search_wikimedia("anything") == []


def test_fetch_info_empty_titles_skips_api():
    """No titles -> [] without any network call."""
    assert images._fetch_info([]) == []


# ── embeddings ─────────────────────────────────────────────────────────────────
def test_available_false_without_sentence_transformers(monkeypatch):
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    assert embeddings.available() is False


def test_embed_texts_raises_when_unavailable(monkeypatch):
    """The documented contract: ImportError (not a crash later) when the dep is absent."""
    monkeypatch.setattr(embeddings, "available", lambda: False)
    with pytest.raises(ImportError):
        embeddings.embed_texts(["x"])


def test_embed_texts_serves_fully_from_cache(tmp_brain, monkeypatch):
    """All-hit lookups never load the model - resumes stay torch-free."""
    monkeypatch.setattr(embeddings, "available", lambda: True)
    monkeypatch.setattr(embeddings, "_get_model",
                        lambda: pytest.fail("model loaded on a full cache hit"))
    cpath = tmp_brain / ".index" / "embed_cache.json"
    cpath.parent.mkdir(parents=True, exist_ok=True)
    cpath.write_text(json.dumps({embeddings._key("hello"): [0.5, 0.5]}), encoding="utf-8")
    assert embeddings.embed_texts(["hello"], cache_path=cpath) == [[0.5, 0.5]]


def test_embed_texts_encodes_only_misses_and_writes_cache(tmp_brain, monkeypatch):
    """Misses are encoded once and persisted; cached texts are not re-encoded."""
    monkeypatch.setattr(embeddings, "available", lambda: True)

    class _Vec:
        def __init__(self, v):
            self._v = v

        def tolist(self):
            return self._v

    class _Model:
        def __init__(self):
            self.seen: list[list[str]] = []

        def encode(self, texts):
            self.seen.append(list(texts))
            return [_Vec([1.0, 0.0]) for _ in texts]

    model = _Model()
    monkeypatch.setattr(embeddings, "_get_model", lambda: model)
    cpath = tmp_brain / ".index" / "embed_cache.json"
    cpath.parent.mkdir(parents=True, exist_ok=True)
    cpath.write_text(json.dumps({embeddings._key("old"): [0.0, 1.0]}), encoding="utf-8")
    out = embeddings.embed_texts(["old", "new"], cache_path=cpath)
    assert out == [[0.0, 1.0], [1.0, 0.0]]
    assert model.seen == [["new"]]                    # only the miss hit the model
    on_disk = json.loads(cpath.read_text(encoding="utf-8"))
    assert embeddings._key("new") in on_disk          # cache persisted for next run


def test_cosine_similarity_values():
    assert embeddings.cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert embeddings.cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert embeddings.cosine([0.0, 0.0], [1.0, 0.0]) == 0.0   # zero vector guarded
    assert embeddings.cosine([1.0, 1.0], [1.0, 0.0]) == pytest.approx(0.7071, abs=1e-3)
