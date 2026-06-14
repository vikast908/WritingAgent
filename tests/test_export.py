"""Regression tests for manuscript export fixes (PDF code wrap, Mermaid images,
unicode normalization, placeholder byline)."""
from writingagent import export


def test_normalize_text_strips_tofu_glyphs():
    # U+2011 non-breaking hyphen and U+202F narrow no-break space render as boxes
    # in the PDF serif font - they must be normalized to ASCII equivalents.
    raw = "multi‑orchestrator runs in 20 ms"
    out = export._normalize_text(raw)
    assert "‑" not in out and " " not in out
    assert out == "multi-orchestrator runs in 20 ms"


def test_normalize_text_drops_placeholder_byline():
    md = "# Title\n\n**By:** [AUTHOR NAME]\n\nBody text."
    out = export._normalize_text(md)
    assert "[AUTHOR NAME]" not in out
    assert "Body text." in out


def test_normalize_text_keeps_real_byline():
    md = "# Title\n\n**By:** Ada Lovelace\n\nBody."
    out = export._normalize_text(md)
    assert "Ada Lovelace" in out


def test_pre_linebreaks_preserves_code_lines():
    import markdown
    md = "```python\nfrom enum import Enum\nclass S(Enum):\n    A = 1\n```"
    html = export._pre_linebreaks(markdown.markdown(md, extensions=["extra"]))
    # one <br/> per source newline inside the block - keeps code from flattening
    assert html.count("<br/>") == 3
    assert "<pre" in html


def test_render_mermaid_offline_keeps_source(monkeypatch):
    # In fake mode (and on any network failure) the fenced block is preserved so
    # the diagram source still appears instead of breaking the export.
    monkeypatch.setenv("WRITINGAGENT_FAKE", "1")
    md = "```mermaid\nsequenceDiagram\n  A->>B: hi\n```"
    assert export._render_mermaid(md) == md


def test_render_mermaid_falls_back_when_fetch_fails(monkeypatch):
    monkeypatch.delenv("WRITINGAGENT_FAKE", raising=False)
    monkeypatch.setattr(export, "_mermaid_png", lambda code, timeout=12.0: None)
    md = "```mermaid\ngraph TD\n  A-->B\n```"
    assert export._render_mermaid(md) == md  # unchanged: source survives


def test_render_mermaid_embeds_data_uri_without_base_dir(monkeypatch):
    monkeypatch.delenv("WRITINGAGENT_FAKE", raising=False)
    monkeypatch.setattr(export, "_mermaid_png", lambda code, timeout=12.0: b"\x89PNG\r\n\x1a\nXX")
    md = "```mermaid\ngraph TD\n  A-->B\n```"
    out = export._render_mermaid(md)  # no base_dir → inline data URI
    assert "data:image/png;base64," in out and "```mermaid" not in out


def test_render_mermaid_caches_and_references_local_file(tmp_path, monkeypatch):
    # With base_dir the PNG is written under images/ and referenced by relative path,
    # so EPUB/DOCX can package it. A second call reads the cache (no re-fetch).
    monkeypatch.delenv("WRITINGAGENT_FAKE", raising=False)
    calls = {"n": 0}

    def fake_png(code, timeout=12.0):
        calls["n"] += 1
        return b"\x89PNG\r\n\x1a\nDATA"
    monkeypatch.setattr(export, "_mermaid_png", fake_png)
    md = "```mermaid\ngraph TD\n  A-->B\n```"
    out = export._render_mermaid(md, base_dir=tmp_path)
    assert "![Diagram](images/mermaid_" in out
    pngs = list((tmp_path / "images").glob("mermaid_*.png"))
    assert len(pngs) == 1
    export._render_mermaid(md, base_dir=tmp_path)   # second export
    assert calls["n"] == 1                           # served from cache, not re-fetched


def test_normalize_text_strips_section_prefix():
    md = "## Section 5: Wiring It Up\n\nBody.\n\n### Chapter 3 - keep this"
    out = export._normalize_text(md)
    assert "## Wiring It Up" in out          # "Section 5:" stripped
    assert "Chapter 3 - keep this" in out    # book "Chapter" headings untouched


def test_epub_css_wraps_code():
    assert "pre-wrap" in export._EPUB_CSS


def test_pdf_css_wraps_code():
    # The PDF stylesheet must let <pre> wrap, or long code lines get clipped.
    assert "white-space: pre-wrap" in export._PDF_CSS
    assert "word-wrap: break-word" in export._PDF_CSS


def test_markdown_to_pdf_renders_long_code_without_error(tmp_path, monkeypatch):
    monkeypatch.setenv("WRITINGAGENT_FAKE", "1")  # skip mermaid network
    long_line = "x = " + " + ".join(f"variable_number_{i}" for i in range(40))
    md = f"# Doc\n\nText.\n\n```python\n{long_line}\n```\n"
    out = export.markdown_to_pdf(md, tmp_path / "doc.pdf", title="Doc")
    assert out.exists() and out.stat().st_size > 0


def test_markdown_to_txt_normalizes(tmp_path):
    md = "# T\n\nsub‑100 ms latency"
    out = export.markdown_to_txt(md, tmp_path / "o.txt", title="T")
    text = out.read_text(encoding="utf-8")
    assert "‑" not in text and " " not in text
    assert "sub-100 ms" in text
