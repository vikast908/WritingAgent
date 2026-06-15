"""The controller action trace (plan.md §21.4).

An append-only ``agent_trace.jsonl`` per project, sibling of ``revision_log.md``.
Every controller decision is one JSON line: auditable now, and the training corpus
for a learned policy later (plan §21.11). Writing is best-effort - a trace breadcrumb
must never break a run.
"""
from __future__ import annotations

import json

from .. import brain


def trace_path(paths):
    return paths.root / "agent_trace.jsonl"


def append(paths, record: dict) -> None:
    """Append one controller action as a single JSON line (no internal newlines)."""
    try:
        brain.append_text(trace_path(paths),
                          json.dumps(record, separators=(",", ":"), default=str))
    except Exception:  # noqa: BLE001 - a trace breadcrumb must never break a run
        pass


def read(paths) -> list[dict]:
    """Parse the trace back into records (skips blank/corrupt lines). [] if none."""
    txt = brain.read_text(trace_path(paths))
    if not txt:
        return []
    out: list[dict] = []
    for line in txt.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out
