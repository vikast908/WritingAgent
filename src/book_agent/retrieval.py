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


def _tokens(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if len(w) > 2}


def assemble_context(store: Store, paths: BookPaths, blueprint: ChapterBlueprint) -> str:
    """Canon + the summaries of the chapters this one depends on (and the previous one)."""
    parts = [store.canon_context(max_facts_per_char=MAX_CANON_FACTS_PER_CHAR)]
    dep_chapters = sorted(set(blueprint.depends_on) | ({blueprint.number - 1}
                          if blueprint.number > 1 else set()))
    summaries = []
    for n in dep_chapters:
        if n < 1:
            continue
        s = brain.read_text(paths.ch_summary(n))
        if s:
            summaries.append(f"### Summary of chapter {n}\n{s}")
    if summaries:
        parts.append("## Prior chapter summaries\n" + "\n\n".join(summaries))
    return "\n\n".join(p for p in parts if p.strip())


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
