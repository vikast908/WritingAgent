"""Tests for the quality machinery: thesis, voice exemplars, surgical humanizer,
divergent drafting, insight gate, and /praise."""
import pytest

from writingagent import brain, humanizer, nodes, orchestrator
from writingagent import schemas as S
from writingagent.brain import ArticlePaths
from writingagent.config import load_config, load_settings


@pytest.fixture
def fake_llm(monkeypatch):
    monkeypatch.setenv("WRITINGAGENT_FAKE", "1")


def _angle():
    return S.ArticleAngle(title="A", angle="technical deep-dive",
                          audience="engineers", hook="h")


def _silent(*_a, **_k):
    pass


# ── Thesis ────────────────────────────────────────────────────────────────────
def test_start_article_writes_thesis(tmp_brain, fake_llm):
    cfg, settings = load_config(), load_settings()
    aid = orchestrator.start_article(cfg, settings, "u", "topic", _angle(),
                                     "thesart", 1, 1, autonomous=True)
    paths = ArticlePaths(aid, "u")
    assert brain.read_json(paths.root / "thesis.json")
    md = brain.read_text(paths.root / "thesis.md")
    assert md and "**Claim:**" in md


def test_thesis_reaches_writer_and_critic(tmp_brain, fake_llm, monkeypatch):
    seen = {}

    def write_spy(cfg, outline, section, fix_notes=None, *, thesis=None, voice=None, **_kw):
        seen["writer_thesis"] = thesis
        return "## Section\n\nBody."

    def crit_spy(cfg, outline, section, prose, *, thesis=None, research_on=True, **_kw):
        seen["critic_thesis"] = thesis
        seen["research_on"] = research_on
        return S.Critique(verdict="approve", confidence=0.9, blocking=[], nits=[], insight=5)

    monkeypatch.setattr(nodes, "write_article_section", write_spy)
    monkeypatch.setattr(nodes, "critique_article_section", crit_spy)
    cfg, settings = load_config(), load_settings()
    settings.divergent_drafts = 1
    aid = orchestrator.start_article(cfg, settings, "u", "topic", _angle(),
                                     "thes2", 1, 1, autonomous=True)
    orchestrator.run(cfg, "u", aid, log=_silent)
    assert seen["writer_thesis"] and "**Claim:**" in seen["writer_thesis"]
    assert seen["critic_thesis"]


# ── Voice exemplars ───────────────────────────────────────────────────────────
def test_voice_exemplars_budget_and_filtering(tmp_brain):
    d = brain.voice_dir("u")
    d.mkdir(parents=True)
    (d / "a.md").write_text("# Heading skipped\n\nFirst paragraph.\n\n```\ncode skipped\n```\n\n"
                            "Second paragraph.", encoding="utf-8")
    out = brain.voice_exemplars("u")
    assert "First paragraph." in out and "Second paragraph." in out
    assert "Heading skipped" not in out and "code skipped" not in out
    # budget respected
    tiny = brain.voice_exemplars("u", max_chars=18)
    assert tiny == "First paragraph."


def test_voice_exemplars_none_when_empty(tmp_brain):
    assert brain.voice_exemplars("u") is None


def test_voice_reaches_writer(tmp_brain, fake_llm, monkeypatch):
    d = brain.voice_dir("u")
    d.mkdir(parents=True)
    (d / "v.md").write_text("Exemplar paragraph with a distinct register.", encoding="utf-8")
    seen = {}

    def write_spy(cfg, outline, section, fix_notes=None, *, voice=None, **_kw):
        seen["voice"] = voice
        return "## Section\n\nBody."
    monkeypatch.setattr(nodes, "write_article_section", write_spy)
    cfg, settings = load_config(), load_settings()
    settings.divergent_drafts = 1
    aid = orchestrator.start_article(cfg, settings, "u", "topic", _angle(),
                                     "voicea", 1, 1, autonomous=True)
    orchestrator.run(cfg, "u", aid, log=_silent)
    assert "distinct register" in (seen["voice"] or "")


def test_critic_sees_pre_cleaned_draft(tmp_brain, fake_llm, monkeypatch):
    """The de-tell pass runs BEFORE critique: the critic must receive ship-form prose
    (no em-dashes / curly quotes), so it never burns a revision round on tells a
    deterministic pass removes."""
    seen = {}

    def write_spy(cfg, outline, section, fix_notes=None, **_kw):
        return "## Section\n\nA claim — with “curly quotes” and an em-dash."

    def crit_spy(cfg, outline, section, prose, **_kw):
        seen["prose"] = prose
        return S.Critique(verdict="approve", confidence=0.9, blocking=[], nits=[], insight=5)

    monkeypatch.setattr(nodes, "write_article_section", write_spy)
    monkeypatch.setattr(nodes, "critique_article_section", crit_spy)
    cfg, settings = load_config(), load_settings()
    settings.divergent_drafts = 1
    aid = orchestrator.start_article(cfg, settings, "u", "topic", _angle(),
                                     "preclean", 1, 1, autonomous=True)
    orchestrator.run(cfg, "u", aid, log=_silent)
    assert "—" not in seen["prose"] and "“" not in seen["prose"]
    assert "curly quotes" in seen["prose"]        # content survives, typography is cleaned


def test_watch_list_merges_across_runs(tmp_brain, fake_llm, monkeypatch):
    """The watch-list is cross-run memory: a new run's items must MERGE with (not
    overwrite) the previous runs' - overwriting gave failure patterns a memory
    lifetime of exactly one project."""
    from types import SimpleNamespace

    from writingagent.orchestrator import common
    brain.ensure_user("uwm")
    brain.write_text(brain.watch_list("uwm"),
                     "# Avoid list (watch-list)\n\n- old pattern - from a prior book")

    out = SimpleNamespace(skills=[], watch_items=[
        SimpleNamespace(pattern="new pattern", why="from this run"),
        SimpleNamespace(pattern="OLD PATTERN", why="dupe, different case")])
    monkeypatch.setattr(nodes, "learn", lambda *a, **k: out)
    paths = ArticlePaths("wm1", "uwm")
    paths.ensure()
    common._run_learner(load_config(), paths, object(), "", "", log=_silent)
    text = brain.read_text(brain.watch_list("uwm"))
    assert "new pattern" in text
    assert "old pattern" in text.lower()                 # prior run's lesson survives
    assert text.lower().count("old pattern") == 1        # deduped on the pattern half


def test_critique_wire_schema_requires_scores():
    """The wire JSON Schema must REQUIRE the 1-5 scores (an omitted insight would
    silently read as a passing 3, making the min_insight gate inert) while the
    Python defaults keep old eval JSON files loadable."""
    req = set(S.Critique.model_json_schema().get("required", []))
    assert {"insight", "clarity", "structure", "evidence"} <= req
    c = S.Critique(verdict="approve", confidence=0.9, blocking=[], nits=[])
    assert c.insight == 3                       # old files still load


def test_judge_pick_maps_through_shuffled_order(monkeypatch):
    """Variants are presented to the judge in a shuffled (position-bias-breaking)
    order; the winner index must map back through that order, not the dict order."""
    from writingagent.orchestrator import common
    drafts = {f"v{i}": f"draft body {i}" for i in range(3)}
    crits = {k: S.Critique(verdict="approve", confidence=0.9, blocking=[], nits=[])
             for k in drafts}
    seen = {}

    def fake_rank(cfg, unit_desc, labelled, thesis=None):
        seen["labelled"] = dict(labelled)
        return S.VariantRanking(winner=2, ranking=[2, 1, 3], reason="r",
                                winner_weakness="w")
    monkeypatch.setattr(nodes, "rank_variants", fake_rank)
    draft, _crit, _note, _pref = common._pick_variant(
        None, "unit", None, drafts, crits, None, lambda *a, **k: None)
    assert draft == seen["labelled"]["2"]       # winner = the draft shown in slot 2


# ── Surgical humanizer ────────────────────────────────────────────────────────
def test_find_tell_sentences_flags_and_skips_code():
    text = ("Plain sentence. We will delve into the details.\n\n"
            "```python\n# delve inside code is fine\n```\n\n"
            "This is a robust solution. Clean closer here.")
    flagged = humanizer.find_tell_sentences(text)
    sents = [s for _, _, s in flagged]
    assert any("delve" in s for s in sents)
    assert any("robust" in s for s in sents)
    assert not any("code" in s for s in sents)
    assert not any("Plain sentence" in s for s in sents)


def test_rewrite_ok_guards():
    old = "The system leverages caching to hit 100ms targets [2]."
    assert humanizer._rewrite_ok(old, "The system uses caching to hit 100ms targets [2].")
    # dropped citation
    assert not humanizer._rewrite_ok(old, "The system uses caching to hit 100ms targets.")
    # drifted number
    assert not humanizer._rewrite_ok(old, "The system uses caching to hit 200ms targets [2].")
    # tell still present
    assert not humanizer._rewrite_ok(old, "The system leverages caching for 100ms targets [2].")
    # absurd length
    assert not humanizer._rewrite_ok(old, "Uses caching " * 40 + "100 ms [2].")


def test_rewrite_ok_preserves_n_style_citations():
    # [N12] synthesis-style citations must be preserved by the guard, not just plain [12] -
    # a \[\d+\] guard was blind to the N-form and let a rewrite silently strip the marker.
    old = "We rely on the primary study [N12] for this."
    assert humanizer._rewrite_ok(old, "We rely on the primary study [N12] here.")
    # dropping the N-citation (leaving the bare number) must now be rejected
    assert not humanizer._rewrite_ok(old, "We rely on the primary study 12 for this.")


def test_humanize_splices_only_guarded_rewrites(monkeypatch):
    monkeypatch.delenv("WRITINGAGENT_FAKE", raising=False)
    text = ("Keep this sentence. We delve into caching here.\n\n"
            "It is a robust design with 99 nodes.")

    def fake_structured(model, system, user, schema, **kw):
        return S.LineEdits(edits=[
            S.LineEdit(index=1, text="We explore caching here."),
            # index 2 drops the number 99 -> guard must reject it
            S.LineEdit(index=2, text="It is a sturdy design with many nodes."),
        ])
    monkeypatch.setattr(humanizer, "complete_structured", fake_structured)
    out = humanizer.humanize(load_config(), text)
    assert "We explore caching here." in out
    assert "Keep this sentence." in out
    assert "99 nodes" in out          # bad rewrite rejected, original kept


def test_humanize_fake_mode_is_mechanical_only(fake_llm):
    text = "We delve into things — deeply."
    out = humanizer.humanize(load_config(), text)
    assert "—" not in out             # mechanical pass ran
    assert "delve" in out             # no LLM rewrite in fake mode


def test_lexicon_single_source_consistency():
    """Both views are GENERATED from slop.py - the writer prompt (NO_SLOP) and the
    humanizer's tell-detector (`_TELL_RE` = `slop.tell_pattern()`) - so neither can drift,
    while a TECHNICAL_EXCEPTION is never hard-banned or stripped (the old 'optimize' bug)."""
    from writingagent import prompts, slop
    # The prompt is a derived view of the single source.
    assert "delve→explore" in prompts.NO_SLOP and "MANDATORY WRITING CONSTRAINTS" in prompts.NO_SLOP
    # Every banned verb (+ inflections) and adjective/noun is caught by the deterministic stripper.
    for word in list(slop.BANNED_VERBS) + slop.BANNED_TERMS:
        assert humanizer._TELL_RE.search(word), f"humanizer misses banned term {word!r}"
    for verb in slop.BANNED_VERBS:                       # inflections, not just the base form
        assert humanizer._TELL_RE.search(verb + ("s" if verb.endswith("e") else "ing"))
    # Multi-word phrases / openers are caught too (the phrase group is generated as well).
    for phrase in ["serves as a testament", "in conclusion", "at the end of the day"]:
        assert humanizer._TELL_RE.search(phrase), f"humanizer misses banned phrase {phrase!r}"
    # A caveated entry ("additionally (when merely listing)") is NOT blindly stripped - the
    # stripper can't judge the condition, so it stays out of the regex.
    assert not humanizer._TELL_RE.search("additionally we add a second point")
    # Exceptions are neither hard-banned in the prompt nor stripped by the humanizer.
    for ex in slop.TECHNICAL_EXCEPTIONS:
        assert not humanizer._TELL_RE.search(ex), f"humanizer wrongly strips exception {ex!r}"
        assert f"{ex}→" not in prompts.NO_SLOP, f"{ex!r} is hard-banned but is a technical exception"


def test_structural_report_metrics():
    text = ("One two three four five.\n\n" * 5) + "Alpha, beta, and gamma walked in."
    rep = humanizer.structural_report(text)
    assert "paragraph lengths" in rep
    assert "rule-of-three" in rep
    assert "specificity density" in rep


# ── Divergent drafting + insight gate ─────────────────────────────────────────
def test_divergent_drafts_writes_n_variants(tmp_brain, fake_llm, monkeypatch):
    calls = []

    def write_spy(cfg, outline, section, fix_notes=None, *, temperature=None, **_kw):
        calls.append(temperature)
        return f"## Section\n\nBody at {temperature}."
    monkeypatch.setattr(nodes, "write_article_section", write_spy)
    cfg, settings = load_config(), load_settings()
    settings.divergent_drafts = 2
    aid = orchestrator.start_article(cfg, settings, "u", "topic", _angle(),
                                     "divart", 1, 1, autonomous=True)
    orchestrator.run(cfg, "u", aid, log=_silent)
    # first attempt = 2 variants at distinct temps (fake critic approves -> no revisions)
    assert len([t for t in calls if t is not None]) == 2
    assert len(set(t for t in calls if t is not None)) == 2


def test_low_insight_triggers_sharpening_revision(tmp_brain, fake_llm, monkeypatch):
    monkeypatch.setenv("WRITINGAGENT_FAKE_INSIGHT", "2")   # below the min_insight=3 bar
    writes = []

    real_write = nodes.write_article_section

    def write_spy(*a, **kw):
        writes.append(kw.get("fix_notes"))
        return real_write(*a, **kw)
    monkeypatch.setattr(nodes, "write_article_section", write_spy)
    cfg, settings = load_config(), load_settings()
    settings.divergent_drafts = 1
    settings.min_insight = 3
    aid = orchestrator.start_article(cfg, settings, "u", "topic", _angle(),
                                     "insart", 1, 1, autonomous=True)
    state = orchestrator.run(cfg, "u", aid, log=_silent)
    assert state["phase"] == "done"   # autonomous still completes (commits best)
    # at least one revision carried the sharpening note
    assert any(n and "generic" in n for n in writes if n)


def test_crit_better_prefers_higher_insight():
    a = S.Critique(verdict="approve", confidence=0.8, blocking=[], nits=[], insight=5)
    b = S.Critique(verdict="approve", confidence=0.9, blocking=[], nits=[], insight=3)
    assert orchestrator._crit_better(a, b)       # insight beats confidence
    assert not orchestrator._crit_better(b, a)


def _approve(insight=5):
    return S.Critique(verdict="approve", confidence=0.9, blocking=[], nits=[], insight=insight)


# ── #1 Adversarial side-by-side judge (best-of-N tournament) ──────────────────
def test_pick_variant_uses_side_by_side_judge(monkeypatch):
    """The judge reads the drafts together and can override the critic's scalar pick:
    the scalar pick is v0 (insight 5) but the judge chooses the draft it saw as
    variant 2. Presentation order is shuffled (position-bias fix), so the fake judge
    picks BY CONTENT and the assertion maps back through the labels it was shown."""
    seen = {}

    def fake_rank(cfg, unit_desc, labelled, thesis=None):
        seen["labelled"] = dict(labelled)
        winner = next(i for i, body in labelled.items() if "Beta" in body)
        return S.VariantRanking(winner=int(winner),
                                ranking=[int(k) for k in labelled],
                                reason="sharper, less hedged claim",
                                winner_weakness="ending is thin")
    monkeypatch.setattr(nodes, "rank_variants", fake_rank)
    drafts = {"v0": "## A\n\nAlpha.", "v1": "## B\n\nBeta."}
    crits = {"v0": _approve(5), "v1": _approve(2)}
    d, _c, note, pref = orchestrator._pick_variant(
        load_config(), "section 1", "THESIS", drafts, crits, None, _silent, use_judge=True)
    assert d == drafts["v1"]                 # judge overrode the scalar (insight) pick
    assert note == "ending is thin"          # weakness fed to the refine pass
    assert "sharper" in pref                 # preference breadcrumb for the learner


def test_pick_variant_judge_error_falls_back_to_scalar(monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("judge unavailable")
    monkeypatch.setattr(nodes, "rank_variants", boom)
    drafts = {"v0": "## A\n\nAlpha.", "v1": "## B\n\nBeta."}
    crits = {"v0": _approve(5), "v1": _approve(2)}
    d, _c, note, pref = orchestrator._pick_variant(
        load_config(), "u", None, drafts, crits, None, _silent, use_judge=True)
    assert d == drafts["v0"] and note == "" and pref == ""   # scalar pick, no crash


def test_tournament_judge_setting_off_skips_judge(tmp_brain, fake_llm, monkeypatch):
    calls = {"n": 0}
    real = nodes.rank_variants

    def spy(*a, **k):
        calls["n"] += 1
        return real(*a, **k)
    monkeypatch.setattr(nodes, "rank_variants", spy)
    cfg, settings = load_config(), load_settings()
    settings.divergent_drafts = 2
    settings.tournament_judge = False
    aid = orchestrator.start_article(cfg, settings, "u", "topic", _angle(),
                                     "nojudge", 1, 1, autonomous=True)
    orchestrator.run(cfg, "u", aid, log=_silent)
    assert calls["n"] == 0


# ── #2 Claim <-> source verification ──────────────────────────────────────────
def _unsupported_audit(*_a, **_k):
    return S.ClaimAudit(checks=[
        S.ClaimCheck(claim="Sales doubled in 2024", source=1,
                     supported="unsupported", note="the source reports 10% growth"),
        S.ClaimCheck(claim="A supported one", source=2, supported="supported"),
    ])


def test_verify_claims_gate_blocks_on_deep_research(monkeypatch):
    """Full-text ground truth (deep research): unsupported -> BLOCKING + revision."""
    monkeypatch.setattr(nodes, "verify_claims", _unsupported_audit)
    crit = _approve(5)
    draft = "Sales doubled in 2024 [1]. Another claim [2]."
    out, note = orchestrator._verify_claims_gate(
        load_config(), {"verify_claims": True, "deep_research": True}, draft,
        "SOURCE TEXT", crit, _silent)
    assert out.verdict == "revise"                       # approve downgraded
    assert any(b.type == "evidence" for b in out.blocking)
    assert "Sales doubled" in note                       # revision note names the bad claim


def test_verify_claims_gate_shallow_is_advisory_only(monkeypatch):
    """Thin snippets (shallow research): unsupported -> nits, never blocking."""
    monkeypatch.setattr(nodes, "verify_claims", _unsupported_audit)
    crit = _approve(5)
    draft = "Sales doubled in 2024 [1]. Another claim [2]."
    out, note = orchestrator._verify_claims_gate(
        load_config(), {"verify_claims": True}, draft, "SNIPPET TEXT", crit, _silent)
    assert out.verdict == "approve"                      # NOT downgraded on weak evidence
    assert not out.blocking
    assert any("Sales doubled" in nit for nit in out.nits)
    assert note == ""


def test_verify_claims_gate_noops(monkeypatch):
    calls = {"n": 0}

    def fake_verify(*_a, **_k):
        calls["n"] += 1
        return S.ClaimAudit(checks=[])
    monkeypatch.setattr(nodes, "verify_claims", fake_verify)
    cfg = load_config()
    deep = {"verify_claims": True, "deep_research": True}
    # no source text → skip
    o, n = orchestrator._verify_claims_gate(cfg, deep, "x [1]", "", _approve(), _silent)
    assert o.verdict == "approve" and n == ""
    # no inline citations → skip
    o, n = orchestrator._verify_claims_gate(cfg, deep, "no cites", "SRC", _approve(), _silent)
    assert o.verdict == "approve" and n == ""
    # disabled → skip
    o, n = orchestrator._verify_claims_gate(
        cfg, {"verify_claims": False, "deep_research": True}, "x [1]", "SRC", _approve(), _silent)
    assert o.verdict == "approve" and n == ""
    assert calls["n"] == 0                                # node never called in any skip case


# ── #4 Counterargument engagement + closed table-read loop ────────────────────
def test_writer_thesis_block_demands_counterargument_engagement(monkeypatch):
    seen = {}

    def cap(model, system, user, **_kw):
        seen["user"] = user
        return "## S\n\nBody."
    monkeypatch.setattr(nodes, "complete_text", cap)
    nodes.write_article_section(
        load_config(),
        S.ArticleOutline(title="T", angle="a", target_word_count=0, sections=[]),
        S.ArticleSection(number=1, heading="H", purpose="p",
                         include_code=False, include_image=False),
        thesis="**Claim:** X\n**Strongest counterargument:** Y")
    assert "ENGAGE it head-on" in seen["user"]


def test_apply_top_reader_fix_revises_target_section(tmp_brain, fake_llm, monkeypatch):
    cfg, settings = load_config(), load_settings()
    settings.divergent_drafts = 1
    aid = orchestrator.start_article(cfg, settings, "u", "topic", _angle(),
                                     "readerfix", 2, 1, autonomous=True)
    orchestrator.run(cfg, "u", aid, log=_silent)
    paths = ArticlePaths(aid, "u")
    outline = S.ArticleOutline(**brain.read_json(paths.outline_json))
    state = brain.read_json(paths.run_state)

    def fake_report(cfg, outline, body):
        return S.ReaderReport(bored=[], distrust=[], confusing=[], missing=[],
                              top_fix="Open with a concrete example.", top_fix_section=1)
    monkeypatch.setattr(nodes, "reader_report", fake_report)
    orchestrator._apply_top_reader_fix(cfg, paths, outline, state, log=_silent)
    versions = list((paths.root / "versions").glob("section_01.v*.md"))
    assert any("reader-fix" in v.read_text(encoding="utf-8") for v in versions)
    assert "reader-loop revision" in (brain.read_text(paths.revision_log) or "")


def test_apply_top_reader_fix_noop_when_section_out_of_range(tmp_brain, fake_llm, monkeypatch):
    cfg, settings = load_config(), load_settings()
    settings.divergent_drafts = 1
    aid = orchestrator.start_article(cfg, settings, "u", "topic", _angle(),
                                     "readernoop", 1, 1, autonomous=True)
    orchestrator.run(cfg, "u", aid, log=_silent)
    paths = ArticlePaths(aid, "u")
    outline = S.ArticleOutline(**brain.read_json(paths.outline_json))
    state = brain.read_json(paths.run_state)

    def fake_report(cfg, outline, body):
        return S.ReaderReport(bored=[], distrust=[], confusing=[], missing=[],
                              top_fix="whole-piece tone", top_fix_section=0)   # 0 = whole-piece
    monkeypatch.setattr(nodes, "reader_report", fake_report)
    orchestrator._apply_top_reader_fix(cfg, paths, outline, state, log=_silent)
    assert "reader-loop revision" not in (brain.read_text(paths.revision_log) or "")


# ── #3 Compounding learner from preference data ───────────────────────────────
def test_preferences_recorded_and_fed_to_learner(tmp_brain, fake_llm, monkeypatch):
    seen = {}
    real_learn = nodes.learn

    def learn_spy(cfg, plan, instructions, findings, existing, praised="", preferences=""):
        seen["preferences"] = preferences
        return real_learn(cfg, plan, instructions, findings, existing,
                          praised=praised, preferences=preferences)
    monkeypatch.setattr(nodes, "learn", learn_spy)
    cfg, settings = load_config(), load_settings()
    settings.divergent_drafts = 2          # a tournament -> records a preference signal
    aid = orchestrator.start_article(cfg, settings, "u", "topic", _angle(),
                                     "prefart", 1, 1, autonomous=True)
    orchestrator.run(cfg, "u", aid, log=_silent)
    assert "Tournament" in (seen.get("preferences") or "")
    # the breadcrumb file survives until the learner reads it
    paths = ArticlePaths(aid, "u")
    assert orchestrator._read_preferences(paths)


def test_models_yaml_nodes_are_selectable_in_shell():
    """Every node routed in the SHIPPED models.yaml (the bundled default every user
    starts from) must be selectable via the shell `/model` command (`shell._NODES`),
    or the documented per-agent override - e.g. routing the `judge`/`verifier`
    cross-family - is silently rejected as an 'unknown agent'."""
    import yaml

    from writingagent import shell
    from writingagent.config import _BUNDLED
    routed = set((yaml.safe_load((_BUNDLED / "models.yaml").read_text(encoding="utf-8"))
                  or {}).get("nodes", {}))
    assert {"judge", "verifier"} <= set(shell._NODES)        # the new quality nodes
    missing = routed - set(shell._NODES)
    assert not missing, f"models.yaml nodes not selectable via /model: {sorted(missing)}"


# ── /praise ───────────────────────────────────────────────────────────────────
def test_praise_saves_section_to_voice_dir(tmp_brain, fake_llm):
    from writingagent.shell import _cmd_praise
    cfg, settings = load_config(), load_settings()
    aid = orchestrator.start_article(cfg, settings, "u", "topic", _angle(),
                                     "praiseart", 1, 1, autonomous=True)
    orchestrator.run(cfg, "u", aid, log=_silent)
    state = {"uid": "u", "book": aid}
    _cmd_praise(None, state, [])                  # no arg -> latest committed
    files = list(brain.voice_dir("u").glob("praised-*.md"))
    assert len(files) == 1
    assert orchestrator._praised_passages("u")    # learner sees it


# ── SVG diagrams: fill guard + flash fallback ─────────────────────────────────
def test_svg_fill_guard_kills_black_blobs():
    """A connector <path> without fill renders as a solid black polygon (SVG fills
    paths by default). The guard forces fill="none"; declared fills are untouched."""
    svg = ('<svg><path d="M 0 0 L 10 0 L 10 10" stroke="#555"/>'
           '<path d="M 1 1" fill="#fff" stroke="#000"/>'
           '<polyline points="0,0 5,5"/></svg>')
    out = nodes._svg_fill_guard(svg)
    assert out.count('fill="none"') == 2          # bare path + polyline fixed
    assert 'fill="#fff"' in out                   # explicit fill preserved


def test_diagram_falls_back_to_flash_when_pro_returns_no_spec(tmp_brain, monkeypatch):
    """The pro tier can return an empty (node-less) spec - the node must retry on the flash
    tier and render that, instead of shipping a placeholder."""
    monkeypatch.delenv("WRITINGAGENT_FAKE", raising=False)
    cfg = load_config()
    calls = []

    def fake_spec(model, system, user, schema, **_kw):
        calls.append(model)
        if len(calls) == 1:
            return S.DiagramSpec(title="x", nodes=[], edges=[])          # empty -> None
        return S.DiagramSpec(title="Pipeline", archetype="flow",
                             nodes=[S.DiagramNode(id="a", label="Capture"),
                                    S.DiagramNode(id="b", label="Process")],
                             edges=[S.DiagramEdge(source="a", target="b")])
    monkeypatch.setattr(nodes, "complete_structured", fake_spec)

    out = nodes.generate_svg_diagram(cfg, "topic heading", context="ctx")
    assert out.startswith("<svg") and "Capture" in out and "Process" in out
    assert calls[0] == cfg.model_for("diagram")
    assert calls[1] == cfg.model_for("diagram_fallback")
    assert calls[0] != calls[1]
