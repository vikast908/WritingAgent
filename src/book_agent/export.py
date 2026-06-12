"""Manuscript export: PDF (xhtml2pdf) and EPUB (ebooklib)."""
from __future__ import annotations

import base64
import mimetypes
import re
from html import escape as _esc
from pathlib import Path

# Manuscripts reference images relatively (images/...). Exporters must resolve them
# against the project root (base_dir) and package/inline them - a bare relative path
# resolves against the process CWD (PDF), a temp dir (DOCX via pandoc), or nothing
# at all (EPUB), silently dropping every figure.
_IMG_TAG = re.compile(r'<img\b[^>]*?src="([^"]+)"[^>]*/?>', re.IGNORECASE)


def _resolve_local(src: str, base_dir: Path | None) -> Path | None:
    """Local file for a relative img src, or None (absolute URLs, missing files)."""
    if not base_dir or re.match(r"^[a-z][a-z0-9+.-]*:", src):
        return None
    p = base_dir / src
    return p if p.is_file() else None


def _inline_images(html_body: str, base_dir: Path | None) -> str:
    """Rewrite local <img> srcs to data URIs so the HTML file is self-contained."""
    def repl(m):
        p = _resolve_local(m.group(1), base_dir)
        if p is None:
            return m.group(0)
        media = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        b64 = base64.b64encode(p.read_bytes()).decode()
        return m.group(0).replace(m.group(1), f"data:{media};base64,{b64}")
    return _IMG_TAG.sub(repl, html_body)


def _pdf_prepare_images(html_body: str, base_dir: Path | None) -> str:
    """Make images renderable by xhtml2pdf: local paths become absolute. SVGs are
    rasterized via cairosvg when installed (full fidelity incl. arrow markers);
    otherwise the absolute .svg path is passed through and xhtml2pdf renders it as
    VECTOR art via its svglib dependency (svglib ignores marker-end, so arrowheads
    degrade to plain lines - still far better than the old behavior of dropping
    the figure entirely, which produced image-less PDFs)."""
    def repl(m):
        src = m.group(1)
        p = _resolve_local(src, base_dir)
        if p is None:
            return "" if src.lower().endswith(".svg") else m.group(0)
        if p.suffix.lower() == ".svg":
            try:
                import cairosvg
                png = cairosvg.svg2png(url=str(p), output_width=860)
                uri = "data:image/png;base64," + base64.b64encode(png).decode()
                return m.group(0).replace(src, uri)
            except Exception:  # noqa: BLE001 - cairosvg absent or bad SVG
                pass
        return m.group(0).replace(src, str(p))
    return _IMG_TAG.sub(repl, html_body)


def _slug_id(title: str) -> str:
    """A stable, ASCII-safe identifier for the EPUB (no spaces/punctuation)."""
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return f"bookwriter-{s or 'book'}"


# Manuscript markdown can carry raw HTML straight from an LLM (python-markdown
# passes it through unescaped). Strip active content so exported HTML/EPUB can't
# execute script when opened with file:// privileges. Conservative denylist -
# not a full sanitizer, but it neutralizes the realistic injection vectors here.
_DANGER_TAGS = "script|iframe|object|embed|link|meta|base|form|svg|math"
_STRIP_BLOCK = re.compile(rf"<\s*({_DANGER_TAGS})\b[^>]*>.*?<\s*/\s*\1\s*>",
                          re.IGNORECASE | re.DOTALL)
_STRIP_SELFCLOSE = re.compile(rf"<\s*({_DANGER_TAGS})\b[^>]*/?>", re.IGNORECASE)
_STRIP_HANDLERS = re.compile(r"\son\w+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", re.IGNORECASE)
_STRIP_JS_URL = re.compile(r"(href|src)\s*=\s*([\"']?)\s*javascript:[^\"'>]*\2",
                           re.IGNORECASE)


def _sanitize_html(html_body: str) -> str:
    html_body = _STRIP_BLOCK.sub("", html_body)
    html_body = _STRIP_SELFCLOSE.sub("", html_body)
    html_body = _STRIP_HANDLERS.sub("", html_body)
    html_body = _STRIP_JS_URL.sub(r'\1=\2#\2', html_body)
    return html_body


# ── Markdown preprocessing (applied before any exporter renders) ──────────────
# Glyphs the humanizer/LLM emit that the PDF serif font can't render (they show as
# □/■ "tofu") or that confuse downstream tools. Normalize to plain ASCII equivalents.
_UNICODE_FIXES = {
    "‑": "-",   # non-breaking hyphen  → hyphen   (the main "tofu" culprit in PDFs)
    "‐": "-",   # unicode hyphen       → hyphen
    " ": " ",   # narrow no-break space → space
    " ": " ",   # no-break space        → space
}
# A byline the article producer leaves when no author is known. Drop the whole line
# rather than print the literal placeholder on the title page.
_PLACEHOLDER_BYLINE = re.compile(r"(?im)^\**By:\**\s*\[AUTHOR NAME\]\s*$\n?")
# An LLM-added "Section N:" heading prefix (numbering is the producer's job). Matches
# only "Section <num>" - book "Chapter N" headings are deliberately left intact.
_SECTION_PREFIX = re.compile(r"(?im)^(#{1,4}\s*)Section\s+\d+\s*[:.–—-]\s*")
# A fenced ```mermaid block. Rendered to an image so it isn't dumped as raw source.
_MERMAID_RE = re.compile(r"```mermaid[ \t]*\r?\n(.*?)\r?\n```", re.DOTALL)
# A <pre>...</pre> block, for preserving source line breaks in the PDF (see below).
_PRE_BLOCK = re.compile(r"(<pre\b[^>]*>)(.*?)(</pre>)", re.DOTALL | re.IGNORECASE)


def _pre_linebreaks(html_body: str) -> str:
    """Turn newlines inside <pre> into explicit <br/>.

    xhtml2pdf collapses newlines in <pre> even under white-space: pre-wrap, which
    flattens every code block into one run-on line. Converting each newline to <br/>
    keeps the source line structure while word-wrap still prevents right-edge clipping.
    PDF-only - HTML/EPUB readers honour <pre> newlines natively.
    """
    def repl(m):
        return m.group(1) + m.group(2).replace("\n", "<br/>") + m.group(3)
    return _PRE_BLOCK.sub(repl, html_body)


def _normalize_text(md_text: str) -> str:
    """Unicode + placeholder + heading cleanup that every exporter wants."""
    for bad, good in _UNICODE_FIXES.items():
        md_text = md_text.replace(bad, good)
    md_text = _PLACEHOLDER_BYLINE.sub("", md_text)
    return _SECTION_PREFIX.sub(r"\1", md_text)


def _mermaid_png(code: str, timeout: float = 12.0) -> bytes | None:
    """Render a Mermaid diagram to PNG bytes via the mermaid.ink service.

    Returns None on any failure (offline, bad diagram, non-200) so callers can fall
    back to the raw source block instead of breaking the whole export.
    """
    import base64 as _b64
    import urllib.request
    try:
        payload = _b64.urlsafe_b64encode(code.strip().encode()).decode()
        url = f"https://mermaid.ink/img/{payload}?type=png&bgColor=white"
        # mermaid.ink (Cloudflare-fronted) 403s the default Python-urllib UA; send a
        # browser-like User-Agent so the request is served.
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; writing-agent/0.1; +https://github.com/vikast908/WritingAgent)"})
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 - fixed host
            if getattr(r, "status", 200) != 200:
                return None
            data = r.read()
        return data if data[:8] == b"\x89PNG\r\n\x1a\n" else None
    except Exception:  # noqa: BLE001 - any network/parse error → fall back to source
        return None


def _mermaid_asset(code: str, base_dir: Path | None) -> tuple[bytes | None, str | None]:
    """Ensure a diagram PNG exists; return (png_bytes, relative_path_or_None).

    When base_dir is set the PNG is cached at base_dir/images/mermaid_<hash>.png and
    its relative path is returned, so every exporter routes the diagram through its
    normal LOCAL-image path (PDF → absolute file, HTML → inlined, EPUB → packaged as a
    real item, DOCX → embedded via --resource-path). The cache also means mermaid.ink
    is hit at most once per diagram - later re-exports are offline. With no base_dir the
    caller falls back to an inline data URI. None bytes ⇒ render failed, keep the source.
    """
    import hashlib
    if base_dir:
        digest = hashlib.sha1(code.strip().encode()).hexdigest()[:16]
        rel = f"images/mermaid_{digest}.png"
        path = Path(base_dir) / rel
        if path.is_file():
            return path.read_bytes(), rel
        png = _mermaid_png(code)
        if png:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(png)
                return png, rel
            except OSError:
                return png, None   # couldn't cache; fall back to inline data URI
        return None, None
    return _mermaid_png(code), None


def _render_mermaid(md_text: str, base_dir: Path | None = None) -> str:
    """Replace ```mermaid blocks with a rendered PNG image.

    Emits a local-image reference when cached under base_dir (so EPUB/DOCX package it
    properly), else an inline data URI. On failure or in offline/fake mode the original
    fenced block is kept, so the diagram source still appears (and wraps, not clipped).
    """
    import os
    if os.getenv("BOOK_AGENT_FAKE", "").lower() in ("1", "true", "yes"):
        return md_text

    def repl(m):
        png, rel = _mermaid_asset(m.group(1), base_dir)
        if not png:
            return m.group(0)
        if rel:   # block-level markdown image → each exporter resolves it locally
            return f"\n\n![Diagram]({rel})\n\n"
        uri = "data:image/png;base64," + base64.b64encode(png).decode()
        return f'<p><img src="{uri}" alt="Diagram" /></p>'
    return _MERMAID_RE.sub(repl, md_text)


def _preprocess(md_text: str, *, diagrams: bool, base_dir: Path | None = None) -> str:
    """Shared pre-render pass: normalize glyphs, drop placeholder byline, and
    (for rich formats) turn Mermaid source into images."""
    md_text = _normalize_text(md_text)
    return _render_mermaid(md_text, base_dir) if diagrams else md_text

# ── Shared styles ─────────────────────────────────────────────────────────────
_PDF_CSS = """
@page { size: A4; margin: 2cm 2cm; }
body { font-family: Georgia, 'Times New Roman', serif; font-size: 11pt; line-height: 1.5; }
h1 { font-size: 22pt; text-align: center; margin: 2cm 0 1cm; }
h2 { font-size: 15pt; margin-top: 1cm; page-break-before: always; }
h3 { font-size: 12pt; margin-top: 0.8cm; }
p { text-align: justify; margin: 0 0 0.6em; }
hr { border: 0; margin: 1em 0; }
em { font-style: italic; }
img { max-width: 100%; }
/* Code & diagram source must WRAP, not clip: xhtml2pdf hard-truncates any line in a
   <pre> wider than the page unless white-space lets it wrap. A smaller mono size plus
   pre-wrap/word-wrap keeps every character on the page. */
pre { font-family: 'DejaVu Sans Mono', 'Courier New', monospace; font-size: 8pt;
      line-height: 1.3; background: #f4f4f4; padding: 0.5em 0.7em; margin: 0.8em 0;
      white-space: pre-wrap; word-wrap: break-word; page-break-inside: avoid; }
code { font-family: 'DejaVu Sans Mono', 'Courier New', monospace; font-size: 0.92em; }
pre code { font-size: 8pt; }
"""

_EPUB_CSS = """
body { font-family: Georgia, 'Times New Roman', serif; font-size: 1em; line-height: 1.6; margin: 1em 2em; }
h1 { font-size: 2em; text-align: center; margin: 2em 0 1em; }
h2 { font-size: 1.4em; margin-top: 2em; }
h3 { font-size: 1.1em; margin-top: 1.2em; }
p { text-align: justify; margin: 0 0 0.7em; }
img { max-width: 100%; height: auto; }
em { font-style: italic; }
/* Wrap code so long lines don't clip off the page edge in e-readers. */
pre { white-space: pre-wrap; word-wrap: break-word; overflow-wrap: break-word;
      background: #f4f4f4; padding: 0.6em 0.8em; font-size: 0.85em;
      font-family: 'DejaVu Sans Mono', Consolas, monospace; }
code { font-family: 'DejaVu Sans Mono', Consolas, monospace; word-wrap: break-word; }
"""


# ── PDF ───────────────────────────────────────────────────────────────────────
def markdown_to_pdf(md_text: str, out_path, title: str = "Manuscript", base_dir=None):
    """Render Markdown to a paginated PDF. New page per chapter (## heading)."""
    import logging

    import markdown
    from xhtml2pdf import pisa

    # svglib (xhtml2pdf's SVG renderer) logs a warning per <text> element whose
    # font-family it can't map (e.g. system-ui) before falling back to Helvetica -
    # dozens of identical lines per diagram that would spam the export output.
    logging.getLogger("svglib").setLevel(logging.ERROR)

    md_text = _preprocess(md_text, diagrams=True, base_dir=Path(base_dir) if base_dir else None)
    html_body = _pre_linebreaks(markdown.markdown(md_text, extensions=["extra", "sane_lists"]))
    html_body = _sanitize_html(html_body)
    html_body = _pdf_prepare_images(html_body, Path(base_dir) if base_dir else None)
    html = (f"<html><head><meta charset='utf-8'><title>{_esc(title)}</title>"
            f"<style>{_PDF_CSS}</style></head><body>{html_body}</body></html>")
    out_path = Path(out_path)
    with open(out_path, "wb") as f:
        result = pisa.CreatePDF(src=html, dest=f, encoding="utf-8")
    if result.err:
        raise RuntimeError(f"PDF generation reported {result.err} error(s).")
    return out_path


# ── EPUB ──────────────────────────────────────────────────────────────────────
def markdown_to_epub(
    md_text: str,
    out_path,
    title: str = "Manuscript",
    author: str = "Unknown",
    language: str = "en",
    base_dir=None,
) -> Path:
    """Convert assembled manuscript Markdown to an EPUB file.

    The manuscript is split on '---' separators (the assembly format). Each section
    becomes one EPUB spine item. The first heading in each section is used as the
    section title for the NCX/Nav table of contents.
    """
    import markdown as md_lib
    from ebooklib import epub

    book = epub.EpubBook()
    book.set_title(title)
    book.add_author(author)
    book.set_language(language)
    book.set_identifier(_slug_id(title))

    # Shared stylesheet
    css_item = epub.EpubItem(
        uid="main-css", file_name="style/main.css",
        media_type="text/css", content=_EPUB_CSS.encode(),
    )
    book.add_item(css_item)

    # Split on '---' separators that the manuscript assembler inserts between sections
    md_text = _preprocess(md_text, diagrams=True, base_dir=Path(base_dir) if base_dir else None)
    raw_sections = [s.strip() for s in md_text.split("\n---\n") if s.strip()]

    spine_items = []
    toc_links = []
    base = Path(base_dir) if base_dir else None
    packaged: set[str] = set()   # image srcs already added as EPUB items

    for i, section in enumerate(raw_sections):
        html_body = _sanitize_html(md_lib.markdown(section, extensions=["extra", "sane_lists"]))

        # Package referenced local images into the EPUB - an unpackaged relative src
        # renders as a broken image in every reader.
        for m in _IMG_TAG.finditer(html_body):
            src = m.group(1)
            p = _resolve_local(src, base)
            if p is None or src in packaged:
                continue
            packaged.add(src)
            book.add_item(epub.EpubItem(
                uid=f"img-{len(packaged)}", file_name=src.replace("\\", "/"),
                media_type=mimetypes.guess_type(p.name)[0] or "application/octet-stream",
                content=p.read_bytes()))

        # Derive a title from the first heading line
        first = section.splitlines()[0] if section else ""
        sec_title = first.lstrip("#").strip() if first.startswith("#") else f"Section {i + 1}"

        file_name = f"section_{i + 1:03d}.xhtml"
        ch = epub.EpubHtml(title=sec_title, file_name=file_name, lang=language)
        ch.content = (
            f'<?xml version="1.0" encoding="utf-8"?>'
            f'<html xmlns="http://www.w3.org/1999/xhtml"><head>'
            f'<title>{_esc(sec_title)}</title>'   # EPUB XHTML must be well-formed XML
            f'<link rel="stylesheet" href="style/main.css" type="text/css"/>'
            f'</head><body>{html_body}</body></html>'
        ).encode()
        ch.add_item(css_item)
        book.add_item(ch)
        spine_items.append(ch)
        toc_links.append(epub.Link(file_name, sec_title, f"section-{i + 1}"))

    book.spine = ["nav"] + spine_items
    book.toc = toc_links
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    out_path = Path(out_path)
    epub.write_epub(str(out_path), book)
    return out_path


# ── HTML ──────────────────────────────────────────────────────────────────────
_HTML_CSS = """
* { box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       max-width: 760px; margin: 48px auto; padding: 0 24px;
       font-size: 18px; line-height: 1.75; color: #1a1a1a; background: #fff; }
h1 { font-size: 2.2em; line-height: 1.2; margin: 0 0 0.25em; }
h2 { font-size: 1.45em; margin-top: 2.2em; padding-bottom: 0.25em;
     border-bottom: 1px solid #e8e8e8; }
h3 { font-size: 1.15em; margin-top: 1.6em; }
p  { margin: 0 0 1.1em; }
a  { color: #0057b8; text-decoration: none; }
a:hover { text-decoration: underline; }
code { background: #f3f3f3; padding: 2px 6px; border-radius: 4px;
       font-size: 0.88em; font-family: 'SFMono-Regular', Consolas, monospace; }
pre  { background: #f6f8fa; border: 1px solid #e1e4e8; border-radius: 6px;
       padding: 1em 1.2em; overflow-x: auto; margin: 1.4em 0; }
pre code { background: none; padding: 0; font-size: 0.85em; }
blockquote { border-left: 4px solid #d0d7de; margin: 1.4em 0;
             padding: 0.4em 1em; color: #57606a; }
img { max-width: 100%; height: auto; border-radius: 4px; }
hr  { border: none; border-top: 1px solid #e8e8e8; margin: 2.5em 0; }
em  { font-style: italic; }
strong { font-weight: 600; }
ol, ul { padding-left: 1.4em; }
li { margin-bottom: 0.4em; }
"""


def markdown_to_html(md_text: str, out_path, title: str = "Article", base_dir=None) -> Path:
    """Render Markdown to a self-contained HTML file with embedded CSS + inlined images."""
    import markdown

    md_text = _preprocess(md_text, diagrams=True, base_dir=Path(base_dir) if base_dir else None)
    try:
        html_body = markdown.markdown(
            md_text, extensions=["extra", "sane_lists", "codehilite", "fenced_code"]
        )
    except Exception:
        html_body = markdown.markdown(md_text, extensions=["extra", "sane_lists"])
    html_body = _sanitize_html(html_body)
    html_body = _inline_images(html_body, Path(base_dir) if base_dir else None)
    html = (
        "<!DOCTYPE html>\n"
        f'<html lang="en"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{_esc(title)}</title>'
        f"<style>{_HTML_CSS}</style>"
        f"</head><body>{html_body}</body></html>"
    )
    out = Path(out_path)
    out.write_text(html, encoding="utf-8")
    return out


# ── DOCX ─────────────────────────────────────────────────────────────────────
def markdown_to_docx(md_text: str, out_path, title: str = "Article", base_dir=None) -> Path:
    """Convert Markdown to .docx via pandoc (must be on PATH)."""
    import subprocess
    import tempfile

    out = Path(out_path)
    md_text = _preprocess(md_text, diagrams=True, base_dir=Path(base_dir) if base_dir else None)
    # Replace horizontal rules (---) with a unicode divider so pandoc
    # doesn't interpret them as YAML metadata block separators.
    safe_md = md_text.replace("\n---\n", "\n\n* * *\n\n")
    with tempfile.NamedTemporaryFile(
        suffix=".md", mode="w", encoding="utf-8", delete=False
    ) as tmp:
        # Write a YAML front-matter block so pandoc won't try to parse
        # the body as YAML, and disable the yaml_metadata_block extension.
        tmp.write(f"---\ntitle: \"{title.replace(chr(34), chr(39))}\"\n---\n\n" + safe_md)
        tmp_path = tmp.name

    cmd = ["pandoc", tmp_path, "-o", str(out),
           "--from", "markdown-yaml_metadata_block+yaml_metadata_block",
           "--to", "docx",
           "--syntax-highlighting=kate",
           "-V", "geometry:margin=1in"]
    if base_dir:
        # The source md is a temp file in another directory - without a resource
        # path, every relative image reference fails to resolve.
        cmd.append(f"--resource-path={base_dir}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        raise RuntimeError("pandoc not found on PATH - install pandoc to export .docx") from None
    finally:
        Path(tmp_path).unlink(missing_ok=True)   # never leak the temp file, even on error
    if result.returncode != 0:
        raise RuntimeError(f"pandoc failed: {result.stderr.strip()}")
    return out


# ── Plain text ────────────────────────────────────────────────────────────────
def markdown_to_txt(md_text: str, out_path, title: str = "Article") -> Path:
    """Strip Markdown to readable plain text."""
    import re
    text = f"{title}\n{'=' * len(title)}\n\n" + _preprocess(md_text, diagrams=False)
    # fenced code blocks first, so their contents aren't mangled by the inline passes
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    # headings
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # bold / italic
    text = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", text)
    text = re.sub(r"_{1,2}([^_]+)_{1,2}", r"\1", text)
    # inline code
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # links → just the label
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # images → empty
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    # html tags
    text = re.sub(r"<[^>]+>", "", text)
    # collapse 3+ blank lines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    out = Path(out_path)
    out.write_text(text.strip() + "\n", encoding="utf-8")
    return out


# ── Markdown passthrough ──────────────────────────────────────────────────────
def markdown_to_md(md_text: str, out_path, title: str = "Article") -> Path:
    """Save the raw Markdown manuscript (title header only if it doesn't have one)."""
    md_text = _normalize_text(md_text)
    first = next((ln for ln in md_text.splitlines() if ln.strip()), "")
    if not first.startswith("# "):
        md_text = f"# {title}\n\n" + md_text
    out = Path(out_path)
    out.write_text(md_text, encoding="utf-8")
    return out
