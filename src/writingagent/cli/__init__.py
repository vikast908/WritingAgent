"""CLI for Writing Agent (plan.md §13).

This package is a facade over the command seams - it re-exports every public and
test-reached name so `cli.X` (and `from writingagent.cli import X`) keeps resolving
unchanged for the entry point, the shell, and the test suite. The seams:

- ``_common``    shared leaf helpers (console, project/path resolution, spinner, diff)
- ``create``     the ``new`` command + the manual-mode outline gate
- ``interview``  the autonomous ``write`` flow (upfront interview -> run -> export)
- ``commands``   the core project commands (run/status/review/read/eval/skills/...)
- ``export``     export / polish / evidence (format parsing, isolated per-format failures)
- ``app``        the command registry, argparse surface, provider selection, ``main()``

Subcommands: new, write, run, status, review, revise, versions, brief, tableread,
eval, read, memory, produce, consolidate, skills, list, export, polish, evidence,
seed-skills, delete, config.
"""
from __future__ import annotations

from ._common import *  # noqa: F401,F403
from .app import *  # noqa: F401,F403
from .commands import *  # noqa: F401,F403
from .create import *  # noqa: F401,F403
from .export import *  # noqa: F401,F403
from .interview import *  # noqa: F401,F403
