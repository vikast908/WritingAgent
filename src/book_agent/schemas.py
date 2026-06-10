"""Pydantic schemas for structured node outputs (see plan.md §4–§16)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator


# ── Planner ────────────────────────────────────────────────────────────────
class Direction(BaseModel):
    title: str
    premise: str
    tone: str
    themes: list[str]
    hook: str
    why_it_works: str


class Directions(BaseModel):
    directions: list[Direction]


class BookPlan(BaseModel):
    title: str
    premise: str
    genre: str
    tone: str
    audience: str
    themes: list[str]
    constraints: list[str]
    world_rules: list[str]
    main_characters: list[str]  # "Name - one-line role / voice"


# ── TOC ──────────────────────────────────────────────────────────────────────
class ChapterBlueprint(BaseModel):
    number: int
    title: str
    purpose: str
    emotional_role: str
    plot_function: str
    setup: str
    payoff: str
    depends_on: list[int]
    target_words: int = 0    # 0 = unspecified (pre-existing TOCs); planner sets per-chapter


class TOC(BaseModel):
    chapters: list[ChapterBlueprint]


# ── Critic ────────────────────────────────────────────────────────────────────
class BlockingIssue(BaseModel):
    type: str  # continuity | character | plot | style | clarity | setup_payoff | plan
    where: str
    detail: str
    fix: str


class Critique(BaseModel):
    verdict: Literal["approve", "revise", "escalate"]
    confidence: float
    blocking: list[BlockingIssue]
    nits: list[str]

    @field_validator("confidence")
    @classmethod
    def _clamp_confidence(cls, v: float) -> float:
        # Models sometimes emit 0-100 or stray values; clamp so threshold checks and
        # the "{:.2f}" displays stay sane (a returned 95 would otherwise read 95.00).
        if v > 1.0:
            v = v / 100.0 if v <= 100.0 else 1.0
        return min(1.0, max(0.0, v))


# ── Extraction (canon update on commit, plan §3.4) ───────────────────────────
class CharacterUpdate(BaseModel):
    name: str
    status: str          # e.g. "alive", "introduced", "dead" - "" if unchanged
    new_facts: list[str]
    voice_notes: list[str]


class TimelineEvent(BaseModel):
    chapter: int
    event: str


class ExtractionResult(BaseModel):
    characters: list[CharacterUpdate]
    locations: list[str]
    world_rules: list[str]
    timeline: list[TimelineEvent]
    threads_touched: list[str]


# ── Consolidation (plan §9) ──────────────────────────────────────────────────
class Contradiction(BaseModel):
    kind: str
    detail: str
    chapters: list[int]
    fix: str


class ConsolidationReport(BaseModel):
    contradictions: list[Contradiction]
    duplicate_facts: list[str]
    unresolved_threads: list[str]
    notes: list[str]


# ── Production (plan §16) ─────────────────────────────────────────────────────
class ProductionPlan(BaseModel):
    front_matter: list[str]   # component names, in order
    back_matter: list[str]
    rationale: str


# ── Learner (plan §8) ─────────────────────────────────────────────────────────
class SkillProposal(BaseModel):
    name: str                 # kebab-case
    genre_tags: list[str]
    when_to_apply: str
    technique: list[str]
    anti_pattern: str


class WatchItem(BaseModel):
    pattern: str
    why: str


class LearnerOutput(BaseModel):
    skills: list[SkillProposal]
    watch_items: list[WatchItem]


# ── Researcher (optional, plan §4) ────────────────────────────────────────────
class ResearchBrief(BaseModel):
    facts: list[str]
    style_cues: list[str]
    comparisons: list[str]


class SearchQueries(BaseModel):
    """Query-expansion output for the deep researcher (plan §15)."""
    queries: list[str]


# ── Article mode ──────────────────────────────────────────────────────────────
class ArticleAngle(BaseModel):
    title: str
    angle: str       # editorial take / thesis
    audience: str
    hook: str


class ArticleAngles(BaseModel):
    angles: list[ArticleAngle]


class ArticleSection(BaseModel):
    number: int
    heading: str
    purpose: str
    include_code: bool
    include_image: bool
    search_query: str = ""   # pre-built query for the researcher node
    target_words: int = 0    # 0 = unspecified; falls back to an even share of the outline total


class ArticleOutline(BaseModel):
    title: str
    angle: str
    target_word_count: int
    sections: list[ArticleSection]


class Source(BaseModel):
    title: str
    url: str
    date: str = ""


class ArticleResearchBrief(BaseModel):
    facts: list[str]
    style_cues: list[str]
    sources: list[Source]
