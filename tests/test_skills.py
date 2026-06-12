"""Focused offline tests for the skill library + efficacy tracking (skills.py)."""
from book_agent import brain, retrieval
from book_agent import schemas as S
from book_agent import skills as skmod


def _prop(name, tags=("thriller",)):
    return S.SkillProposal(name=name, genre_tags=list(tags), when_to_apply="w",
                           technique=["t1", "t2"], anti_pattern="ap")


def test_load_index_default_shape(tmp_brain):
    """A missing sidecar yields the zeroed baseline structure, not None."""
    idx = skmod.load_index("u")
    assert idx == {"_baseline": {"chapters": 0, "first_pass": 0}, "skills": {}}


def test_record_chapter_updates_baseline_and_skill(tmp_brain):
    """Every chapter bumps the baseline; only applied skills get per-skill counters."""
    brain.ensure_user("u")
    skmod.record_chapter("u", ["s1"], True)
    skmod.record_chapter("u", [], False)
    idx = skmod.load_index("u")
    assert idx["_baseline"] == {"chapters": 2, "first_pass": 1}
    assert idx["skills"]["s1"] == {"applied": 1, "first_pass": 1, "target_failures": 0}


def test_write_skill_same_name_overwrites(tmp_brain):
    """Re-proposing the same skill name rewrites the page in place (no -2 copy)."""
    skmod.write_skill("u", _prop("show tell"))
    skmod.write_skill("u", _prop("show tell"))
    files = list(brain.skills_dir("u").glob("show-tell*.md"))
    assert len(files) == 1


def test_write_skill_body_sections(tmp_brain):
    """The skill page carries the when/technique/anti-pattern sections verbatim."""
    skmod.write_skill("u", _prop("pace it"))
    body = (brain.skills_dir("u") / "pace-it.md").read_text(encoding="utf-8")
    assert "## When to apply" in body and "## Technique" in body
    assert "- t1" in body and "- t2" in body
    assert "## Anti-pattern it replaces" in body
    fm = retrieval._parse_frontmatter(body)
    assert fm["status"] == "candidate"   # new skills always start as candidates


def test_reconcile_below_min_sample_stays_candidate(tmp_brain):
    """No promotion/retirement decisions before MIN_SAMPLE applications."""
    skmod.write_skill("u", _prop("young"))
    for _ in range(skmod.MIN_SAMPLE - 1):
        skmod.record_chapter("u", ["young"], True)
    assert dict(skmod.reconcile("u"))["young"] == "candidate"


def test_reconcile_keeps_candidate_within_retire_gap(tmp_brain):
    """Underperforming but within RETIRE_GAP of baseline: stays candidate (not retired)."""
    skmod.write_skill("u", _prop("meh"))
    for _ in range(5):                      # baseline-only successes
        skmod.record_chapter("u", [], True)
    for i in range(5):                      # skill: 4/5 first-pass
        skmod.record_chapter("u", ["meh"], i != 0)
    # p_base = 9/10 = 0.9, p_skill = 0.8 -> gap 0.1 <= RETIRE_GAP and p_skill < p_base
    assert dict(skmod.reconcile("u"))["meh"] == "candidate"


def test_reconcile_retires_on_target_failures(tmp_brain):
    """Two attributed target failures retire a skill regardless of first-pass rate."""
    skmod.write_skill("u", _prop("harmful"))
    idx = skmod.load_index("u")
    idx["skills"]["harmful"] = {"applied": 5, "first_pass": 5, "target_failures": 2}
    skmod.save_index("u", idx)
    assert dict(skmod.reconcile("u"))["harmful"] == "retired"


def test_reconcile_retired_is_terminal(tmp_brain):
    """A retired skill never comes back, even if its counters later look good."""
    skmod.write_skill("u", _prop("zombie"))
    idx = skmod.load_index("u")
    idx["skills"]["zombie"] = {"applied": 5, "first_pass": 5, "target_failures": 2}
    skmod.save_index("u", idx)
    assert dict(skmod.reconcile("u"))["zombie"] == "retired"
    idx["skills"]["zombie"] = {"applied": 10, "first_pass": 10, "target_failures": 0}
    skmod.save_index("u", idx)
    assert dict(skmod.reconcile("u"))["zombie"] == "retired"


def test_list_skills_rows(tmp_brain):
    skmod.write_skill("u", _prop("alpha"))
    skmod.record_chapter("u", ["alpha"], True)
    skmod.record_chapter("u", [], False)
    rows = skmod.list_skills("u")
    assert len(rows) == 1
    row = rows[0]
    assert row["name"] == "alpha" and row["status"] == "candidate"
    assert row["applied"] == 1 and row["p_skill"] == 1.0 and row["p_base"] == 0.5


def test_list_skills_empty_user(tmp_brain):
    assert skmod.list_skills("ghost") == []
