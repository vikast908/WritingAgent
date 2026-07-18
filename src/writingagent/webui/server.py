"""The web dashboard's HTTP server (plan §25).

Pure stdlib: ThreadingHTTPServer + SSE. One JSON API over the same engine the TUI
drives (api.Agent / orchestrator / telemetry / trace / skills / config), plus a
single-page app served from static/index.html.

Design constraints:
- **Local, single-user**: binds 127.0.0.1 only; no auth (same trust boundary as the
  TUI on the same machine). Do NOT expose this on a network interface.
- **One active run at a time**: llm.run_session serializes runs process-wide anyway,
  so the job manager enforces a single live job and returns 409 for a second.
- **Never lie about state**: every view reads the on-disk brain (run_state,
  telemetry JSONL, agent_trace.jsonl) - the same files the TUI uses, so the two
  surfaces can't drift.
"""
from __future__ import annotations

import json
import re
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .. import brain, telemetry, ui
from ..brain import ArticlePaths, BookPaths
from ..config import (
    Settings,
    _clamp_settings,
    load_config,
    load_settings,
    save_config,
    save_settings,
)

_STATIC = Path(__file__).parent / "static"
_EVENT_CAP = 5000          # max buffered events per job (a run logs ~hundreds)
_MAX_RETAINED_JOBS = 20    # cap finished jobs kept in memory (each holds up to _EVENT_CAP events)
_RECORDS_CAP = 800         # max raw telemetry rows returned per request


# ── Jobs: background runs with buffered, replayable event streams ─────────────
class _Control:
    """Duck-typed run control consumed by orchestrator._apply_run_control."""

    def __init__(self):
        self.pause = False

    def take_manual(self) -> bool:
        return False


class Job:
    def __init__(self, kind: str, project: str | None):
        self.id = uuid.uuid4().hex[:10]
        self.kind = kind
        self.project = project
        self.status = "running"          # running | done | error | paused
        self.error = ""
        self.control = _Control()
        self.events: list[dict] = []
        self.cond = threading.Condition()

    def emit(self, event: dict) -> None:
        with self.cond:
            if len(self.events) < _EVENT_CAP:
                self.events.append(event)
            self.cond.notify_all()

    def log(self, *parts) -> None:
        line = " ".join(str(p) for p in parts)
        self.emit({"t": "log", "line": line})

    def finish(self, status: str, error: str = "") -> None:
        self.status = status
        self.error = error
        self.emit({"t": "done", "status": status, "error": error,
                   "project": self.project})


class JobManager:
    def __init__(self):
        self.jobs: dict[str, Job] = {}
        self.lock = threading.Lock()

    def active(self) -> Job | None:
        with self.lock:
            return next((j for j in self.jobs.values() if j.status == "running"), None)

    def _prune(self) -> None:
        """Cap retained finished jobs so a long-lived dashboard doesn't accumulate thousands
        of buffered event dicts (and an ever-growing /api/state payload). Running jobs are
        always kept; the oldest finished jobs beyond the cap are dropped. Caller holds the lock."""
        finished = [jid for jid, j in self.jobs.items() if j.status != "running"]
        for jid in finished[:max(0, len(finished) - _MAX_RETAINED_JOBS)]:  # dict is insertion-ordered
            del self.jobs[jid]

    def start(self, kind: str, project: str | None, body) -> Job:
        """Run `body(job)` on a daemon thread. Raises RuntimeError if a job is live."""
        with self.lock:
            if any(j.status == "running" for j in self.jobs.values()):
                raise RuntimeError("a job is already running - one run at a time")
            self._prune()
            job = Job(kind, project)
            self.jobs[job.id] = job

        def _run():
            try:
                body(job)
                job.finish("paused" if job.control.pause else "done")
            except Exception as e:  # noqa: BLE001 - surface, never kill the server
                job.finish("error", f"{type(e).__name__}: {e}")
        threading.Thread(target=_run, name=f"webui-{kind}", daemon=True).start()
        return job


_jobs = JobManager()


# ── Engine helpers ─────────────────────────────────────────────────────────────
def _uid() -> str:
    return load_settings().default_user


def _paths(uid: str, pid: str):
    art = ArticlePaths(pid, uid)
    return art if art.run_state.exists() else BookPaths(pid, uid)


def _title(root) -> str:
    """The piece's human title (articles: outline.json, books: plan.json) - '' when absent."""
    for name in ("outline.json", "plan.json"):
        data = brain.read_json(root / name) or {}
        if data.get("title"):
            return str(data["title"])
    return ""


def _project_overview(uid: str) -> list[dict]:
    from .. import orchestrator
    out = []
    for pid, ptype in brain.list_projects(uid):
        try:
            st = orchestrator.status(uid, pid)
        except Exception:  # noqa: BLE001 - a corrupt project must not hide the rest
            st = {}
        is_article = ptype == "article"
        cur, tot = (("current_section", "num_sections") if is_article
                    else ("current_chapter", "num_chapters"))
        ms = brain.read_text(_paths(uid, pid).manuscript) or ""
        out.append({
            "id": pid, "title": _title(_paths(uid, pid).root),
            "mode": ptype, "phase": st.get("phase", "?"),
            "unit": st.get(cur), "total_units": st.get(tot),
            "committed": st.get("committed", 0),
            "pending_review": bool(st.get("pending_review")),
            "agentic": st.get("controller") == "agentic",
            "words": len(ms.split()) if ms else 0,
        })
    return out


def _options() -> dict:
    """Selectable option lists for the Settings dropdowns + restyle (register/persona/
    emotion) and the export format set - every enum setting becomes a dropdown."""
    from .. import emotions, fields, images, personas, providers, registers, search
    return {
        "registers": list(registers.names()),
        "personas": list(personas.names()),
        "emotions": list(emotions.names()),
        "fields": list(fields.names()),
        "export_formats": ["pdf", "epub", "html", "docx", "txt", "md"],
        "citation_styles": ["influence", "numeric", "apa", "mla", "chicago", "ap", "none"],
        "search_providers": list(search.PROVIDERS),
        "image_sources": list(images.image_sources()),
        "modes": ["article", "book"],
        "cost_modes": ["standard", "budget"],
        "agentic_policies": ["default", "llm", "trace"],
        "diagram_engines": ["auto", "d2", "builtin"],
        "providers": list(providers.names()),
    }


def _mask(v: str) -> str:
    """Show only the last 4 chars of a key, so the UI can confirm what's set without leaking it."""
    v = v or ""
    return ("•" * max(0, min(len(v) - 4, 12)) + v[-4:]) if v else ""


def _key_envs() -> set[str]:
    """Every env var the UI is allowed to write - the model hosts', search backends', and
    keyed image sources' key vars. A setkey for anything outside this set is rejected."""
    from .. import images, providers, search
    envs: set[str] = set()
    for p in providers._PROVIDERS:
        envs.update(p.key_env)
    for b in search._BACKENDS.values():
        envs.add(b.key_env)
    for ib in images._IMG_BACKENDS.values():
        if ib.key_env:
            envs.add(ib.key_env)
    return envs


def _keys_payload() -> dict:
    """Masked key status for every model host + keyed search + keyed image provider."""
    import os

    from .. import images, providers, search
    hosts = []
    for p in providers._PROVIDERS:
        if p.local or p.id in ("custom", "bedrock", "azure") or not p.key_env:
            continue   # local servers / gateways don't take a single first-party key
        val = providers.api_key_for(p) or ""
        hosts.append({"id": p.id, "name": p.name, "env": p.key_env[0],
                      "set": bool(val), "masked": _mask(val)})
    searches = []
    for name, b in search._BACKENDS.items():
        val = os.getenv(b.key_env, "")
        searches.append({"id": name, "name": name, "env": b.key_env,
                         "set": bool(val), "masked": _mask(val)})
    # only the keyed image sources need a row; openverse/wikimedia are keyless
    imgs = []
    for name, ib in images._IMG_BACKENDS.items():
        if not ib.key_env:
            continue
        val = os.getenv(ib.key_env, "")
        imgs.append({"id": name, "name": ib.label, "env": ib.key_env,
                     "set": bool(val), "masked": _mask(val)})
    return {"hosts": hosts, "search": searches, "images": imgs}


def _themes() -> dict:
    keep = ("GOLD", "GOLD_HI", "INK", "PARCH", "DIM", "RULE", "ERR",
            "ON_CLR", "OFF_CLR", "DESC")
    return {name: {k.lower(): v for k, v in t.items() if k in keep}
            for name, t in ui.THEMES.items()}


def _settings_payload(s: Settings) -> list[dict]:
    import dataclasses
    out = []
    for f in dataclasses.fields(s):
        v = getattr(s, f.name)
        out.append({"name": f.name, "value": v,
                    "type": ("bool" if isinstance(v, bool)
                             else "int" if isinstance(v, int)
                             else "float" if isinstance(v, float) else "str")})
    return out


def _apply_setting(field: str, value) -> Settings:
    import dataclasses
    s = load_settings()
    valid = {f.name: f for f in dataclasses.fields(Settings)}
    if field not in valid:
        raise ValueError(f"unknown setting '{field}'")
    # Coerce by the field's DECLARED type (its default), never the current runtime value:
    # a value corrupted to the wrong type (e.g. default_user saved as an int) must not make
    # every future write coerce the same wrong way.
    fld = valid[field]
    declared = fld.default if fld.default is not dataclasses.MISSING else getattr(s, field)
    if isinstance(declared, bool):
        value = value if isinstance(value, bool) else str(value).lower() in ("1", "true", "yes", "on")
    elif isinstance(declared, int):
        value = int(value)
    elif isinstance(declared, float):
        value = float(value)
    else:
        value = str(value)
    setattr(s, field, value)
    s = _clamp_settings(s)
    save_settings(s)
    return s


# Artifact whitelist: name -> relative path under the project root. promo/* and
# versions/* resolve dynamically but stay inside the root (checked) and inside
# a fixed suffix set - the server must never become a file browser.
_ARTIFACTS = {
    "manuscript": "manuscript.md",
    "thesis": "thesis.md",
    "evidence": "evidence_report.md",
    "seo": "seo_report.md",
    "table_read": "table_read.md",
    "eval": "eval_report.md",
    "keywords": "keywords.json",
    "outline": "outline.md",
    "toc": "toc.md",
    "cohesion": "cohesion_report.md",
}
_ART_RASTER = {".png", ".jpg", ".jpeg", ".gif", ".webp"}   # binary; served as a data-URI <img>
_ART_OK_SUFFIX = {".md", ".json", ".txt", ".jsonl", ".svg"} | _ART_RASTER
_ART_DYN = re.compile(r"^(promo|versions|restyled|images)/[\w.\- ]+$")


def _artifact_path(root: Path, name: str) -> Path | None:
    rel = _ARTIFACTS.get(name) or (name if _ART_DYN.match(name) else None)
    if not rel:
        return None
    p = (root / rel).resolve()
    try:
        p.relative_to(root.resolve())
    except ValueError:
        return None
    return p if (p.suffix in _ART_OK_SUFFIX and p.exists()) else None


def _artifact_list(root: Path) -> list[str]:
    have = [k for k, rel in _ARTIFACTS.items() if (root / rel).exists()]
    promo = root / "promo"
    if promo.exists():
        have += [f"promo/{p.name}" for p in sorted(promo.glob("*.md"))]
    return have


def _trace_records(uid: str, pid: str) -> list[dict]:
    from .. import agentic
    try:
        return agentic.trace.read(_paths(uid, pid))
    except Exception:  # noqa: BLE001 - no trace (non-agentic run) is normal
        return []


def _plain_x_thread(md: str) -> str:
    """The promo X-thread markdown as paste-ready plain text: drop headers and bold/italic
    markers, keep the tweets and their separators."""
    import re
    out = []
    for ln in md.splitlines():
        ln = re.sub(r"^#+\s*", "", ln)                 # markdown headers
        ln = re.sub(r"\*\*(.+?)\*\*", r"\1", ln)       # **bold**
        ln = re.sub(r"(?<!\*)\*(?!\*)(.+?)\*", r"\1", ln)  # *italics*
        out.append(ln)
    return "\n".join(out).strip()


def _evals(uid: str, pid: str) -> dict:
    p = _paths(uid, pid)
    state = brain.read_json(p.run_state) or {}
    per_attempt = []
    for f in sorted(p.root.glob("eval_*.json")):
        d = brain.read_json(f)
        if d:
            per_attempt.append(d)
    return {"scores": state.get("scores") or [], "insights": state.get("insights") or [],
            "attempts": per_attempt,
            "eval_report": brain.read_text(p.root / "eval_report.md") or ""}


def _memory(uid: str) -> dict:
    """Everything the agent remembers about one user, for the Memory view: the five
    memory types (profile, learned skills, watch-list, standing preferences, voice
    exemplars) with the stats and bodies the UI needs to display and manage them."""
    from .. import retrieval
    from .. import skills as skills_mod
    rows = skills_mod.list_skills(uid)          # name/status/stats, frontmatter-accurate
    bodies = {}                                 # name -> full md, keyed to match rows[].name
    d = brain.skills_dir(uid)
    if d.exists():
        for p in sorted(d.glob("*.md")):
            text = p.read_text(encoding="utf-8")
            fm = retrieval._parse_frontmatter(text)
            bodies[str(fm.get("name") or p.stem)] = text
    return {
        "profile": brain.read_text(brain.user_profile(uid)) or "",
        "skills": rows,
        "skill_bodies": bodies,
        "watch_list": brain.read_text(brain.watch_list(uid)) or "",
        "preferences": brain.list_preferences(uid),
        "voice": brain.list_voice(uid),
    }


def _memory_op(uid: str, body: dict) -> dict:
    """Mutate one memory item. Dispatched on (kind, op); every branch is a small, explicit
    write so the Memory UI can add/edit/delete without a generic file-write surface."""
    from .. import skills as skills_mod
    kind = body.get("kind", "")
    op = body.get("op", "")
    text = body.get("text", "")
    if kind == "profile":                        # free-text markdown; blank clears
        if text.strip():
            brain.write_text(brain.user_profile(uid), text)
        else:
            brain.user_profile(uid).unlink(missing_ok=True)
        return {"ok": True}
    if kind == "watch":
        if text.strip():
            brain.write_text(brain.watch_list(uid), text)
        else:
            brain.watch_list(uid).unlink(missing_ok=True)
        return {"ok": True}
    if kind == "pref":
        if op == "add":
            brain.record_preference(uid, text)
        elif op == "delete":
            if not brain.delete_preference(uid, text):
                raise ValueError("preference not found")
        else:
            raise ValueError(f"unknown pref op: {op}")
        return {"ok": True}
    if kind == "skill":
        name = body.get("name", "")
        if op == "status":
            if not skills_mod.set_skill_status(uid, name, body.get("status", "")):
                raise ValueError("skill not found")
        elif op == "delete":
            if not skills_mod.delete_skill(uid, name):
                raise ValueError("skill not found")
        else:
            raise ValueError(f"unknown skill op: {op}")
        return {"ok": True}
    if kind == "voice":
        if op == "add":
            name = brain.add_voice_exemplar(uid, body.get("title", ""), text)
            if not name:
                raise ValueError("paste some text to save an exemplar")
            return {"ok": True, "name": name}
        if op == "delete":
            if not brain.delete_voice_exemplar(uid, body.get("name", "")):
                raise ValueError("exemplar not found")
            return {"ok": True}
        raise ValueError(f"unknown voice op: {op}")
    raise ValueError(f"unknown memory kind: {kind}")


# ── Job bodies ─────────────────────────────────────────────────────────────────
def _emit_state(job: Job, uid: str, pid: str) -> None:
    try:
        st = brain.read_json(_paths(uid, pid).run_state) or {}
        job.emit({"t": "state", "state": {k: st.get(k) for k in (
            "phase", "committed", "current_section", "current_chapter",
            "num_sections", "num_chapters", "pending_review")}})
    except Exception:  # noqa: BLE001
        pass


def _job_log(job: Job, uid: str):
    """A log callback that also snapshots run state after every line."""
    def log(*parts):
        job.log(*parts)
        if job.project:
            _emit_state(job, uid, job.project)
    return log


def _finish_piece(job: Job, cfg, settings, uid: str, pid: str, log) -> None:
    """The `write` tail: auto seo+promote (LOCAL artifacts only - never posts
    anywhere) + md/html export, only for a FINISHED run."""
    from .. import orchestrator
    st = orchestrator.status(uid, pid)
    if st.get("phase") != "done":
        log(f"run paused ({st.get('phase')}) - resume from Projects when ready")
        return
    if getattr(settings, "auto_promote", True):
        try:
            orchestrator.apply_seo(cfg, uid, pid, log=log)
            orchestrator.build_promo_pack(cfg, uid, pid, log=log)
        except Exception as e:  # noqa: BLE001
            log(f"[promote] skipped ({type(e).__name__})")
    for fn in ("export_md", "export_html"):
        try:
            getattr(orchestrator, fn)(uid, pid, log=log)
        except Exception as e:  # noqa: BLE001 - export deps may be missing
            log(f"[export] {fn[7:]} failed ({type(e).__name__})")


def _job_start(job: Job, payload: dict) -> None:
    """Create a project from a picked approach and run it end-to-end."""
    from .. import api, orchestrator
    from .. import schemas as S
    uid = payload.get("user") or _uid()
    mode = payload.get("mode") or load_settings().mode
    log = _job_log(job, uid)
    # Per-piece overrides from the Studio form (voice + SEO keyword) - applied to THIS run's
    # settings only, so a specific piece can differ from the global defaults. Whitelisted.
    _PIECE = {"register", "field", "citation_style", "persona", "emotion", "seo_keyword"}
    overrides = {k: v for k, v in (payload.get("overrides") or {}).items()
                 if k in _PIECE and isinstance(v, str) and v.strip()}
    if overrides:
        log("overrides for this piece: " + ", ".join(f"{k}={v}" for k, v in overrides.items()))
    agent = api.Agent(user=uid, **overrides)
    raw = payload.get("approach") or {}
    schema = S.ArticleAngle if mode == "article" else S.Direction
    approach = api.Approach(index=1, title=raw.get("title", ""),
                            summary=raw.get("angle", raw.get("premise", "")),
                            raw=schema(**raw))
    log(f"creating {mode} from angle: {approach.title!r}...")
    project = agent.create(
        payload.get("topic", ""), mode=mode, approach=approach,
        units=int(payload["units"]) if payload.get("units") else None,
        requirements=(payload.get("intake") or "").strip() or None,
        author=(payload.get("author") or "").strip() or None,
        autonomous=True)
    job.project = project.id
    job.emit({"t": "project", "project": project.id})
    log(f"project '{project.id}' created - running...")
    cfg, settings = load_config(), load_settings()
    orchestrator.run(cfg, uid, project.id, log=log, control=job.control)
    _finish_piece(job, cfg, settings, uid, project.id, log)


def _job_resume(job: Job, payload: dict) -> None:
    from .. import orchestrator
    uid = payload.get("user") or _uid()
    pid = job.project
    log = _job_log(job, uid)
    cfg, settings = load_config(), load_settings()
    orchestrator.run(cfg, uid, pid, log=log, control=job.control,
                     force=bool(payload.get("force")))
    _finish_piece(job, cfg, settings, uid, pid, log)


def _job_action(job: Job, payload: dict) -> None:
    """One-off project actions that may take LLM time: evaluate/seo/promote/
    evidence/tableread/export/polish."""
    from .. import orchestrator
    uid = payload.get("user") or _uid()
    pid, action = job.project, payload.get("action")
    log = _job_log(job, uid)
    cfg, settings = load_config(), load_settings()
    if action == "evaluate":
        r = orchestrator.evaluate_project(cfg, uid, pid, log=log)
        job.emit({"t": "result", "scores": r["scores"], "metrics": r["metrics"],
                  "summary": r["summary"]})
    elif action == "seo":
        orchestrator.apply_seo(cfg, uid, pid,
                               keyword=payload.get("keyword", ""), log=log)
    elif action == "promote":
        orchestrator.build_promo_pack(cfg, uid, pid,
                                      formats=payload.get("formats"), log=log)
    elif action == "evidence":
        orchestrator.build_evidence_report(uid, pid, log=log)
    elif action == "tableread":
        orchestrator.run_table_read(cfg, uid, pid,
                                    persona=payload.get("persona"), log=log)
    elif action == "restyle":
        out = orchestrator.build_restyle(cfg, uid, pid, register=payload.get("register", ""),
                                         persona=payload.get("persona", ""),
                                         emotion=payload.get("emotion", ""), log=log)
        job.emit({"t": "result", "path": str(out) if out else ""})
    elif action == "polish":
        orchestrator.repolish_manuscript(uid, pid, settings, log=log)
    elif action == "export":
        fmt = payload.get("format", "md")
        fn = {"pdf": "export_pdf", "epub": "export_epub", "html": "export_html",
              "docx": "export_docx", "txt": "export_txt", "md": "export_md"}.get(fmt)
        if not fn:
            raise ValueError(f"unknown export format '{fmt}'")
        out = getattr(orchestrator, fn)(uid, pid, log=log)
        job.emit({"t": "result", "path": str(out)})
    else:
        raise ValueError(f"unknown action '{action}'")


# ── HTTP layer ─────────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    server_version = "WritingAgentWeb/1.0"
    protocol_version = "HTTP/1.1"

    # -- plumbing ---------------------------------------------------------------
    def log_message(self, fmt, *args):  # quiet the default stderr access log
        pass

    def _json(self, obj, status: int = 200) -> None:
        data = json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _err(self, msg: str, status: int = 400) -> None:
        self._json({"error": msg}, status)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except ValueError:
            return {}

    # -- GET --------------------------------------------------------------------
    def do_GET(self):  # noqa: N802 - http.server API
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        route = u.path
        try:
            if route in ("/", "/index.html"):
                return self._static("index.html", "text/html; charset=utf-8")
            if route.startswith("/static/"):
                return self._static_file(route[len("/static/"):])
            if route == "/api/state":
                return self._state()
            if route == "/api/project":
                return self._project(q)
            if route == "/api/artifact":
                return self._artifact(q)
            if route == "/api/trace":
                return self._json({"records": _trace_records(
                    q.get("user") or _uid(), q.get("project", ""))})
            if route == "/api/rejected":
                return self._rejected(q)
            if route == "/api/evals":
                return self._json(_evals(q.get("user") or _uid(), q.get("project", "")))
            if route == "/api/telemetry":
                return self._telemetry(q)
            if route == "/api/memory":
                return self._json(_memory(q.get("user") or _uid()))
            if route == "/api/keys":
                return self._json(_keys_payload())
            if route == "/api/share":
                return self._share(q)
            if route == "/api/events":
                return self._events(q)
            return self._err("not found", 404)
        except BrokenPipeError:
            pass
        except Exception as e:  # noqa: BLE001 - one bad request must not kill the server
            try:
                self._err(f"{type(e).__name__}: {e}", 500)
            except Exception:  # noqa: BLE001
                pass

    def _static(self, name: str, ctype: str) -> None:
        p = _STATIC / name
        data = p.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    _STATIC_TYPES = {".woff2": "font/woff2", ".css": "text/css; charset=utf-8",
                     ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml",
                     ".png": "image/png", ".ico": "image/x-icon"}

    def _static_file(self, rel: str) -> None:
        """Serve a whitelisted asset from the static dir (fonts/css/js only).
        Path-traversal guarded: the resolved file must stay inside _STATIC and
        carry a known asset suffix - the server is not a file browser."""
        p = (_STATIC / rel).resolve()
        try:
            p.relative_to(_STATIC.resolve())
        except ValueError:
            return self._err("forbidden", 403)
        if not p.is_file() or p.suffix not in self._STATIC_TYPES:
            return self._err("not found", 404)
        data = p.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", self._STATIC_TYPES[p.suffix])
        self.send_header("Content-Length", str(len(data)))
        # Assets are content-stable for a session; fonts especially benefit from caching.
        self.send_header("Cache-Control", "public, max-age=86400")
        self.end_headers()
        self.wfile.write(data)

    def _state(self) -> None:
        s = load_settings()
        cfg = load_config()
        active = _jobs.active()
        self._json({
            "user": s.default_user,
            "theme": s.theme,
            "themes": _themes(),
            "options": _options(),
            "settings": _settings_payload(s),
            "models": {"default": cfg.default, "fallback": cfg.fallback,
                       "nodes": cfg.to_dict()["nodes"]},
            "projects": _project_overview(s.default_user),
            "active_job": ({"id": active.id, "kind": active.kind,
                            "project": active.project} if active else None),
            "jobs": [{"id": j.id, "kind": j.kind, "project": j.project,
                      "status": j.status} for j in _jobs.jobs.values()],
        })

    def _project(self, q: dict) -> None:
        from .. import orchestrator
        uid, pid = q.get("user") or _uid(), q.get("project", "")
        p = _paths(uid, pid)
        if not p.run_state.exists() and not (p.root / "plan.json").exists():
            return self._err(f"no project '{pid}'", 404)
        state = brain.read_json(p.run_state) or {}
        self._json({
            "id": pid,
            "title": _title(p.root),
            "status": orchestrator.status(uid, pid),
            "state": state,
            "artifacts": _artifact_list(p.root),
            "has_trace": bool(_trace_records(uid, pid)),
        })

    def _artifact(self, q: dict) -> None:
        uid, pid = q.get("user") or _uid(), q.get("project", "")
        path = _artifact_path(_paths(uid, pid).root, q.get("name", ""))
        if not path:
            return self._err("unknown artifact", 404)
        if path.suffix.lower() in _ART_RASTER:
            # Binary image: read_text would crash. Hand the SPA an <img> data-URI it can
            # inject as-is (same code path as an inline SVG), so raster dropped-figures render.
            import base64
            import mimetypes
            media = mimetypes.guess_type(path.name)[0] or "image/png"
            b64 = base64.b64encode(path.read_bytes()).decode()
            text = (f'<img src="data:{media};base64,{b64}" '
                    f'style="max-width:100%;height:auto" alt="{path.name}">')
            return self._json({"name": q.get("name"), "text": text})
        self._json({"name": q.get("name"), "text": path.read_text(encoding="utf-8")})

    def _share(self, q: dict) -> None:
        """Platform-ready copy of the finished piece. medium/substack: a self-contained HTML
        body (images + diagrams inlined) to paste into a draft with formatting intact. x: the
        promo X-thread as plain text (needs a Promote pass first)."""
        uid, pid = q.get("user") or _uid(), q.get("project", "")
        target = (q.get("target") or "medium").lower()
        p = _paths(uid, pid)
        title = pid
        src = getattr(p, "outline_json", None) or getattr(p, "book_plan", None)
        if src is not None and src.exists():
            title = (brain.read_json(src) or {}).get("title") or pid
        if target == "x":
            xt = brain.read_text(p.root / "promo" / "x-thread.md") or ""
            if not xt.strip():
                return self._json({"target": "x", "missing": True,
                                   "hint": "Run Promote to generate the X thread first."})
            return self._json({"target": "x", "title": title, "text": _plain_x_thread(xt)})
        md = brain.read_text(p.manuscript) or ""
        if not md.strip():
            return self._err("no manuscript yet — finish the run first", 404)
        from .. import export
        html = export.markdown_to_share_html(md, base_dir=str(p.root))
        self._json({"target": target, "title": title, "html": html, "text": md})

    def _rejected(self, q: dict) -> None:
        """Dropped/unused artifacts for review (plan §26): recorded rejects (unused images)
        plus the draft-variant snapshots under versions/ that weren't the committed final."""
        from ..orchestrator.common import read_rejected
        uid, pid = q.get("user") or _uid(), q.get("project", "")
        p = _paths(uid, pid)
        versions = []
        vdir = p.root / "versions"
        if vdir.exists():
            versions = sorted(f.name for f in vdir.glob("*.md"))
        imgs = []
        idir = p.root / "images"
        if idir.exists():
            ms = brain.read_text(p.manuscript) or ""
            for f in sorted(idir.glob("*")):
                if f.name not in ms:                     # generated but not in the final piece
                    imgs.append(f"images/{f.name}")
        self._json({"records": read_rejected(p), "versions": versions, "unused_images": imgs})

    def _telemetry(self, q: dict) -> None:
        project = q.get("project") or None
        run_id = q.get("run_id") or None
        recs = telemetry.load_records(project)
        if run_id:
            recs = [r for r in recs if r.get("run_id") == run_id]
        self._json({"summary": telemetry.summarize(project, run_id),
                    "records": recs[-_RECORDS_CAP:]})

    def _events(self, q: dict) -> None:
        """SSE: replay the job's buffered events, then stream live ones."""
        job = _jobs.jobs.get(q.get("job", ""))
        if not job:
            return self._err("unknown job", 404)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        # SSE has no Content-Length: the stream is delimited by connection close,
        # so keep-alive must be off or clients block forever after the last event.
        self.send_header("Connection", "close")
        self.close_connection = True
        self.end_headers()
        i = 0
        while True:
            with job.cond:
                while i >= len(job.events) and job.status == "running":
                    job.cond.wait(timeout=15.0)
                    if i >= len(job.events):     # keep-alive comment on idle
                        try:
                            self.wfile.write(b": ping\n\n")
                            self.wfile.flush()
                        except (BrokenPipeError, ConnectionError, OSError):
                            return
                batch = job.events[i:]
                i = len(job.events)
            for ev in batch:
                try:
                    self.wfile.write(f"data: {json.dumps(ev, default=str)}\n\n".encode())
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionError, OSError):
                    return
            if job.status != "running" and i >= len(job.events):
                return

    # -- POST -------------------------------------------------------------------
    def do_POST(self):  # noqa: N802 - http.server API
        route = urlparse(self.path).path
        body = self._body()
        try:
            if route == "/api/plan":
                return self._plan(body)
            if route == "/api/start":
                return self._start_job("start", None, _job_start, body)
            if route == "/api/resume":
                return self._start_job("run", body.get("project"), _job_resume, body)
            if route == "/api/action":
                return self._start_job(body.get("action", "action"),
                                       body.get("project"), _job_action, body)
            if route == "/api/pause":
                return self._pause(body)
            if route == "/api/review":
                return self._review(body)
            if route == "/api/settings":
                s = _apply_setting(body.get("field", ""), body.get("value"))
                return self._json({"ok": True, "settings": _settings_payload(s)})
            if route == "/api/models":
                return self._models(body)
            if route == "/api/setkey":
                return self._setkey(body)
            if route == "/api/testkey":
                return self._testkey(body)
            if route == "/api/delete":
                return self._delete(body)
            if route == "/api/memory":
                return self._json(_memory_op(body.get("user") or _uid(), body))
            return self._err("not found", 404)
        except RuntimeError as e:       # job already running
            self._err(str(e), 409)
        except ValueError as e:         # a bad/rejected request (e.g. memory validation)
            self._err(str(e), 400)
        except Exception as e:  # noqa: BLE001
            self._err(f"{type(e).__name__}: {e}", 500)

    def _plan(self, body: dict) -> None:
        from .. import api
        agent = api.Agent(user=body.get("user") or _uid())
        approaches = agent.plan(body.get("topic", ""),
                                mode=body.get("mode") or None)
        self._json({"approaches": [
            {"index": a.index, "title": a.title, "summary": a.summary,
             "hook": a.hook, "audience": a.audience, "tone": a.tone,
             "raw": a.raw.model_dump()} for a in approaches]})

    def _start_job(self, kind: str, project: str | None, fn, body: dict) -> None:
        job = _jobs.start(kind, project, lambda j: fn(j, body))
        self._json({"job": job.id, "kind": kind, "project": project})

    def _pause(self, body: dict) -> None:
        job = _jobs.jobs.get(body.get("job", ""))
        if not job:
            return self._err("unknown job", 404)
        job.control.pause = True
        self._json({"ok": True})

    def _review(self, body: dict) -> None:
        from .. import orchestrator
        orchestrator.record_instruction(
            body.get("user") or _uid(), body.get("project", ""),
            int(body.get("unit", 0)), body.get("instruction", ""))
        self._json({"ok": True})

    def _models(self, body: dict) -> None:
        cfg = load_config()
        node, slug = body.get("node", ""), (body.get("slug") or "").strip()
        if not slug:
            return self._err("missing model slug")
        if node == "default":
            cfg.set_default(slug)
        elif node == "all":
            cfg.set_all(slug)
        else:
            cfg.set_node(node, slug)
        save_config(cfg)
        self._json({"ok": True, "models": cfg.to_dict()})

    def _setkey(self, body: dict) -> None:
        """Write an API key to .env in the agent home (shared with the TUI). Only known key
        env vars are accepted - no arbitrary environment writes from the browser."""
        env = (body.get("env") or "").strip()
        val = (body.get("value") or "").strip()
        if env not in _key_envs():
            return self._err(f"unknown key variable '{env}'", 400)
        if not val:
            return self._err("empty key", 400)
        from ..shell.branding import _write_env_key
        path = _write_env_key(env, val)   # sets it live AND persists to .env when writable
        self._json({"ok": True, "env": env, "masked": _mask(val), "persisted": bool(path)})

    def _testkey(self, body: dict) -> None:
        """Verify a key with a real, cheap probe: a free /models list for a model host, a
        1-result live search for a search provider. Returns {ok, detail} - never raises."""
        import os
        kind, pid = body.get("kind", ""), body.get("id", "")
        try:
            if kind == "search":
                from .. import search
                b = search._BACKENDS.get(pid)
                if not b:
                    return self._json({"ok": False, "detail": "unknown search provider"})
                if not os.getenv(b.key_env):
                    return self._json({"ok": False, "detail": "no key set"})
                res = b.fn("connectivity test", 1)
                return self._json({"ok": True, "detail": f"reached it - {len(res)} result(s)"})
            if kind == "image":
                from .. import images
                ib = images._IMG_BACKENDS.get(pid)
                if not ib:
                    return self._json({"ok": False, "detail": "unknown image source"})
                if ib.key_env and not os.getenv(ib.key_env):
                    return self._json({"ok": False, "detail": "no key set"})
                res = images.fetch_source(pid, "landscape", 1)
                return self._json({"ok": True, "detail": f"reached it - {len(res)} image(s)"})
            from openai import OpenAI

            from .. import providers
            p = providers.REGISTRY.get(providers.resolve(pid))
            if p is None:
                return self._json({"ok": False, "detail": "unknown host"})
            key = providers.api_key_for(p)
            if key is None and not p.local:
                return self._json({"ok": False, "detail": "no key set"})
            client = OpenAI(base_url=providers.base_url_for(p), api_key=key or "not-needed",
                            default_headers=dict(getattr(p, "headers", {})) or None, timeout=15)
            client.models.list()   # 401 on a bad key; otherwise fine and free (no tokens)
            return self._json({"ok": True, "detail": "key accepted"})
        except Exception as e:  # noqa: BLE001 - a failed probe is a result, not a 500
            msg = str(e)
            hint = "bad key" if "401" in msg or "auth" in msg.lower() else "no /models probe (key may still be valid)" if "404" in msg else msg[:160]
            self._json({"ok": False, "detail": hint})

    def _delete(self, body: dict) -> None:
        from .. import orchestrator
        pid = body.get("project", "")
        if body.get("confirm") != pid:
            return self._err("confirm must equal the project id")
        orchestrator.delete_book(body.get("user") or _uid(), pid)
        self._json({"ok": True})


def _load_env() -> None:
    """Load API keys from the agent home's .env (and a dev-checkout .env in the CWD) into the
    process — the same thing the CLI does — so the dashboard picks up keys written by the Keys
    tab / setkey even when it's launched directly (not via the console script), and after a
    restart. No override: an already-set environment variable wins."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()                       # nearest .env from the CWD (dev checkouts)
    load_dotenv(brain.HOME / ".env")    # the agent home (written by setkey); no override


def serve(port: int = 8787, *, open_browser: bool = True, log=print) -> None:
    """Start the dashboard on 127.0.0.1:`port` (blocking). Ctrl-C to stop."""
    _load_env()                         # so real runs work with a key from .env, not just live
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    httpd.daemon_threads = True
    url = f"http://127.0.0.1:{httpd.server_address[1]}"
    log(f"Writing Agent web dashboard: {url}  (local only - Ctrl-C to stop)")
    if open_browser:
        import webbrowser
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log("\nstopped.")
    finally:
        httpd.server_close()


def make_server(port: int = 0) -> ThreadingHTTPServer:
    """A non-blocking server handle for tests (port 0 = ephemeral)."""
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    httpd.daemon_threads = True
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    # tests read the bound port from httpd.server_address; wait for readiness
    time.sleep(0.05)
    return httpd
