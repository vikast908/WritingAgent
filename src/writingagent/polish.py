"""Deterministic manuscript polishing - no LLM, so it's free to run.

Two jobs, shared by assembly-time and the cheap re-fix of an existing manuscript:

1. Citations & references: pull every stray mid-article reference dump out, optionally
   strip the inline [N] markers from the prose, and build ONE end References list that is
   dated, scored by influence (0-100), and sorted most-influential first.
2. Figures: drop the model's self-numbered "Figure N.N" caption-headings (the misleading
   blank-gap) and de-duplicate a section that carries both a rendered diagram and an embedded
   SVG, so a figure never appears twice.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

# ── citations ─────────────────────────────────────────────────────────────────
# An inline marker: [12], [N1], and chains like [38][39]. The (?!\() guard keeps a
# numeric markdown link label - [1](https://...) - intact (mirrors common._CITE);
# without it strip_inline_citations turned that link into a bare "(url)".
_INLINE_CITE = re.compile(r"[ \t]?\[N?\d+\](?!\()")
# A bare reference line the writer dumped mid-article: "[28] Nielsen, J. (1993)...".
_REF_LINE = re.compile(r"^\s*\[N?\d+\]\s+\S")
# A writer-emitted References/Bibliography/Sources block, heading to next rule or end.
_REF_HEADED = re.compile(r"(?ims)\n#{1,4}[ \t]*(?:references|bibliography|sources|works\s+cited)\b.*?(?=\n---|\Z)")

# ── figures ───────────────────────────────────────────────────────────────────
# Fenced diagrams the model drew itself (we want the producer to own figures).
_MERMAID = re.compile(r"(?ms)^```[ \t]*(?:mermaid|pie|sequenceDiagram|flowchart|graph|gantt)\b.*?^```[ \t]*$\n?")
# A "## Figure 2.1: ..." heading the model emits above its diagram (the blank-gap top).
_FIG_HEADING = re.compile(r"(?im)^#{2,5}[ \t]*Figure\s+\d+(?:\.\d+)?\s*[:.\-–—].*$\n?")
# An embedded generated diagram image + its immediate caption line.
_SVG_EMBED = re.compile(r"(?m)^!\[[^\]]*\]\((?:images/)?[^)]*_diagram\.svg\)\s*\n(?:\*Figure[^\n]*\*\s*\n?)?")

_STOP = frozenset(
    "the a an of to for and or in on at by with from as is are be was were this that these those "
    "it its their our your his her them they we you i he she has have had will would can could may "
    "should must not no but so if then than over under into out up down off about which who whom "
    "what when where why how all any each more most other some such only own same too very".split()
)


def _tokens(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", (text or "").lower())
            if len(w) > 2 and w not in _STOP]


# ── public transforms ─────────────────────────────────────────────────────────
def strip_inline_citations(md: str) -> str:
    """Remove every inline [N]/[N1] marker (and chains), tidy the spacing left behind."""
    out = _INLINE_CITE.sub("", md)
    out = re.sub(r"[ \t]+([.,;:!?])", r"\1", out)     # "word ." -> "word."
    out = re.sub(r"\(\s+", "(", out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    return out


def strip_reference_dumps(md: str) -> str:
    """Remove writer-emitted reference lists that leaked into the body - both headed
    blocks and bare runs of 2+ '[N] ...' lines - so references live only at the end."""
    md = _REF_HEADED.sub("", md)
    lines = md.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        if _REF_LINE.match(lines[i]):
            j = i
            refs = 0
            while j < len(lines) and (_REF_LINE.match(lines[j]) or not lines[j].strip()):
                if _REF_LINE.match(lines[j]):
                    refs += 1
                j += 1
            if refs >= 2:                              # a dump, not a one-off line
                i = j
                continue
        out.append(lines[i])
        i += 1
    return "\n".join(out)


def strip_model_figures(md: str) -> str:
    """Remove model-drawn diagrams and self-numbered figure headings (used going
    forward, where the producer owns every figure)."""
    return _FIG_HEADING.sub("", _MERMAID.sub("", md))


def dedupe_figures(md: str) -> str:
    """For an existing manuscript: drop the model's 'Figure N.N' caption-headings, and
    when a section has BOTH a rendered diagram and an embedded _diagram.svg, drop the
    redundant SVG embed so the figure doesn't appear twice."""
    md = _FIG_HEADING.sub("", md)
    sections = re.split(r"(?m)^(?=## )", md)
    fixed = []
    for sec in sections:
        has_mermaid = bool(_MERMAID.search(sec))
        if has_mermaid and _SVG_EMBED.search(sec):
            sec = _SVG_EMBED.sub("", sec)              # keep the prose-referenced diagram
        fixed.append(sec)
    return "".join(fixed)


def _norm_date(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw or raw.lower() in {"n/a", "unknown", "no date", "n.d.", "none", "null"}:
        return "n.d."
    m = re.search(r"(?:19|20)\d{2}", raw)              # prefer a clean 4-digit year
    return m.group(0) if m else raw


# ── source authority (credibility heuristic, deterministic) ──────────────────────
# A source's domain is a cheap, deterministic proxy for how much weight a reader should
# give a citation. The blind A/B pilot found the writer padding citations with low-
# authority sources (e.g. resume-template sites) to hit volume: authority lets the
# evidence report SURFACE that and the References ranking DEMOTE it, without any model
# call. Scores are 0-100; an unknown domain gets a neutral baseline - absence of signal
# is not a penalty. All tables/constants are tunable (plan §15.5).
AUTH_NEUTRAL = 60       # unknown / no strong domain signal
AUTH_HIGH = 95          # government, standards bodies, primary research
AUTH_REPUTABLE = 80     # established reference works, official docs, major outlets
AUTH_LOW = 25           # SEO / template / content-farm signals

_HIGH_TLDS = (".gov", ".mil", ".int", ".edu")
_HIGH_TLD_PARTS = (".gov.", ".edu.", ".ac.")      # e.g. nih.gov.uk, ox.ac.uk, anu.edu.au
_HIGH_DOMAINS = frozenset("""
arxiv.org nature.com science.org sciencedirect.com ieee.org acm.org ietf.org
rfc-editor.org w3.org whatwg.org nist.gov ncbi.nlm.nih.gov pubmed.ncbi.nlm.nih.gov
doi.org springer.com link.springer.com jstor.org plos.org who.int oecd.org
""".split())
_REPUTABLE_DOMAINS = frozenset("""
wikipedia.org developer.mozilla.org docs.python.org python.org postgresql.org
kubernetes.io reuters.com apnews.com bbc.com bbc.co.uk nytimes.com wsj.com
economist.com ft.com theguardian.com github.com gitlab.com stackoverflow.com
""".split())
# Substrings in the host that flag a low-authority SEO / template / content-farm page.
# Kept conservative so a legitimate domain is not penalised by accident.
_LOW_SIGNALS = ("template", "resume", "-cv", "cv-", "topten", "top-10",
                "listicle", "best-of-", "freelancer")


def _domain_of(url: str) -> str:
    """Registrable-ish host for a URL, leading 'www.' stripped ('' on error)."""
    try:
        net = urlparse(url).netloc.lower()
        return net[4:] if net.startswith("www.") else net
    except Exception:  # noqa: BLE001
        return ""


def _domain_in(dom: str, table: frozenset) -> bool:
    return dom in table or any(dom.endswith("." + d) for d in table)


def source_authority(url: str) -> int:
    """A 0-100 credibility proxy for a source, derived from its domain alone (no model
    call). Unknown domains get a neutral baseline; SEO/template signals are demoted;
    government/standards/primary research and established outlets are promoted. Tunable
    via the tables above (plan §15.5)."""
    dom = _domain_of(url)
    if not dom:
        return AUTH_NEUTRAL
    if any(sig in dom for sig in _LOW_SIGNALS):
        return AUTH_LOW
    if dom.endswith(_HIGH_TLDS) or any(p in dom for p in _HIGH_TLD_PARTS):
        return AUTH_HIGH
    if _domain_in(dom, _HIGH_DOMAINS):
        return AUTH_HIGH
    if _domain_in(dom, _REPUTABLE_DOMAINS):
        return AUTH_REPUTABLE
    return AUTH_NEUTRAL


def score_sources(sources: list, body: str, keywords_text: str) -> list[dict]:
    """Rank sources by influence on the article. Influence = how often the source is
    actually cited in the body (weighted heavily) + how well its title matches the
    article's thesis/headings. Each source also carries an `authority` (0-100, from its
    domain) that breaks ties so a heavily-cited low-authority pad ranks below an equally-
    cited credible source. Returns dicts with score (0-100), cited, overlap, authority,
    sorted most-influential first. `body` must still contain inline [N] markers."""
    kw = set(_tokens(keywords_text))
    counts: dict[int, int] = {}
    for m in re.finditer(r"\[(\d+)\]", body):
        n = int(m.group(1))
        counts[n] = counts.get(n, 0) + 1
    scored: list[dict] = []
    for idx, s in enumerate(sources, 1):
        title = s.get("title", "") if isinstance(s, dict) else getattr(s, "title", "")
        ttok = set(_tokens(title))
        overlap = (len(ttok & kw) / len(ttok)) if ttok else 0.0
        cited = counts.get(idx, 0)
        raw = 3.0 * cited + 4.0 * overlap
        src = s if isinstance(s, dict) else s.model_dump()
        url = src.get("url", "")
        scored.append({"source": src, "cited": cited, "overlap": round(overlap, 3),
                       "authority": source_authority(url), "raw": raw})
    max_raw = max((x["raw"] for x in scored), default=0.0) or 1.0
    for x in scored:
        x["score"] = round(100 * x["raw"] / max_raw)
    scored.sort(key=lambda x: (x["score"], x["authority"], x["cited"]), reverse=True)
    return scored


_STYLE_LABEL = {"numeric": "", "apa": " (APA-style)", "mla": " (MLA-style)",
                "chicago": " (Chicago-style)", "ap": " (AP-style)"}


def _ref_row(style: str, i: int, title: str, url: str, date: str) -> str:
    """One reference row in a named citation style. Best-effort: our captured source fields
    are title/url/date (no author/publisher), so the author-name styles approximate by
    leading with the title - honest within the data we have, not a full bibliographic entry."""
    link = f"[{title}]({url})" if url else title
    dated = "" if date in ("", "n.d.") else date
    if style == "apa":
        return f"{i}. {title}. ({date}). {url}".rstrip()
    if style == "mla":
        return f'{i}. "{title}." {url}{(" (" + dated + ")") if dated else ""}'.rstrip()
    if style == "chicago":
        return f'{i}. "{title}." Accessed {date}. {url}'.rstrip(" .") + "."
    if style == "ap":
        return f"{i}. {title}" + (f", {dated}" if dated else "") + (f" — {url}" if url else "")
    # "numeric": plain dated link list
    return f"{i}. {link}" + (f" ({dated})" if dated else "")


def build_references(scored: list[dict], *, drop_noise: bool = True,
                     style: str = "influence") -> str:
    """A References section. `style='influence'` (default) is the dated, 0-100 influence-
    ranked, sorted list (unchanged); other styles (numeric/apa/mla/chicago/ap) render the
    same filtered, ranked sources in that citation convention; 'none' emits nothing.

    Drops pure noise (sources never cited and unrelated to the article) unless drop_noise
    is False, in every style."""
    if style == "none":
        return ""
    # Only prune zero-influence sources when SOME source has signal to rank against -
    # otherwise (e.g. researcher off, no inline citations) keep them all, just listed.
    has_signal = any(x["cited"] or x["overlap"] for x in scored)
    rows: list[str] = []
    for x in scored:
        auth = x.get("authority", AUTH_NEUTRAL)
        # Drop a source that never earned its place: pure noise (never cited, no topical
        # overlap), OR an uncited low-authority pad (cited 0 + SEO/template domain) - the
        # citation-padding failure mode the blind A/B pilot caught.
        if (drop_noise and has_signal and x["cited"] == 0
                and (x["overlap"] == 0 or auth <= AUTH_LOW)):
            continue
        s = x["source"]
        title = (s.get("title") or "Source").strip()
        url = (s.get("url") or "").strip()
        date = _norm_date(s.get("date", ""))
        if style == "influence":
            link = f"[{title}]({url})" if url else title
            rows.append(f"{len(rows) + 1}. **{x['score']}** · {date} · {link}")
        else:
            rows.append(_ref_row(style, len(rows) + 1, title, url, date))
    if not rows:
        return ""
    if style == "influence":
        return ("## References\n\n*Ranked by influence on this article (0–100; higher = more "
                "influence). Dated where known.*\n\n" + "\n".join(rows))
    return f"## References{_STYLE_LABEL.get(style, '')}\n\n" + "\n".join(rows)


# ── reading time ────────────────────────────────────────────────────────────────
READ_WPM = 225          # words/minute for the prose-only read-time estimate (tunable)

_CODE_FENCE = re.compile(r"(?ms)^```.*?^```")
_IMG_LINE = re.compile(r"(?m)^!\[[^\]]*\]\([^)]*\).*$")


def prose_word_count(md: str) -> int:
    """Words a human actually *reads* - prose only. Fenced code blocks, the end
    References list, and image/figure embeds are excluded: counting them (a naive
    `len(md.split())`) overstates the read time of code-heavy or reference-heavy pieces
    (e.g. a technical article reads as ~16 min, not the ~24 min a raw split() implies)."""
    if not md:
        return 0
    text = _CODE_FENCE.sub(" ", md)
    text = re.split(r"(?im)^#{1,4}[ \t]*References\b", text, maxsplit=1)[0]
    text = _IMG_LINE.sub(" ", text)
    return len(text.split())


def read_time_min(md: str, wpm: int = READ_WPM) -> int:
    """Estimated reading time in minutes from prose words (see `prose_word_count`)."""
    return max(1, round(prose_word_count(md) / max(1, wpm)))


_READ_TIME_LINE = re.compile(r"(?im)^(\*\*Estimated read time:\*\*\s*)\d+(\s*min\b.*)$")


def refresh_read_time(md: str) -> str:
    """Rewrite the manuscript's '**Estimated read time:** N min' header in place to the
    current prose-based estimate (used when re-polishing an already-assembled article)."""
    return _READ_TIME_LINE.sub(rf"\g<1>{read_time_min(md)}\g<2>", md, count=1)


# ── evidence report (shareable trust artifact) ──────────────────────────────────
_CLAIM_RE = re.compile(r"(?im)^\*\*Claim:\*\*\s*(.+)$")
_H1_RE = re.compile(r"(?m)^#\s+(.+)$")
_REF_SECTION = re.compile(r"(?ims)^##[ \t]*References\b.*?(?=\n##\s|\Z)")
# One ranked reference row: "12. **87** · 2024 · [Title](url)" -> (score, date, tail)
_REF_ROW = re.compile(r"(?m)^\s*\d+\.\s+\*\*(\d+)\*\*\s*·\s*([^·]+?)\s*·\s*(.+)$")
_ROW_URL = re.compile(r"\]\(([^)]+)\)")


def build_evidence_report(manuscript_md: str, thesis_md: str = "", title: str = "") -> str:
    """A shareable 'how grounded is this piece' report, built deterministically (no LLM)
    from the finished manuscript: the thesis it argues, plus every source ranked by the
    same 0-100 influence score the References list already carries. Turns the otherwise
    invisible trust machinery into proof a reader can see. Returns "" when there's nothing
    to report (no thesis and no ranked references)."""
    rows = _REF_ROW.findall(manuscript_md or "")
    cm = _CLAIM_RE.search(thesis_md or "")
    claim = cm.group(1).strip() if cm else ""
    if not title:
        hm = _H1_RE.search(manuscript_md or "")
        title = hm.group(1).strip() if hm else ""
    if not rows and not claim:
        return ""
    out = ["# Evidence report" + (f" — {title}" if title else ""), "",
           "*How grounded this piece is: the argument it makes, and the sources behind it. "
           "Built deterministically from the finished manuscript - no model call.*"]
    if claim:
        out += ["", "## The argument it makes", "", f"> {claim}"]
    if rows:
        scores = [int(s) for s, _d, _t in rows]
        high = sum(1 for s in scores if s >= 50)
        dated = sum(1 for _s, d, _t in rows if d.strip().lower() not in ("n.d.", "", "n/a"))
        auths = []
        for _s, _d, tail in rows:
            um = _ROW_URL.search(tail)
            auths.append(source_authority(um.group(1) if um else ""))
        credible = sum(1 for a in auths if a >= AUTH_REPUTABLE)
        low = sum(1 for a in auths if a <= AUTH_LOW)
        avg_auth = round(sum(auths) / len(auths)) if auths else AUTH_NEUTRAL
        out += ["", "## At a glance", "",
                f"- **{len(rows)}** sources behind the piece",
                f"- **{high}** high-influence (score ≥ 50)",
                f"- **{credible}/{len(rows)}** from high-authority domains "
                "(gov · standards · primary research · established outlets)",
                f"- **{avg_auth}/100** average source authority",
                f"- **{dated}/{len(rows)}** carry a date"]
        if low:
            out += [f"- ⚠️ **{low}** low-authority source(s) (SEO/template-style) - "
                    "treat their claims with extra caution"]
        sec = _REF_SECTION.search(manuscript_md or "")
        if sec:
            body = re.sub(r"(?im)^##[ \t]*References\b.*$",
                          "## Sources, ranked by influence (0–100)",
                          sec.group(0).strip(), count=1)
            out += ["", body]
    return "\n".join(out).rstrip() + "\n"


def source_stats(manuscript_md: str) -> dict:
    """A quick, deterministic tally of the finished piece's References (no model call):
    ``{count, high_influence, credible, avg_auth}``. Shares the row parsing + authority
    scoring with ``build_evidence_report`` so the completion card and the evidence report
    can never disagree. ``count == 0`` when there is no ranked References block yet."""
    rows = _REF_ROW.findall(manuscript_md or "")
    if not rows:
        return {"count": 0, "high_influence": 0, "credible": 0, "avg_auth": 0}
    scores = [int(s) for s, _d, _t in rows]
    auths = []
    for _s, _d, tail in rows:
        um = _ROW_URL.search(tail)
        auths.append(source_authority(um.group(1) if um else ""))
    return {
        "count": len(rows),
        "high_influence": sum(1 for s in scores if s >= 50),
        "credible": sum(1 for a in auths if a >= AUTH_REPUTABLE),
        "avg_auth": round(sum(auths) / len(auths)) if auths else AUTH_NEUTRAL,
    }


# ── cross-chapter cohesion (book, D-008) ─────────────────────────────────────────
def _prose_only(md: str) -> str:
    """Strip fenced code and headings so repetition scanning sees only prose."""
    text = _CODE_FENCE.sub(" ", md or "")
    text = re.sub(r"(?m)^#{1,6}[ \t].*$", " ", text)   # headings repeat by design
    return _IMG_LINE.sub(" ", text)


def _ngrams(tokens: list[str], n: int) -> list[str]:
    return [" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


def cross_chapter_repetition(
    chapters: list[tuple[str, str]], *, n: int = 6, min_chapters: int = 2, top: int = 20
) -> dict:
    """Detect prose that repeats VERBATIM across different chapters (D-008).

    The book pipeline has no whole-manuscript smoothing pass (a 10-chapter rewrite is
    impractical and risks losing narrative content), so this is a deterministic, free
    DETECTOR rather than a rewriter: it finds the cross-chapter repetition a human editor
    would flag - reused stock phrasings and near-identical chapter openers - and reports
    them for a targeted `revise`. `chapters` is a list of (label, prose) in order.

    Returns {"phrases": [(phrase, [labels...]), ...], "openers": [(label_a, label_b), ...]}.
    Repetition WITHIN one chapter is ignored (that's the per-chapter critic's job)."""
    prepped = [(label, _tokens(_prose_only(prose))) for label, prose in chapters]

    # Repeated n-grams: an n-gram seen in min_chapters+ DISTINCT chapters (dedup within a
    # chapter first, so a phrase a writer leans on inside one chapter doesn't count).
    where: dict[str, set[str]] = {}
    for label, toks in prepped:
        for g in set(_ngrams(toks, n)):
            where.setdefault(g, set()).add(label)
    phrases = sorted(
        ((g, sorted(labels)) for g, labels in where.items() if len(labels) >= min_chapters),
        key=lambda x: (-len(x[1]), x[0]),
    )[:top]

    # Near-identical openers: the first ~12 prose tokens of two chapters overlapping heavily
    # reads as formulaic ("In this chapter we...") even when no single n-gram matches.
    openers = []
    heads = [(label, set(toks[:12])) for label, toks in prepped if len(toks) >= 8]
    for i in range(len(heads)):
        for j in range(i + 1, len(heads)):
            a, sa = heads[i]
            b, sb = heads[j]
            inter = len(sa & sb)
            union = len(sa | sb) or 1
            if inter / union >= 0.6:
                openers.append((a, b))
    return {"phrases": phrases, "openers": openers}


# ── voice-drift (stylometric consistency across chapters, plan §22) ───────────────
# A function-word distribution is a style fingerprint that's stable within one author's
# work (classic stylometry); when chapters are written by independent model calls, a
# chapter whose function-word profile drifts far from the book's centroid reads as a
# DIFFERENT voice even when no single phrase repeats. This is a deterministic, free
# detector (no model call) - a human editor would call it "this chapter doesn't sound
# like the rest." Reported, never auto-rewritten.
_FUNCTION_WORDS = (
    "the a an of to in and that it is was for on with as at by from but or if this these "
    "those i you he she we they his her their our your my not no be are were been has have "
    "had will would can could may should do did so then than there here what when which who "
    "how all any more most some such only").split()
_FW_INDEX = {w: i for i, w in enumerate(_FUNCTION_WORDS)}


def _function_word_profile(prose: str) -> list[float]:
    """Normalized frequency of each tracked function word in a chapter (a style vector)."""
    words = re.findall(r"[a-z']+", _prose_only(prose).lower())
    total = len(words) or 1
    vec = [0.0] * len(_FUNCTION_WORDS)
    for w in words:
        i = _FW_INDEX.get(w)
        if i is not None:
            vec[i] += 1
    return [v / total for v in vec]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def voice_drift(chapters: list[tuple[str, str]], *, z: float = 1.3) -> list[tuple[str, float]]:
    """Chapters whose function-word profile is a statistical outlier from the book's
    centroid (distance > mean + z·std). Returns [(label, distance), ...], worst first.
    Needs >= 4 chapters to have a meaningful distribution; fewer -> []."""
    profs = [(label, _function_word_profile(prose)) for label, prose in chapters
             if prose and prose.strip()]
    if len(profs) < 4:
        return []
    dim = len(_FUNCTION_WORDS)
    centroid = [sum(p[i] for _, p in profs) / len(profs) for i in range(dim)]
    dists = [(label, 1.0 - _cosine(p, centroid)) for label, p in profs]
    vals = [d for _, d in dists]
    mean = sum(vals) / len(vals)
    std = (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5
    if std == 0:
        return []
    out = [(label, round(d, 3)) for label, d in dists if d > mean + z * std]
    return sorted(out, key=lambda x: -x[1])


def cohesion_report(chapters: list[tuple[str, str]]) -> str:
    """Markdown report of cross-chapter repetition (see `cross_chapter_repetition`) plus
    stylometric voice drift (see `voice_drift`). Always returns a report - a clean book
    gets an explicit all-clear line."""
    found = cross_chapter_repetition(chapters)
    drift = voice_drift(chapters)
    out = ["# Cross-chapter cohesion report", "",
           f"Scanned {len(chapters)} chapter(s) for verbatim repetition and voice drift.", ""]
    if not found["phrases"] and not found["openers"] and not drift:
        out += ["No significant cross-chapter repetition or voice drift detected. ✓"]
        return "\n".join(out) + "\n"
    if found["phrases"]:
        out += ["## Repeated phrasings", "",
                "Phrases that appear in multiple chapters - consider varying them:", ""]
        out += [f'- "{phrase}" — {", ".join(labels)}' for phrase, labels in found["phrases"]]
        out += [""]
    if found["openers"]:
        out += ["## Formulaic openers", "",
                "Chapter pairs that begin almost identically:", ""]
        out += [f"- {a} ↔ {b}" for a, b in found["openers"]]
        out += [""]
    if drift:
        out += ["## Voice drift", "",
                "Chapters whose prose style (function-word profile) reads as an outlier "
                "from the rest of the book - check that the voice holds:", ""]
        out += [f"- {label} (drift {dist})" for label, dist in drift]
        out += [""]
    out += ["_Report only - nothing was rewritten. Use `revise --chapter N` to address._"]
    return "\n".join(out).rstrip() + "\n"
