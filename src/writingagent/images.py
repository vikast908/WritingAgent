"""Wikimedia Commons image fetch (plan §2 - illustrated/technical books).

Queries the Wikimedia Commons API, filters for CC/PD licenses, and returns structured
results with URL + full attribution ready for markdown embedding.

Only used when `use_images=True` in settings (default on; fiction rarely needs it).
No extra deps: uses stdlib urllib only.
"""
from __future__ import annotations

import html
import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass

_API = "https://commons.wikimedia.org/w/api.php"
_MD_SPECIAL = re.compile(r"([\\`*_\[\]])")


def _md_text(s: str) -> str:
    """Make LLM/Commons text safe to embed in Markdown: decode entities, collapse
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
    generated: bool = False   # True = made by an image model (different caption/attribution)

    def to_markdown(self, figure_label: str = "") -> str:
        prefix = f"Figure {figure_label}: " if figure_label else ""
        desc = _md_text(self.description)
        if self.generated:
            # AI-generated illustrations carry their own honest attribution, not a
            # Wikimedia source line (which would be a false provenance claim).
            return (f"![{desc}]({_md_url(self.url)})\n"
                    f"*{prefix}{desc}. AI-generated illustration ({_md_text(self.author)}).*")
        bare_title = _md_text(self.title.removeprefix("File:"))
        author = _md_text(self.author)
        lic = _md_text(self.license)
        return (
            f"![{desc}]({_md_url(self.url)})\n"
            f'*{prefix}{desc}. Source: "{bare_title}" by {author}, '
            f"{lic}, via Wikimedia Commons.*"
        )


def _call(params: dict) -> dict:
    qs = urllib.parse.urlencode({"format": "json", "formatversion": "2", **params})
    req = urllib.request.Request(
        f"{_API}?{qs}",
        headers={"User-Agent": "WritingAgent/1.0 (open-source book writing tool)"},
    )
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
            license=lic, description=desc,
        ))
    return results


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
    any failure / in fake mode / when no model is set - the caller then falls back to a
    Wikimedia fetch, then an SVG diagram. Best-effort: image gen never blocks a run.
    """
    import os
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
            import urllib.request
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
