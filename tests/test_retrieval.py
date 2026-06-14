"""Focused offline tests for context-slice assembly and skill retrieval (retrieval.py)."""
from writingagent import brain, embeddings, retrieval
from writingagent import schemas as S
from writingagent import skills as skmod
from writingagent.brain import BookPaths
from writingagent.store import Store


def _plan(genre="thriller", themes=("memory", "fog")):
    return S.BookPlan(title="T", premise="p", genre=genre, tone="dark",
                      audience="a", themes=list(themes), constraints=[],
                      world_rules=[], main_characters=[])


def _bp(number=2, title="x", depends_on=(1,)):
    return S.ChapterBlueprint(number=number, title=title, purpose="p",
                              emotional_role="e", plot_function="f", setup="s",
                              payoff="o", depends_on=list(depends_on))


def _skill(uid, name, tags):
    skmod.write_skill(uid, S.SkillProposal(name=name, genre_tags=list(tags),
                      when_to_apply="w", technique=["t"], anti_pattern="a"))


def test_assemble_context_includes_excerpts_outside_deps(tmp_brain):
    """FTS excerpts come from committed chapters outside the dependency set."""
    paths = BookPaths("b", "u").ensure()
    brain.write_text(paths.ch(1), "The lighthouse keeper counted boats.")
    brain.write_text(paths.ch_summary(2), "Maya rests.")
    st = Store.open(paths)
    st.index_documents(paths)
    ctx = retrieval.assemble_context(st, paths, _bp(number=3, title="lighthouse", depends_on=[2]))
    st.close()
    assert "From ch01" in ctx                       # excerpt from outside deps
    assert "Summary of chapter 2" in ctx            # dependency summary block


def test_assemble_context_chapter_one_has_no_summaries(tmp_brain):
    """Chapter 1 has no prior chapters: no summary block, canon only."""
    paths = BookPaths("b", "u").ensure()
    st = Store.open(paths)
    st.update_from_extraction(1, S.ExtractionResult(
        characters=[S.CharacterUpdate(name="Maya", status="", new_facts=["keeper"],
                                      voice_notes=[])],
        locations=[], world_rules=[], timeline=[], threads_touched=[]))
    ctx = retrieval.assemble_context(st, paths, _bp(number=1, depends_on=[]))
    st.close()
    assert "Maya" in ctx
    assert "Prior chapter summaries" not in ctx


def test_assemble_context_wires_fact_cap(tmp_brain, monkeypatch):
    """MAX_CANON_FACTS_PER_CHAR caps the canon block fed to the writer prompt."""
    monkeypatch.setattr(retrieval, "MAX_CANON_FACTS_PER_CHAR", 2)
    paths = BookPaths("b", "u").ensure()
    st = Store.open(paths)
    for ch in range(1, 5):
        st.update_from_extraction(ch, S.ExtractionResult(
            characters=[S.CharacterUpdate(name="Maya", status="",
                        new_facts=[f"fact-{ch}"], voice_notes=[])],
            locations=[], world_rules=[], timeline=[], threads_touched=[]))
    ctx = retrieval.assemble_context(st, paths, _bp(number=5, depends_on=[]))
    st.close()
    assert "fact-4" in ctx and "fact-3" in ctx   # newest kept
    assert "fact-1" not in ctx                   # oldest dropped


def test_relevant_skills_empty_library(tmp_brain):
    """No skills dir / no tagged skills -> []."""
    assert retrieval.relevant_skills("nouser", _plan()) == []
    brain.ensure_user("u")
    assert retrieval.relevant_skills("u", _plan()) == []


def test_relevant_skills_skips_retired_and_untagged(tmp_brain):
    brain.ensure_user("u")
    _skill("u", "alive", ["thriller"])
    _skill("u", "dead", ["thriller"])
    _skill("u", "untagged", [])
    dead = brain.skills_dir("u") / "dead.md"
    dead.write_text(dead.read_text(encoding="utf-8").replace(
        "status: candidate", "status: retired"), encoding="utf-8")
    names = [n for n, _ in retrieval.relevant_skills("u", _plan())]
    assert names == ["alive"]


def test_relevant_skills_lexical_ranking_and_limit(tmp_brain):
    """Higher tag overlap ranks first; zero-overlap skills are dropped; limit honored."""
    brain.ensure_user("u")
    _skill("u", "best", ["thriller", "memory", "fog"])
    _skill("u", "ok", ["thriller"])
    _skill("u", "off-genre", ["cookbook"])
    rel = retrieval.relevant_skills("u", _plan(), limit=1)
    assert [n for n, _ in rel] == ["best"]
    names = {n for n, _ in retrieval.relevant_skills("u", _plan(), limit=5)}
    assert names == {"best", "ok"}   # no-overlap skill never surfaces


def test_relevant_skills_semantic_falls_back_on_embed_error(tmp_brain, monkeypatch):
    """An embedding failure degrades to lexical scoring instead of raising."""
    brain.ensure_user("u")
    _skill("u", "lex", ["thriller"])
    monkeypatch.setattr(retrieval, "_try_embeddings_available", lambda: True)

    def boom(*a, **k):
        raise RuntimeError("no model")
    monkeypatch.setattr(embeddings, "embed_texts", boom)
    rel = retrieval.relevant_skills("u", _plan(), use_embeddings=True)
    assert [n for n, _ in rel] == ["lex"]


def test_relevant_skills_semantic_ranking(tmp_brain, monkeypatch):
    """With embeddings available, cosine similarity drives selection (no lexical overlap)."""
    brain.ensure_user("u")
    _skill("u", "close", ["suspense pacing"])
    _skill("u", "far", ["watercolor technique"])
    monkeypatch.setattr(retrieval, "_try_embeddings_available", lambda: True)

    def fake_embed(texts, cache_path=None):
        # Profile and the "suspense" skill share a direction; the other is orthogonal.
        return [[1.0, 0.0] if (i == 0 or "suspense" in t) else [0.0, 1.0]
                for i, t in enumerate(texts)]
    monkeypatch.setattr(embeddings, "embed_texts", fake_embed)
    rel = retrieval.relevant_skills("u", _plan(), use_embeddings=True)
    assert [n for n, _ in rel] == ["close"]   # zero-cosine skill dropped


def test_parse_frontmatter_invalid_yaml_returns_empty():
    """A YAML parse error in frontmatter yields {} rather than propagating."""
    assert retrieval._parse_frontmatter("---\nname: [unclosed\n---\nbody") == {}
    assert retrieval._parse_frontmatter("no frontmatter at all") == {}
