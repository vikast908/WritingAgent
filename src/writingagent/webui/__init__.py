"""Local web dashboard (plan §25): run the pipeline from a browser, with full
observability - live runs (SSE), per-agent/per-unit/per-run cost, traces, evals,
skills, settings, and themes. Pure stdlib (http.server) - no new dependencies,
same philosophy as the rest of the engine. Single-user, binds 127.0.0.1 only.
"""
from .server import serve

__all__ = ["serve"]
