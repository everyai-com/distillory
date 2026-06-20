"""The whole engine in one SQLite file: profiles, sources, chunks, FTS5,
dense vectors, the edge-typed fact ledger, and engine metadata.

`profiles` + `profile_sources` are lifted verbatim from the AIOS Desktop app's
validated `settings.db` (the `feat/memory-engine` branch), with one addition: a
`name` column so the public API can resolve a human name -> slug. Every other
table is created up front so later slices (dense read, ledger writes, sqlite-vec
accelerator) need no migration.
"""

from __future__ import annotations

import sqlite3

SCHEMA_VERSION = 1

_DDL = """
-- ── Living profiles (verbatim from workspace.py + a `name` column) ──────────
CREATE TABLE IF NOT EXISTS profiles (
    slug             TEXT PRIMARY KEY,
    name             TEXT NOT NULL DEFAULT '',
    entity_type      TEXT NOT NULL DEFAULT 'prospect',
    status           TEXT NOT NULL DEFAULT 'active',
    stage            TEXT NOT NULL DEFAULT 'new',
    owner            TEXT NOT NULL DEFAULT '',
    deal_value_usd   REAL,
    next_action_date TEXT,
    last_contact     TEXT,
    content_md       TEXT NOT NULL DEFAULT '',
    dirty            INTEGER NOT NULL DEFAULT 0,
    last_synthesized TEXT,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_profiles_dirty ON profiles(dirty, updated_at);

-- Append-only pointers to the immutable sources each profile was built from.
CREATE TABLE IF NOT EXISTS profile_sources (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    slug        TEXT NOT NULL,
    source_ref  TEXT NOT NULL,
    source_kind TEXT NOT NULL DEFAULT 'file',
    event_date  TEXT,
    summary     TEXT NOT NULL DEFAULT '',
    added_at    TEXT NOT NULL,
    UNIQUE(slug, source_ref)
);
CREATE INDEX IF NOT EXISTS idx_profile_sources_slug ON profile_sources(slug, added_at);

-- ── Raw chunks (the literal / cross-entity half of the hybrid index) ────────
CREATE TABLE IF NOT EXISTS chunks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    chunk_uid   TEXT NOT NULL UNIQUE,          -- sha1(source_ref + ord) -> idempotent re-ingest
    slug        TEXT,
    source_ref  TEXT NOT NULL,
    ord         INTEGER NOT NULL DEFAULT 0,
    text        TEXT NOT NULL,                  -- contextual-prepend applied here when enabled (slice 6)
    raw_text    TEXT NOT NULL,                  -- original pre-prepend (audit)
    context_flag TEXT,
    event_date  TEXT,
    embed_model TEXT,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_slug   ON chunks(slug);
CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks(source_ref);

-- ── FTS5 over chunks (heritage: mbrain search._open) + content-sync triggers ─
CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts USING fts5(
    text, chunk_uid UNINDEXED, slug UNINDEXED,
    content='chunks', content_rowid='id', tokenize='porter unicode61'
);
CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
  INSERT INTO chunk_fts(rowid, text, chunk_uid, slug) VALUES(new.id, new.text, new.chunk_uid, new.slug);
END;
CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
  INSERT INTO chunk_fts(chunk_fts, rowid, text, chunk_uid, slug) VALUES('delete', old.id, old.text, old.chunk_uid, old.slug);
END;
CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
  INSERT INTO chunk_fts(chunk_fts, rowid, text, chunk_uid, slug) VALUES('delete', old.id, old.text, old.chunk_uid, old.slug);
  INSERT INTO chunk_fts(rowid, text, chunk_uid, slug) VALUES(new.id, new.text, new.chunk_uid, new.slug);
END;

-- ── Dense vectors. DEFAULT: BLOB table, numpy brute-force cosine. ALWAYS exists. ─
CREATE TABLE IF NOT EXISTS chunk_vec (
    chunk_id INTEGER PRIMARY KEY REFERENCES chunks(id) ON DELETE CASCADE,
    dim      INTEGER NOT NULL,
    norm     REAL NOT NULL,                      -- precomputed L2 norm -> cosine = dot/(nq*nd)
    quant    TEXT NOT NULL DEFAULT 'f32',        -- f32 | f16 | i8 (slice 5)
    vec      BLOB NOT NULL                        -- little-endian, dtype per `quant`
);

-- ── Edge-typed, temporally-grounded fact ledger (structured; written in slice 2) ─
CREATE TABLE IF NOT EXISTS ledger (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    slug          TEXT NOT NULL,
    edge          TEXT NOT NULL,                 -- assert | update | extend | derive
    statement     TEXT NOT NULL,
    source_ref    TEXT NOT NULL,
    doc_date      TEXT NOT NULL,                 -- when learned
    event_date    TEXT,                           -- when it happened (powers decay)
    status        TEXT NOT NULL DEFAULT 'active', -- active | superseded | stale
    supersedes_id INTEGER REFERENCES ledger(id),
    created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ledger_slug   ON ledger(slug, created_at);
CREATE INDEX IF NOT EXISTS idx_ledger_status ON ledger(slug, status);

-- ── Engine metadata: embedder-identity lock, schema version ─────────────────
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(_DDL)
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    conn.commit()


def get_meta(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO meta(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, str(value)),
    )
    conn.commit()
