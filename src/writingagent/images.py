"""Free-licensed image sourcing for illustrated/technical pieces (plan §2).

Pluggable, multi-source, and configurable via the `image_source` setting (an ordered
comma list). The agent tries each selected source in order until one yields an image,
then falls back to an SVG diagram. Sources:

  openverse   no key     CC/PD aggregator (Wikimedia + Flickr + museums); keyless default
  wikimedia   no key     Wikimedia Commons, CC/PD only
  pixabay     PIXABAY_API_KEY    Pixabay License (free, commercial ok)
  pexels      PEXELS_API_KEY     Pexels License (free, commercial ok)
  unsplash    UNSPLASH_ACCESS_KEY  Unsplash License (free, commercial ok)
  generate    (image_model)      make one with a text-to-image model

Deliberately NOT included: Shutterstock and other paid/rights-managed catalogues (can't
be auto-embedded without a license), and raw web-scrape / general web-search image
results (unknown, un-attributable licensing). Every source here returns images whose
license permits reuse, with attribution carried into the caption.

Only used when `use_images=True`. No extra deps: stdlib urllib only.
"""
from __future__ import annotations

import html
import json
import os
import re
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

_UA = "WritingAgent/1.0 (open-source writing tool)"
_MD_SPECIAL = re.compile(r"([\\`*_\[\]])")


def _md_text(s: str) -> str:
    """Make LLM/provider text safe to embed in Markdown: decode entities, collapse
    whitespace, and backslash-escape the chars that would break image/italic syntax."""
    s = html.unescape(s or "")
    s = re.sub(r"\s+", " ", s).strip()
    return _MD_SPECIAL.sub(r"\\\1", s)


def _md_url(u: str) -> str:
    """Percent-encode a URL so spaces and parens can't terminate `(...)` early."""
    return urllib.parse.quote(u or "", safe="/:?#@!$&'+,;=~")
_FREE_LICENSE = re.compile(r"cc[-_ ]?by|cc0|public.?domain|pd[-_ ]", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
_IMG_EXT = re.compile(r"\.(jpe?g|png|gif|svg|webp)$", re.IGNORECASE)


@dataclass
class ImageResult:
    url: str
    title: str
    author: str
    license: str
    description: str
    source: str = ""          # human provider name for attribution (e.g. "Openverse")
    generated: bool = False   # True = made by an image model (different caption/attribution)

    def to_markdown(self, figure_label: str = "") -> str:
        prefix = f"Figure {figure_label}: " if figure_label else ""
        desc = _md_text(self.description)
        if self.generated:
            # AI-generated illustrations carry their own honest attribution, not a
            # stock-source line (which would be a false provenance claim).
            return (f"![{desc}]({_md_url(self.url)})\n"
                    f"*{prefix}{desc}. AI-generated illustration ({_md_text(self.author)}).*")
        bare_title = _md_text(self.title.removeprefix("File:"))
        author = _md_text(self.author)
        lic = _md_text(self.license)
        src = _md_text(self.source or "Wikimedia Commons")
        return (
            f"![{desc}]({_md_url(self.url)})\n"
            f'*{prefix}{desc}. Source: "{bare_title}" by {author}, {lic}, via {src}.*'
        )


# ── Fetch-backend registry (mirrors search.py) ──────────────────────────────────
@dataclass
class _ImgBackend:
    fn: Callable[[str, int], list[ImageResult]]
    key_env: str = ""         # "" = keyless
    label: str = ""           # human provider name (attribution + UI)


_IMG_BACKENDS: dict[str, _ImgBackend] = {}


def _register_img(name: str, key_env: str = "", label: str = ""):
    def deco(fn):
        _IMG_BACKENDS[name] = _ImgBackend(fn, key_env, label or name.title())
        return fn
    return deco


def _img_key(env: str) -> str:
    return os.getenv(env, "").strip() if env else ""


def _img_http_json(url: str, *, headers: dict | None = None, timeout: int = 10) -> dict:
    """Minimal stdlib JSON GET (no extra deps). Raises on any error; every caller runs
    under fetch_source's try/except, so a raise just degrades to the next source."""
    req = urllib.request.Request(
        url, headers={"User-Agent": _UA, "Accept": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 - fixed https hosts
        return json.loads(r.read().decode("utf-8", errors="replace"))


# ── Wikimedia Commons ───────────────────────────────────────────────────────────
_API = "https://commons.wikimedia.org/w/api.php"


def _call(params: dict) -> dict:
    qs = urllib.parse.urlencode({"format": "json", "formatversion": "2", **params})
    req = urllib.request.Request(f"{_API}?{qs}", headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())


def _search_titles(query: str, limit: int) -> list[str]:
    data = _call({
        "action": "query", "list": "search",
        "srsearch": query, "srnamespace": "6",  # File namespace only
        "srlimit": str(min(limit, 50)),
    })
    return [r["title"] for r in data.get("query", {}).get("search", [])]


def _fetch_info(titles: list[str]) -> list[ImageResult]:
    if not titles:
        return []
    data = _call({
        "action": "query",
        "titles": "|".join(titles[:10]),  # API batch limit
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
        "iiextmetadatafilter": "LicenseShortName|Artist|ImageDescription",
    })
    results: list[ImageResult] = []
    # formatversion=2 returns `pages` as a list; v1 as an id-keyed dict. The dict
    # parse against the real (v2) API raised, and search_wikimedia's net-error guard
    # silently turned every live image search into [].
    pages = (data.get("query") or {}).get("pages", [])
    if isinstance(pages, dict):
        pages = pages.values()
    for page in pages:
        ii = (page.get("imageinfo") or [{}])[0]
        url = ii.get("url", "")
        if not url or not _IMG_EXT.search(url):
            continue
        meta = ii.get("extmetadata", {})
        lic = _TAG.sub("", (meta.get("LicenseShortName") or {}).get("value", "")).strip()
        if not _FREE_LICENSE.search(lic):
            continue
        author = _TAG.sub("", (meta.get("Artist") or {}).get("value", "Unknown")).strip() or "Unknown"
        desc_raw = _TAG.sub("", (meta.get("ImageDescription") or {}).get("value", "")).strip()
        title = page.get("title", "")
        desc = (desc_raw or title.removeprefix("File:"))[:120]
        results.append(ImageResult(
            url=url, title=title, author=author,
            license=lic, description=desc, source="Wikimedia Commons",
        ))
    return results


@_register_img("wikimedia", "", "Wikimedia Commons")
def search_wikimedia(query: str, max_results: int = 3) -> list[ImageResult]:
    """Search Wikimedia Commons and return up to max_results freely-licensed images.

    Returns an empty list (rather than raising) on any network error so the writer
    can always proceed even if the fetch times out.
    """
    try:
        titles = _search_titles(query, limit=max_results * 4)
        results = _fetch_info(titles)
        return results[:max_results]
    except Exception:  # noqa: BLE001 - network errors are non-fatal
        return []


# ── Openverse (keyless CC/PD aggregator) ────────────────────────────────────────
def _cc_label(lic: str, ver: str) -> str:
    lic = (lic or "").strip().lower()
    if lic in ("cc0", "pdm", "publicdomain"):
        return "CC0 / Public Domain" if lic != "pdm" else "Public Domain Mark"
    return f"CC {lic.upper()} {ver}".strip() if lic else "CC"


@_register_img("openverse", "", "Openverse")
def _openverse_search(query: str, max_results: int) -> list[ImageResult]:
    # commercial + modification -> images safe to embed and adapt in a published piece
    qs = urllib.parse.urlencode({"q": query, "page_size": max(1, max_results),
                                 "license_type": "commercial,modification"})
    data = _img_http_json(f"https://api.openverse.org/v1/images/?{qs}")
    out: list[ImageResult] = []
    for r in (data.get("results") or [])[:max_results]:
        url = (r.get("url") or "").strip()
        if not url:
            continue
        out.append(ImageResult(
            url=url, title=r.get("title") or query,
            author=r.get("creator") or "Unknown",
            license=_cc_label(r.get("license", ""), str(r.get("license_version") or "")),
            description=(r.get("title") or query)[:120], source="Openverse"))
    return out


# ── Pixabay / Pexels / Unsplash (keyed, each free-to-use with its own license) ──
@_register_img("pixabay", "PIXABAY_API_KEY", "Pixabay")
def _pixabay_search(query: str, max_results: int) -> list[ImageResult]:
    key = _img_key("PIXABAY_API_KEY")
    if not key:
        return []
    qs = urllib.parse.urlencode({"key": key, "q": query, "image_type": "photo",
                                 "safesearch": "true", "per_page": max(3, max_results)})
    data = _img_http_json(f"https://pixabay.com/api/?{qs}")
    out: list[ImageResult] = []
    for r in (data.get("hits") or [])[:max_results]:
        url = (r.get("largeImageURL") or r.get("webformatURL") or "").strip()
        if not url:
            continue
        out.append(ImageResult(
            url=url, title=(r.get("tags") or query), author=r.get("user") or "Unknown",
            license="Pixabay License", description=(r.get("tags") or query)[:120],
            source="Pixabay"))
    return out


@_register_img("pexels", "PEXELS_API_KEY", "Pexels")
def _pexels_search(query: str, max_results: int) -> list[ImageResult]:
    key = _img_key("PEXELS_API_KEY")
    if not key:
        return []
    qs = urllib.parse.urlencode({"query": query, "per_page": max(1, max_results)})
    data = _img_http_json(f"https://api.pexels.com/v1/search?{qs}",
                          headers={"Authorization": key})
    out: list[ImageResult] = []
    for r in (data.get("photos") or [])[:max_results]:
        url = ((r.get("src") or {}).get("large") or (r.get("src") or {}).get("original") or "").strip()
        if not url:
            continue
        out.append(ImageResult(
            url=url, title=(r.get("alt") or query), author=r.get("photographer") or "Unknown",
            license="Pexels License", description=(r.get("alt") or query)[:120],
            source="Pexels"))
    return out


@_register_img("unsplash", "UNSPLASH_ACCESS_KEY", "Unsplash")
def _unsplash_search(query: str, max_results: int) -> list[ImageResult]:
    key = _img_key("UNSPLASH_ACCESS_KEY")
    if not key:
        return []
    qs = urllib.parse.urlencode({"query": query, "per_page": max(1, max_results)})
    data = _img_http_json(f"https://api.unsplash.com/search/photos?{qs}",
                          headers={"Authorization": f"Client-ID {key}"})
    out: list[ImageResult] = []
    for r in (data.get("results") or [])[:max_results]:
        url = ((r.get("urls") or {}).get("regular") or (r.get("urls") or {}).get("full") or "").strip()
        if not url:
            continue
        desc = (r.get("description") or r.get("alt_description") or query)
        out.append(ImageResult(
            url=url, title=desc, author=((r.get("user") or {}).get("name") or "Unknown"),
            license="Unsplash License", description=desc[:120], source="Unsplash"))
    return out


# ── Source selection + dispatch ─────────────────────────────────────────────────
# Canonical priority when the user doesn't impose their own order: generate first (the
# deliberate choice), then keyless fetchers, then keyed ones.
_CANON_ORDER = ("generate", "openverse", "wikimedia", "pixabay", "pexels", "unsplash")


def image_sources() -> tuple[str, ...]:
    """Every selectable source id: the fetch backends + 'generate', canonical order."""
    valid = {"generate", *_IMG_BACKENDS}
    return tuple(s for s in _CANON_ORDER if s in valid)


def source_label(name: str) -> str:
    """Human name for a source id (for logs/attribution)."""
    if name == "generate":
        return "an image model"
    b = _IMG_BACKENDS.get(name)
    return b.label if b else name


def source_needs_key(name: str) -> str:
    """The env var a source needs, or '' if keyless / not a fetch source."""
    b = _IMG_BACKENDS.get(name)
    return b.key_env if b else ""


def parse_sources(spec: str) -> list[str]:
    """A comma/space list of source ids -> an ordered, deduped, validated list (the user's
    order is priority). Unknown tokens are dropped; empty input -> []."""
    valid = set(image_sources())
    seen: set[str] = set()
    out: list[str] = []
    for tok in re.split(r"[,\s]+", (spec or "").strip().lower()):
        if tok in valid and tok not in seen:
            seen.add(tok)
            out.append(tok)
    return out


def fetch_source(name: str, query: str, max_results: int = 2) -> list[ImageResult]:
    """Fetch from ONE named provider. Returns [] for an unknown source, a keyed source
    with no key set, or any network error (the caller then tries the next source)."""
    b = _IMG_BACKENDS.get(name)
    if b is None:
        return []
    if b.key_env and not _img_key(b.key_env):
        return []
    try:
        return b.fn(query, max_results)[:max_results]
    except Exception:  # noqa: BLE001 - a provider failure is non-fatal
        return []


# ── Image generation via any image-capable model (plan §2) ──────────────────────
def _image_provider(provider_id: str = ""):
    """The host to run image generation on: a named provider, else the active LLM host.
    Both go through the same OpenAI-compatible client, so any host that exposes an
    /images/generations endpoint works - the tool is not tied to one vendor."""
    from . import llm, providers
    if provider_id:
        pid = providers.resolve(provider_id)
        p = providers.REGISTRY.get(pid)
        if p is not None:
            return p
    return llm.active_provider()


def generate_image(caption: str, prompt: str, out_path, *, model: str = "",
                   provider_id: str = "", size: str = "1024x1024", log=None) -> ImageResult | None:
    """Text-to-image via the OpenAI-compatible images endpoint of the configured (or a
    named) host. Writes the image to `out_path` and returns an ImageResult, or None on
    any failure / in fake mode / when no model is set - the caller then falls back to the
    next source, then an SVG diagram. Best-effort: image gen never blocks a run.
    """
    if os.getenv("WRITINGAGENT_FAKE", "").lower() in ("1", "true", "yes"):
        return None
    model = (model or "").strip()
    if not model:
        return None
    try:
        import base64

        from openai import OpenAI

        from . import providers
        p = _image_provider(provider_id)
        base = providers.base_url_for(p)
        if not base:
            return None
        key = providers.api_key_for(p)
        client = OpenAI(base_url=base, api_key=key or "not-needed",
                        default_headers=dict(getattr(p, "headers", {})) or None, timeout=120)
        resp = client.images.generate(model=model, prompt=prompt, size=size, n=1)
        datum = resp.data[0]
        raw = None
        b64 = getattr(datum, "b64_json", None)
        if b64:
            raw = base64.b64decode(b64)
        elif getattr(datum, "url", None):
            with urllib.request.urlopen(datum.url, timeout=30) as r:  # noqa: S310 - model-returned URL
                raw = r.read()
        if not raw:
            return None
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(raw)
        if log:
            log(f"   generated image -> {out_path.name} ({model})")
        return ImageResult(url=f"images/{out_path.name}", title=caption, author=model,
                           license="AI-generated", description=caption, generated=True)
    except Exception:  # noqa: BLE001 - generation is best-effort; the caller falls back
        return None
