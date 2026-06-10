"""Tiny thread-pool helper for overlapping independent I/O-bound work.

The pipeline is dominated by network latency (LLM + web/image fetches). Most of it
is an inherently sequential chain - each chapter is written from the *previous*
chapter's summary for continuity, so chapters cannot be parallelised without
breaking canon. But a few steps within a single unit of work are genuinely
independent (e.g. web research vs. image fetch, or the front/back-matter
components), and those can run concurrently. Threads are the right tool here:
the work blocks on sockets, so the GIL is released while waiting.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

_log = logging.getLogger(__name__)


def gather(tasks: dict[str, Callable[[], Any]], *, max_workers: int = 8,
           strict: bool = False) -> dict[str, Any]:
    """Run each zero-arg thunk concurrently; return {name: result}.

    By default a task that raises is logged and its result set to None - a failed
    image fetch must never sink the whole chapter (mirrors the pipeline's existing
    "network errors are non-fatal" contract). With strict=True the first failure is
    re-raised after all tasks finish - for steps that must not silently degrade
    (e.g. the commit-time summary/extraction calls).
    """
    if not tasks:
        return {}
    if len(tasks) == 1:  # no point spinning up a pool for a single task
        (name, fn), = tasks.items()
        try:
            return {name: fn()}
        except Exception:  # noqa: BLE001
            if strict:
                raise
            _log.exception("parallel task %r failed", name)
            return {name: None}

    results: dict[str, Any] = {}
    first_error: Exception | None = None
    with ThreadPoolExecutor(max_workers=min(max_workers, len(tasks))) as pool:
        futures = {pool.submit(fn): name for name, fn in tasks.items()}
        for fut, name in futures.items():
            try:
                results[name] = fut.result()
            except Exception as e:  # noqa: BLE001
                _log.exception("parallel task %r failed", name)
                results[name] = None
                if first_error is None:
                    first_error = e
    if strict and first_error is not None:
        raise first_error
    return results
