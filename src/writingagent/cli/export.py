"""Export, polish, and evidence commands: format parsing (single / list / 'all' /
plain English), per-format rendering with isolated failures, and the deterministic
re-polish + evidence-report commands."""
from __future__ import annotations

import re
import sys

from .. import brain, orchestrator, ui
from ._common import _console, _resolve_book

__all__ = [
    "_EXPORT_FORMATS",
    "_QUIET",
    "_EXPORT_FNS",
    "_resolve_formats",
    "_report_export",
    "_export_failed",
    "_run_exports",
    "cmd_export",
    "_DELIVERABLE",
    "cmd_polish",
    "cmd_evidence",
    "cmd_seo",
    "cmd_promote",
]

_EXPORT_FORMATS = ["pdf", "epub", "html", "docx", "txt", "md"]


def _QUIET(*_a, **_k):   # suppress the exporters' own log line; cmd_export prints its own
    return None


_EXPORT_FNS = {
    "pdf":  lambda uid, bid: orchestrator.export_pdf(uid, bid, log=_QUIET),
    "epub": lambda uid, bid: orchestrator.export_epub(uid, bid, log=_QUIET),
    "html": lambda uid, bid: orchestrator.export_html(uid, bid, log=_QUIET),
    "docx": lambda uid, bid: orchestrator.export_docx(uid, bid, log=_QUIET),
    "txt":  lambda uid, bid: orchestrator.export_txt(uid, bid, log=_QUIET),
    "md":   lambda uid, bid: orchestrator.export_md(uid, bid, log=_QUIET),
}


# Split a format request on any reasonable separator: whitespace, comma,
# semicolon, slash, middot, ampersand, plus.
_FMT_SEP = re.compile(r"[\s,;/·&+]+")
# Connector/filler words ignored in plain-English requests ("pdf, epub and word",
# "give me pdf or docx please") - they're noise, not unknown formats.
_FMT_FILLER = frozenset({
    "and", "or", "plus", "also", "then", "the", "a", "an", "to", "in", "into", "as",
    "with", "of", "format", "formats", "file", "files", "version", "versions",
    "please", "me", "i", "want", "need", "would", "like", "export", "exports", "give",
})
# "all" and its plain-English synonyms expand to every format.
_FMT_ALL = frozenset({"all", "everything", "every", "each", "both"})
# Synonyms so natural words resolve to a format id.
_FMT_ALIASES = {
    "word": "docx", "doc": "docx", "msword": "docx", "ms-word": "docx",
    "markdown": "md", "mkd": "md",
    "text": "txt", "plain": "txt", "plaintext": "txt",
    "web": "html", "webpage": "html", "website": "html", "htm": "html",
    "ebook": "epub", "e-book": "epub",
}
_FMT_STRIP = ".,;:!?'\"()[]{}"


def _resolve_formats(raw: str) -> tuple[list[str], list[str]]:
    """Parse an export request into (formats, unknown).

    Understands a single format, a list in any separator (comma, semicolon, slash,
    ·, &, +, or just spaces), 'all', and plain English - "pdf, epub and word",
    "give me markdown & pdf please", "everything". Connector words are ignored;
    common synonyms (word→docx, markdown→md, ebook→epub) are mapped. Order is
    preserved, duplicates removed - so even the whole 'pdf · epub · …' choices line
    resolves to every format."""
    out: list[str] = []
    bad: list[str] = []
    seen: set[str] = set()

    def add(fmt: str) -> None:
        if fmt not in seen:
            seen.add(fmt)
            out.append(fmt)

    for tok in _FMT_SEP.split((raw or "").strip().lower()):
        tok = tok.strip(_FMT_STRIP)
        if not tok or tok in _FMT_FILLER:
            continue
        if tok in _FMT_ALL:
            for f in _EXPORT_FORMATS:
                add(f)
        elif tok in _EXPORT_FORMATS:
            add(tok)
        elif tok in _FMT_ALIASES:
            add(_FMT_ALIASES[tok])
        else:
            bad.append(tok)
    return out, bad


def _report_export(console, fmt: str, out) -> None:
    if console and out is not None:
        kb = out.stat().st_size / 1024
        # Show the ABSOLUTE path so "where's my file?" is never a guess - the export dir
        # defaults to the project's brain folder, not the writer's cwd. Rich renders an
        # OSC-8 hyperlink where supported; as_uri() is valid on Windows/macOS/Linux.
        try:
            full = out.resolve()
            uri = full.as_uri()
        except ValueError:
            full, uri = out, str(out)
        console.print(f"  [bold {ui.ON_CLR}]✓ {fmt}[/]  "
                      f"[link={uri}]{full}[/]  [{ui.DIM}]({kb:.0f} KB)[/]")
    else:
        try:
            out = out.resolve() if out is not None else out
        except (OSError, ValueError):
            pass
        print(f"[OK] {fmt} -> {out}")


def _export_failed(console, fmt: str, e: Exception) -> None:
    """One format failing must never abort the rest - but the message should preserve
    momentum: say WHY and HOW to recover, not just dump the exception. Special-cases
    the two common, fully-recoverable causes (file open elsewhere; optional dep missing)."""
    s = str(e)
    locked = (isinstance(e, PermissionError) or getattr(e, "winerror", None) == 32
              or "being used by another process" in s.lower() or "permission denied" in s.lower())
    if locked:
        hint = f"the open file is locked — close it in your viewer, then  export {fmt}"
    elif isinstance(e, ModuleNotFoundError) or "No module named" in s:
        mod = s.split("'")[1] if "'" in s else "the optional dependency"
        hint = f"needs an optional package —  pip install {mod}  then  export {fmt}"
    else:
        hint = f"{type(e).__name__}: {e}  —  retry with  export {fmt}"
    if console:
        console.print(f"  [bold {ui.ERR}]✗ {fmt}[/]  [{ui.DIM}]{hint}[/]")
        console.print(f"  [{ui.DIM}](other formats were still written)[/]")
    else:
        print(f"[FAIL] {fmt}: {hint}  (other formats were still written)")


def _run_exports(console, formats, uid, project_id) -> int:
    """Render every requested format, reporting each result. One format failing must
    not abort the rest (its error is shown, the loop continues). Returns the count of
    formats written successfully."""
    ok = 0
    for fmt in formats:
        try:
            out = _EXPORT_FNS[fmt](uid, project_id)
        except Exception as e:  # noqa: BLE001 - one bad format must not abort the others
            _export_failed(console, fmt, e)
            continue
        ok += 1
        _report_export(console, fmt, out)
    return ok


def cmd_export(args, cfg, settings, uid):
    book_id = _resolve_book(uid, args.book_id)
    console = _console()
    # Request can come positionally (`export all`, `export pdf epub`) or via --format.
    raw = " ".join(getattr(args, "formats", None) or [])
    if getattr(args, "format", None):
        raw = f"{raw} {args.format}".strip()
    if not raw:
        choices = "  ·  ".join(_EXPORT_FORMATS)
        if console:
            console.print(f"  [{ui.GOLD}]formats[/]  [dim]{choices}  ·  all[/]")
            raw = console.input(f"  [{ui.INK}]format[/] [dim][pdf, or 'all']:[/] ").strip() or "pdf"
        else:
            print(f"\nExport formats:  {choices}  ·  all")
            raw = input("Format [pdf]: ").strip() or "pdf"
    formats, bad = _resolve_formats(raw)
    if bad:
        valid = ", ".join(_EXPORT_FORMATS)
        note = f"unknown format(s): {', '.join(bad)} - choose from {valid}, or 'all'"
        if console:
            console.print(f"  [{ui.ERR}]{note}[/]")
        elif not formats:
            sys.exit(f"Unknown format(s): {', '.join(bad)}. Choose from {valid}, or 'all'.")
    if not formats:
        if console:
            console.print(f"  [{ui.ERR}]nothing to export[/]")
            return
        sys.exit("No formats to export.")
    ok = _run_exports(console, formats, uid, book_id)
    if len(formats) > 1:
        line = f"exported {ok}/{len(formats)} formats"
        console.print(f"  [{ui.DIM}]{line}[/]") if console else print(line)


_DELIVERABLE = {"pdf": "manuscript.pdf", "epub": "manuscript.epub",
                "html": "manuscript.html", "docx": "manuscript.docx",
                "txt": "manuscript.txt", "md": "manuscript_export.md"}


def cmd_polish(args, cfg, settings, uid):
    """Deterministically re-fix an existing manuscript (references, citations,
    figures) with no LLM call, then refresh its exports."""
    book_id = _resolve_book(uid, args.book_id)
    console = _console()
    log = (lambda m: console.print(m)) if console else print
    orchestrator.repolish_manuscript(uid, book_id, settings, log=log)
    out_dir = brain.resolve_export_dir(uid, book_id)
    raw = getattr(args, "format", None)
    if raw:
        formats, _bad = _resolve_formats(raw)
    else:   # refresh whatever deliverables already exist; nothing -> just the .md source
        formats = [f for f, name in _DELIVERABLE.items() if (out_dir / name).exists()]
    if console:
        console.print(f"  [bold {ui.ON_CLR}]✓ polished[/]  [dim]{book_id}[/]")
    _run_exports(console, formats, uid, book_id)


def cmd_evidence(args, cfg, settings, uid):
    """Write evidence_report.md - the thesis + every source ranked by influence. No LLM."""
    book_id = _resolve_book(uid, args.book_id)
    console = _console()
    log = (lambda m: console.print(m)) if console else print
    out = orchestrator.build_evidence_report(uid, book_id, log=log)
    if out:
        _report_export(console, "evidence", out)


def cmd_seo(args, cfg, settings, uid):
    """Write seo_report.md + keywords.json - the on-page audit (deterministic) plus
    the keyword/hashtag/meta-description signals pack (one flash call)."""
    book_id = _resolve_book(uid, args.book_id)
    console = _console()
    log = (lambda m: console.print(m)) if console else print
    out = orchestrator.build_seo_report(cfg, uid, book_id,
                                        keyword=getattr(args, "keyword", "") or "", log=log)
    _report_export(console, "seo", out)


def cmd_promote(args, cfg, settings, uid):
    """Write promo/<format>.md - X thread, LinkedIn post, newsletter teaser, TL;DR -
    plus 5 headline variants, all reusing the SEO keyword pack."""
    from .. import promote as promote_mod
    book_id = _resolve_book(uid, args.book_id)
    console = _console()
    log = (lambda m: console.print(m)) if console else print
    raw = (getattr(args, "to", "") or "").strip()
    formats = [f.strip() for f in raw.split(",") if f.strip()] or None
    bad = [f for f in (formats or []) if f not in promote_mod.FORMATS]
    if bad:
        sys.exit(f"Unknown format(s): {', '.join(bad)}. "
                 f"Choose from: {', '.join(promote_mod.FORMATS)}")
    out = orchestrator.build_promo_pack(cfg, uid, book_id, formats=formats,
                                        keyword=getattr(args, "keyword", "") or "", log=log)
    if console:
        console.print(f"  [bold {ui.ON_CLR}]✓ promo pack[/]  [dim]{out}[/]")
    else:
        print(f"promo pack -> {out}")
