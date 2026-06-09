"""Manuscript export: PDF (xhtml2pdf) and EPUB (ebooklib)."""
from __future__ import annotations

from pathlib import Path

# ── Shared styles ─────────────────────────────────────────────────────────────
_PDF_CSS = """
@page { size: A5; margin: 2cm 1.8cm; }
body { font-family: Georgia, 'Times New Roman', serif; font-size: 11pt; line-height: 1.5; }
h1 { font-size: 22pt; text-align: center; margin: 2cm 0 1cm; }
h2 { font-size: 15pt; margin-top: 1cm; page-break-before: always; }
h3 { font-size: 12pt; margin-top: 0.8cm; }
p { text-align: justify; margin: 0 0 0.6em; }
hr { border: 0; margin: 1em 0; }
em { font-style: italic; }
"""

_EPUB_CSS = """
body { font-family: Georgia, 'Times New Roman', serif; font-size: 1em; line-height: 1.6; margin: 1em 2em; }
h1 { font-size: 2em; text-align: center; margin: 2em 0 1em; }
h2 { font-size: 1.4em; margin-top: 2em; }
h3 { font-size: 1.1em; margin-top: 1.2em; }
p { text-align: justify; margin: 0 0 0.7em; }
img { max-width: 100%; }
em { font-style: italic; }
"""


# ── PDF ───────────────────────────────────────────────────────────────────────
def markdown_to_pdf(md_text: str, out_path, title: str = "Manuscript"):
    """Render Markdown to a paginated PDF. New page per chapter (## heading)."""
    import markdown
    from xhtml2pdf import pisa

    html_body = markdown.markdown(md_text, extensions=["extra", "sane_lists"])
    html = (f"<html><head><meta charset='utf-8'><title>{title}</title>"
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
    book.set_identifier(f"bookwriter-{title.lower().replace(' ', '-')}")

    # Shared stylesheet
    css_item = epub.EpubItem(
        uid="main-css", file_name="style/main.css",
        media_type="text/css", content=_EPUB_CSS.encode(),
    )
    book.add_item(css_item)

    # Split on '---' separators that the manuscript assembler inserts between sections
    raw_sections = [s.strip() for s in md_text.split("\n---\n") if s.strip()]

    spine_items = []
    toc_links = []

    for i, section in enumerate(raw_sections):
        html_body = md_lib.markdown(section, extensions=["extra", "sane_lists"])

        # Derive a title from the first heading line
        first = section.splitlines()[0] if section else ""
        sec_title = first.lstrip("#").strip() if first.startswith("#") else f"Section {i + 1}"

        file_name = f"section_{i + 1:03d}.xhtml"
        ch = epub.EpubHtml(title=sec_title, file_name=file_name, lang=language)
        ch.content = (
            f'<?xml version="1.0" encoding="utf-8"?>'
            f'<html xmlns="http://www.w3.org/1999/xhtml"><head>'
            f'<title>{sec_title}</title>'
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


def markdown_to_html(md_text: str, out_path, title: str = "Article") -> "Path":
    """Render Markdown to a self-contained HTML file with embedded CSS."""
    import markdown

    try:
        html_body = markdown.markdown(
            md_text, extensions=["extra", "sane_lists", "codehilite", "fenced_code"]
        )
    except Exception:
        html_body = markdown.markdown(md_text, extensions=["extra", "sane_lists"])
    html = (
        "<!DOCTYPE html>\n"
        f'<html lang="en"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{title}</title>'
        f"<style>{_HTML_CSS}</style>"
        f"</head><body>{html_body}</body></html>"
    )
    out = Path(out_path)
    out.write_text(html, encoding="utf-8")
    return out


# ── DOCX ─────────────────────────────────────────────────────────────────────
def markdown_to_docx(md_text: str, out_path, title: str = "Article") -> "Path":
    """Convert Markdown to .docx via pandoc (must be on PATH)."""
    import subprocess
    import tempfile

    out = Path(out_path)
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

    result = subprocess.run(
        ["pandoc", tmp_path, "-o", str(out),
         "--from", "markdown-yaml_metadata_block+yaml_metadata_block",
         "--to", "docx",
         "--syntax-highlighting=kate",
         "-V", "geometry:margin=1in"],
        capture_output=True, text=True,
    )
    Path(tmp_path).unlink(missing_ok=True)
    if result.returncode != 0:
        raise RuntimeError(f"pandoc failed: {result.stderr.strip()}")
    return out


# ── Plain text ────────────────────────────────────────────────────────────────
def markdown_to_txt(md_text: str, out_path, title: str = "Article") -> "Path":
    """Strip Markdown to readable plain text."""
    import re
    text = f"{title}\n{'=' * len(title)}\n\n" + md_text
    # headings
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # bold / italic
    text = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", text)
    text = re.sub(r"_{1,2}([^_]+)_{1,2}", r"\1", text)
    # inline code
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # fenced code blocks
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
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
def markdown_to_md(md_text: str, out_path, title: str = "Article") -> "Path":
    """Save the raw Markdown manuscript (with a title header prepended)."""
    out = Path(out_path)
    out.write_text(f"# {title}\n\n" + md_text, encoding="utf-8")
    return out
