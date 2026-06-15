"""Deterministic manuscript polishing: citation stripping, reference-dump removal,
figure de-duplication, and the influence-scored / dated / ranked References list."""
from writingagent import polish


def test_strip_inline_citations_handles_chains_and_keeps_links():
    md = "Latency matters [28]. Decoding helps [38][39]. See [Title](http://x) and [N1] notes."
    out = polish.strip_inline_citations(md)
    assert "[28]" not in out and "[38]" not in out and "[39]" not in out and "[N1]" not in out
    assert "[Title](http://x)" in out          # markdown links survive
    assert "matters." in out and "helps." in out  # spacing tidied, no " ."


def test_strip_reference_dumps_removes_runs_and_headed_blocks():
    md = (
        "Body paragraph one.\n\n"
        "[28] Nielsen, J. (1993). Response Times.\n"
        "[29] Templeton, E. (2022). PNAS.\n\n"
        "More body.\n\n"
        "## References\n[1] Foo\n[2] Bar\n"
    )
    out = polish.strip_reference_dumps(md)
    assert "Nielsen" not in out and "Templeton" not in out   # bare run removed
    assert "## References" not in out and "Foo" not in out    # headed block removed
    assert "Body paragraph one." in out and "More body." in out


def test_strip_reference_dumps_keeps_single_stray_line():
    md = "A point worth making [5] here.\n\n[5] is not a reference dump alone.\n\nNext."
    out = polish.strip_reference_dumps(md)
    assert "Next." in out                       # a lone bracketed line is not a dump


def test_score_sources_ranks_cited_and_relevant_first():
    body = "Streaming STT cuts latency [1]. Speculative decoding [1] helps the LLM."
    sources = [
        {"title": "Streaming STT and speculative decoding for low latency", "url": "u1", "date": "2024"},
        {"title": "Unrelated gardening tips", "url": "u2", "date": ""},
    ]
    scored = polish.score_sources(sources, body, "streaming STT latency LLM decoding")
    assert scored[0]["source"]["url"] == "u1"   # cited + relevant ranks first
    assert scored[0]["score"] == 100
    assert scored[-1]["source"]["url"] == "u2" and scored[-1]["cited"] == 0


def test_build_references_format_dates_and_drops_noise():
    scored = [
        {"source": {"title": "Cited Source", "url": "http://a", "date": "5 May 2023"},
         "cited": 2, "overlap": 0.5, "score": 100},
        {"source": {"title": "Pure noise", "url": "http://b", "date": ""},
         "cited": 0, "overlap": 0.0, "score": 0},
    ]
    out = polish.build_references(scored)
    assert "## References" in out
    assert "1. **100** · 2023 · [Cited Source](http://a)" in out   # score · normalized date
    assert "Pure noise" not in out                                  # zero-influence dropped
    # keeping noise when asked
    assert "Pure noise" in polish.build_references(scored, drop_noise=False)
    assert "· n.d. ·" in polish.build_references(scored, drop_noise=False)  # missing date


def test_source_authority_tiers():
    assert polish.source_authority("https://www.cdc.gov/x") == polish.AUTH_HIGH      # .gov
    assert polish.source_authority("https://ox.ac.uk/paper") == polish.AUTH_HIGH     # .ac.uk
    assert polish.source_authority("https://arxiv.org/abs/1") == polish.AUTH_HIGH    # primary
    assert polish.source_authority("https://en.wikipedia.org/x") == polish.AUTH_REPUTABLE
    assert polish.source_authority("https://best-resume-templates.io/x") == polish.AUTH_LOW
    assert polish.source_authority("https://some-random-blog.xyz/x") == polish.AUTH_NEUTRAL
    assert polish.source_authority("") == polish.AUTH_NEUTRAL                        # no signal


def test_score_sources_authority_breaks_ties_and_padding_dropped():
    # Two equally cited+relevant sources; the high-authority one must rank first.
    body = "Latency matters [1] and also [2]."
    sources = [
        {"title": "latency study", "url": "https://low-quality-resume.io/latency", "date": ""},
        {"title": "latency study", "url": "https://arxiv.org/abs/2", "date": "2024"},
    ]
    scored = polish.score_sources(sources, body, "latency study")
    assert scored[0]["source"]["url"] == "https://arxiv.org/abs/2"   # authority wins the tie
    # An uncited low-authority pad is dropped from References even with some overlap.
    padded = [
        {"source": {"title": "real cited", "url": "https://nist.gov/a", "date": "2023"},
         "cited": 3, "overlap": 0.5, "score": 100, "authority": polish.AUTH_HIGH},
        {"source": {"title": "resume template tips", "url": "https://x-resume-templates.com/y",
                    "date": ""}, "cited": 0, "overlap": 0.4, "score": 0,
         "authority": polish.AUTH_LOW},
    ]
    out = polish.build_references(padded)
    assert "real cited" in out and "resume template tips" not in out


def test_evidence_report_surfaces_credibility():
    ms = ("# T\n\nBody.\n\n---\n\n## References\n\n*Ranked by influence on this article.*\n\n"
          "1. **100** · 2024 · [Gov](https://www.cdc.gov/a)\n"
          "2. **40** · n.d. · [Pad](https://best-resume-templates.io/b)\n")
    rep = polish.build_evidence_report(ms, "**Claim:** X.\n**Arguments:**\n- a")
    assert "average source authority" in rep
    assert "high-authority domains" in rep
    assert "low-authority source(s)" in rep        # the resume-template pad is flagged


def test_dedupe_figures_drops_heading_and_redundant_svg():
    md = (
        "## Transport\n\n"
        "### Figure 5.1: Overlap\n\n"
        "![diagram](images/section_05_diagram.svg)\n"
        "*Figure: Transport*\n\n"
        "```mermaid\nsequenceDiagram\nA->>B: hi\n```\n\n"
        "Prose referencing the diagram.\n"
    )
    out = polish.dedupe_figures(md)
    assert "### Figure 5.1" not in out          # caption-heading (blank-gap) removed
    assert "section_05_diagram.svg" not in out  # redundant SVG dropped (mermaid present)
    assert "```mermaid" in out                  # the prose-referenced diagram stays


def test_strip_model_figures_removes_mermaid_and_headings():
    md = "## S\n\n#### Figure 2.1: X\n\n```mermaid\npie title T\n\"a\": 1\n```\n\nText."
    out = polish.strip_model_figures(md)
    assert "mermaid" not in out and "Figure 2.1" not in out and "Text." in out
