"""Book Agent - a self-correcting, multi-book writing system. See plan.md.

Public API (stable, semver-guaranteed within a major version)::

    from book_agent import Agent, write

    # one-shot: topic in, finished file out
    write("How vector databases work", mode="article", export="docx")

    # full lifecycle
    agent = Agent(autonomous=True)
    project = agent.create("How vector databases work", mode="article", units=6)
    project.run(progress=print)
    project.export("pdf")

Everything re-exported here lives in :mod:`book_agent.api`; the internal modules
(``orchestrator``, ``nodes``, ``brain``, ...) are not part of the stable surface.
"""
from __future__ import annotations

# Single source of truth for the version: pyproject derives from this (dynamic = version,
# attr = book_agent.__version__) and the TUI/CLI import it - so there is exactly one place
# to bump. Keep it a plain string literal (setuptools reads it statically).
__version__ = "0.2.0"

__all__ = [
    "Agent", "Project", "Approach", "Status", "Evaluation", "WriteResult",
    "write", "BookAgentError", "ProjectNotFound", "EXPORT_FORMATS", "MODES",
    "Settings", "ModelConfig", "__version__",
]

# Names resolved lazily (PEP 562) so `import book_agent` and lightweight imports
# like `from book_agent import brain` stay fast and never pull the whole pipeline
# (orchestrator/llm/nodes) unless the public API is actually used.
_API_EXPORTS = frozenset({
    "Agent", "Project", "Approach", "Status", "Evaluation", "WriteResult",
    "write", "BookAgentError", "ProjectNotFound", "EXPORT_FORMATS", "MODES",
})
_CONFIG_EXPORTS = frozenset({"Settings", "ModelConfig"})


def __getattr__(name: str):
    if name in _API_EXPORTS:
        from . import api
        return getattr(api, name)
    if name in _CONFIG_EXPORTS:
        from . import config
        return getattr(config, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(__all__)
