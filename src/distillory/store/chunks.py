"""ChunkStore — the raw, immutable half of the index.

Every `add()` lands its source text here as one or more chunks: inserted into
`chunks` (FTS5 stays in sync via triggers) and embedded into `chunk_vec` (BLOB)
for the dense read path. In slice 1 the dense vectors are written but the read
path is keyword-only (FTS5 BM25); slice 4 lights up cosine + RRF over the same
vectors with no re-ingest.
"""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass

import numpy as np

from .db import utc_now


def _chunk_uid(source_ref: str, ord_: int) -> str:
    return hashlib.sha1(f"{source_ref}\x00{ord_}".encode("utf-8")).hexdigest()


@dataclass
class ChunkHit:
    chunk_uid: str
    slug: str | None
    source_ref: str
    text: str
    score: float


class ChunkStore:
    def __init__(self, conn: sqlite3.Connection, embedder):
        self.conn = conn
        self.embedder = embedder

    def add_chunk(self, slug: str | None, source_ref: str, text: str, *,
                  ord_: int = 0, event_date: str | None = None,
                  raw_text: str | None = None) -> dict:
        """Insert one chunk + its embedding. Idempotent on chunk_uid."""
        text = (text or "").strip()
        if not text:
            return {"added": False, "chunk_id": None}
        uid = _chunk_uid(source_ref, ord_)
        info = getattr(self.embedder, "info", None)
        embed_model = getattr(info, "model_id", "none") if info else "none"
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO chunks "
            "(chunk_uid, slug, source_ref, ord, text, raw_text, event_date, embed_model, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (uid, slug, source_ref, ord_, text, raw_text if raw_text is not None else text,
             event_date, embed_model, utc_now()),
        )
        added = cur.rowcount > 0
        chunk_id = None
        if added:
            chunk_id = self.conn.execute(
                "SELECT id FROM chunks WHERE chunk_uid = ?", (uid,)
            ).fetchone()[0]
            self._store_vec(chunk_id, text)
        self.conn.commit()
        return {"added": added, "chunk_id": chunk_id}

    def _store_vec(self, chunk_id: int, text: str) -> None:
        vecs = self.embedder.embed([text])
        if not vecs or not vecs[0]:
            return  # embed="none" -> keyword-only for this chunk
        v = np.asarray(vecs[0], dtype=np.float32)
        norm = float(np.linalg.norm(v)) or 1.0
        self.conn.execute(
            "INSERT OR REPLACE INTO chunk_vec (chunk_id, dim, norm, quant, vec) VALUES (?, ?, ?, 'f32', ?)",
            (chunk_id, int(v.shape[0]), norm, v.tobytes()),
        )

    def search_fts(self, query: str, *, limit: int = 8, slug: str | None = None) -> list[ChunkHit]:
        """BM25-ranked chunk search (heritage: mbrain search.search)."""
        sql = (
            "SELECT c.chunk_uid, c.slug, c.source_ref, c.text, "
            "bm25(chunk_fts) AS score "
            "FROM chunk_fts JOIN chunks c ON c.id = chunk_fts.rowid "
            "WHERE chunk_fts MATCH ?"
        )
        params: list = [query]
        if slug:
            sql += " AND c.slug = ?"
            params.append(slug)
        sql += " ORDER BY score LIMIT ?"
        params.append(int(limit))
        try:
            rows = self.conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError:
            # FTS5 syntax error (bare punctuation etc.) -> retry as a quoted literal
            safe = '"' + (query or "").replace('"', " ") + '"'
            rows = self.conn.execute(sql, [safe, *params[1:]]).fetchall()
        return [
            ChunkHit(chunk_uid=r["chunk_uid"], slug=r["slug"], source_ref=r["source_ref"],
                     text=r["text"], score=float(r["score"]))
            for r in rows
        ]

    def sources_text(self, slug: str, *, per_source: int = 6000, total_cap: int = 60000) -> str:
        """Assemble the immutable source text for a slug, capped — mirrors the
        app's synthesize_profile assembly (per-source [:6000], total 60000)."""
        rows = self.conn.execute(
            "SELECT source_ref, text FROM chunks WHERE slug = ? ORDER BY id", (slug,)
        ).fetchall()
        blocks, total = [], 0
        for r in rows:
            body = (r["text"] or "").strip()
            if not body:
                continue
            block = f"### {r['source_ref']}\n{body[:per_source]}"
            if total + len(block) > total_cap:
                break
            blocks.append(block)
            total += len(block)
        return "\n\n".join(blocks)

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
