"""Context-slice retrieval (plan §2) and genre-relevance skill retrieval (plan §10).

Genre relevance defaults to lexical (Jaccard token-overlap) similarity. Pass
`use_embeddings=True` to upgrade to semantic cosine similarity via embeddings.py
(requires sentence-transformers; falls back to Jaccard if the library is absent).
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from . import brain
from .brain import BookPaths
from .schemas import BookPlan, ChapterBlueprint
from .store import Store

_WORD = re.compile(r"[a-z0-9]+")

# Most-recent facts per character injected into the writer/critic prompt. Uncapped,
# the canon block grows linearly with the book - late chapters pay maximum prompt
# latency and token cost. Consolidation/extraction still see the full canon.
MAX_CANON_FACTS_PER_CHAR = 12

# Default char budget for the assembled context block (overridable per call via
# Settings.max_context_chars). Even with the per-char fact cap, canon + summaries +
# excerpts can grow until a late-chapter writer prompt exceeds the model window and
# hard-fails the run; this bounds it, dropping lowest-priority parts first.
MAX_CONTEXT_CHARS = 24000


def _tokens(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if len(w) > 2}


def _within_budget(blocks: list[str], budget: int) -> str:
    """Join `blocks` (highest priority first) under a char budget. Whole lower-priority
    blocks are dropped before a higher one is touched; the block that overflows is included
    as a meaningful partial (with a truncation marker) only if there's real room left."""
    if budget <= 0:
        return "\n\n".join(blocks)
    kept: list[str] = []
    used = 0
    for block in blocks:
        if used + len(block) <= budget:
            kept.append(block)
            used += len(block)
        else:
            room = budget - used
            if room > 600:   # a partial of this block beats dropping it whole
                kept.append(block[:room].rstrip() + "\n\n_[context truncated to fit the budget]_")
            break
    return "\n\n".join(kept)


def assemble_context(store: Store, paths: BookPaths, blueprint: ChapterBlueprint,
                     *, max_chars: int | None = None) -> str:
    """Canon + dependency-chapter summaries + relevant excerpts from other chapters.

    The excerpt block queries the per-book FTS index with the blueprint's key terms,
    pulling passages from committed chapters *outside* the dependency set - the long-
    range recall that summaries of only the last/dependent chapters can't provide.

    The result is budgeted to `max_chars` (default MAX_CONTEXT_CHARS) by priority -
    canon (continuity) is kept first, then prior summaries, then cross-chapter excerpts -
    so a long book can't silently blow the model window (plan §10/§19).
    """
    canon = store.canon_context(max_facts_per_char=MAX_CANON_FACTS_PER_CHAR)
    dep_chapters = sorted(set(blueprint.depends_on) | ({blueprint.number - 1}
                          if blueprint.number > 1 else set()))
    summaries = []
    for n in dep_chapters:
        if n < 1:
            continue
        s = brain.read_text(paths.ch_summary(n))
        if s:
            summaries.append(f"### Summary of chapter {n}\n{s}")
    summaries_block = ("## Prior chapter summaries\n" + "\n\n".join(summaries)) if summaries else ""

    covered = {f"ch{n:02d}" for n in dep_chapters if n >= 1}
    covered.add(f"ch{blueprint.number:02d}")
    terms = sorted(_tokens(f"{blueprint.title} {blueprint.purpose} {blueprint.setup} "
                           f"{blueprint.payoff}"))
    excerpts = store.search_excerpts(terms, limit=2, exclude_refs=covered)
    excerpts_block = ("## Relevant excerpts from earlier chapters\n" + "\n\n".join(
        f"### From {ref}\n...{snip}..." for ref, snip in excerpts)) if excerpts else ""

    blocks = [b for b in (canon, summaries_block, excerpts_block) if b.strip()]
    budget = MAX_CONTEXT_CHARS if max_chars is None else int(max_chars)
    return _within_budget(blocks, budget)


def _parse_frontmatter(text: str) -> dict:
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            try:
                data = yaml.safe_load(text[3:end])
            except yaml.YAMLError:
                return {}
            # Malformed frontmatter can parse to a str/list; callers expect a dict
            # and would AttributeError on .get(), so coerce non-dicts to {}.
            return data if isinstance(data, dict) else {}
    return {}


def _profile_text(plan: BookPlan) -> str:
    return " ".join([plan.genre, plan.tone, *plan.themes])


def relevant_skills(
    uid: str,
    plan: BookPlan,
    limit: int = 3,
    use_embeddings: bool = False,
    embed_cache: Path | None = None,
) -> list[tuple[str, str]]:
    """Return up to `limit` (name, body) skill pages relevant to this book's genre/themes.

    When use_embeddings=True and sentence-transformers is installed, ranks by semantic
    cosine similarity. Otherwise ranks by Jaccard token overlap (the v1 default).
    """
    sdir = brain.skills_dir(uid)
    if not sdir.exists():
        return []

    # Collect non-retired skills with genre tags.
    candidates: list[tuple[str, str, list[str], str]] = []  # (name, body, tags_list, tags_text)
    for p in sdir.glob("*.md"):
        body = p.read_text(encoding="utf-8")
        fm = _parse_frontmatter(body)
        if fm.get("status") == "retired":
            continue
        tags = [str(t) for t in (fm.get("genre_tags") or [])]
        if not tags:
            continue
        name = str(fm.get("name") or p.stem)
        candidates.append((name, body, tags, fm.get("status", "candidate")))

    if not candidates:
        return []

    use_sem = use_embeddings and _try_embeddings_available()

    if use_sem:
        scored = _score_semantic(plan, candidates, embed_cache)
    else:
        scored = _score_lexical(plan, candidates)

    scored.sort(key=lambda t: t[0], reverse=True)
    return [(name, body) for _, name, body in scored[:limit]]


def _try_embeddings_available() -> bool:
    try:
        from . import embeddings
        return embeddings.available()
    except Exception:  # noqa: BLE001
        return False


def _score_lexical(
    plan: BookPlan,
    candidates: list[tuple[str, str, list[str], str]],
) -> list[tuple[float, str, str]]:
    profile = _tokens(_profile_text(plan))
    scored = []
    for name, body, tags, status in candidates:
        tag_tokens = _tokens(" ".join(tags))
        union = profile | tag_tokens
        score = len(profile & tag_tokens) / len(union) if union else 0.0
        if status == "trusted":
            score += 0.05
        if score > 0:
            scored.append((score, name, body))
    return scored


def _score_semantic(
    plan: BookPlan,
    candidates: list[tuple[str, str, list[str], str]],
    embed_cache: Path | None,
) -> list[tuple[float, str, str]]:
    from . import embeddings as emb

    profile_text = _profile_text(plan)
    skill_texts = [" ".join(tags) for _, _, tags, _ in candidates]
    all_texts = [profile_text] + skill_texts

    try:
        vecs = emb.embed_texts(all_texts, cache_path=embed_cache)
    except Exception:  # noqa: BLE001 - fall back to lexical on any embedding failure
        return _score_lexical(plan, candidates)

    profile_vec = vecs[0]
    scored = []
    for i, (name, body, _, status) in enumerate(candidates):
        score = emb.cosine(profile_vec, vecs[i + 1])
        if status == "trusted":
            score = min(1.0, score + 0.05)
        if score > 0:
            scored.append((score, name, body))
    return scored
