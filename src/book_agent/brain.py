"""The brain: multi-tenant, markdown-first filesystem layout (plan.md §3, §11)."""
from __future__ import annotations

import json
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
BRAIN = _ROOT / "brain"
INDEX_DIR = _ROOT / ".index"   # derived, gitignored


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "untitled"


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

    def ensure(self) -> "BookPaths":
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
    """Flat paths for one article — no subdirectories except images/."""

    def __init__(self, article_id: str, uid: str = "default"):
        self.uid = uid
        self.article_id = article_id
        self.root = user_dir(uid) / "articles" / article_id

    # core files (all at root — no subdirs)
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

    # per-section (flat, intermediate — cleaned up after assembly)
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

    def ensure(self) -> "ArticlePaths":
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


# ── IO helpers ───────────────────────────────────────────────────────────────
def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def append_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(content.rstrip() + "\n")


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def read_json(path: Path):
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8-sig")  # utf-8-sig strips BOM if present
    return json.loads(text)


def read_text(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.exists() else None
