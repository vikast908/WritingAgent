"""SEO / distribution signals - the promotion layer (plan §24).

The pipeline used to stop at "manuscript on disk"; this module covers the next step:
making the piece rank-able and postable. Two halves, mirroring the evidence report's
"deterministic where possible" pattern (polish.py):

- ``keyword_pack()`` - ONE flash-tier call that names the piece's search + social
  signals (primary/secondary keywords, meta description, per-platform hashtags).
  Deterministic fallback offline, so it never blocks.
- ``validate()`` - a DETERMINISTIC on-page audit (no model call): title and
  description lengths, keyword placement (title / opening / headings), keyword
  density bounds, heading hierarchy, word-count floor, reading grade, link and
  image-alt hygiene. Returns scored checks; ``render_report()`` turns them into
  ``seo_report.md`` with the craft ("feel") metrics appended.

All numeric thresholds are module constants (tunable config per CLAUDE.md).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from . import craft
from . import prompts as P
from . import schemas as S
from .config import ModelConfig
from .llm import complete_structured

# ── Tunable thresholds ─────────────────────────────────────────────────────────
TITLE_LEN = (30, 60)          # chars; the SERP truncates past ~60
DESC_LEN = (120, 160)         # chars; the meta-description sweet spot
MIN_WORDS = 800               # long-form floor for ranking intent
MAX_READING_GRADE = 12.0      # FK grade ceiling before "hard to read" warns
KEYWORD_DENSITY = (0.3, 2.5)  # % of words; below = off-topic, above = stuffing
MIN_REF_LINKS = 3             # outbound links (References) a sourced piece should carry
OPENING_WORDS = 100           # the primary keyword should appear this early

_H1 = re.compile(r"(?m)^# (.+)$")
_H2PLUS = re.compile(r"(?m)^(#{2,6}) (.+)$")
_IMG = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_LINK = re.compile(r"(?<!!)\[[^\]]+\]\((https?://[^)]+)\)")
_WORD = re.compile(r"[A-Za-z0-9']+")


@dataclass
class Check:
    name: str
    status: str      # "pass" | "warn" | "fail"
    detail: str
    fix: str = ""


# ── Keyword pack (the one model call; deterministic fallback) ──────────────────
_STOP = frozenset(
    "a an the and or but of to in on for with as at by from is are was were be been "
    "how why what when your you our their its this that these those it we they".split())


def _fallback_pack(title: str, explicit_primary: str = "") -> S.KeywordPack:
    """Offline/failed-call fallback: derive a usable pack from the title alone."""
    words = [w.lower() for w in _WORD.findall(title) if w.lower() not in _STOP]
    primary = explicit_primary or " ".join(words[:3])
    tags = ["".join(w.capitalize() for w in words[:2]) or "Article"]
    return S.KeywordPack(primary=primary, secondary=[" ".join(words[i:i + 2])
                                                     for i in range(1, min(4, len(words)))],
                         meta_description="", hashtags_x=tags, hashtags_linkedin=tags)


def keyword_pack(cfg: ModelConfig, title: str, thesis: str, body: str,
                 explicit_primary: str = "") -> S.KeywordPack:
    """Name the piece's search + social signals. One flash call; never raises.

    `explicit_primary` (user-supplied keyword) always wins the primary slot -
    the model then fills the supporting signals around it.
    """
    intro = body.strip()[:2000]
    user = (f"TITLE: {title}\n\nTHESIS:\n{thesis.strip()[:800]}\n\n"
            f"OPENING:\n{intro}\n\n"
            + (f"REQUIRED primary keyword (use exactly): {explicit_primary}\n"
               if explicit_primary else ""))
    try:
        pack = complete_structured(cfg.model_for("seo"), P.SEO_KEYWORDS_SYS, user,
                                   S.KeywordPack, max_tokens=2000,
                                   temperature=cfg.temperature_for("seo"))
    except Exception:  # noqa: BLE001 - signals are additive; never block the report
        return _fallback_pack(title, explicit_primary)
    if explicit_primary:
        pack.primary = explicit_primary
    if not pack.primary.strip():
        return _fallback_pack(title, explicit_primary)
    return pack


# ── Deterministic on-page audit ─────────────────────────────────────────────────
def _fk_grade(prose: str) -> float:
    sents = craft._sentences(prose) or [prose]
    words = _WORD.findall(prose)
    if not words:
        return 0.0
    syll = sum(craft._count_syllables(w) for w in words)
    return 0.39 * (len(words) / len(sents)) + 11.8 * (syll / len(words)) - 15.59


def validate(manuscript_md: str, pack: S.KeywordPack,
             register: str | None = None) -> tuple[int, list[Check]]:
    """Deterministic on-page SEO audit of the finished manuscript. (score, checks)."""
    checks: list[Check] = []
    md = manuscript_md or ""
    prose = craft._prose(md)
    words = _WORD.findall(prose)
    kw = (pack.primary or "").strip().lower()

    def add(name, ok, detail, fix="", *, hard=False):
        checks.append(Check(name, "pass" if ok else ("fail" if hard else "warn"),
                            detail, "" if ok else fix))

    # Title
    h1s = _H1.findall(md)
    title = h1s[0].strip() if h1s else ""
    add("title", bool(title) and len(h1s) == 1,
        f'"{title[:70]}"' if title else "no H1 title",
        "Add exactly one H1 title.", hard=not title)
    if title:
        add("title-length", TITLE_LEN[0] <= len(title) <= TITLE_LEN[1],
            f"{len(title)} chars (target {TITLE_LEN[0]}-{TITLE_LEN[1]})",
            "Search results truncate past ~60 chars; too short wastes the slot.")
        if kw:
            add("keyword-in-title", kw in title.lower(),
                f'primary "{pack.primary}" {"in" if kw in title.lower() else "NOT in"} the title',
                "Work the primary keyword into the title naturally.", hard=True)

    # Meta description
    desc = (pack.meta_description or "").strip()
    add("meta-description", bool(desc) and DESC_LEN[0] <= len(desc) <= DESC_LEN[1],
        f"{len(desc)} chars (target {DESC_LEN[0]}-{DESC_LEN[1]})" if desc else "missing",
        "Write a 120-160 char description carrying the primary keyword.")
    if desc and kw:
        add("keyword-in-description", kw in desc.lower(),
            "primary keyword " + ("present" if kw in desc.lower() else "absent"),
            "Include the primary keyword once in the description.")

    if kw and words:
        opening = " ".join(words[:OPENING_WORDS]).lower()
        add("keyword-early", kw in opening,
            f'primary "{pack.primary}" {"appears" if kw in opening else "missing"} '
            f"in the first {OPENING_WORDS} words",
            "State the topic plainly in the opening paragraph.")
        heads = [h.lower() for _lvl, h in _H2PLUS.findall(md)]
        add("keyword-in-headings", any(kw in h for h in heads),
            "primary keyword " + ("in a subheading" if any(kw in h for h in heads)
                                  else "in no subheading"),
            "Use the primary keyword (or a close variant) in at least one H2/H3.")
        # Word-boundary match so a phrase keyword ("data model") isn't over-counted inside a
        # longer word ("data modeling"), which falsely tripped the stuffing warning.
        hits = len(re.findall(rf"\b{re.escape(kw)}\b", prose.lower()))
        density = 100.0 * hits * max(1, len(kw.split())) / max(1, len(words))
        add("keyword-density", KEYWORD_DENSITY[0] <= density <= KEYWORD_DENSITY[1],
            f"{density:.2f}% ({hits} uses; healthy {KEYWORD_DENSITY[0]}-{KEYWORD_DENSITY[1]}%)",
            "Too low reads off-topic; too high reads stuffed - vary with the secondary phrases.")

    # Structure (seed with the H1 so an H1 -> H3/H4 jump counts as a skip too)
    levels = ([1] if h1s else []) + [len(m) for m, _h in _H2PLUS.findall(md)]
    skips = [i for i in range(1, len(levels)) if levels[i] - levels[i - 1] > 1]
    add("heading-hierarchy", not skips,
        "no level skips" if not skips else f"{len(skips)} heading level skip(s)",
        "Don't jump H2->H4; crawlers and readers both use the ladder.")
    add("word-count", len(words) >= MIN_WORDS,
        f"{len(words)} words (floor {MIN_WORDS})",
        "Long-form intent needs depth; thin pieces rarely rank.")

    grade = _fk_grade(prose)
    add("reading-grade", grade <= MAX_READING_GRADE,
        f"FK grade {grade:.1f} (ceiling {MAX_READING_GRADE:g})",
        "Shorten sentences; prefer concrete words. Skimmers bounce, and bounces bury rank.")

    links = _LINK.findall(md)
    add("outbound-links", len(links) >= MIN_REF_LINKS,
        f"{len(links)} outbound link(s) (floor {MIN_REF_LINKS})",
        "Cited, linkable sources are a trust signal - keep the References list.")
    imgs = _IMG.findall(md)
    if imgs:
        missing = sum(1 for alt, _u in imgs if not alt.strip())
        add("image-alt-text", missing == 0,
            f"{len(imgs)} image(s), {missing} without alt text",
            "Give every figure a descriptive alt text - it's indexed and it's accessibility.")

    score = 100
    for c in checks:
        score -= 10 if c.status == "fail" else (5 if c.status == "warn" else 0)
    return max(0, score), checks


def render_report(title: str, score: int, checks: list[Check], pack: S.KeywordPack,
                  register: str | None = None, feel: str = "") -> str:
    """seo_report.md - the promotion-readiness receipt (deterministic sections)."""
    icon = {"pass": "✓", "warn": "⚠", "fail": "✗"}
    out = [f"# SEO report — {title}" if title else "# SEO report", "",
           "*On-page audit of the finished manuscript - deterministic checks, "
           "plus the signals pack the repurposer and HTML export reuse.*", "",
           f"## Score: {score}/100", ""]
    out += [f"- {icon[c.status]} **{c.name}** — {c.detail}"
            + (f"\n  - fix: {c.fix}" if c.fix else "")
            for c in checks]
    out += ["", "## Signals", "",
            f"- **Primary keyword:** {pack.primary or '(none)'}",
            f"- **Secondary:** {', '.join(pack.secondary) or '(none)'}",
            f"- **Meta description:** {pack.meta_description or '(none)'}",
            f"- **Hashtags (X):** {' '.join(_tag(t) for t in pack.hashtags_x) or '(none)'}",
            f"- **Hashtags (LinkedIn):** "
            f"{' '.join(_tag(t) for t in pack.hashtags_linkedin) or '(none)'}"]
    if feel:
        out += ["", "## Feel (deterministic craft metrics)", "", feel]
    return "\n".join(out) + "\n"


def _tag(t: str) -> str:
    t = t.strip().lstrip("#")
    return f"#{t}" if t else ""


# ── Apply SEO (change the piece, not just report) ─────────────────────────────
def optimize_manuscript(cfg: ModelConfig, manuscript_md: str, pack: S.KeywordPack,
                        *, log=lambda *a: None) -> tuple[str, list[str]]:
    """The highest-impact fix a report can't make: rewrite the H1 title so it carries the
    primary keyword and fits the SERP length (one flash call, guarded). Keyword presence
    in the body/opening/headings is handled up front by the `seo_keyword` writer threading;
    meta/OG tags come from the pack at export. Returns (manuscript, changes)."""
    changes: list[str] = []
    kw = (pack.primary or "").strip()
    md = manuscript_md or ""
    m = re.search(r"(?m)^# (.+)$", md)
    if not kw or not m:
        return md, changes
    title = m.group(1).strip()
    if kw.lower() in title.lower() and len(title) <= TITLE_LEN[1]:
        return md, changes                          # already carries the keyword and fits
    try:
        out = complete_structured(
            cfg.model_for("seo"), P.SEO_TITLE_SYS,
            f"CURRENT TITLE: {title}\nPRIMARY KEYWORD (must appear): {kw}\n"
            f"SECONDARY: {', '.join(pack.secondary)}",
            S.HeadlineVariants, max_tokens=800, temperature=cfg.temperature_for("seo"))
        cand = next((h.strip() for h in out.headlines
                     if h.strip() and kw.lower() in h.lower() and len(h.strip()) <= 70), "")
    except Exception:  # noqa: BLE001 - optimization is additive, never a blocker
        cand = ""
    if cand and cand != title:
        md = md[:m.start()] + f"# {cand}" + md[m.end():]
        changes.append(f"title → {cand!r}")
        log(f"   [seo] title optimized for '{kw}' → {cand}")
    return md, changes
