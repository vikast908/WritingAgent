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

# ── citations ─────────────────────────────────────────────────────────────────
# An inline marker: [12], [N1], and chains like [38][39]. A bracketed bare number is
# always a citation here (markdown links are [text](url), never [digits]).
_INLINE_CITE = re.compile(r"[ \t]?\[N?\d+\]")
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


def score_sources(sources: list, body: str, keywords_text: str) -> list[dict]:
    """Rank sources by influence on the article. Influence = how often the source is
    actually cited in the body (weighted heavily) + how well its title matches the
    article's thesis/headings. Returns dicts with score (0-100), cited, overlap, sorted
    most-influential first. `body` must still contain inline [N] markers."""
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
        scored.append({"source": src, "cited": cited, "overlap": round(overlap, 3), "raw": raw})
    max_raw = max((x["raw"] for x in scored), default=0.0) or 1.0
    for x in scored:
        x["score"] = round(100 * x["raw"] / max_raw)
    scored.sort(key=lambda x: (x["score"], x["cited"]), reverse=True)
    return scored


def build_references(scored: list[dict], *, drop_noise: bool = True) -> str:
    """A dated, influence-scored, rank-sorted References section. Drops pure noise
    (sources never cited and unrelated to the article) unless drop_noise is False."""
    # Only prune zero-influence sources when SOME source has signal to rank against -
    # otherwise (e.g. researcher off, no inline citations) keep them all, just listed.
    has_signal = any(x["cited"] or x["overlap"] for x in scored)
    rows: list[str] = []
    for x in scored:
        if drop_noise and has_signal and x["cited"] == 0 and x["overlap"] == 0:
            continue
        s = x["source"]
        title = (s.get("title") or "Source").strip()
        url = (s.get("url") or "").strip()
        date = _norm_date(s.get("date", ""))
        link = f"[{title}]({url})" if url else title
        rows.append(f"{len(rows) + 1}. **{x['score']}** · {date} · {link}")
    if not rows:
        return ""
    return ("## References\n\n*Ranked by influence on this article (0–100; higher = more "
            "influence). Dated where known.*\n\n" + "\n".join(rows))


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
