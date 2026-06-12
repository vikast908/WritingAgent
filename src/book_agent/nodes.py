"""All LLM nodes (plan §4, §8, §9, §16). Thin wrappers over llm + prompts + schemas."""
from __future__ import annotations

import json
import os
import re as _re

from . import prompts as P
from . import schemas as S
from .config import ModelConfig
from .llm import complete_structured, complete_text

# SVG fills paths BLACK by default: a multi-segment connector that doesn't declare
# fill="none" renders as a solid black polygon over the diagram (the "random black
# blob"). Models forget this constantly, so it's enforced deterministically on every
# generated diagram rather than trusted to the prompt.
_SVG_CONNECTOR_RE = _re.compile(r"<(path|polyline)\b((?:(?!fill=)[^>])*?)(\s*/?)>",
                                _re.IGNORECASE)


def _svg_fill_guard(svg: str) -> str:
    return _SVG_CONNECTOR_RE.sub(lambda m: f'<{m.group(1)}{m.group(2)} fill="none"{m.group(3)}>',
                                 svg)


def _ctx(obj) -> str:
    data = obj.model_dump() if hasattr(obj, "model_dump") else obj
    return json.dumps(data, indent=2, ensure_ascii=False)


# ── Upfront interview ─────────────────────────────────────────────────────────
def interview(
    cfg: ModelConfig, topic: str, mode: str = "book",
    research_brief: str | None = None, n: int = 6,
) -> S.Interview:
    """Generate one batch of clarifying questions to ask the author upfront.

    The whole point is to gather everything that shapes the piece in a single pass,
    so the autonomous run that follows never needs to interrupt the author again.
    """
    model = cfg.model_for("planner")
    kind = "long-form article" if mode == "article" else "book"
    parts = [f"The author wants to write a {kind} about:\n{topic}"]
    if research_brief:
        parts.append("Quick research context (use it to ask sharper, better-grounded "
                     f"questions - do not just summarize it):\n{P.wrap_untrusted(research_brief)}")
    parts.append(f"Propose up to {n} clarifying questions, each with a sensible default "
                 "'suggestion'.")
    out = complete_structured(model, P.INTERVIEW_SYS, "\n\n".join(parts), S.Interview,
                              max_tokens=2000, temperature=cfg.temperature_for("planner"))
    return S.Interview(questions=list(out.questions)[:n])


# ── Planner ───────────────────────────────────────────────────────────────────
def planner_directions(cfg: ModelConfig, abstract: str, n: int = 3) -> S.Directions:
    model = cfg.model_for("planner")
    user = f"Abstract:\n{abstract}\n\nPropose {n} distinct creative directions."
    return complete_structured(model, P.PLANNER_DIRECTIONS_SYS, user, S.Directions,
                               temperature=cfg.temperature_for("planner"))


def planner_expand(cfg: ModelConfig, abstract: str, chosen: S.Direction) -> S.BookPlan:
    model = cfg.model_for("planner")
    user = (f"Abstract:\n{abstract}\n\nChosen direction:\n{_ctx(chosen)}\n\n"
            "Expand this into a complete book plan.")
    return complete_structured(model, P.PLANNER_EXPAND_SYS, user, S.BookPlan,
                               temperature=cfg.temperature_for("planner"))


# ── TOC ───────────────────────────────────────────────────────────────────────
def build_toc(cfg: ModelConfig, plan: S.BookPlan, num_chapters: int) -> S.TOC:
    model = cfg.model_for("toc")
    user = (f"Book plan:\n{_ctx(plan)}\n\n"
            f"Design a table of contents with exactly {num_chapters} chapters.")
    return complete_structured(model, P.TOC_SYS, user, S.TOC,
                               max_tokens=16000, temperature=cfg.temperature_for("toc"))


# ── Writer ────────────────────────────────────────────────────────────────────
def write_chapter(
    cfg: ModelConfig,
    plan: S.BookPlan,
    blueprint: S.ChapterBlueprint,
    fix_notes: str | None = None,
    *,
    context: str | None = None,
    skills: list[str] | None = None,
    images: list[str] | None = None,
    base_draft: str | None = None,
    length_note: str | None = None,
    requirements: str | None = None,
    voice: str | None = None,
    temperature: float | None = None,
) -> str:
    model = cfg.model_for("writer")
    parts = [f"Book plan:\n{_ctx(plan)}", f"Chapter blueprint:\n{_ctx(blueprint)}"]
    if requirements:
        parts.append("AUTHOR REQUIREMENTS (gathered upfront - the highest priority; honor "
                     f"every point exactly):\n{requirements}")
    if voice:
        parts.append("VOICE EXEMPLARS - passages in the register to MATCH. Imitate their "
                     "rhythm, diction, and stance; do NOT copy their content:\n\n" + voice)
    if context:
        parts.append(f"Canonical context:\n{context}")
    if skills:
        parts.append("Relevant craft skills (apply where they fit):\n\n" + "\n\n---\n\n".join(skills))
    if images:
        parts.append(
            "## Suggested images (embed where relevant; keep the attribution line verbatim):\n\n"
            + "\n\n".join(images)
        )
    if base_draft:
        parts.append("PRIOR DRAFT (revise this; keep what works):\n" + base_draft)
    if fix_notes:
        parts.append("Revision notes (address every point):\n" + fix_notes)
    if length_note:
        parts.append(length_note)
    parts.append(f'Write chapter {blueprint.number}: "{blueprint.title}".')
    return complete_text(model, P.WRITER_SYS, "\n\n".join(parts),
                         max_tokens=16000, thinking=True,
                         temperature=(temperature if temperature is not None
                                      else cfg.temperature_for("writer")))


# ── Critic ────────────────────────────────────────────────────────────────────
def critique_chapter(
    cfg: ModelConfig,
    plan: S.BookPlan,
    blueprint: S.ChapterBlueprint,
    prose: str,
    *,
    context: str | None = None,
    watch_list: str | None = None,
    skills: list[str] | None = None,
    length_note: str | None = None,
    requirements: str | None = None,
) -> S.Critique:
    model = cfg.model_for("critic")
    parts = [f"Book plan:\n{_ctx(plan)}", f"Chapter blueprint:\n{_ctx(blueprint)}"]
    if requirements:
        parts.append("AUTHOR REQUIREMENTS (gathered upfront; treat a clear violation - wrong "
                     f"audience, length, tone, or a missing must-include - as BLOCKING):\n{requirements}")
    if context:
        parts.append(f"Canonical context:\n{context}")
    if watch_list:
        parts.append(f"LEARNED WATCH-LIST (flag these patterns as blocking):\n{watch_list}")
    if skills:
        parts.append("Craft skills the writer was asked to apply:\n\n" + "\n\n---\n\n".join(skills))
    if length_note:
        parts.append(length_note)
    from .humanizer import structural_report
    parts.append("DETERMINISTIC STYLE METRICS (computed from the draft, not opinions):\n"
                 + structural_report(prose))
    parts.append(f"Chapter draft:\n{prose}")
    return complete_structured(model, P.CRITIC_SYS, "\n\n".join(parts), S.Critique,
                               max_tokens=8000, temperature=cfg.temperature_for("critic"))


# ── Summary + extraction (commit) ─────────────────────────────────────────────
def summarize_chapter(cfg: ModelConfig, blueprint: S.ChapterBlueprint, prose: str) -> str:
    model = cfg.model_for("summarizer")
    user = f"Chapter {blueprint.number}: {blueprint.title}\n\n{prose}"
    return complete_text(model, P.SUMMARIZER_SYS, user,
                         max_tokens=1500, temperature=cfg.temperature_for("summarizer"))


def extract_canon(
    cfg: ModelConfig, blueprint: S.ChapterBlueprint, prose: str, known_canon: str
) -> S.ExtractionResult:
    model = cfg.model_for("summarizer")  # cheap node; reuse summarizer model
    user = (f"Already known canon:\n{known_canon or '(none)'}\n\n"
            f"Chapter {blueprint.number} text:\n{prose}\n\n"
            "Extract only what is new or changed.")
    return complete_structured(model, P.EXTRACTION_SYS, user, S.ExtractionResult,
                               max_tokens=8000)


# ── Consolidation (plan §9) ───────────────────────────────────────────────────
def consolidate(
    cfg: ModelConfig, plan: S.BookPlan, summaries: str, canon: str
) -> S.ConsolidationReport:
    model = cfg.model_for("consolidation")
    user = (f"Book plan:\n{_ctx(plan)}\n\nCanonical state:\n{canon}\n\n"
            f"Chapter summaries:\n{summaries}\n\nAudit the whole book for problems.")
    return complete_structured(model, P.CONSOLIDATION_SYS, user, S.ConsolidationReport,
                               max_tokens=8000)


# ── Production (plan §16) ─────────────────────────────────────────────────────
def plan_production(cfg: ModelConfig, plan: S.BookPlan, num_sources: int = 0) -> S.ProductionPlan:
    model = cfg.model_for("production")
    user = f"Book plan:\n{_ctx(plan)}\n\nDecide the front- and back-matter components."
    if num_sources:
        user += (f"\n\nNote: {num_sources} real web research source(s) were used while "
                 "writing - include a references/bibliography back-matter component.")
    return complete_structured(model, P.PRODUCTION_PLAN_SYS, user, S.ProductionPlan,
                               max_tokens=4000)


def generate_component(
    cfg: ModelConfig, plan: S.BookPlan, component: str, where: str,
    author_meta: str | None, toc_md: str | None = None,
    sources_md: str | None = None,
) -> str:
    model = cfg.model_for("production")
    parts = [f"Book plan:\n{_ctx(plan)}",
             f"Generate the {where}-matter component: \"{component}\"."]
    if author_meta:
        parts.append(f"Known author/publishing facts:\n{author_meta}")
    if component.lower().startswith("table of contents") and toc_md:
        parts.append(f"Use this table of contents:\n{toc_md}")
    if sources_md:
        parts.append("These are the ACTUAL research sources used while writing - list "
                     f"exactly these (do not invent any others):\n{sources_md}")
    return complete_text(model, P.PRODUCTION_COMPONENT_SYS, "\n\n".join(parts),
                         max_tokens=4000)


# ── Researcher (optional, plan §4) ────────────────────────────────────────────
def research(
    cfg: ModelConfig,
    plan: S.BookPlan,
    blueprint: S.ChapterBlueprint,
    web_results: str | None = None,
) -> S.ResearchBrief:
    model = cfg.model_for("researcher")
    parts = [f"Book plan:\n{_ctx(plan)}", f"Chapter blueprint:\n{_ctx(blueprint)}"]
    if web_results:
        parts.append("Live web search results (use as factual grounding):\n"
                     + P.wrap_untrusted(web_results))
    parts.append("Produce a short research brief for this chapter.")
    return complete_structured(model, P.RESEARCHER_SYS, "\n\n".join(parts),
                               S.ResearchBrief, max_tokens=4000)


# ── Deep researcher (multi-source, plan §15) ──────────────────────────────────
def propose_search_queries(cfg: ModelConfig, topic: str, focus: str, n: int = 4) -> S.SearchQueries:
    """Expand a topic + focus into a few distinct web search queries."""
    model = cfg.model_for("researcher")
    user = (f"Writing project:\n{topic}\n\nFocus for this part:\n{focus}\n\n"
            f"Propose {n} distinct, specific web search queries that together cover this "
            "from different angles.")
    out = complete_structured(model, P.QUERY_PLANNER_SYS, user, S.SearchQueries, max_tokens=1000)
    # The schema doesn't bound the list - cap it so a chatty model can't trigger
    # an unbounded search fan-out.
    return S.SearchQueries(queries=list(out.queries)[:n])


def deep_research(
    cfg: ModelConfig, plan: S.BookPlan, blueprint: S.ChapterBlueprint, sources_block: str | None
) -> S.ResearchBrief:
    """Synthesize a grounded brief across multiple full-text sources (book chapter)."""
    model = cfg.model_for("researcher")
    parts = [f"Book plan:\n{_ctx(plan)}", f"Chapter blueprint:\n{_ctx(blueprint)}"]
    if sources_block:
        parts.append("Full-text web sources (cite by number):\n"
                     + P.wrap_untrusted(sources_block))
    parts.append("Synthesize a tight, source-grounded research brief for this chapter.")
    return complete_structured(model, P.DEEP_RESEARCHER_SYS, "\n\n".join(parts),
                               S.ResearchBrief, max_tokens=4000)


def deep_research_article(
    cfg: ModelConfig, outline: S.ArticleOutline, section: S.ArticleSection, sources_block: str | None
) -> S.ArticleResearchBrief:
    """Synthesize a grounded, source-cited brief across multiple full-text sources (article)."""
    model = cfg.model_for("researcher")
    parts = [f"Article outline:\n{_ctx(outline)}", f"Section:\n{_ctx(section)}"]
    if sources_block:
        parts.append("Full-text web sources (cite by number):\n"
                     + P.wrap_untrusted(sources_block))
    parts.append("Synthesize a tight, source-grounded brief for this section.")
    return complete_structured(model, P.DEEP_ARTICLE_RESEARCHER_SYS, "\n\n".join(parts),
                               S.ArticleResearchBrief, max_tokens=3500)


# ── Learner (plan §8) ─────────────────────────────────────────────────────────
def learn(
    cfg: ModelConfig, plan: S.BookPlan, instructions: str, critic_findings: str,
    existing_skills: str, praised: str = ""
) -> S.LearnerOutput:
    model = cfg.model_for("learner")
    user = (f"Book plan (for genre):\n{_ctx(plan)}\n\n"
            f"Human directed revision instructions (strongest signal):\n{instructions or '(none)'}\n\n"
            f"Passages the human PRAISED (positive exemplars - distill what makes them "
            f"work, not just what to avoid):\n{praised or '(none)'}\n\n"
            f"Recurring critic findings (secondary):\n{critic_findings or '(none)'}\n\n"
            f"Existing skills (do not duplicate):\n{existing_skills or '(none)'}\n\n"
            "Distill reusable skills + a watch-list.")
    return complete_structured(model, P.LEARNER_SYS, user, S.LearnerOutput, max_tokens=6000)


# ── Article nodes ─────────────────────────────────────────────────────────────
def plan_article_angles(cfg: ModelConfig, abstract: str, n: int = 3) -> S.ArticleAngles:
    model = cfg.model_for("planner")
    user = f"Topic / abstract:\n{abstract}\n\nPropose {n} distinct editorial angles."
    return complete_structured(model, P.ARTICLE_ANGLES_SYS, user, S.ArticleAngles,
                               temperature=cfg.temperature_for("planner"))


def build_article_outline(
    cfg: ModelConfig, abstract: str, chosen: S.ArticleAngle, num_sections: int
) -> S.ArticleOutline:
    model = cfg.model_for("planner")
    user = (f"Topic / abstract:\n{abstract}\n\nChosen angle:\n{_ctx(chosen)}\n\n"
            f"Design an article outline with exactly {num_sections} sections.")
    return complete_structured(model, P.ARTICLE_OUTLINE_SYS, user, S.ArticleOutline,
                               max_tokens=8000, temperature=cfg.temperature_for("planner"))


def generate_thesis(
    cfg: ModelConfig, abstract: str, angle: S.ArticleAngle | None, outline: S.ArticleOutline
) -> S.Thesis:
    """The piece's contestable argument - generated once, injected into every
    writer and critic call so sections argue rather than merely cover."""
    model = cfg.model_for("planner")
    parts = [f"Topic / abstract:\n{abstract}"]
    if angle:
        parts.append(f"Chosen editorial angle:\n{_ctx(angle)}")
    parts.append(f"Article outline:\n{_ctx(outline)}")
    parts.append("Produce the thesis for this piece.")
    return complete_structured(model, P.THESIS_SYS, "\n\n".join(parts), S.Thesis,
                               max_tokens=2000, temperature=cfg.temperature_for("planner"))


def render_thesis(thesis: S.Thesis) -> str:
    """Markdown rendering of the thesis for prompt injection and thesis.md."""
    return "\n".join([
        f"**Claim:** {thesis.claim}",
        f"**Stakes:** {thesis.stakes}",
        "**Arguments:**", *(f"- {a}" for a in thesis.arguments),
        f"**Strongest counterargument:** {thesis.counterargument}",
        f"**Rebuttal:** {thesis.rebuttal}",
        "**Deliberately not covered:**", *(f"- {g}" for g in thesis.non_goals),
    ])


def write_article_section(
    cfg: ModelConfig,
    outline: S.ArticleOutline,
    section: S.ArticleSection,
    fix_notes: str | None = None,
    *,
    context: str | None = None,
    skills: list[str] | None = None,
    images: list[str] | None = None,
    base_draft: str | None = None,
    length_note: str | None = None,
    requirements: str | None = None,
    thesis: str | None = None,
    voice: str | None = None,
    temperature: float | None = None,
) -> str:
    model = cfg.model_for("writer")
    parts = [f"Article outline:\n{_ctx(outline)}", f"Section to write:\n{_ctx(section)}"]
    if requirements:
        parts.append("AUTHOR REQUIREMENTS (gathered upfront - the highest priority; honor "
                     f"every point exactly):\n{requirements}")
    if thesis:
        parts.append("ARTICLE THESIS - every section must ADVANCE this argument (argue it, "
                     "evidence it, or set it up), not merely cover the topic:\n" + thesis)
    if voice:
        parts.append("VOICE EXEMPLARS - passages in the register to MATCH. Imitate their "
                     "rhythm, diction, and stance; do NOT copy their content:\n\n" + voice)
    if context:
        parts.append(f"Prior section summaries (for continuity):\n{context}")
    if skills:
        parts.append("Relevant craft skills:\n\n" + "\n\n---\n\n".join(skills))
    if images:
        parts.append("## Suggested images (embed where relevant):\n\n" + "\n\n".join(images))
    if base_draft:
        parts.append("PRIOR DRAFT (revise this; keep what works):\n" + base_draft)
    if fix_notes:
        parts.append(f"Revision notes (address every point):\n{fix_notes}")
    if length_note:
        parts.append(length_note)
    parts.append(f'Write section {section.number}: "{section.heading}".')
    return complete_text(model, P.ARTICLE_WRITER_SYS, "\n\n".join(parts),
                         max_tokens=8000,
                         temperature=(temperature if temperature is not None
                                      else cfg.temperature_for("writer")))


def critique_article_section(
    cfg: ModelConfig,
    outline: S.ArticleOutline,
    section: S.ArticleSection,
    prose: str,
    *,
    context: str | None = None,
    watch_list: str | None = None,
    length_note: str | None = None,
    requirements: str | None = None,
    thesis: str | None = None,
    research_on: bool = True,
) -> S.Critique:
    model = cfg.model_for("critic")
    parts = [f"Article outline:\n{_ctx(outline)}", f"Section blueprint:\n{_ctx(section)}"]
    if requirements:
        parts.append("AUTHOR REQUIREMENTS (gathered upfront; treat a clear violation - wrong "
                     f"audience, length, tone, or a missing must-include - as BLOCKING):\n{requirements}")
    if thesis:
        parts.append("ARTICLE THESIS (the section must advance or set up this argument):\n"
                     + thesis)
    if not research_on:
        parts.append("NO WEB RESEARCH was available for this draft - every specific statistic, "
                     "study citation, or named-source attribution is a fabrication risk.")
    if context:
        parts.append(f"Prior context:\n{context}")
    if watch_list:
        parts.append(f"LEARNED WATCH-LIST (flag these patterns as blocking):\n{watch_list}")
    if length_note:
        parts.append(length_note)
    from .humanizer import structural_report
    parts.append("DETERMINISTIC STYLE METRICS (computed from the draft, not opinions):\n"
                 + structural_report(prose))
    parts.append(f"Section draft:\n{prose}")
    return complete_structured(model, P.ARTICLE_CRITIC_SYS, "\n\n".join(parts), S.Critique,
                               max_tokens=4000, temperature=cfg.temperature_for("critic"))


def research_article(
    cfg: ModelConfig,
    outline: S.ArticleOutline,
    section: S.ArticleSection,
    web_results: str | None = None,
) -> S.ArticleResearchBrief:
    model = cfg.model_for("researcher")
    parts = [f"Article outline:\n{_ctx(outline)}", f"Section:\n{_ctx(section)}"]
    if web_results:
        parts.append("Live web search results:\n" + P.wrap_untrusted(web_results))
    parts.append("Produce a source-grounded research brief for this section.")
    return complete_structured(model, P.ARTICLE_RESEARCHER_SYS, "\n\n".join(parts),
                               S.ArticleResearchBrief, max_tokens=3000)


def summarize_section(cfg: ModelConfig, section: S.ArticleSection, prose: str) -> str:
    model = cfg.model_for("summarizer")
    user = f"Section {section.number}: {section.heading}\n\n{prose}"
    return complete_text(model, P.SUMMARIZER_SYS, user,
                         max_tokens=600, temperature=cfg.temperature_for("summarizer"))


def table_read(cfg: ModelConfig, outline: S.ArticleOutline, body_md: str,
               persona: str | None = None) -> str:
    """Whole-piece cold read as a skeptical target-audience reader (not a line editor).

    Catches problems no per-section critic can see: boredom curves, trust breaks,
    concepts never grounded, missing answers. `persona` swaps the default reader for
    a specific one ("a CTO evaluating vendors", "a recruiter skimming in 90 seconds").
    Returns a Markdown report; the caller saves it - it never auto-rewrites anything.
    """
    model = cfg.model_for("consolidation")   # whole-piece reasoning = pro tier
    parts = [f"Article outline (who it is for, what it promised):\n{_ctx(outline)}"]
    if persona:
        parts.append(f"READ AS THIS SPECIFIC PERSONA (override the default audience): {persona}")
    parts.append(f"The finished article:\n{body_md}\n\nGive your reader report.")
    return complete_text(model, P.TABLE_READ_SYS, "\n\n".join(parts),
                         max_tokens=2000, temperature=0.4)


def evaluate_manuscript(cfg: ModelConfig, context: str, body_md: str) -> S.ManuscriptEval:
    """Post-hoc quality rubric over a finished manuscript (the `eval` command)."""
    model = cfg.model_for("consolidation")   # whole-piece judgment = pro tier
    user = (f"What the piece set out to be:\n{context}\n\n"
            f"The finished manuscript:\n{body_md}\n\nProduce the quality report.")
    return complete_structured(model, P.MANUSCRIPT_EVAL_SYS, user, S.ManuscriptEval,
                               max_tokens=3000, temperature=0.2)


def change_summary(cfg: ModelConfig, old: str, new: str) -> str:
    """Semantic Added/Removed/Improved comparison of two versions of one passage."""
    model = cfg.model_for("summarizer")
    user = f"BEFORE:\n{old}\n\nAFTER:\n{new}\n\nReport the semantic changes."
    return complete_text(model, P.CHANGE_SUMMARY_SYS, user,
                         max_tokens=600, temperature=0.0)


def cohesion_edit(cfg: ModelConfig, outline: S.ArticleOutline, body_md: str) -> str:
    """Whole-article smoothing pass over the assembled section bodies (plan: article mode).

    Smooths transitions, removes cross-section repetition, unifies terminology. The
    caller guards the result (length ratio, headings survive) and falls back to the
    original on any suspicion - this pass must never be able to lose content.
    """
    model = cfg.model_for("writer")
    user = (f"Article outline (for the intended arc):\n{_ctx(outline)}\n\n"
            f"Assembled article body:\n{body_md}\n\n"
            "Return the cohesion-edited article body.")
    return complete_text(model, P.COHESION_SYS, user,
                         max_tokens=16000, temperature=cfg.temperature_for("writer"))


def generate_svg_diagram(cfg: ModelConfig, heading: str, context: str = "") -> str:
    """Generate a detailed, self-contained SVG diagram for the given heading/topic.

    Returns raw SVG XML (starts with <svg ...). On failure returns a minimal placeholder SVG.
    """
    model = cfg.model_for("diagram")  # pro by default; the 16k budget leaves room for reasoning
    _diagram_key = (model, heading, context[:900])
    _fake = bool(os.getenv("BOOK_AGENT_FAKE"))
    if not _fake:
        from . import cache
        cached = cache.get("diagram", _diagram_key)
        if cached:
            return cached

    def _store(result: str) -> str:
        result = _svg_fill_guard(result)
        if not _fake:
            from . import cache
            cache.put("diagram", _diagram_key, result)
        return result

    ctx_block = f"\nContext (use this to choose specific labels/concepts for nodes):\n{context[:900]}" if context else ""
    user = (
        f"Topic: {heading}{ctx_block}\n\n"
        "Produce a publication-quality SVG diagram that visually explains the ONE most "
        "diagram-worthy idea in this topic. Pick the archetype that fits: pipeline, layered "
        "architecture, decision flow, comparison, timeline, or cycle.\n\n"
        "CRITICAL:\n"
        "- First character of your response must be '<' - no preamble, no fences, no explanation.\n"
        "- Use the ACTUAL concepts from the topic as node/label text - not generic placeholders.\n"
        "- Real numbers from the context (latencies, budgets, percentages) belong on the "
        "diagram as annotations.\n"
        "- Every node/box must have a readable text label; every arrow the #arrow marker.\n"
        "- Canvas: 860 × 520 px.\n"
    )
    import re

    def _extract(raw: str) -> str | None:
        raw = (raw or "").strip()
        # 1. A proper greedy match (SVG is fully closed)
        m = re.search(r"(<svg\b[\s\S]+</svg>)", raw, re.IGNORECASE)
        if m:
            return m.group(1)
        # 2. Model wrapped in a code fence but may not have closed </svg> -
        #    extract from <svg to the last >, strip stray fences, force-close.
        m2 = re.search(r"(<svg\b[\s\S]+)", raw, re.IGNORECASE)
        if not m2:
            return None
        content = m2.group(1)
        last_gt = content.rfind(">")
        if last_gt != -1:
            content = content[:last_gt + 1]
        content = re.sub(r"```[\s\S]*$", "", content).rstrip()
        if not re.search(r"</svg\s*>", content, re.IGNORECASE):
            content += "\n</svg>"
        return content

    # 16k budget: with a reasoning-tier model the thinking tokens come out of the same
    # cap, and a starved cap returns no SVG at all (the original v4-pro failure mode).
    out = _extract(complete_text(model, P.DIAGRAM_SYS, user, max_tokens=16000,
                                 temperature=0.4))
    if out is None and not _fake:
        # The pro tier occasionally reasons itself out of budget and emits no SVG.
        # A flash-tier retry reliably produces *a* diagram - a plainer figure beats
        # the text-only placeholder that would otherwise ship in the export.
        fallback = cfg.model_for("diagram_fallback")
        if fallback != model:
            out = _extract(complete_text(fallback, P.DIAGRAM_SYS, user,
                                         max_tokens=8000, temperature=0.4))
    if out is not None:
        return _store(out)

    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="860" height="120">'
        '<rect width="860" height="120" fill="#f8f9fb" rx="8"/>'
        f'<text x="430" y="67" text-anchor="middle" font-family="system-ui,sans-serif" '
        f'font-size="16" fill="#333">{heading[:100]}</text>'
        "</svg>"
    )
