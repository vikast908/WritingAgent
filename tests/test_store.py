"""Focused offline tests for the per-book SQLite store (store.py)."""
from book_agent import brain
from book_agent import schemas as S
from book_agent.brain import BookPaths
from book_agent.store import Store


def _ex(name="Maya", status="", facts=(), voice=(), rules=(), timeline=(), threads=()):
    return S.ExtractionResult(
        characters=[S.CharacterUpdate(name=name, status=status,
                    new_facts=list(facts), voice_notes=list(voice))] if name else [],
        locations=[], world_rules=list(rules),
        timeline=[S.TimelineEvent(chapter=1, event=e) for e in timeline],
        threads_touched=list(threads))


def test_open_close_persists_across_reopen(tmp_brain):
    """Canon committed in one session must survive close + reopen of the db."""
    paths = BookPaths("b", "u").ensure()
    st = Store.open(paths)
    st.update_from_extraction(1, _ex(facts=["keeper"]))
    st.close()
    st2 = Store.open(paths)
    assert "keeper" in st2.canon_context()
    st2.close()


def test_search_like_fallback_without_fts(tmp_brain):
    """With fts disabled, search() and search_excerpts() fall back to LIKE scans."""
    paths = BookPaths("b", "u").ensure()
    brain.write_text(paths.ch(1), "Maya counted the boats at the lighthouse.")
    st = Store.open(paths)
    st.index_documents(paths)
    st.fts = False
    assert st.search("lighthouse")
    hits = st.search_excerpts(["lighthouse"], limit=2)
    assert hits and hits[0][0] == "ch01"
    assert st.search_excerpts(["lighthouse"], limit=2, exclude_refs={"ch01"}) == []
    st.close()


def test_search_punctuation_does_not_raise(tmp_brain):
    """FTS-operator characters in the query must not surface an fts5 syntax error."""
    paths = BookPaths("b", "u").ensure()
    brain.write_text(paths.ch(1), "Maya at the lighthouse.")
    st = Store.open(paths)
    st.index_documents(paths)
    for q in ('light"house AND *', "a:b - c OR d", '"'):
        assert isinstance(st.search(q), list)   # no exception, list contract holds
    st.close()


def test_search_excerpts_empty_terms_returns_empty(tmp_brain):
    """Blank/whitespace-only term lists short-circuit to [] (the on-error contract)."""
    paths = BookPaths("b", "u").ensure()
    st = Store.open(paths)
    assert st.search_excerpts([]) == []
    assert st.search_excerpts(["   ", ""]) == []
    st.close()


def test_index_documents_skips_drafts(tmp_brain):
    """Uncommitted .draft.md files must never leak into the FTS index."""
    paths = BookPaths("b", "u").ensure()
    brain.write_text(paths.ch(1), "committed harbour text")
    brain.write_text(paths.ch_draft(1), "draftonlyword")
    brain.write_text(paths.ch_summary(1), "summary of harbour")
    st = Store.open(paths)
    st.index_documents(paths)
    assert not st.search("draftonlyword")
    kinds = dict(st.search("harbour", limit=10))
    assert kinds == {"ch01": "chapter", "ch01.summary": "summary"}
    st.close()


def test_status_upsert_keeps_existing_on_blank(tmp_brain):
    """A blank extraction status must not wipe a previously committed status."""
    paths = BookPaths("b", "u").ensure()
    st = Store.open(paths)
    st.update_from_extraction(1, _ex(status="alive"))
    st.update_from_extraction(2, _ex(status=""))
    row = st.conn.execute("SELECT status FROM character WHERE name='Maya'").fetchone()
    assert row == ("alive",)
    st.update_from_extraction(3, _ex(status="dead"))   # a real status does update
    row = st.conn.execute("SELECT status FROM character WHERE name='Maya'").fetchone()
    st.close()
    assert row == ("dead",)


def test_memory_summary_counts(tmp_brain):
    paths = BookPaths("b", "u").ensure()
    st = Store.open(paths)
    st.update_from_extraction(1, _ex(facts=["keeper", "limps"], rules=["fog erases"],
                                     timeline=["arrives"], threads=["fog"]))
    head = st.memory_summary().splitlines()[0]
    st.close()
    assert "1 characters" in head and "2 facts" in head
    assert "1 world rules" in head and "1 threads" in head


def test_render_canon_names_filter(tmp_brain):
    """names=[...] limits which character pages are (re)written; unknown names are ignored."""
    paths = BookPaths("b", "u").ensure()
    st = Store.open(paths)
    st.update_from_extraction(1, _ex(name="Maya", facts=["keeper"]))
    st.update_from_extraction(1, _ex(name="Bob", facts=["sailor"]))
    st.render_canon(paths, names=["Maya", "Nobody"])
    st.close()
    assert (paths.characters / "maya.md").exists()
    assert not (paths.characters / "bob.md").exists()
    assert paths.world_rules.exists() and paths.timeline.exists()   # always rendered


def test_render_canon_voice_section(tmp_brain):
    """Voice notes get their own ## Voice section on the character page."""
    paths = BookPaths("b", "u").ensure()
    st = Store.open(paths)
    st.update_from_extraction(1, _ex(facts=["keeper"], voice=["wry, clipped"]))
    st.render_canon(paths)
    st.close()
    page = (paths.characters / "maya.md").read_text(encoding="utf-8")
    assert "## Voice" in page and "wry, clipped" in page
    assert "- keeper" in page
