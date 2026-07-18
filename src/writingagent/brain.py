"""The brain: multi-tenant, markdown-first filesystem layout (plan.md §3, §11)."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

from . import paths

# The agent home (see paths.py: $WRITINGAGENT_HOME override, else the OS user-data
# dir). HOME is re-exported module-level so shell/cli code and tests address it as
# brain.HOME; BRAIN/INDEX_DIR are patched separately in tests (derived at import).
HOME = paths.HOME
BRAIN = HOME / "brain"
INDEX_DIR = HOME / ".index"   # derived - safe to delete, rebuilt on demand

_SAFE_ID = re.compile(r"[a-z0-9][a-z0-9._-]*\Z")


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    # Non-ASCII titles can collapse to empty; fall back to a short stable hash so
    # two such projects don't all slug to "untitled" and overwrite each other.
    if not s:
        s = "untitled-" + hashlib.sha1(text.encode("utf-8")).hexdigest()[:6]
    return s


def is_safe_id(s: str) -> bool:
    """A project/user id that stays within the brain dir (no traversal, no abs path)."""
    return bool(s) and ".." not in s and _SAFE_ID.fullmatch(s) is not None


def _atomic_write(path: Path, text: str) -> None:
    """Write via a temp file + os.replace so a crash can't leave a truncated file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # suffix=".tmp" (not the real extension) so a leftover temp from a hard kill
    # can't be picked up by "*.md"/"*.json" globs elsewhere.
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)   # atomic on POSIX and Windows
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ── User scope ───────────────────────────────────────────────────────────────
def user_dir(uid: str = "default") -> Path:
    return BRAIN / "users" / uid


def ensure_user(uid: str = "default") -> Path:
    d = user_dir(uid)
    (d / "prefs").mkdir(parents=True, exist_ok=True)
    (d / "skills").mkdir(parents=True, exist_ok=True)
    return d


def user_profile(uid: str = "default") -> Path:
    return user_dir(uid) / "profile.md"


def skills_dir(uid: str = "default") -> Path:
    return user_dir(uid) / "skills"


def watch_list(uid: str = "default") -> Path:
    return user_dir(uid) / "prefs" / "watch_list.md"


def user_preferences(uid: str = "default") -> Path:
    """The reader's standing preferences: their own review/revise corrections, accumulated
    across every project (user scope, not per-piece). The learner distills these into
    skills + watch items, so the agent follows the user's stated tastes on the next run -
    the 'slowly becomes like the user' loop (plan §8, §11)."""
    return user_dir(uid) / "prefs" / "preferences.md"


_PREF_CAP = 30   # keep the newest N standing preferences; recurring ones reinforce and stay


def _parse_preferences(uid: str) -> list[list]:
    """Read preferences.md into [base_text, count] rows in on-disk (newest-first) order."""
    entries: list[list] = []
    for ln in (read_text(user_preferences(uid)) or "").splitlines():
        ln = ln.strip()
        if not ln.startswith("- "):
            continue
        body = ln[2:]
        # match both "×N" (what we write) and a legacy "(×N)" form
        m = re.search(r"\s+\(?×(\d+)\)?\s*$", body)
        cnt = int(m.group(1)) if m else 1
        base = (body[: m.start()] if m else body).strip()
        if base:
            entries.append([base, cnt])
    return entries


def _write_preferences(uid: str, entries: list[list]) -> None:
    out = "\n".join(f"- {b}" + (f"  ×{c}" if c > 1 else "") for b, c in entries)
    _atomic_write(user_preferences(uid), (out + "\n") if out else "")


def record_preference(uid: str = "default", text: str = "") -> None:
    """Durably record one user correction. A repeat of the same guidance increments its
    count (reinforcement) and moves it to the front; the list is capped newest-first.
    Best-effort - a learning breadcrumb must never break the caller."""
    text = " ".join((text or "").split()).strip()
    if not text:
        return
    try:
        ensure_user(uid)
        entries = _parse_preferences(uid)
        key = text.lower()
        hit = next((e for e in entries if e[0].lower() == key), None)
        if hit:
            hit[1] += 1
            entries.remove(hit)
            entries.insert(0, hit)          # reinforce + surface
        else:
            entries.insert(0, [text, 1])
        _write_preferences(uid, entries[:_PREF_CAP])
    except Exception:  # noqa: BLE001 - never let a learning write break a run
        pass


def user_preferences_text(uid: str = "default") -> str:
    """The standing-preferences block (empty string when none), for the learner."""
    return (read_text(user_preferences(uid)) or "").strip()


def list_preferences(uid: str = "default") -> list[dict]:
    """The standing preferences as structured rows, for the Memory UI."""
    return [{"text": b, "count": c} for b, c in _parse_preferences(uid)]


def delete_preference(uid: str = "default", text: str = "") -> bool:
    """Drop one standing preference by its text (case-insensitive). Returns True if removed."""
    key = " ".join((text or "").split()).strip().lower()
    if not key:
        return False
    entries = _parse_preferences(uid)
    kept = [e for e in entries if e[0].lower() != key]
    if len(kept) == len(entries):
        return False
    _write_preferences(uid, kept)
    return True


def voice_dir(uid: str = "default") -> Path:
    """Admired writing samples: user-dropped .md/.txt files plus /praise'd passages.
    Injected into writer calls as register to MATCH (showing voice beats describing
    it) and read by the learner as positive exemplars."""
    return user_dir(uid) / "voice"


def voice_exemplars(uid: str = "default", max_chars: int = 2400) -> str | None:
    """Assemble exemplar paragraphs from voice_dir under a character budget.

    Takes leading prose paragraphs (skipping headings and code fences) from each
    file in name order until the budget is spent, so users control priority by
    file naming. Returns None when there are no exemplars.
    """
    d = voice_dir(uid)
    if not d.exists():
        return None
    chunks: list[str] = []
    total = 0
    for p in sorted(list(d.glob("*.md")) + list(d.glob("*.txt"))):
        text = read_text(p) or ""
        for para in re.split(r"\n\s*\n", text):
            para = para.strip()
            if not para or para.startswith("#") or para.startswith("```"):
                continue
            if total + len(para) > max_chars:
                break
            chunks.append(para)
            total += len(para)
        if total >= max_chars:
            break
    return "\n\n".join(chunks) or None


def style_exemplars(uid: str = "default", register: str | None = None,
                    max_chars: int = 2400) -> str | None:
    """The writer's 'match this' style anchor: the user's own voice exemplars if any exist,
    otherwise the register's shipped gold corpus (registers.gold_exemplars). A default anchor
    matters most on a basic model - showing a target paragraph beats describing the voice in
    adjectives. Returns None only when there are neither user nor gold exemplars."""
    user = voice_exemplars(uid, max_chars=max_chars)
    if user:
        return user
    from . import registers
    return registers.gold_exemplars(register, max_chars=min(max_chars, 1200))


def list_voice(uid: str = "default") -> list[dict]:
    """The voice exemplar files as {name, chars, text} rows, for the Memory UI."""
    d = voice_dir(uid)
    if not d.exists():
        return []
    rows = []
    for p in sorted(list(d.glob("*.md")) + list(d.glob("*.txt"))):
        text = read_text(p) or ""
        rows.append({"name": p.name, "chars": len(text), "text": text})
    return rows


def add_voice_exemplar(uid: str = "default", title: str = "", text: str = "") -> str | None:
    """Save a pasted writing sample as a voice exemplar (a .md file the writer matches).
    The filename is slugified from the title (or a stable hash of the text). Returns the
    stored filename, or None when there's no text to save."""
    text = (text or "").strip()
    if not text:
        return None
    slug = slugify(title) if title.strip() else "sample-" + hashlib.sha1(text.encode("utf-8")).hexdigest()[:6]
    d = voice_dir(uid)
    d.mkdir(parents=True, exist_ok=True)
    name = f"{slug}.md"
    n = 2
    while (d / name).exists():          # never clobber an existing exemplar
        name = f"{slug}-{n}.md"
        n += 1
    body = (f"# {title.strip()}\n\n{text}" if title.strip() else text)
    _atomic_write(d / name, body.rstrip() + "\n")
    return name


def delete_voice_exemplar(uid: str = "default", name: str = "") -> bool:
    """Delete one voice exemplar by filename. Basename-only (no path traversal). Returns
    True if the file existed and was removed."""
    name = Path(name or "").name          # strip any directory components
    if not name or name.startswith("."):
        return False
    p = voice_dir(uid) / name
    if not p.exists():
        return False
    p.unlink(missing_ok=True)
    return True


# ── Book scope ───────────────────────────────────────────────────────────────
class BookPaths:
    """All paths for one book. The brain on disk is the source of truth."""

    def __init__(self, book_id: str, uid: str = "default"):
        self.uid = uid
        self.book_id = book_id
        self.root = user_dir(uid) / "books" / book_id

    # top-level
    @property
    def book_plan(self) -> Path: return self.root / "book_plan.md"
    @property
    def toc(self) -> Path: return self.root / "toc.md"
    @property
    def manuscript(self) -> Path: return self.root / "manuscript.md"
    @property
    def revision_log(self) -> Path: return self.root / "revision_log.md"
    @property
    def run_state(self) -> Path: return self.root / "run_state.json"
    @property
    def directions(self) -> Path: return self.root / "directions.json"
    @property
    def sources_json(self) -> Path: return self.root / "sources.json"
    # dirs
    @property
    def chapters(self) -> Path: return self.root / "chapters"
    @property
    def eval(self) -> Path: return self.root / "eval"
    @property
    def reviews(self) -> Path: return self.root / "reviews"
    @property
    def instructions(self) -> Path: return self.root / "instructions"
    @property
    def frontmatter(self) -> Path: return self.root / "frontmatter"
    @property
    def backmatter(self) -> Path: return self.root / "backmatter"
    @property
    def canon(self) -> Path: return self.root / "canon"
    @property
    def consolidation(self) -> Path: return self.root / "consolidation"
    # canon files
    @property
    def characters(self) -> Path: return self.canon / "characters"
    @property
    def world_rules(self) -> Path: return self.canon / "world_rules.md"
    @property
    def timeline(self) -> Path: return self.canon / "timeline.md"
    # derived index db (per book)
    @property
    def index_db(self) -> Path: return INDEX_DIR / f"{self.uid}__{self.book_id}.db"

    # per-chapter
    def ch(self, n: int) -> Path: return self.chapters / f"ch{n:02d}.md"
    def ch_draft(self, n: int) -> Path: return self.chapters / f"ch{n:02d}.draft.md"
    def ch_summary(self, n: int) -> Path: return self.chapters / f"ch{n:02d}.summary.md"
    def eval_of(self, n: int) -> Path: return self.eval / f"ch{n:02d}.json"
    def review_of(self, n: int) -> Path: return self.reviews / f"ch{n:02d}.md"
    def instruction_of(self, n: int) -> Path: return self.instructions / f"ch{n:02d}.md"

    def ensure(self) -> BookPaths:
        for d in (self.chapters, self.eval, self.reviews, self.instructions,
                  self.frontmatter, self.backmatter, self.characters,
                  self.consolidation):
            d.mkdir(parents=True, exist_ok=True)
        INDEX_DIR.mkdir(parents=True, exist_ok=True)
        return self


def list_books(uid: str = "default") -> list[str]:
    base = user_dir(uid) / "books"
    if not base.exists():
        return []
    return sorted(p.name for p in base.iterdir() if p.is_dir())


# ── Article scope ─────────────────────────────────────────────────────────────
class ArticlePaths:
    """Flat paths for one article - no subdirectories except images/."""

    def __init__(self, article_id: str, uid: str = "default"):
        self.uid = uid
        self.article_id = article_id
        self.root = user_dir(uid) / "articles" / article_id

    # core files (all at root - no subdirs)
    @property
    def run_state(self) -> Path: return self.root / "run_state.json"
    @property
    def outline_json(self) -> Path: return self.root / "outline.json"
    @property
    def outline_md(self) -> Path: return self.root / "outline.md"
    @property
    def angle_json(self) -> Path: return self.root / "article_angle.json"
    @property
    def sources_json(self) -> Path: return self.root / "sources.json"
    @property
    def revision_log(self) -> Path: return self.root / "revision_log.md"
    @property
    def manuscript(self) -> Path: return self.root / "manuscript.md"
    @property
    def images(self) -> Path: return self.root / "images"

    # per-section (flat, intermediate - cleaned up after assembly)
    def section(self, n: int) -> Path: return self.root / f"section_{n:02d}.md"
    def section_summary(self, n: int) -> Path: return self.root / f"section_{n:02d}.summary.md"
    def section_eval(self, n: int) -> Path: return self.root / f"eval_{n:02d}.json"
    def section_draft(self, n: int) -> Path: return self.root / f"draft_{n:02d}.md"
    def instruction_of(self, n: int) -> Path: return self.root / f"instruction_{n:02d}.md"
    def review_of(self, n: int) -> Path: return self.root / f"review_{n:02d}.md"

    # BookPaths-compatible aliases so shared orchestrator helpers work unchanged
    def ch(self, n: int) -> Path: return self.section(n)
    def ch_draft(self, n: int) -> Path: return self.section_draft(n)
    def ch_summary(self, n: int) -> Path: return self.section_summary(n)
    def eval_of(self, n: int) -> Path: return self.section_eval(n)

    @property
    def index_db(self) -> Path:
        return INDEX_DIR / f"{self.uid}__{self.article_id}.db"

    def ensure(self) -> ArticlePaths:
        self.root.mkdir(parents=True, exist_ok=True)
        self.images.mkdir(parents=True, exist_ok=True)
        INDEX_DIR.mkdir(parents=True, exist_ok=True)
        return self

    def cleanup_sections(self) -> None:
        """Remove intermediate section/eval/draft files once manuscript is assembled."""
        for pattern in ("section_*.md", "eval_*.json", "draft_*.md"):
            for f in self.root.glob(pattern):
                f.unlink(missing_ok=True)


def list_articles(uid: str = "default") -> list[str]:
    base = user_dir(uid) / "articles"
    if not base.exists():
        return []
    return sorted(p.name for p in base.iterdir() if p.is_dir())


def project_root(uid: str, project_id: str) -> Path:
    """The brain working dir for a project - article scope if it has run_state, else book."""
    art = user_dir(uid) / "articles" / project_id
    if (art / "run_state.json").exists():
        return art
    return user_dir(uid) / "books" / project_id


# ── Export save location (where rendered deliverables land; see /path) ─────────
# The rendered files an export produces. NOT the brain's `manuscript.md` source -
# that and every other working file stay in the project root; only these move.
# format -> the on-disk deliverable filename. Single source for the export writers AND the
# "refresh whatever deliverables exist" logic (cli/export.py) so the two can't drift.
EXPORT_DELIVERABLE_BY_FORMAT = {
    "pdf": "manuscript.pdf", "epub": "manuscript.epub", "html": "manuscript.html",
    "docx": "manuscript.docx", "txt": "manuscript.txt", "md": "manuscript_export.md",
}
EXPORT_DELIVERABLES = tuple(EXPORT_DELIVERABLE_BY_FORMAT.values())
_EXPORT_DIR_SIDECAR = "export_dir.txt"   # one line: the per-project save folder


def get_project_export_dir(uid: str, project_id: str) -> str | None:
    """The per-project save-folder override, or None if unset."""
    f = project_root(uid, project_id) / _EXPORT_DIR_SIDECAR
    try:
        val = f.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return val or None


def set_project_export_dir(uid: str, project_id: str, path: str | None) -> None:
    """Set (or clear, with falsy `path`) a project's save-folder override."""
    f = project_root(uid, project_id) / _EXPORT_DIR_SIDECAR
    if path and path.strip():
        _atomic_write(f, path.strip())
    else:
        f.unlink(missing_ok=True)


def resolve_export_dir(uid: str, project_id: str) -> Path:
    """Where rendered exports for this project are written, and ensured to exist.

    Priority: per-project override (sidecar) > global default `settings.export_dir`
    namespaced by project id > the project's own brain root (the original behaviour).
    An unwritable target falls back to the brain root so an export never crashes."""
    root = project_root(uid, project_id)
    override = get_project_export_dir(uid, project_id)
    if override:
        target = Path(override).expanduser()
    else:
        base = ""
        try:                       # lazy: avoid an import cycle and import-time cost
            from .config import load_settings
            base = (load_settings().export_dir or "").strip()
        except Exception:
            base = ""
        target = (Path(base).expanduser() / project_id) if base else root
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError:
        return root
    return target


def move_exports(old_dir, new_dir) -> list[str]:
    """Move existing rendered deliverables from old_dir to new_dir. Returns the
    basenames moved (empty if the dirs are the same or nothing was there)."""
    old_dir, new_dir = Path(old_dir), Path(new_dir)
    if old_dir.resolve() == new_dir.resolve():
        return []
    new_dir.mkdir(parents=True, exist_ok=True)
    moved: list[str] = []
    for name in EXPORT_DELIVERABLES:
        src = old_dir / name
        if src.exists():
            dst = new_dir / name
            dst.unlink(missing_ok=True)   # overwrite a stale copy at the destination
            shutil.move(str(src), str(dst))
            moved.append(name)
    return moved


def list_projects(uid: str = "default") -> list[tuple[str, str]]:
    """Return [(id, type)] for all books and articles, sorted by id.

    Type comes from run_state.json 'mode' field when present, so a project
    created in article mode but stored under books/ shows as 'article'.
    """
    items: list[tuple[str, str]] = []
    for bid in list_books(uid):
        rs = read_json(BookPaths(bid, uid).run_state)
        ptype = (rs.get("mode") or "book") if rs else "book"
        items.append((bid, ptype))
    for aid in list_articles(uid):
        rs = read_json(user_dir(uid) / "articles" / aid / "run_state.json")
        ptype = (rs.get("mode") or "article") if rs else "article"
        items.append((aid, ptype))
    return sorted(items, key=lambda x: x[0])


# ── Fuzzy project lookup (slugs are long; users type excerpts) ─────────────────
def _project_match_score(query: str, qtokens: list[str], pid: str) -> float:
    """Heuristic match in [0,1] between a (lowercased) query and a project id."""
    import difflib
    pl = pid.lower()
    ptoks = [t for t in pl.split("-") if t]
    if pl == query:
        return 1.0
    qhyph = "-".join(qtokens)
    if qhyph and qhyph in pl:                          # a contiguous slug fragment
        return 0.9 + 0.1 * (len(qhyph) / len(pl))
    if qtokens and query.replace(" ", "") in pl.replace("-", ""):
        return 0.86                                    # fragment ignoring separators
    if qtokens and all(any(qt in pt for pt in ptoks) for qt in qtokens):
        return 0.78                                    # every query word lands in some id word
    overlap = (len(set(qtokens) & set(ptoks)) / len(qtokens)) if qtokens else 0.0
    # per-token typo tolerance: average best fuzzy match of each query word to an
    # id word ("voicebott"->"voicebot"), which a whole-slug ratio washes out.
    if qtokens and ptoks:
        tok_fuzzy = sum(max(difflib.SequenceMatcher(None, qt, pt).ratio() for pt in ptoks)
                        for qt in qtokens) / len(qtokens)
    else:
        tok_fuzzy = 0.0
    ratio = difflib.SequenceMatcher(None, query, pl).ratio()
    return max(overlap * 0.75, ratio * 0.6, tok_fuzzy * 0.9)


def match_projects(uid: str, query: str, limit: int = 8) -> list[tuple[str, str, float]]:
    """Rank a user's projects by how well each matches `query`, best first.
    Returns [(id, type, score)] - tolerant of excerpts, typos, and word order."""
    q = (query or "").strip().lower()
    qtokens = [t for t in re.split(r"[^a-z0-9]+", q) if t]
    scored = [(pid, ptype, _project_match_score(q, qtokens, pid))
              for pid, ptype in list_projects(uid)]
    scored.sort(key=lambda x: (x[2], -len(x[0])), reverse=True)
    return scored[:limit]


def resolve_project(uid: str, query: str, *, threshold: float = 0.5) -> tuple[str | None, list[str]]:
    """Smart project resolution. Returns (resolved_id, candidates):

    - `resolved_id` when one match is confident (exact id, a clear fragment, or a
      sole plausible hit) - so `/use voicebot` lands the right project;
    - else `candidates` = ranked plausible ids for the caller to offer as options;
    - `(None, [])` when nothing is close enough.
    """
    scored = match_projects(uid, query)
    if not scored:
        return None, []
    if scored[0][2] >= 0.999:                          # exact id always wins
        return scored[0][0], []
    cands = [(pid, s) for pid, _t, s in scored if s >= threshold]
    if not cands:
        return None, []
    if len(cands) == 1:
        return cands[0][0], []
    # A clear leader (strong, and well ahead of the runner-up) resolves outright;
    # otherwise hand back the close field as options to choose from.
    if cands[0][1] >= 0.8 and cands[0][1] - cands[1][1] >= 0.12:
        return cands[0][0], []
    return None, [pid for pid, _s in cands[:8]]


# ── IO helpers ───────────────────────────────────────────────────────────────
def write_text(path: Path, content: str) -> None:
    _atomic_write(path, content.rstrip() + "\n")


def append_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(content.rstrip() + "\n")


def write_json(path: Path, data) -> None:
    _atomic_write(path, json.dumps(data, indent=2, ensure_ascii=False))


def read_json(path: Path):
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8-sig")  # utf-8-sig strips BOM if present
        return json.loads(text)
    except (json.JSONDecodeError, OSError, ValueError):
        # A truncated/corrupt file (e.g. a crash mid-write before atomic writes
        # existed) is treated as absent rather than crashing every caller.
        return None


def read_text(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.exists() else None
