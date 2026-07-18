"""Focused offline tests for the skill library + efficacy tracking (skills.py)."""
from writingagent import brain, retrieval
from writingagent import schemas as S
from writingagent import skills as skmod


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


# ── Ablation-duel efficacy (the causal signal) ────────────────────────────────

def test_record_duel_counts_wins_and_failures(tmp_brain):
    """A win bumps duels+duel_wins; a loss bumps duels + target_failures."""
    brain.ensure_user("u")
    skmod.record_duel("u", "s", True)
    skmod.record_duel("u", "s", False)
    s = skmod.load_index("u")["skills"]["s"]
    assert s["duels"] == 2 and s["duel_wins"] == 1 and s["target_failures"] == 1


def test_reconcile_trusts_on_winning_duels(tmp_brain):
    """>=MIN_DUELS with a high smoothed win-rate -> trusted (duels beat first_pass)."""
    skmod.write_skill("u", _prop("winner"))
    for _ in range(skmod.MIN_DUELS):
        skmod.record_duel("u", "winner", True)
    assert dict(skmod.reconcile("u"))["winner"] == "trusted"


def test_reconcile_retires_on_losing_duels(tmp_brain):
    """>=MIN_DUELS with a low smoothed win-rate -> retired."""
    skmod.write_skill("u", _prop("flop"))
    for _ in range(skmod.MIN_DUELS):
        skmod.record_duel("u", "flop", False)
    assert dict(skmod.reconcile("u"))["flop"] == "retired"


def test_reconcile_below_min_duels_falls_back(tmp_brain):
    """Too few duels -> the duel rule doesn't fire; stays candidate (no first_pass data)."""
    skmod.write_skill("u", _prop("young"))
    skmod.record_duel("u", "young", True)
    assert dict(skmod.reconcile("u"))["young"] == "candidate"


def test_pick_duel_target_prefers_least_dueled_then_stops(tmp_brain):
    """Returns the least-dueled candidate under MIN_DUELS; None once all are decided."""
    brain.ensure_user("u")
    skmod.record_duel("u", "a", True)            # a has 1 duel, b has 0
    assert skmod.pick_duel_target("u", ["a", "b"]) == "b"
    for name in ("a", "b"):
        for _ in range(skmod.MIN_DUELS):
            skmod.record_duel("u", name, True)
    assert skmod.pick_duel_target("u", ["a", "b"]) is None
    assert skmod.pick_duel_target("u", []) is None


def test_distill_retires_near_duplicate(tmp_brain):
    """Two near-identical skills -> one retired (status only; file kept), the other survives."""
    skmod.write_skill("u", _prop("alpha"))
    skmod.write_skill("u", _prop("beta"))   # identical body, different name
    retired = skmod.distill("u")
    assert len(retired) == 1
    statuses = {r["name"]: r["status"] for r in skmod.list_skills("u")}
    assert sorted(statuses.values()) == ["candidate", "retired"]


def test_watch_block_framing():
    """Guarded enforcement says BLOCKING; advisory says nit-only; empty -> None."""
    from writingagent import nodes
    assert "BLOCKING" in nodes._watch_block("p - why", True)
    assert "advisory" in nodes._watch_block("p - why", False)
    assert nodes._watch_block(None, True) is None


# ── learned reader preferences (durable, reinforced, cross-run) ──────────────────
def test_record_preference_dedupes_reinforces_and_caps(tmp_brain):
    """A repeat correction increments a count and surfaces; the list is capped newest-first."""
    brain.record_preference("u", "stop hedging")
    brain.record_preference("u", "use shorter sentences")
    brain.record_preference("u", "Stop  hedging")          # same guidance (norm/case) -> reinforce
    text = brain.user_preferences_text("u")
    assert "- stop hedging  ×2" in text                    # reinforced with a count
    assert text.splitlines()[0].startswith("- stop hedging")  # moved to the front
    assert "use shorter sentences" in text
    # cap: only the newest _PREF_CAP survive
    for i in range(brain._PREF_CAP + 5):
        brain.record_preference("u", f"pref number {i}")
    kept = [ln for ln in brain.user_preferences_text("u").splitlines() if ln.startswith("- ")]
    assert len(kept) == brain._PREF_CAP


def test_record_preference_ignores_blank(tmp_brain):
    brain.record_preference("u", "   ")
    assert brain.user_preferences_text("u") == ""


def test_record_instruction_accumulates_user_preference(tmp_brain, monkeypatch):
    """A user review/revise instruction lands in the durable cross-run preferences (gated on)."""
    from writingagent import orchestrator
    from writingagent.config import Settings
    monkeypatch.setattr("writingagent.config.load_settings",
                        lambda: Settings(learn_preferences=True))
    paths = brain.ArticlePaths("prefart", "u")
    brain.write_json(paths.run_state, {"phase": "sections"})   # makes it an article project
    orchestrator.record_instruction("u", "prefart", 1, "cut the throat-clearing intros")
    assert "cut the throat-clearing intros" in brain.user_preferences_text("u")


def test_record_instruction_respects_the_gate(tmp_brain, monkeypatch):
    """learn_preferences=False keeps the instruction out of the durable preferences."""
    from writingagent import orchestrator
    from writingagent.config import Settings
    monkeypatch.setattr("writingagent.config.load_settings",
                        lambda: Settings(learn_preferences=False))
    paths = brain.ArticlePaths("noprefart", "u")
    brain.write_json(paths.run_state, {"phase": "sections"})
    orchestrator.record_instruction("u", "noprefart", 1, "make it punchier")
    assert brain.user_preferences_text("u") == ""
