"""Per-book SQLite store: derived FTS index + canonical state + entity graph.

Honors the GBrain pattern in spirit (one queryable store synced from / rendered to
markdown). v1 simplification: structured canon lives here and is *rendered* to markdown
pages under canon/; full markdown-as-source-of-truth-with-sync is a later refinement
(noted in plan.md §3.2). The DB file is derived and gitignored (.index/).
"""
from __future__ import annotations

import sqlite3

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
    def open(cls, paths: BookPaths) -> Store:
        paths.index_db.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(paths.index_db))
        # Anything that fails during schema init (e.g. DatabaseError on a corrupt/locked db -
        # common on Windows when the .index is in a synced folder) must close `conn` before
        # propagating: open() returns nothing, so the caller's `finally: store.close()` never
        # runs and the connection (and its file lock) would leak.
        try:
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
        except BaseException:
            conn.close()
            raise
        return cls(conn, fts)

    def close(self) -> None:
        self.conn.commit()
        self.conn.close()

    # ── full-text index over committed chapters + summaries ──────────────────
    def index_chapter(self, paths: BookPaths, n: int) -> None:
        """Incrementally (re)index one chapter's text + summary.

        Re-reading and re-inserting every chapter on every commit would be
        O(n^2) over a run, so commits index only the chapter that changed.
        """
        c = self.conn
        for p, kind in ((paths.ch(n), "chapter"), (paths.ch_summary(n), "summary")):
            c.execute("DELETE FROM docs WHERE ref=?", (p.stem,))
            if p.exists():
                c.execute("INSERT INTO docs (kind, ref, body) VALUES (?,?,?)",
                          (kind, p.stem, p.read_text(encoding="utf-8")))
        c.commit()

    def search_excerpts(self, terms: list[str], limit: int = 2,
                        exclude_refs: set[str] | None = None) -> list[tuple[str, str]]:
        """Top FTS-matched chapter excerpts for a set of terms: [(ref, excerpt)].

        Powers retrieval beyond dependency summaries - relevant passages from
        *other* committed chapters (plan §2 context slice). Best-effort: returns
        [] on any FTS error or when FTS is unavailable.
        """
        terms = [t.replace('"', "") for t in terms if t.strip()]
        if not terms:
            return []
        exclude = exclude_refs or set()
        c = self.conn
        out: list[tuple[str, str]] = []
        if self.fts:
            match = " OR ".join(f'"{t}"' for t in terms[:8])
            try:
                rows = c.execute(
                    "SELECT ref, kind, snippet(docs, 2, '', '', ' ... ', 32) "
                    "FROM docs WHERE docs MATCH ? ORDER BY rank LIMIT ?",
                    (match, limit + len(exclude) + 4),
                ).fetchall()
            except sqlite3.OperationalError:
                return []
            for ref, kind, snip in rows:
                if kind != "chapter" or ref in exclude:
                    continue
                out.append((ref, snip))
                if len(out) >= limit:
                    break
            return out
        rows = c.execute(
            "SELECT ref, kind, substr(body, 1, 400) FROM docs WHERE body LIKE ? LIMIT ?",
            (f"%{terms[0]}%", limit + len(exclude) + 4),
        ).fetchall()
        for ref, kind, snip in rows:
            if kind != "chapter" or ref in exclude:
                continue
            out.append((ref, snip))
            if len(out) >= limit:
                break
        return out

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
            # Record under the chapter actually being committed - the LLM-reported
            # chapter number is sometimes wrong and would mis-order the timeline.
            c.execute("INSERT OR IGNORE INTO timeline VALUES (?,?)", (chapter, ev.event))
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
    def canon_context(self, *, max_facts_per_char: int | None = None) -> str:
        """Compact canonical context for the writer/critic (plan §2 context slice).

        max_facts_per_char caps each character at their N most recent facts (by
        chapter) - the writer/critic prompt would otherwise grow linearly with the
        book and pay maximum latency/cost on late chapters. None = everything
        (consolidation and extraction audit the full canon).
        """
        c = self.conn
        out: list[str] = []
        chars = c.execute("SELECT name, status FROM character ORDER BY name").fetchall()
        facts_by_char: dict[str, list[str]] = {}
        for name, fact in c.execute(
                "SELECT name, fact FROM character_fact ORDER BY name, chapter"):
            facts_by_char.setdefault(name, []).append(fact)
        if chars:
            out.append("## Characters")
            for name, status in chars:
                line = f"- **{name}**" + (f" ({status})" if status else "")
                out.append(line)
                facts = facts_by_char.get(name, [])
                if max_facts_per_char is not None and len(facts) > max_facts_per_char:
                    facts = facts[-max_facts_per_char:]   # chapter-ordered: keep newest
                for fact in facts:
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
    def render_canon(self, paths: BookPaths, *, names: list[str] | None = None) -> None:
        """Render canon pages. names limits the character pages rewritten (per-commit
        only the characters the extraction touched can have changed)."""
        c = self.conn
        # Which characters to render, with their status (one query, optionally name-filtered) -
        # then batch facts/voice for exactly those names, instead of 3 queries per character.
        if names is None:
            char_rows = c.execute("SELECT name, status FROM character ORDER BY name").fetchall()
        else:
            wanted = sorted(set(names))
            ph = ",".join("?" * len(wanted))
            char_rows = c.execute(
                f"SELECT name, status FROM character WHERE name IN ({ph}) ORDER BY name",
                wanted).fetchall() if wanted else []
        render_names = sorted({name for name, _ in char_rows})
        facts_by: dict[str, list[str]] = {}
        voice_by: dict[str, list[str]] = {}
        if render_names:
            ph = ",".join("?" * len(render_names))
            for nm, fact in c.execute(
                    f"SELECT name, fact FROM character_fact WHERE name IN ({ph}) "
                    "ORDER BY name, chapter", render_names):
                facts_by.setdefault(nm, []).append(fact)
            for nm, note in c.execute(
                    f"SELECT name, note FROM character_voice WHERE name IN ({ph})", render_names):
                voice_by.setdefault(nm, []).append(note)
        for name, status in char_rows:
            facts = facts_by.get(name, [])
            voice = voice_by.get(name, [])
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
