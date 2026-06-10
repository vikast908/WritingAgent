"""Per-book SQLite store: derived FTS index + canonical state + entity graph.

Honors the GBrain pattern in spirit (one queryable store synced from / rendered to
markdown). v1 simplification: structured canon lives here and is *rendered* to markdown
pages under canon/; full markdown-as-source-of-truth-with-sync is a later refinement
(noted in plan.md §3.2). The DB file is derived and gitignored (.index/).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from . import brain
from .brain import BookPaths
from .schemas import ExtractionResult

_SCHEMA = """
CREATE TABLE IF NOT EXISTS character (name TEXT PRIMARY KEY, status TEXT);
CREATE TABLE IF NOT EXISTS character_fact (name TEXT, fact TEXT, chapter INT,
    UNIQUE(name, fact));
CREATE TABLE IF NOT EXISTS character_voice (name TEXT, note TEXT, UNIQUE(name, note));
CREATE TABLE IF NOT EXISTS timeline (chapter INT, event TEXT, UNIQUE(chapter, event));
CREATE TABLE IF NOT EXISTS world_rule (rule TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS thread (name TEXT PRIMARY KEY, status TEXT);
CREATE TABLE IF NOT EXISTS gnode (type TEXT, name TEXT, UNIQUE(type, name));
CREATE TABLE IF NOT EXISTS gedge (src TEXT, rel TEXT, dst TEXT, chapter INT,
    UNIQUE(src, rel, dst, chapter));
"""


class Store:
    def __init__(self, conn: sqlite3.Connection, fts: bool):
        self.conn = conn
        self.fts = fts

    # ── lifecycle ────────────────────────────────────────────────────────────
    @classmethod
    def open(cls, paths: BookPaths) -> "Store":
        paths.index_db.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(paths.index_db))
        conn.executescript(_SCHEMA)
        fts = True
        try:
            conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS docs USING fts5(kind, ref, body)"
            )
        except sqlite3.OperationalError:
            fts = False
            conn.execute(
                "CREATE TABLE IF NOT EXISTS docs (kind TEXT, ref TEXT, body TEXT)"
            )
        conn.commit()
        return cls(conn, fts)

    def close(self) -> None:
        self.conn.commit()
        self.conn.close()

    # ── full-text index over committed chapters + summaries ──────────────────
    def index_documents(self, paths: BookPaths) -> None:
        c = self.conn
        c.execute("DELETE FROM docs")
        for p in sorted(paths.chapters.glob("ch*.md")):
            if p.name.endswith(".draft.md"):
                continue
            kind = "summary" if p.name.endswith(".summary.md") else "chapter"
            c.execute("INSERT INTO docs (kind, ref, body) VALUES (?,?,?)",
                      (kind, p.stem, p.read_text(encoding="utf-8")))
        c.commit()

    def search(self, query: str, limit: int = 5) -> list[tuple[str, str]]:
        c = self.conn
        if self.fts:
            # Wrap as a quoted FTS5 phrase so punctuation (", *, :, -, AND/OR) in the
            # query can't trigger an fts5 syntax error; fall back to LIKE if it still does.
            phrase = '"' + query.replace('"', '""') + '"'
            try:
                rows = c.execute(
                    "SELECT ref, kind FROM docs WHERE docs MATCH ? LIMIT ?",
                    (phrase, limit),
                ).fetchall()
            except sqlite3.OperationalError:
                rows = c.execute(
                    "SELECT ref, kind FROM docs WHERE body LIKE ? LIMIT ?",
                    (f"%{query}%", limit),
                ).fetchall()
        else:
            rows = c.execute(
                "SELECT ref, kind FROM docs WHERE body LIKE ? LIMIT ?",
                (f"%{query}%", limit),
            ).fetchall()
        return [(r[0], r[1]) for r in rows]

    # ── canon updates (from extraction on commit) ────────────────────────────
    def update_from_extraction(self, chapter: int, ex: ExtractionResult) -> None:
        c = self.conn
        for ch in ex.characters:
            if ch.status:
                c.execute(
                    "INSERT INTO character (name, status) VALUES (?,?) "
                    "ON CONFLICT(name) DO UPDATE SET status=excluded.status",
                    (ch.name, ch.status),
                )
            else:
                c.execute("INSERT OR IGNORE INTO character (name, status) VALUES (?, '')",
                          (ch.name,))
            for fact in ch.new_facts:
                c.execute("INSERT OR IGNORE INTO character_fact VALUES (?,?,?)",
                          (ch.name, fact, chapter))
            for note in ch.voice_notes:
                c.execute("INSERT OR IGNORE INTO character_voice VALUES (?,?)",
                          (ch.name, note))
            self._node("character", ch.name)
            self._edge(ch.name, "appears_in", f"ch{chapter:02d}", chapter)
        for loc in ex.locations:
            self._node("location", loc)
        for rule in ex.world_rules:
            c.execute("INSERT OR IGNORE INTO world_rule VALUES (?)", (rule,))
        for ev in ex.timeline:
            c.execute("INSERT OR IGNORE INTO timeline VALUES (?,?)", (ev.chapter, ev.event))
        for th in ex.threads_touched:
            c.execute("INSERT OR IGNORE INTO thread (name, status) VALUES (?, 'open')", (th,))
            self._edge(f"ch{chapter:02d}", "advances", th, chapter)
        c.commit()

    def _node(self, type_: str, name: str) -> None:
        self.conn.execute("INSERT OR IGNORE INTO gnode VALUES (?,?)", (type_, name))

    def _edge(self, src: str, rel: str, dst: str, chapter: int) -> None:
        self.conn.execute("INSERT OR IGNORE INTO gedge VALUES (?,?,?,?)",
                          (src, rel, dst, chapter))

    # ── reads ────────────────────────────────────────────────────────────────
    def canon_context(self) -> str:
        """Compact canonical context for the writer/critic (plan §2 context slice)."""
        c = self.conn
        out: list[str] = []
        chars = c.execute("SELECT name, status FROM character ORDER BY name").fetchall()
        if chars:
            out.append("## Characters")
            for name, status in chars:
                line = f"- **{name}**" + (f" ({status})" if status else "")
                out.append(line)
                facts = c.execute(
                    "SELECT fact FROM character_fact WHERE name=? ORDER BY chapter", (name,)
                ).fetchall()
                for (fact,) in facts:
                    out.append(f"  - {fact}")
        rules = c.execute("SELECT rule FROM world_rule").fetchall()
        if rules:
            out.append("\n## World rules")
            out += [f"- {r[0]}" for r in rules]
        tl = c.execute("SELECT chapter, event FROM timeline ORDER BY chapter").fetchall()
        if tl:
            out.append("\n## Timeline")
            out += [f"- ch{ch:02d}: {ev}" for ch, ev in tl]
        return "\n".join(out)

    def memory_summary(self) -> str:
        c = self.conn
        nchar = c.execute("SELECT COUNT(*) FROM character").fetchone()[0]
        nfact = c.execute("SELECT COUNT(*) FROM character_fact").fetchone()[0]
        nrule = c.execute("SELECT COUNT(*) FROM world_rule").fetchone()[0]
        nthread = c.execute("SELECT COUNT(*) FROM thread").fetchone()[0]
        nedge = c.execute("SELECT COUNT(*) FROM gedge").fetchone()[0]
        header = (f"Canon: {nchar} characters, {nfact} facts, {nrule} world rules, "
                  f"{nthread} threads, {nedge} graph edges.\n")
        return header + "\n" + self.canon_context()

    # ── render canon to markdown pages (human-readable view) ──────────────────
    def render_canon(self, paths: BookPaths) -> None:
        c = self.conn
        for (name,) in c.execute("SELECT name FROM character ORDER BY name").fetchall():
            status = c.execute("SELECT status FROM character WHERE name=?", (name,)).fetchone()[0]
            facts = [r[0] for r in c.execute(
                "SELECT fact FROM character_fact WHERE name=? ORDER BY chapter", (name,))]
            voice = [r[0] for r in c.execute(
                "SELECT note FROM character_voice WHERE name=?", (name,))]
            fact_lines = [f"- {f}" for f in facts] or ["- (none yet)"]
            lines = [
                "---", "type: character", f"name: {name}",
                f"status: {status or 'unknown'}", "---", "",
                "## Canon", *fact_lines,
            ]
            if voice:
                lines += ["", "## Voice", *(f"- {v}" for v in voice)]
            brain.write_text(paths.characters / f"{brain.slugify(name)}.md", "\n".join(lines))

        rules = [r[0] for r in c.execute("SELECT rule FROM world_rule")]
        brain.write_text(paths.world_rules,
                         "# World rules\n\n" + ("\n".join(f"- {r}" for r in rules)
                                                or "_(none yet)_"))
        tl = c.execute("SELECT chapter, event FROM timeline ORDER BY chapter").fetchall()
        brain.write_text(paths.timeline,
                         "# Timeline\n\n" + ("\n".join(f"- ch{ch:02d}: {ev}" for ch, ev in tl)
                                             or "_(none yet)_"))
