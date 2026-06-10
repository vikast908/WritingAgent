"""All LLM nodes (plan §4, §8, §9, §16). Thin wrappers over llm + prompts + schemas."""
from __future__ import annotations

import json
import os

from . import prompts as P
from . import schemas as S
from .config import ModelConfig
from .llm import complete_structured, complete_text


def _ctx(obj) -> str:
    data = obj.model_dump() if hasattr(obj, "model_dump") else obj
    return json.dumps(data, indent=2, ensure_ascii=False)


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
    prior_summary: str | None = None,
    fix_notes: str | None = None,
    *,
    context: str | None = None,
    skills: list[str] | None = None,
    images: list[str] | None = None,
) -> str:
    model = cfg.model_for("writer")
    parts = [f"Book plan:\n{_ctx(plan)}", f"Chapter blueprint:\n{_ctx(blueprint)}"]
    if context:
        parts.append(f"Canonical context:\n{context}")
    elif prior_summary:
        parts.append(f"Previous chapter summary:\n{prior_summary}")
    if skills:
        parts.append("Relevant craft skills (apply where they fit):\n\n" + "\n\n---\n\n".join(skills))
    if images:
        parts.append(
            "## Suggested images (embed where relevant; keep the attribution line verbatim):\n\n"
            + "\n\n".join(images)
        )
    if fix_notes:
        parts.append("Revision notes (address every point):\n" + fix_notes)
    parts.append(f'Write chapter {blueprint.number}: "{blueprint.title}".')
    return complete_text(model, P.WRITER_SYS, "\n\n".join(parts),
                         max_tokens=16000, thinking=True,
                         temperature=cfg.temperature_for("writer"))


# ── Critic ────────────────────────────────────────────────────────────────────
def critique_chapter(
    cfg: ModelConfig,
    plan: S.BookPlan,
    blueprint: S.ChapterBlueprint,
    prose: str,
    prior_summary: str | None = None,
    *,
    context: str | None = None,
) -> S.Critique:
    model = cfg.model_for("critic")
    parts = [f"Book plan:\n{_ctx(plan)}", f"Chapter blueprint:\n{_ctx(blueprint)}"]
    if context:
        parts.append(f"Canonical context:\n{context}")
    elif prior_summary:
        parts.append(f"Previous chapter summary:\n{prior_summary}")
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
def plan_production(cfg: ModelConfig, plan: S.BookPlan) -> S.ProductionPlan:
    model = cfg.model_for("production")
    user = f"Book plan:\n{_ctx(plan)}\n\nDecide the front- and back-matter components."
    return complete_structured(model, P.PRODUCTION_PLAN_SYS, user, S.ProductionPlan,
                               max_tokens=4000)


def generate_component(
    cfg: ModelConfig, plan: S.BookPlan, component: str, where: str,
    author_meta: str | None, toc_md: str | None = None
) -> str:
    model = cfg.model_for("production")
    parts = [f"Book plan:\n{_ctx(plan)}",
             f"Generate the {where}-matter component: \"{component}\"."]
    if author_meta:
        parts.append(f"Known author/publishing facts:\n{author_meta}")
    if component.lower().startswith("table of contents") and toc_md:
        parts.append(f"Use this table of contents:\n{toc_md}")
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
        parts.append(f"Live web search results (use as factual grounding):\n{web_results}")
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
    return complete_structured(model, P.QUERY_PLANNER_SYS, user, S.SearchQueries, max_tokens=1000)


def deep_research(
    cfg: ModelConfig, plan: S.BookPlan, blueprint: S.ChapterBlueprint, sources_block: str | None
) -> S.ResearchBrief:
    """Synthesize a grounded brief across multiple full-text sources (book chapter)."""
    model = cfg.model_for("researcher")
    parts = [f"Book plan:\n{_ctx(plan)}", f"Chapter blueprint:\n{_ctx(blueprint)}"]
    if sources_block:
        parts.append(f"Full-text web sources (cite by number):\n{sources_block}")
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
        parts.append(f"Full-text web sources (cite by number):\n{sources_block}")
    parts.append("Synthesize a tight, source-grounded brief for this section.")
    return complete_structured(model, P.DEEP_ARTICLE_RESEARCHER_SYS, "\n\n".join(parts),
                               S.ArticleResearchBrief, max_tokens=3500)


# ── Learner (plan §8) ─────────────────────────────────────────────────────────
def learn(
    cfg: ModelConfig, plan: S.BookPlan, instructions: str, critic_findings: str,
    existing_skills: str
) -> S.LearnerOutput:
    model = cfg.model_for("learner")
    user = (f"Book plan (for genre):\n{_ctx(plan)}\n\n"
            f"Human directed revision instructions (strongest signal):\n{instructions or '(none)'}\n\n"
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


def write_article_section(
    cfg: ModelConfig,
    outline: S.ArticleOutline,
    section: S.ArticleSection,
    fix_notes: str | None = None,
    *,
    context: str | None = None,
    skills: list[str] | None = None,
    images: list[str] | None = None,
) -> str:
    model = cfg.model_for("writer")
    parts = [f"Article outline:\n{_ctx(outline)}", f"Section to write:\n{_ctx(section)}"]
    if context:
        parts.append(f"Prior section summaries (for continuity):\n{context}")
    if skills:
        parts.append("Relevant craft skills:\n\n" + "\n\n---\n\n".join(skills))
    if images:
        parts.append("## Suggested images (embed where relevant):\n\n" + "\n\n".join(images))
    if fix_notes:
        parts.append(f"Revision notes (address every point):\n{fix_notes}")
    parts.append(f'Write section {section.number}: "{section.heading}".')
    return complete_text(model, P.ARTICLE_WRITER_SYS, "\n\n".join(parts),
                         max_tokens=8000, temperature=cfg.temperature_for("writer"))


def critique_article_section(
    cfg: ModelConfig,
    outline: S.ArticleOutline,
    section: S.ArticleSection,
    prose: str,
    *,
    context: str | None = None,
) -> S.Critique:
    model = cfg.model_for("critic")
    parts = [f"Article outline:\n{_ctx(outline)}", f"Section blueprint:\n{_ctx(section)}"]
    if context:
        parts.append(f"Prior context:\n{context}")
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
        parts.append(f"Live web search results:\n{web_results}")
    parts.append("Produce a source-grounded research brief for this section.")
    return complete_structured(model, P.ARTICLE_RESEARCHER_SYS, "\n\n".join(parts),
                               S.ArticleResearchBrief, max_tokens=3000)


def summarize_section(cfg: ModelConfig, section: S.ArticleSection, prose: str) -> str:
    model = cfg.model_for("summarizer")
    user = f"Section {section.number}: {section.heading}\n\n{prose}"
    return complete_text(model, P.SUMMARIZER_SYS, user,
                         max_tokens=600, temperature=cfg.temperature_for("summarizer"))


def generate_svg_diagram(cfg: ModelConfig, heading: str, context: str = "") -> str:
    """Generate a detailed, self-contained SVG diagram for the given heading/topic.

    Returns raw SVG XML (starts with <svg ...). On failure returns a minimal placeholder SVG.
    """
    model = cfg.model_for("diagram")  # Flash - reasoning model wastes tokens on thinking, not SVG
    _diagram_key = (model, heading, context[:900])
    _fake = bool(os.getenv("BOOK_AGENT_FAKE"))
    if not _fake:
        from . import cache
        cached = cache.get("diagram", _diagram_key)
        if cached:
            return cached

    def _store(result: str) -> str:
        if not _fake:
            from . import cache
            cache.put("diagram", _diagram_key, result)
        return result

    ctx_block = f"\nContext (use this to choose specific labels/concepts for nodes):\n{context[:900]}" if context else ""
    user = (
        f"Topic: {heading}{ctx_block}\n\n"
        "Produce a detailed, publication-quality SVG diagram that visually explains a key concept "
        "from this topic. Pick the diagram type that best fits: flowchart, concept map, two-column "
        "comparison, timeline, or process loop.\n\n"
        "CRITICAL:\n"
        "- First character of your response must be '<' - no preamble, no fences, no explanation.\n"
        "- Use the ACTUAL concepts from the topic as node/label text - not generic placeholders.\n"
        "- Every node/box must have a readable text label.\n"
        "- Include connecting arrows (use the #arrow marker from <defs>).\n"
        "- Canvas: 860 × 520 px.\n"
    )
    import re
    svg = complete_text(model, P.DIAGRAM_SYS, user, max_tokens=6000, temperature=0.4)
    svg = svg.strip()

    # 1. Try a proper greedy match (SVG is fully closed)
    m = re.search(r"(<svg\b[\s\S]+</svg>)", svg, re.IGNORECASE)
    if m:
        return _store(m.group(1))

    # 2. Model wrapped in a code fence but may not have closed </svg>
    #    Extract from <svg to the last > in the file, then force-close.
    m2 = re.search(r"(<svg\b[\s\S]+)", svg, re.IGNORECASE)
    if m2:
        content = m2.group(1)
        # Drop anything after the last XML-like closing tag
        last_gt = content.rfind(">")
        if last_gt != -1:
            content = content[:last_gt + 1]
        # Strip trailing code fence / prose that crept in before the last >
        content = re.sub(r"```[\s\S]*$", "", content).rstrip()
        if not re.search(r"</svg\s*>", content, re.IGNORECASE):
            content += "\n</svg>"
        return _store(content)

    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="860" height="120">'
        '<rect width="860" height="120" fill="#f8f9fb" rx="8"/>'
        f'<text x="430" y="67" text-anchor="middle" font-family="system-ui,sans-serif" '
        f'font-size="16" fill="#333">{heading[:100]}</text>'
        "</svg>"
    )
