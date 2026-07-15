"""Repurposing - platform-native variants of a finished piece (plan §24).

The manuscript is depth; distribution is hooks. Each format is ONE flash-tier call
that rewrites the finished piece into the shape a platform actually rewards:

- ``x-thread``           - 6-10 tweets, hook first, each under the character cap
- ``linkedin``           - 150-250 word post with line breaks and a comment prompt
- ``newsletter-teaser``  - subject line + a 100-150 word teaser
- ``tldr``               - 5 takeaway bullets (dev.to / README / repost fodder)

plus ``headline_variants()`` - 5 alternative titles (curiosity / how-to / contrarian /
data-led / direct) for A/B posting. Everything reuses the SEO ``KeywordPack`` so the
hashtags and keyword stay consistent across surfaces. All calls degrade to "" on
failure - promotion is additive, never a run-blocker.
"""
from __future__ import annotations

from . import prompts as P
from . import schemas as S
from .config import ModelConfig
from .llm import complete_structured, complete_text

# Manuscript chars handed to the repurposer (the finished piece is the source of
# truth, but a thread doesn't need all of it - the argument and specifics carry).
SOURCE_CHARS = 12000

FORMATS = ("x-thread", "linkedin", "newsletter-teaser", "tldr")

_FORMAT_SYS = {
    "x-thread": P.REPURPOSE_X_SYS,
    "linkedin": P.REPURPOSE_LINKEDIN_SYS,
    "newsletter-teaser": P.REPURPOSE_NEWSLETTER_SYS,
    "tldr": P.REPURPOSE_TLDR_SYS,
}


def _source_block(title: str, thesis: str, manuscript: str, pack: S.KeywordPack) -> str:
    tags_x = " ".join(f"#{t.lstrip('#')}" for t in pack.hashtags_x if t.strip())
    tags_li = " ".join(f"#{t.lstrip('#')}" for t in pack.hashtags_linkedin if t.strip())
    return (f"TITLE: {title}\n\nTHESIS:\n{thesis.strip()[:800]}\n\n"
            f"PRIMARY KEYWORD: {pack.primary}\n"
            f"HASHTAGS (X): {tags_x or '(none)'}\nHASHTAGS (LinkedIn): {tags_li or '(none)'}\n\n"
            f"ARTICLE:\n{manuscript.strip()[:SOURCE_CHARS]}")


def repurpose(cfg: ModelConfig, fmt: str, *, title: str, thesis: str,
              manuscript: str, pack: S.KeywordPack) -> str:
    """One platform-native variant of the piece. '' on failure or unknown format."""
    sys_prompt = _FORMAT_SYS.get(fmt)
    if not sys_prompt:
        return ""
    try:
        return complete_text(cfg.model_for("repurpose"), sys_prompt,
                             _source_block(title, thesis, manuscript, pack),
                             max_tokens=2000,
                             temperature=cfg.temperature_for("repurpose")).strip()
    except Exception:  # noqa: BLE001 - promotion is additive, never a blocker
        return ""


def restyle(cfg: ModelConfig, *, title: str, manuscript: str, register: str | None = None,
            persona: str | None = None, emotion: str | None = None, voice: str | None = None) -> str:
    """Re-voice a finished manuscript into a target style(register)/persona/emotion on the
    flash tier, preserving structure/citations/facts (see RESTYLE_SYS). One call; guarded -
    returns '' if the result over-trims (so the caller keeps the original). Facts unchanged."""
    body = (manuscript or "").strip()
    if not body:
        return ""
    parts = [f"TITLE: {title}"]
    if voice:
        parts.append("VOICE TO MATCH (imitate its manner, not its content):\n" + voice)
    if persona:
        parts.append(f"PERSONA: {persona}")
    if emotion:
        parts.append(f"EMOTION TO CARRY (show, don't name): {emotion}")
    parts.append("ARTICLE TO RE-VOICE (preserve every heading, [N] citation, image, number, and "
                 "the References verbatim):\n\n" + body[:24000])
    try:
        out = complete_text(cfg.model_for("repurpose"), P.restyle_sys(register),
                            "\n\n".join(parts), max_tokens=8000,
                            temperature=cfg.temperature_for("repurpose")).strip()
    except Exception:  # noqa: BLE001 - restyle is additive, never a blocker
        return ""
    # Guard: a good re-voice keeps roughly the same length. Reject a truncated/over-trimmed
    # result so we never replace the piece with a stub.
    if not out or len(out.split()) < 0.6 * len(body.split()):
        return ""
    return out


def headline_variants(cfg: ModelConfig, *, title: str, thesis: str,
                      pack: S.KeywordPack) -> list[str]:
    """5 alternative titles for A/B posting. [] on failure."""
    user = (f"CURRENT TITLE: {title}\n\nTHESIS:\n{thesis.strip()[:800]}\n\n"
            f"PRIMARY KEYWORD (must appear in at least 3 variants): {pack.primary}")
    try:
        out = complete_structured(cfg.model_for("repurpose"), P.HEADLINES_SYS, user,
                                  S.HeadlineVariants, max_tokens=1500,
                                  temperature=cfg.temperature_for("repurpose"))
        return [h.strip() for h in out.headlines if h.strip()][:5]
    except Exception:  # noqa: BLE001
        return []
