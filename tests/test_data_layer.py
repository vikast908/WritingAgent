"""Offline tests for the non-LLM data layer: store, retrieval, skills."""
from writingagent import brain, retrieval
from writingagent import schemas as S
from writingagent import skills as skmod
from writingagent.brain import BookPaths
from writingagent.store import Store


def _plan():
    return S.BookPlan(title="T", premise="p", genre="thriller", tone="dark",
                      audience="a", themes=["memory", "fog"], constraints=[],
                      world_rules=["fog erases memory"], main_characters=["Maya - keeper"])


def test_store_canon_and_search(tmp_brain):
    paths = BookPaths("b", "u").ensure()
    brain.write_text(paths.ch(1), "## Chapter 1\nMaya at the lighthouse.")
    st = Store.open(paths)
    ex = S.ExtractionResult(
        characters=[S.CharacterUpdate(name="Maya", status="introduced",
                    new_facts=["keeper"], voice_notes=[])],
        locations=["Lighthouse"], world_rules=["fog erases memory"],
        timeline=[S.TimelineEvent(chapter=1, event="arrives")], threads_touched=["fog"])
    st.update_from_extraction(1, ex)
    st.render_canon(paths)
    st.index_documents(paths)
    assert "Maya" in st.canon_context()
    assert st.search("lighthouse")
    st.close()
    assert (paths.characters / "maya.md").exists()


def test_canon_context_caps_facts_per_character(tmp_brain):
    paths = BookPaths("b", "u").ensure()
    st = Store.open(paths)
    for ch in range(1, 6):
        st.update_from_extraction(ch, S.ExtractionResult(
            characters=[S.CharacterUpdate(name="Maya", status="",
                        new_facts=[f"fact-{ch}"], voice_notes=[])],
            locations=[], world_rules=[], timeline=[], threads_touched=[]))
    full = st.canon_context()
    capped = st.canon_context(max_facts_per_char=2)
    st.close()
    assert all(f"fact-{ch}" in full for ch in range(1, 6))
    assert "fact-4" in capped and "fact-5" in capped   # newest kept
    assert "fact-1" not in capped                      # oldest dropped


def test_index_chapter_is_incremental(tmp_brain):
    paths = BookPaths("b", "u").ensure()
    brain.write_text(paths.ch(1), "Maya at the lighthouse.")
    brain.write_text(paths.ch_summary(1), "Maya arrives.")
    st = Store.open(paths)
    st.index_chapter(paths, 1)
    assert st.search("lighthouse")
    # Re-indexing the same chapter replaces, not duplicates.
    brain.write_text(paths.ch(1), "Maya at the harbour.")
    st.index_chapter(paths, 1)
    assert st.search("harbour")
    assert not st.search("lighthouse")
    st.close()


def test_timeline_uses_committing_chapter(tmp_brain):
    """The LLM-reported event chapter is overridden by the actual commit chapter."""
    paths = BookPaths("b", "u").ensure()
    st = Store.open(paths)
    st.update_from_extraction(2, S.ExtractionResult(
        characters=[], locations=[], world_rules=[],
        timeline=[S.TimelineEvent(chapter=99, event="storm hits")], threads_touched=[]))
    rows = st.conn.execute("SELECT chapter, event FROM timeline").fetchall()
    st.close()
    assert rows == [(2, "storm hits")]


def test_search_excerpts_excludes_refs_and_summaries(tmp_brain):
    paths = BookPaths("b", "u").ensure()
    brain.write_text(paths.ch(1), "The lighthouse keeper counted the boats at dawn.")
    brain.write_text(paths.ch_summary(1), "lighthouse summary")
    brain.write_text(paths.ch(2), "Maya walked through the fog to the harbour.")
    st = Store.open(paths)
    st.index_documents(paths)
    hits = st.search_excerpts(["lighthouse", "boats"], limit=2)
    assert hits and hits[0][0] == "ch01"
    assert all(ref != "ch01.summary" for ref, _ in hits)   # chapters only, no summaries
    assert st.search_excerpts(["lighthouse"], limit=2, exclude_refs={"ch01"}) == []
    st.close()


def test_context_slice(tmp_brain):
    paths = BookPaths("b", "u").ensure()
    brain.write_text(paths.ch_summary(1), "Maya arrives at the lighthouse.")
    st = Store.open(paths)
    st.update_from_extraction(1, S.ExtractionResult(
        characters=[S.CharacterUpdate(name="Maya", status="", new_facts=["keeper"], voice_notes=[])],
        locations=[], world_rules=["fog erases memory"], timeline=[], threads_touched=[]))
    bp = S.ChapterBlueprint(number=2, title="x", purpose="p", emotional_role="e",
                            plot_function="f", setup="s", payoff="o", depends_on=[1])
    ctx = retrieval.assemble_context(st, paths, bp)
    st.close()
    assert "Maya" in ctx and "lighthouse" in ctx.lower()


def test_skills_promotion_and_retrieval(tmp_brain):
    brain.ensure_user("u")
    skmod.write_skill("u", S.SkillProposal(name="slow-burn", genre_tags=["thriller"],
                      when_to_apply="w", technique=["t"], anti_pattern="a"))
    for _ in range(5):  # MIN_SAMPLE, all first-pass -> p_skill == p_base
        skmod.record_chapter("u", ["slow-burn"], True)
    statuses = dict(skmod.reconcile("u"))
    assert statuses["slow-burn"] == "trusted"
    rel = retrieval.relevant_skills("u", _plan())
    assert rel and rel[0][0] == "slow-burn"


def test_humanizer_strips_tells_preserves_code():
    from writingagent.humanizer import mechanical_clean
    txt = 'She paused—then ran. “Hi,” he said…\n```py\nx = a—b\n```\n'
    out = mechanical_clean(txt)
    prose = out.split("```")[0]
    assert "—" not in prose          # em-dash gone in prose
    assert "“" not in out            # curly quotes normalized
    assert "..." in out                    # ellipsis char normalized
    assert "a—b" in out               # code fence left untouched


def test_seed_builtin_installs_skills(tmp_brain):
    n = skmod.seed_builtin("u")
    assert n >= 4
    names = {p.stem for p in brain.skills_dir("u").glob("*.md")}
    assert {"humanize-prose", "diagrams-as-code", "web-image-attribution"} <= names
    assert skmod.seed_builtin("u") == 0   # idempotent


def test_skill_retires_on_underperformance(tmp_brain):
    brain.ensure_user("u")
    skmod.write_skill("u", S.SkillProposal(name="dud", genre_tags=["thriller"],
                      when_to_apply="w", technique=["t"], anti_pattern="a"))
    # Baseline strong (5 first-pass without the skill), skill weak (5 applied, 0 first-pass).
    for _ in range(5):
        skmod.record_chapter("u", [], True)
    for _ in range(5):
        skmod.record_chapter("u", ["dud"], False)
    statuses = dict(skmod.reconcile("u"))
    assert statuses["dud"] == "retired"
