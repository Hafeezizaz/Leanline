"""SQLite graph store with FTS5 search.

Nodes are rows (files, sections, terms, log groups); edges live in one table with
string node ids like "file:3" or "section:17".
"""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .extract.base import Extracted
from .tokens import count_tokens

SCHEMA = """
CREATE TABLE IF NOT EXISTS files(
  id INTEGER PRIMARY KEY, path TEXT UNIQUE NOT NULL, content_hash TEXT NOT NULL,
  kind TEXT NOT NULL, size_bytes INTEGER NOT NULL, raw_tokens INTEGER NOT NULL,
  extracted_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sections(
  id INTEGER PRIMARY KEY, file_id INTEGER NOT NULL, ordinal INTEGER NOT NULL,
  heading_path TEXT NOT NULL, level INTEGER NOT NULL, text TEXT NOT NULL, tokens INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS idx_sections_file ON sections(file_id, ordinal);
CREATE VIRTUAL TABLE IF NOT EXISTS sections_fts USING fts5(heading_path, text);
CREATE TABLE IF NOT EXISTS terms(
  id INTEGER PRIMARY KEY, file_id INTEGER NOT NULL, name TEXT NOT NULL, section_id INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS log_groups(
  id INTEGER PRIMARY KEY, file_id INTEGER NOT NULL, signature TEXT NOT NULL, level TEXT NOT NULL,
  count INTEGER NOT NULL, first_ts TEXT, last_ts TEXT, sample TEXT);
CREATE TABLE IF NOT EXISTS edges(
  file_id INTEGER NOT NULL, src TEXT NOT NULL, rel TEXT NOT NULL, dst TEXT NOT NULL, dst_label TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_edges_file ON edges(file_id);
CREATE TABLE IF NOT EXISTS digests(
  path TEXT PRIMARY KEY, content_hash TEXT NOT NULL, digest TEXT NOT NULL, created_at TEXT NOT NULL);
"""


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def _ph(n: int) -> str:
    return ",".join("?" * n)


class Graph:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # ---- writes -----------------------------------------------------------------

    def _clear(self, fid: int) -> None:
        c = self.conn
        ids = [r["id"] for r in c.execute("SELECT id FROM sections WHERE file_id=?", (fid,))]
        c.executemany("DELETE FROM sections_fts WHERE rowid=?", [(i,) for i in ids])
        for table in ("sections", "terms", "log_groups", "edges"):
            c.execute(f"DELETE FROM {table} WHERE file_id=?", (fid,))

    def _edge(self, fid: int, src: str, rel: str, dst: str, label: str) -> None:
        self.conn.execute(
            "INSERT INTO edges(file_id,src,rel,dst,dst_label) VALUES (?,?,?,?,?)", (fid, src, rel, dst, label)
        )

    def upsert_file(self, path: str, content_hash: str, size: int, raw_tokens: int, ex: Extracted) -> int:
        c = self.conn
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with c:  # one transaction
            row = c.execute("SELECT id FROM files WHERE path=?", (path,)).fetchone()
            if row:
                fid = row["id"]
                self._clear(fid)
                c.execute(
                    "UPDATE files SET content_hash=?, kind=?, size_bytes=?, raw_tokens=?, extracted_at=? WHERE id=?",
                    (content_hash, ex.kind, size, raw_tokens, now, fid),
                )
            else:
                cur = c.execute(
                    "INSERT INTO files(path,content_hash,kind,size_bytes,raw_tokens,extracted_at) VALUES (?,?,?,?,?,?)",
                    (path, content_hash, ex.kind, size, raw_tokens, now),
                )
                fid = cur.lastrowid

            sec_ids: dict[int, int] = {}
            for s in ex.sections:
                cur = c.execute(
                    "INSERT INTO sections(file_id,ordinal,heading_path,level,text,tokens) VALUES (?,?,?,?,?,?)",
                    (fid, s.ordinal, s.heading_path, s.level, s.text, count_tokens(s.heading_path + "\n" + s.text)),
                )
                sid = cur.lastrowid
                sec_ids[s.ordinal] = sid
                c.execute(
                    "INSERT INTO sections_fts(rowid,heading_path,text) VALUES (?,?,?)", (sid, s.heading_path, s.text)
                )
                self._edge(fid, f"file:{fid}", "contains", f"section:{sid}", s.heading_path)

            for name, ordn in ex.terms:
                sid = sec_ids.get(ordn)
                if sid is None:
                    continue
                cur = c.execute("INSERT INTO terms(file_id,name,section_id) VALUES (?,?,?)", (fid, name, sid))
                self._edge(fid, f"section:{sid}", "defines", f"term:{cur.lastrowid}", name)

            heads = [(sec_ids[s.ordinal], s.heading_path.split(" > ")[-1]) for s in ex.sections]
            for ordn, target in ex.links:
                src_sid = sec_ids.get(ordn)
                if src_sid is None:
                    continue
                t = target.split("#")[-1].strip() if "#" in target else target.strip()
                dst = ""
                if t and not re.match(r"^[a-zA-Z]+://", target):
                    tl = t.lower()
                    for hid, h in heads:
                        hl = h.lower()
                        if hl == tl or _slug(h) == _slug(t) or hl.startswith(tl + " ") or hl.startswith(tl + "."):
                            dst = f"section:{hid}"
                            break
                self._edge(fid, f"section:{src_sid}", "links_to", dst, target)

            for g in ex.log_groups:
                cur = c.execute(
                    "INSERT INTO log_groups(file_id,signature,level,count,first_ts,last_ts,sample) VALUES (?,?,?,?,?,?,?)",
                    (fid, g.signature, g.level, g.count, g.first_ts, g.last_ts, g.sample),
                )
                self._edge(fid, f"logg:{cur.lastrowid}", "occurs_in", f"file:{fid}", g.signature)
        return fid

    def set_digest(self, path: str, content_hash: str, digest: str) -> None:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO digests(path,content_hash,digest,created_at) VALUES (?,?,?,?)",
                (path, content_hash, digest, now),
            )

    # ---- reads ------------------------------------------------------------------

    def get_file(self, path: str):
        return self.conn.execute("SELECT * FROM files WHERE path=?", (path,)).fetchone()

    def file_infos(self, ids: list[int]) -> list[dict]:
        if not ids:
            return []
        rows = self.conn.execute(f"SELECT * FROM files WHERE id IN ({_ph(len(ids))}) ORDER BY path", ids)
        return [dict(r) for r in rows]

    def search(self, match: str, ids: list[int], limit: int = 50) -> list[dict]:
        if not match or not ids:
            return []
        sql = f"""SELECT s.id, s.ordinal, s.heading_path, s.text, s.tokens, f.path, f.id AS file_id,
                         bm25(sections_fts, 5.0, 1.0) AS score
                  FROM sections_fts
                  JOIN sections s ON s.id = sections_fts.rowid
                  JOIN files f ON f.id = s.file_id
                  WHERE sections_fts MATCH ? AND f.id IN ({_ph(len(ids))})
                  ORDER BY score LIMIT ?"""
        try:
            return [dict(r) for r in self.conn.execute(sql, [match, *ids, limit])]
        except sqlite3.OperationalError:
            return []

    def sections_matching(self, ids: list[int], needle: str) -> list[dict]:
        if not ids:
            return []
        sql = f"""SELECT s.id, s.ordinal, s.heading_path, s.text, s.tokens, f.path, f.id AS file_id
                  FROM sections s JOIN files f ON f.id = s.file_id
                  WHERE f.id IN ({_ph(len(ids))}) AND lower(s.heading_path) LIKE ?
                  ORDER BY f.path, s.ordinal"""
        return [dict(r) for r in self.conn.execute(sql, [*ids, f"%{needle.lower()}%"])]

    def outline(self, ids: list[int], limit: int = 40) -> list[dict]:
        if not ids:
            return []
        sql = f"""SELECT s.heading_path, s.tokens, f.path
                  FROM sections s JOIN files f ON f.id = s.file_id
                  WHERE f.id IN ({_ph(len(ids))}) ORDER BY f.path, s.ordinal LIMIT ?"""
        return [dict(r) for r in self.conn.execute(sql, [*ids, limit])]

    def get_digest(self, path: str):
        return self.conn.execute("SELECT * FROM digests WHERE path=?", (path,)).fetchone()
