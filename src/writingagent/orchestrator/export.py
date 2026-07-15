"""Export + re-polish surface: turn a finished manuscript into pdf/epub/html/docx/
txt/md, rebuild the deterministic evidence report, and re-run the polish pass on an
existing manuscript (repolish_manuscript). Self-contained: only the renderers, brain,
and polish (lazy) - no dependency on the book/article pipelines or common helpers.
"""
from __future__ import annotations

import re

from .. import brain
from ..brain import ArticlePaths, BookPaths

__all__ = [
    '_unique_sources',
    'repolish_manuscript',
    'build_evidence_report',
    'build_seo_report',
    'apply_seo',
    'build_promo_pack',
    'build_restyle',
    '_export_paths_and_title',
    'export_pdf',
    'export_epub',
    'export_html',
    'export_docx',
    'export_txt',
    'export_md',
]


def _unique_sources(paths) -> list[dict]:
    """Registry sources, de-duped by URL, order (= first-seen) preserved."""
    raw = brain.read_json(paths.sources_json) or []
    seen: set = set()
    unique: list[dict] = []
    for s in raw:
        url = s.get("url", "") if isinstance(s, dict) else getattr(s, "url", "")
        if url and url not in seen:
            seen.add(url)
            unique.append(s if isinstance(s, dict) else s.model_dump())
    return unique


def repolish_manuscript(uid: str, project_id: str, settings, *, log=print):
    """Deterministically re-fix an EXISTING article manuscript - no LLM, ~0 tokens.

    Rebuilds the References list (dated, influence-scored, ranked), pulls stray
    mid-article reference dumps, optionally strips inline [N] markers, and de-dupes
    figures (drops the model's 'Figure N.N' caption-headings and a redundant embedded
    SVG when a rendered diagram is already present). Returns the manuscript path."""
    from .. import polish
    paths = ArticlePaths(project_id, uid)
    if not paths.run_state.exists():
        raise FileNotFoundError(f"'{project_id}' is not an article (re-polish is article-only).")
    md = brain.read_text(paths.manuscript)
    if not md:
        raise FileNotFoundError(f"No manuscript for '{project_id}'.")

    # Drop any existing References section + the trailing rule before it (rebuilt below).
    body = re.split(r"(?im)^##[ \t]*References\b", md, maxsplit=1)[0]
    body = re.sub(r"\n+-{3,}\s*$", "", body.rstrip())
    keywords = (brain.read_text(paths.root / "thesis.md") or "") + "\n" + \
        "\n".join(re.findall(r"(?m)^#+ (.+)$", body))

    body = polish.dedupe_figures(body)
    body = polish.strip_reference_dumps(body)

    unique = _unique_sources(paths)
    refs_md = ""
    if unique and getattr(settings, "rank_references", True):
        refs_md = polish.build_references(polish.score_sources(unique, body, keywords))
    elif unique:
        refs_md = "\n".join(["## References", ""]
                            + [f"{i}. [{s.get('title', 'Source')}]({s.get('url', '')})"
                               + (f" - {s['date']}" if s.get("date") else "")
                               for i, s in enumerate(unique, 1)])

    if getattr(settings, "strip_inline_citations", True):
        body = polish.strip_inline_citations(body)        # after scoring, which needs them

    out = body.rstrip() + (("\n\n---\n\n" + refs_md + "\n") if refs_md else "\n")
    out = polish.refresh_read_time(out)   # prose-based estimate (code + refs not counted)
    brain.write_text(paths.manuscript, out)
    n_refs = refs_md.count("\n") and sum(1 for ln in refs_md.splitlines() if re.match(r"\d+\. ", ln))
    log(f"   [re-polish] references rebuilt ({n_refs} ranked), citations + stray refs cleaned, "
        f"read time -> {polish.read_time_min(out)} min")
    try:   # refresh the shareable evidence report too (best-effort)
        build_evidence_report(uid, project_id, log=lambda *_a, **_k: None)
    except Exception:  # noqa: BLE001
        pass
    return paths.manuscript


def build_evidence_report(uid: str, project_id: str, *, log=print):
    """Write `evidence_report.md` for an article: the thesis it argues + every source ranked
    by influence, built deterministically from the finished manuscript (no LLM, ~0 tokens).
    The shareable proof behind the 'argues a thesis, cites real sources' claim. Returns the
    path, or None when there's nothing to report. Article-only."""
    from .. import polish
    paths = ArticlePaths(project_id, uid)
    if not paths.run_state.exists():
        raise FileNotFoundError(f"'{project_id}' is not an article (evidence report is article-only).")
    md = brain.read_text(paths.manuscript) or ""
    thesis = brain.read_text(paths.root / "thesis.md") or ""
    report = polish.build_evidence_report(md, thesis)
    if not report:
        log("   [evidence] nothing to report (no ranked sources or thesis)")
        return None
    out = paths.root / "evidence_report.md"
    brain.write_text(out, report)
    log(f"   [evidence] -> {out}")
    return out


def _project_paths(uid: str, project_id: str):
    """ArticlePaths when the id is an article, else BookPaths."""
    art = ArticlePaths(project_id, uid)
    return art if art.run_state.exists() else BookPaths(project_id, uid)


def build_seo_report(cfg, uid: str, project_id: str, *, keyword: str = "", log=print):
    """Write `seo_report.md` + `keywords.json` (plan §24): one flash call names the
    signals pack (primary/secondary keywords, meta description, hashtags - pass
    `keyword` to pin the primary), then a DETERMINISTIC on-page audit scores the
    manuscript (title/keyword placement/hierarchy/readability/links/alts) with the
    craft 'feel' metrics appended. Returns the report path. Articles and books."""
    from .. import craft, seo
    root, manuscript, title, _out = _export_paths_and_title(uid, project_id)
    md = brain.read_text(manuscript)
    if not md:
        raise FileNotFoundError(f"No manuscript for '{project_id}'. Run it first.")
    m = re.search(r"(?m)^# (.+)$", md)
    title = m.group(1).strip() if m else title
    thesis = brain.read_text(root / "thesis.md") or ""
    state = brain.read_json(_project_paths(uid, project_id).run_state) or {}
    register = state.get("register") or None
    pack = seo.keyword_pack(cfg, title, thesis, md, explicit_primary=keyword)
    score, checks = seo.validate(md, pack, register)
    report = seo.render_report(title, score, checks, pack, register,
                               feel=craft.report(md, register))
    out = root / "seo_report.md"
    brain.write_text(out, report)
    brain.write_json(root / "keywords.json", pack.model_dump())
    todo = sum(1 for c in checks if c.status != "pass")
    log(f"   [seo] score {score}/100, {todo} item(s) to fix -> {out}")
    return out


def apply_seo(cfg, uid: str, project_id: str, *, keyword: str = "", log=print):
    """APPLY SEO to the finished piece (plan §24.1), not just report it: name the signals
    pack (keyword pinned), rewrite the manuscript title to carry the primary keyword + fit
    the SERP length, write it back, then (re)build the report + keywords.json so the HTML
    export picks up the fresh meta tags. Returns the report path. Called by the auto-promote
    tail and the `seo --apply` command. Deterministic where it can be; one flash call for
    the title. Never raises fatally (promotion is additive)."""
    from .. import seo
    root, manuscript, title, _out = _export_paths_and_title(uid, project_id)
    md = brain.read_text(manuscript)
    if not md:
        raise FileNotFoundError(f"No manuscript for '{project_id}'. Run it first.")
    m = re.search(r"(?m)^# (.+)$", md)
    hd = m.group(1).strip() if m else title
    thesis = brain.read_text(root / "thesis.md") or ""
    kw = keyword or (brain.read_json(_project_paths(uid, project_id).run_state) or {}).get("seo_keyword", "")
    pack = seo.keyword_pack(cfg, hd, thesis, md, explicit_primary=kw)
    new_md, changes = seo.optimize_manuscript(cfg, md, pack, log=log)
    if changes:
        brain.write_text(manuscript, new_md)
        log(f"   [seo] applied: {'; '.join(changes)}")
    else:
        log("   [seo] title already carries the keyword and fits - no change")
    # rebuild report + keywords.json against the (possibly) updated manuscript
    return build_seo_report(cfg, uid, project_id, keyword=pack.primary, log=log)


def build_promo_pack(cfg, uid: str, project_id: str, *, formats=None,
                     keyword: str = "", log=print):
    """Write `promo/<format>.md` (x-thread, linkedin, newsletter-teaser, tldr) +
    `promo/headlines.md` for a finished piece (plan §24). Reuses `keywords.json`
    when present (run `seo` first, or it derives a pack on the fly) so the keyword
    and hashtags stay consistent across every surface. Returns the promo dir."""
    from .. import promote, seo
    from .. import schemas as S
    root, manuscript, title, _out = _export_paths_and_title(uid, project_id)
    md = brain.read_text(manuscript)
    if not md:
        raise FileNotFoundError(f"No manuscript for '{project_id}'. Run it first.")
    m = re.search(r"(?m)^# (.+)$", md)
    title = m.group(1).strip() if m else title
    thesis = brain.read_text(root / "thesis.md") or ""
    saved = brain.read_json(root / "keywords.json")
    pack = (S.KeywordPack(**saved) if saved
            else seo.keyword_pack(cfg, title, thesis, md, explicit_primary=keyword))
    promo = root / "promo"
    promo.mkdir(parents=True, exist_ok=True)
    for fmt in [f for f in (formats or promote.FORMATS) if f in promote.FORMATS]:
        text = promote.repurpose(cfg, fmt, title=title, thesis=thesis,
                                 manuscript=md, pack=pack)
        if text:
            brain.write_text(promo / f"{fmt}.md", text + "\n")
            log(f"   [promote] {fmt} -> {promo / (fmt + '.md')}")
        else:
            log(f"   [promote] {fmt}: nothing produced")
    heads = promote.headline_variants(cfg, title=title, thesis=thesis, pack=pack)
    if heads:
        brain.write_text(promo / "headlines.md", "# Headline variants\n\n"
                         + "\n".join(f"{i}. {h}" for i, h in enumerate(heads, 1)) + "\n")
        log(f"   [promote] {len(heads)} headline variants -> {promo / 'headlines.md'}")
    return promo


def build_restyle(cfg, uid: str, project_id: str, *, register: str = "", persona: str = "",
                  emotion: str = "", log=print):
    """Re-voice the finished manuscript into a chosen style/persona/emotion (plan §23), on
    the flash tier, and write it to `restyled/<combo>.md` (the original is untouched). Values
    are validated against the known sets; unknown -> ignored. Returns the path, or None if
    nothing was produced. Books and articles."""
    from .. import compositor, emotions, personas, promote, registers
    reg = register if register in registers.names() else ""
    per = persona if persona in personas.names() else ""
    emo = emotion if (emotion and emotions.get(emotion)) else ""
    if not (reg or per or emo):
        raise ValueError("restyle needs at least one of register/persona/emotion")
    root, manuscript, title, _out = _export_paths_and_title(uid, project_id)
    md = brain.read_text(manuscript)
    if not md:
        raise FileNotFoundError(f"No manuscript for '{project_id}'. Run it first.")
    m = re.search(r"(?m)^# (.+)$", md)
    hd = m.group(1).strip() if m else title
    voice = compositor.voice(uid, reg or None, per or None, emo or None, log=lambda *a: None)
    out_text = promote.restyle(cfg, title=hd, manuscript=md, register=reg or None,
                               persona=per or None, emotion=emo or None, voice=voice)
    if not out_text:
        log("   [restyle] no output (guard tripped or flash unavailable) - original kept")
        return None
    combo = "-".join(x for x in (reg, per, emo) if x) or "restyled"
    out = root / "restyled" / f"{combo}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    brain.write_text(out, out_text)
    log(f"   [restyle] {combo} -> {out}")
    return out


def _export_paths_and_title(uid: str, project_id: str):
    """Return (root, manuscript_path, title, out_dir) for either article or book.

    `root` stays the brain working dir (used as base_dir for images/diagrams);
    `out_dir` is where the rendered file is written - the user's chosen save folder
    (see /path), defaulting to `root`."""
    art = ArticlePaths(project_id, uid)
    if art.run_state.exists():
        state = brain.read_json(art.run_state) or {}
        title = state.get("article_id", project_id)
        root, manuscript = art.root, art.manuscript
    else:
        bk = BookPaths(project_id, uid)
        plan_data = brain.read_json(bk.root / "plan.json") or {}
        title = plan_data.get("title", project_id)
        root, manuscript = bk.root, bk.manuscript
    return root, manuscript, title, brain.resolve_export_dir(uid, project_id)


def _export(uid: str, book_id: str, *, filename: str, renderer: str, label: str,
            log=print, pass_base_dir: bool = True, **extra):
    """Shared body for every export_*: load the manuscript, render it to `filename`
    in the project's export dir via the named `export` renderer, log, return the path.

    `renderer` is the attribute name on the `export` module (e.g. "markdown_to_pdf").
    `pass_base_dir` forwards the project root as base_dir (rich formats); the plain
    text/markdown renderers take no base_dir. `extra` carries per-format kwargs
    (e.g. author= for epub)."""
    from .. import export
    root, manuscript, title, out_dir = _export_paths_and_title(uid, book_id)
    md = brain.read_text(manuscript)
    if not md:
        raise FileNotFoundError(f"No manuscript for '{book_id}'. Run it first.")
    out = out_dir / filename
    kwargs = dict(title=title, **extra)
    if pass_base_dir:
        kwargs["base_dir"] = root
    getattr(export, renderer)(md, out, **kwargs)
    log(f"[OK] {label} -> {out}")
    return out


def _epub_author(uid: str) -> str:
    """Author for the EPUB metadata: the `name:` line from the user profile, else uid."""
    author_meta = brain.read_text(brain.user_profile(uid)) or ""
    m = re.search(r"(?m)^name:\s*(.+)$", author_meta)
    return m.group(1).strip() if m else uid


def export_pdf(uid: str, book_id: str, *, log=print):
    return _export(uid, book_id, filename="manuscript.pdf",
                   renderer="markdown_to_pdf", label="PDF", log=log)


def export_epub(uid: str, book_id: str, *, log=print):
    return _export(uid, book_id, filename="manuscript.epub",
                   renderer="markdown_to_epub", label="EPUB", log=log,
                   author=_epub_author(uid))


def export_html(uid: str, book_id: str, *, log=print):
    # SEO/OG head tags from the signals pack (run `seo` to build keywords.json);
    # missing pack -> thesis claim as the description, or no extra tags at all.
    root, _m, _t, _o = _export_paths_and_title(uid, book_id)
    saved = brain.read_json(root / "keywords.json") or {}
    desc = (saved.get("meta_description") or "").strip()
    if not desc:
        thesis = brain.read_text(root / "thesis.md") or ""
        cm = re.search(r"(?m)^\*\*Claim:\*\*\s*(.+)$", thesis)
        desc = cm.group(1).strip()[:300] if cm else ""
    keywords = [k for k in [saved.get("primary", ""), *(saved.get("secondary") or [])] if k]
    meta = {"description": desc, "keywords": keywords} if (desc or keywords) else None
    return _export(uid, book_id, filename="manuscript.html",
                   renderer="markdown_to_html", label="HTML", log=log, meta=meta)


def export_docx(uid: str, book_id: str, *, log=print):
    return _export(uid, book_id, filename="manuscript.docx",
                   renderer="markdown_to_docx", label="DOCX", log=log)


def export_txt(uid: str, book_id: str, *, log=print):
    return _export(uid, book_id, filename="manuscript.txt",
                   renderer="markdown_to_txt", label="TXT", log=log,
                   pass_base_dir=False)


def export_md(uid: str, book_id: str, *, log=print):
    return _export(uid, book_id, filename="manuscript_export.md",
                   renderer="markdown_to_md", label="MD", log=log,
                   pass_base_dir=False)
