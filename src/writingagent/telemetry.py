"""Structured per-LLM-call telemetry: one JSONL record per call.

Files land under `.index/telemetry/calls-YYYYMMDD.jsonl` (or `$WRITINGAGENT_HOME`),
one JSON object per line - greppable/jq-able for "why was chapter 3 slow or
expensive". Records carry: timestamp, run_id, unit (ch03/sec02/production/...),
kind (text/structured), model, latency_ms, attempts, token counts, cost (when
the provider reports it), and the error string for failed calls.

Telemetry must NEVER break a run: every write is wrapped and failures are
silently dropped.
"""
from __future__ import annotations

import datetime
import json

from . import brain


def log_call(record: dict) -> None:
    """Append one call record as a JSONL line. Best-effort - never raises."""
    try:
        d = brain.INDEX_DIR / "telemetry"
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"calls-{datetime.date.today():%Y%m%d}.jsonl"
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001 - observability must not take down the pipeline
        pass


def load_records(project: str | None = None) -> list[dict]:
    """All call records (oldest file first), optionally filtered to one project.
    Corrupt lines are skipped - the files are append-only across crashes."""
    out: list[dict] = []
    d = brain.INDEX_DIR / "telemetry"
    if not d.exists():
        return out
    for path in sorted(d.glob("calls-*.jsonl")):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if project is None or rec.get("project") == project:
                out.append(rec)
    return out


def summarize(project: str | None = None) -> dict:
    """Aggregate the call log for the /dashboard view.

    Returns: {totals: {calls, tokens, cost, errors, avg_latency_ms},
              by_model: [(model, calls, tokens, cost)],
              by_unit:  [(unit, calls, tokens, cost)]   (only when project given),
              runs:     [(run_id, project, calls, tokens, cost)]  (most recent last)}
    """
    recs = load_records(project)
    totals = {"calls": 0, "tokens": 0, "cost": 0.0, "errors": 0, "avg_latency_ms": 0}
    by_model: dict[str, list] = {}
    by_unit: dict[str, list] = {}
    runs: dict[str, list] = {}
    lat_sum = 0
    for r in recs:
        toks = r.get("total_tokens", 0) or 0
        cost = r.get("cost", 0) or 0
        totals["calls"] += 1
        totals["tokens"] += toks
        totals["cost"] += cost
        totals["errors"] += 1 if r.get("error") else 0
        lat_sum += r.get("latency_ms", 0) or 0
        m = by_model.setdefault(r.get("model") or "?", [0, 0, 0.0])
        m[0] += 1
        m[1] += toks
        m[2] += cost
        u = by_unit.setdefault(r.get("unit") or "-", [0, 0, 0.0])
        u[0] += 1
        u[1] += toks
        u[2] += cost
        rn = runs.setdefault(r.get("run_id") or "?", [r.get("project") or "-", 0, 0, 0.0])
        rn[1] += 1
        rn[2] += toks
        rn[3] += cost
    if totals["calls"]:
        totals["avg_latency_ms"] = round(lat_sum / totals["calls"])
    return {
        "totals": totals,
        "by_model": sorted(((k, *v) for k, v in by_model.items()),
                           key=lambda x: -x[2]),
        "by_unit": sorted(((k, *v) for k, v in by_unit.items()), key=lambda x: x[0]),
        "runs": [(k, *v) for k, v in runs.items()],
    }
