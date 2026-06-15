"""Stable, public Python API for the Writing Agent.

This module is the **supported import-and-call surface** for embedding the
pipeline in your own program. Everything exported here (and re-exported from the
``writingagent`` package root) follows the project's versioning policy: names and
call signatures will not break within a major version. The internal modules
(``orchestrator``, ``nodes``, ``brain``, ``llm``, ...) carry no such guarantee
and may change between releases - reach for them only when the facade can't.

Quick start
-----------
One-shot (topic in, finished file out)::

    from writingagent import write

    result = write("How vector databases work", mode="article", export="docx")
    print(result.export_path, result.word_count)

Full lifecycle (create -> run -> inspect -> revise -> export)::

    from writingagent import Agent

    agent = Agent(autonomous=True)
    project = agent.create(
        "How vector databases work",
        mode="article", units=6,
        requirements="audience: senior engineers; ~2000 words; include a benchmark",
    )
    project.run(progress=print)             # blocking; streams log lines to `progress`
    if project.status().done:
        project.export("pdf")

Human-in-the-loop (non-autonomous runs pause for review)::

    project = agent.create("...", autonomous=False)
    st = project.run(progress=print)
    while st.pending_review:
        project.review(unit=st.unit, instruction="tighten the intro, add a citation")
        st = project.run(progress=print)
"""
from __future__ import annotations

import dataclasses
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import brain, llm, nodes, orchestrator
from .brain import ArticlePaths, BookPaths
from .config import ModelConfig, Settings, load_config, load_settings

__all__ = [
    "Agent", "Project", "Approach", "Status", "Evaluation", "WriteResult",
    "write", "WritingAgentError", "ProjectNotFound", "EXPORT_FORMATS", "MODES",
]

#: Output formats accepted by :meth:`Project.export` / ``export=`` arguments.
EXPORT_FORMATS: tuple[str, ...] = ("pdf", "epub", "html", "docx", "txt", "md")
#: Project modes.
MODES: tuple[str, ...] = ("book", "article")

Progress = Callable[[str], None]


def _noop(*_a: Any, **_k: Any) -> None:
    """A silent log sink - libraries shouldn't print unless the caller asks."""


# ── Exceptions ────────────────────────────────────────────────────────────────
class WritingAgentError(Exception):
    """Base class for all errors raised by the public API."""


class ProjectNotFound(WritingAgentError):
    """Raised when a project id can't be found for the given user."""


# ── Value types (stable shapes; not the internal pydantic schemas) ────────────
@dataclass(frozen=True)
class Approach:
    """One proposed creative direction (book) or editorial angle (article).

    Returned by :meth:`Agent.plan`; pass one straight back to
    :meth:`Agent.create` / :meth:`Agent.write` via ``approach=`` to skip a second
    planning call. ``raw`` holds the underlying schema object and is opaque - do
    not depend on its type.
    """
    index: int            # 1-based position in the proposed list
    title: str
    summary: str          # premise (book) / editorial angle (article)
    hook: str = ""
    audience: str = ""    # articles
    tone: str = ""        # books
    raw: Any = field(default=None, repr=False, compare=False)


@dataclass(frozen=True)
class Status:
    """A normalized snapshot of a project's run state."""
    mode: str
    phase: str
    unit: int | None          # current chapter (book) / section (article), 1-based
    total_units: int | None
    committed: int
    pending_review: bool
    done: bool
    open_reviews: list[str]
    raw: dict = field(repr=False, default_factory=dict)

    @classmethod
    def _from_raw(cls, d: dict, mode: str | None) -> Status:
        is_article = mode == "article" or "current_section" in d or d.get("mode") == "article"
        unit = d.get("current_section") if is_article else d.get("current_chapter")
        total = d.get("num_sections") if is_article else d.get("num_chapters")
        return cls(
            mode="article" if is_article else "book",
            phase=d.get("phase", ""),
            unit=unit,
            total_units=total,
            committed=d.get("committed", 0),
            pending_review=bool(d.get("pending_review")),
            done=d.get("phase") == "done",
            open_reviews=list(d.get("open_reviews", [])),
            raw=d,
        )


@dataclass(frozen=True)
class Evaluation:
    """Result of :meth:`Project.evaluate` - a judged rubric plus hard metrics."""
    scores: dict          # 5-dimension rubric, each 1-5
    metrics: dict         # words, ai_tells, citations, verified_sources, ...
    summary: str
    report_path: Path


@dataclass(frozen=True)
class WriteResult:
    """Result of the one-shot :func:`write` / :meth:`Agent.write`."""
    project_id: str
    mode: str
    manuscript_path: Path
    export_path: Path | None
    export_format: str | None
    word_count: int
    status: Status


# ── Helpers ───────────────────────────────────────────────────────────────────
def _requirements_to_intake(requirements: str | dict | None) -> str | None:
    """Normalize a caller's ``requirements`` into the pipeline's intake markdown.

    A plain string is taken verbatim (it's injected into every writer/critic call);
    a dict is rendered as a labelled requirements list.
    """
    if requirements is None:
        return None
    if isinstance(requirements, str):
        return requirements if requirements.strip() else None
    if isinstance(requirements, dict):
        lines = ["# Author requirements (captured via API)", ""]
        for key, val in requirements.items():
            if str(val).strip():
                lines.append(f"- **{key}**: {val}")
        return "\n".join(lines) if len(lines) > 2 else None
    raise TypeError("requirements must be a str, dict, or None")


_EXPORT_FNS: dict[str, Callable[..., Any]] = {
    "pdf": orchestrator.export_pdf, "epub": orchestrator.export_epub,
    "html": orchestrator.export_html, "docx": orchestrator.export_docx,
    "txt": orchestrator.export_txt, "md": orchestrator.export_md,
}


# ── Agent: holds user + settings + model routing so callers don't thread them ─
class Agent:
    """Entry point to the writing pipeline.

    Bundles the per-call plumbing (``user``, :class:`~writingagent.config.Settings`,
    model routing) the internal functions otherwise require, so your code calls
    :meth:`create` / :meth:`write` directly.

    Parameters
    ----------
    user:
        Tenant/user id - isolates projects, skills, and voice memory on disk.
    settings:
        A :class:`Settings`; defaults to ``config/settings.yaml`` (or built-in
        defaults). Any individual field can be overridden via ``**overrides``.
    models:
        A :class:`ModelConfig`, or a model slug string to route **every** node to
        one model, or ``None`` for ``config/models.yaml``.
    autonomous:
        Convenience override of ``settings.autonomous``.
    **overrides:
        Any :class:`Settings` field (``mode``, ``num_sections``, ``humanize``,
        ``use_researcher``, ...). Validated against the dataclass.
    """

    def __init__(
        self,
        *,
        user: str = "default",
        settings: Settings | None = None,
        models: ModelConfig | str | None = None,
        autonomous: bool | None = None,
        **overrides: Any,
    ) -> None:
        if not brain.is_safe_id(user):
            raise ValueError(f"Invalid user id {user!r} (use letters, digits, - . _).")
        self.user = user

        base = settings or load_settings()
        if autonomous is not None:
            overrides.setdefault("autonomous", autonomous)
        if overrides:
            valid = {f.name for f in dataclasses.fields(Settings)}
            unknown = set(overrides) - valid
            if unknown:
                raise TypeError(f"unknown Settings field(s): {', '.join(sorted(unknown))}")
            base = dataclasses.replace(base, **overrides)
        self.settings = base

        if models is None:
            self.models = load_config()
        elif isinstance(models, str):
            self.models = load_config()
            self.models.set_all(models)
        else:
            self.models = models

    # -- internal --------------------------------------------------------------
    def _apply_runtime(self) -> None:
        """Sync process-global LLM knobs to this agent's settings before a call."""
        llm.configure_headroom(self.settings.use_headroom)
        llm.configure_timeout(self.settings.request_timeout)
        llm.configure_openrouter_providers(self.settings.openrouter_providers)
        llm.configure_fallback(self.models.fallback)
        try:
            llm.configure_provider(self.settings.provider)
        except ValueError:
            pass  # unknown id -> keep the current/default host

    def _resolve_approach(self, topic: str, mode: str, approach: Any) -> Any:
        """Return the raw schema object for the chosen direction/angle."""
        if isinstance(approach, Approach):
            if approach.raw is None:
                raise WritingAgentError("Approach carries no plan; get it from Agent.plan().")
            return approach.raw
        options = self.plan(topic, mode=mode)
        if approach is None:
            chosen = options[0]
        elif isinstance(approach, bool):   # guard: bool is an int subclass
            raise TypeError("approach must be None, int, Approach, or callable")
        elif isinstance(approach, int):
            if not 1 <= approach <= len(options):
                raise WritingAgentError(f"approach index {approach} out of range 1..{len(options)}")
            chosen = options[approach - 1]
        elif callable(approach):
            picked = approach(options)
            chosen = options[picked - 1] if isinstance(picked, int) else picked
            if not isinstance(chosen, Approach):
                raise WritingAgentError("approach callable must return an Approach or 1-based int")
        else:
            raise TypeError("approach must be None, int, Approach, or callable")
        return chosen.raw

    # -- planning --------------------------------------------------------------
    def plan(self, topic: str, *, mode: str | None = None, n: int = 3) -> list[Approach]:
        """Propose ``n`` creative approaches for ``topic`` without committing.

        Inspect the returned list and pass one back via ``create(approach=...)``,
        or skip this entirely and let ``create`` auto-pick the first.
        """
        mode = mode or self.settings.mode
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
        self._apply_runtime()
        if mode == "article":
            angles = nodes.plan_article_angles(self.models, topic, n=n).angles
            return [Approach(index=i, title=a.title, summary=a.angle,
                             hook=a.hook, audience=a.audience, raw=a)
                    for i, a in enumerate(angles, 1)]
        dirs = nodes.planner_directions(self.models, topic, n=n).directions
        return [Approach(index=i, title=d.title, summary=d.premise,
                         hook=d.hook, tone=d.tone, raw=d)
                for i, d in enumerate(dirs, 1)]

    # -- lifecycle -------------------------------------------------------------
    def create(
        self,
        topic: str,
        *,
        mode: str | None = None,
        approach: int | Approach | Callable[[list[Approach]], Any] | None = None,
        units: int | None = None,
        max_revisions: int | None = None,
        requirements: str | dict | None = None,
        author: str | None = None,
        autonomous: bool | None = None,
        humanize: bool | None = None,
        project_id: str | None = None,
    ) -> Project:
        """Plan and scaffold a new project, returning a :class:`Project` handle.

        Nothing is written yet beyond the plan/outline; call :meth:`Project.run`
        to drive the pipeline. ``approach`` selects the creative direction:
        ``None`` auto-picks the first, an ``int`` is a 1-based index, an
        :class:`Approach` (from :meth:`plan`) is used directly, and a callable
        receives ``list[Approach]`` and returns one (or a 1-based int).
        """
        mode = mode or self.settings.mode
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
        if project_id is not None and not brain.is_safe_id(project_id):
            raise ValueError(f"Invalid project_id {project_id!r} (letters, digits, - . _).")
        self._apply_runtime()

        chosen = self._resolve_approach(topic, mode, approach)
        autonomous = self.settings.autonomous if autonomous is None else autonomous
        max_rev = self.settings.max_revisions if max_revisions is None else max_revisions
        intake = _requirements_to_intake(requirements)

        if mode == "article":
            units = units or self.settings.num_sections
            pid = orchestrator.start_article(
                self.models, self.settings, self.user, topic, chosen, project_id,
                units, max_rev, autonomous=autonomous, humanize=humanize,
                intake=intake, author=author)
        else:
            units = units or self.settings.num_chapters
            pid = orchestrator.start_book(
                self.models, self.settings, self.user, topic, chosen, project_id,
                units, max_rev, autonomous=autonomous, humanize=humanize,
                intake=intake, author=author)
        return Project(self, pid, mode)

    def open(self, project_id: str) -> Project:
        """Return a handle to an existing project (raises :class:`ProjectNotFound`)."""
        for pid, ptype in brain.list_projects(self.user):
            if pid == project_id:
                return Project(self, pid, ptype)
        raise ProjectNotFound(f"No project {project_id!r} for user {self.user!r}.")

    def projects(self) -> list[Project]:
        """Every project (book or article) belonging to this agent's user."""
        return [Project(self, pid, ptype) for pid, ptype in brain.list_projects(self.user)]

    def write(
        self,
        topic: str,
        *,
        mode: str | None = None,
        units: int | None = None,
        max_revisions: int | None = None,
        requirements: str | dict | None = None,
        author: str | None = None,
        approach: int | Approach | Callable[[list[Approach]], Any] | None = None,
        export: str | None = "pdf",
        humanize: bool | None = None,
        project_id: str | None = None,
        progress: Progress | None = None,
    ) -> WriteResult:
        """One-shot: create -> run -> export, returning a :class:`WriteResult`.

        Always runs **autonomously** (a one-shot has no way to answer a review
        prompt). Pass ``export=None`` to skip the export step and keep just the
        assembled manuscript.
        """
        project = self.create(
            topic, mode=mode, approach=approach, units=units,
            max_revisions=max_revisions, requirements=requirements, author=author,
            autonomous=True, humanize=humanize, project_id=project_id)
        status = project.run(progress=progress)
        export_path = project.export(export, progress=progress) if export else None
        return WriteResult(
            project_id=project.id, mode=project.mode,
            manuscript_path=project.manuscript_path, export_path=export_path,
            export_format=(export or None), word_count=project.word_count(),
            status=status)


# ── Project: a handle to one book/article ─────────────────────────────────────
class Project:
    """A handle to one project. Obtained from :meth:`Agent.create`,
    :meth:`Agent.open`, or :meth:`Agent.projects`. Cheap to construct; all state
    lives on disk under the agent's user."""

    def __init__(self, agent: Agent, project_id: str, mode: str | None = None) -> None:
        self._agent = agent
        self.id = project_id
        self._mode = mode

    def __repr__(self) -> str:
        return f"Project(id={self.id!r}, mode={self.mode!r}, user={self._agent.user!r})"

    # -- identity --------------------------------------------------------------
    @property
    def mode(self) -> str:
        """``"book"`` or ``"article"`` (detected from disk on first access)."""
        if self._mode is None:
            art = ArticlePaths(self.id, self._agent.user)
            self._mode = "article" if art.run_state.exists() else "book"
        return self._mode

    @property
    def user(self) -> str:
        return self._agent.user

    def _paths(self):
        return (ArticlePaths(self.id, self._agent.user) if self.mode == "article"
                else BookPaths(self.id, self._agent.user))

    @property
    def root(self) -> Path:
        return self._paths().root

    @property
    def manuscript_path(self) -> Path:
        return self._paths().manuscript

    # -- driving the pipeline --------------------------------------------------
    def run(self, *, progress: Progress | None = None, autonomous: bool | None = None,
            force: bool = False) -> Status:
        """Drive the pipeline until it finishes or pauses for review. Blocking.

        ``progress`` receives human-readable log lines as work proceeds. Returns
        the :class:`Status` afterwards - check ``.done`` and ``.pending_review``.
        """
        self._agent._apply_runtime()
        orchestrator.run(self._agent.models, self._agent.user, self.id,
                         force=force, autonomous=autonomous, log=progress or _noop)
        return self.status()

    def status(self) -> Status:
        raw = orchestrator.status(self._agent.user, self.id)
        return Status._from_raw(raw, self._mode)

    def review(self, unit: int, instruction: str) -> None:
        """Answer an escalation on ``unit``; the next :meth:`run` resumes with it."""
        orchestrator.record_instruction(self._agent.user, self.id, unit, instruction)

    def revise(self, unit: int, instruction: str, *,
               confirm: Callable[[str, str, str], bool] | None = None,
               progress: Progress | None = None) -> None:
        """Rewrite one *committed* chapter/section of a finished piece to
        ``instruction`` and patch the assembled manuscript. ``confirm(old, new,
        summary) -> bool``, if given, gates the write (return ``False`` to discard)."""
        self._agent._apply_runtime()
        orchestrator.revise_unit(self._agent.models, self._agent.user, self.id, unit,
                                 instruction, log=progress or _noop, confirm=confirm)

    # -- inspection ------------------------------------------------------------
    def read(self, unit: int | None = None, *, manuscript: bool = False,
             summary: bool = False, version: int | None = None) -> str:
        """Return chapter/section text, a summary, the assembled manuscript, or a
        specific draft ``version``. Raises ``FileNotFoundError`` if absent."""
        p = self._paths()
        if version is not None:
            n = unit or 1
            tag = f"section_{n:02d}" if self.mode == "article" else f"ch{n:02d}"
            target = p.root / "versions" / f"{tag}.v{version:02d}.md"
        elif manuscript:
            target = p.manuscript
        elif summary:
            target = p.ch_summary(unit or 1)
        else:
            target = p.ch(unit or 1)
        text = brain.read_text(target)
        if text is None:
            raise FileNotFoundError(target)
        return text

    def word_count(self) -> int:
        """Words in the assembled manuscript, falling back to committed parts."""
        p = self._paths()
        txt = brain.read_text(p.manuscript)
        if txt:
            return len(txt.split())
        if self.mode == "article":
            if p.root.exists():
                return sum(len(f.read_text(encoding="utf-8").split())
                           for f in p.root.glob("section_*.md")
                           if not f.name.endswith(".summary.md"))
            return 0
        if p.chapters.exists():
            return sum(len(f.read_text(encoding="utf-8").split())
                       for f in p.chapters.glob("ch*.md")
                       if not f.name.endswith((".draft.md", ".summary.md")))
        return 0

    def evaluate(self, *, progress: Progress | None = None) -> Evaluation:
        """Quality report: deterministic metrics + a judged 5-dimension rubric."""
        self._agent._apply_runtime()
        r = orchestrator.evaluate_project(self._agent.models, self._agent.user, self.id,
                                          log=progress or _noop)
        return Evaluation(scores=r["scores"], metrics=r["metrics"],
                          summary=r["summary"], report_path=r["report_path"])

    def table_read(self, *, persona: str | None = None,
                   progress: Progress | None = None) -> str:
        """Run a skeptical cold-read pass and return the report markdown."""
        self._agent._apply_runtime()
        out = orchestrator.run_table_read(self._agent.models, self._agent.user, self.id,
                                          persona=persona, log=progress or _noop)
        return brain.read_text(out) or ""

    def evidence_report(self, *, progress: Progress | None = None) -> str:
        """Build (and return) evidence_report.md - the thesis + every source ranked by
        influence. Deterministic, no model call; articles only. Returns the markdown ("" if
        there was nothing to report)."""
        out = orchestrator.build_evidence_report(self._agent.user, self.id, log=progress or _noop)
        return brain.read_text(out) if out else ""

    def memory(self) -> str:
        """Human-readable canon + entity-graph summary (books only)."""
        return orchestrator.memory_summary(self._agent.user, self.id)

    # -- production / output ---------------------------------------------------
    def consolidate(self, *, progress: Progress | None = None) -> None:
        self._agent._apply_runtime()
        orchestrator.run_consolidation(self._agent.models, self._agent.user, self.id,
                                       log=progress or _noop)

    def produce(self, *, progress: Progress | None = None) -> None:
        """Run the Production layer (front/back matter + manuscript assembly)."""
        self._agent._apply_runtime()
        orchestrator.run_production(self._agent.models, self._agent.user, self.id,
                                    log=progress or _noop)

    def export(self, fmt: str = "pdf", *, progress: Progress | None = None) -> Path:
        """Export the manuscript to ``fmt`` (one of :data:`EXPORT_FORMATS`).
        Returns the path to the written file."""
        fmt = (fmt or "").lower()
        if fmt not in EXPORT_FORMATS:
            raise WritingAgentError(f"unknown export format {fmt!r}; choose from {EXPORT_FORMATS}")
        return _EXPORT_FNS[fmt](self._agent.user, self.id, log=progress or _noop)

    def delete(self) -> None:
        """Permanently delete this project and its index. Irreversible."""
        orchestrator.delete_book(self._agent.user, self.id)


# ── Module-level one-shot (builds an Agent for you) ───────────────────────────
def write(
    topic: str,
    *,
    user: str = "default",
    settings: Settings | None = None,
    models: ModelConfig | str | None = None,
    mode: str | None = None,
    units: int | None = None,
    max_revisions: int | None = None,
    requirements: str | dict | None = None,
    author: str | None = None,
    approach: int | Approach | Callable[[list[Approach]], Any] | None = None,
    export: str | None = "pdf",
    humanize: bool | None = None,
    project_id: str | None = None,
    progress: Progress | None = None,
    **overrides: Any,
) -> WriteResult:
    """Topic in, finished file out - the fire-and-forget entry point.

    Builds an autonomous :class:`Agent`, creates the project, runs it to
    completion, and exports it. Any :class:`Settings` field can be passed as a
    keyword (``num_sections=8``, ``use_researcher=False``, ...). For resume,
    revision, or inspection, use :class:`Agent` / :class:`Project` directly.
    """
    agent = Agent(user=user, settings=settings, models=models, autonomous=True, **overrides)
    return agent.write(
        topic, mode=mode, units=units, max_revisions=max_revisions,
        requirements=requirements, author=author, approach=approach,
        export=export, humanize=humanize, project_id=project_id, progress=progress)
