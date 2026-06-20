"""ProfileStore — one living, synthesized page per entity.

CRUD lifted from the AIOS Desktop app's validated `workspace.py` (the
`feat/memory-engine` branch). The only changes: methods hang off a passed-in
connection instead of a module-global `connect()`, and a `name` column is
written/read so the public API can resolve a human name -> slug.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from .db import utc_now

# Scalar columns the front-matter parser is allowed to write back onto a profile.
_PROFILE_SCALARS = (
    "entity_type", "status", "stage", "owner", "deal_value_usd",
    "next_action_date", "last_contact",
)


def _profile_row(r: sqlite3.Row) -> dict[str, Any]:
    d = dict(r)
    if "dirty" in d:
        d["dirty"] = bool(d["dirty"])
    return d


class ProfileStore:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        # When False, writes are left uncommitted so the caller (engine.add) can
        # commit several store operations as ONE atomic transaction.
        self.autocommit = True

    def _commit(self) -> None:
        if self.autocommit:
            self.conn.commit()

    # ── reads ───────────────────────────────────────────────────────────────
    def list(self, entity_type: str | None = None, dirty_only: bool = False) -> dict[str, Any]:
        where: list[str] = []
        params: list[Any] = []
        if entity_type and entity_type != "all":
            where.append("entity_type = ?")
            params.append(entity_type)
        if dirty_only:
            where.append("dirty = 1")
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        rows = self.conn.execute(
            "SELECT slug, name, entity_type, status, stage, owner, deal_value_usd, "
            "next_action_date, last_contact, dirty, last_synthesized, updated_at "
            f"FROM profiles{clause} ORDER BY updated_at DESC",
            params,
        ).fetchall()
        return {"profiles": [_profile_row(r) for r in rows]}

    def get(self, slug: str) -> dict[str, Any]:
        slug = (slug or "").strip()
        if not slug:
            raise ValueError("slug is required")
        row = self.conn.execute("SELECT * FROM profiles WHERE slug = ?", (slug,)).fetchone()
        if not row:
            return {"profile": None, "sources": []}
        sources = self.conn.execute(
            "SELECT source_ref, source_kind, event_date, summary, added_at "
            "FROM profile_sources WHERE slug = ? ORDER BY added_at DESC",
            (slug,),
        ).fetchall()
        return {"profile": _profile_row(row), "sources": [dict(s) for s in sources]}

    def name_for(self, slug: str) -> str:
        row = self.conn.execute("SELECT name FROM profiles WHERE slug = ?", (slug,)).fetchone()
        return (row["name"] if row else "") or ""

    def exists(self, slug: str) -> bool:
        return self.conn.execute(
            "SELECT 1 FROM profiles WHERE slug = ?", (slug,)
        ).fetchone() is not None

    # ── writes ──────────────────────────────────────────────────────────────
    def ensure(self, slug: str, name: str = "", entity_type: str = "prospect") -> None:
        """Create the row if missing; backfill a name if we didn't have one."""
        now = utc_now()
        self.conn.execute(
            "INSERT OR IGNORE INTO profiles (slug, name, entity_type, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (slug, name or "", entity_type or "prospect", now, now),
        )
        if name:
            self.conn.execute(
                "UPDATE profiles SET name = ? WHERE slug = ? AND (name = '' OR name IS NULL)",
                (name, slug),
            )
        self._commit()

    def upsert(self, slug: str, entity_type: str = "prospect", **fields: Any) -> dict[str, Any]:
        slug = (slug or "").strip()
        if not slug:
            raise ValueError("slug is required")
        now = utc_now()
        merged = {"entity_type": entity_type, **fields}
        self.conn.execute(
            "INSERT OR IGNORE INTO profiles (slug, entity_type, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (slug, entity_type or "prospect", now, now),
        )
        sets, params = [], []
        for k in _PROFILE_SCALARS:
            if merged.get(k) is not None:
                sets.append(f"{k} = ?")
                params.append(merged[k])
        sets.append("updated_at = ?")
        params.append(now)
        params.append(slug)
        self.conn.execute(f"UPDATE profiles SET {', '.join(sets)} WHERE slug = ?", params)
        self._commit()
        row = self.conn.execute("SELECT * FROM profiles WHERE slug = ?", (slug,)).fetchone()
        return {"profile": _profile_row(row)}

    def add_source(self, slug: str, source_ref: str, source_kind: str = "file",
                   event_date: str | None = None, summary: str = "") -> dict[str, Any]:
        """Append a source pointer and mark the profile dirty. Idempotent on (slug, source_ref)."""
        slug = (slug or "").strip()
        source_ref = (source_ref or "").strip()
        if not slug or not source_ref:
            raise ValueError("slug and source_ref are required")
        now = utc_now()
        self.conn.execute(
            "INSERT OR IGNORE INTO profiles (slug, created_at, updated_at) VALUES (?, ?, ?)",
            (slug, now, now),
        )
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO profile_sources (slug, source_ref, source_kind, event_date, summary, added_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (slug, source_ref, source_kind or "file", event_date, (summary or "")[:2000], now),
        )
        added = cur.rowcount > 0
        if added:
            self.conn.execute("UPDATE profiles SET dirty = 1, updated_at = ? WHERE slug = ?", (now, slug))
        self._commit()
        return {"ok": True, "added": added, "slug": slug}

    def mark_dirty(self, slug: str, dirty: bool = True) -> dict[str, Any]:
        self.conn.execute(
            "UPDATE profiles SET dirty = ?, updated_at = ? WHERE slug = ?",
            (1 if dirty else 0, utc_now(), (slug or "").strip()),
        )
        self._commit()
        return {"ok": True}

    def set_content(self, slug: str, content_md: str, fields: dict[str, Any] | None = None,
                    clear_dirty: bool = True) -> dict[str, Any]:
        """Store the synthesized profile markdown + parsed scalar fields; clear dirty."""
        slug = (slug or "").strip()
        if not slug:
            raise ValueError("slug is required")
        now = utc_now()
        sets = ["content_md = ?", "last_synthesized = ?", "updated_at = ?"]
        params: list[Any] = [content_md or "", now, now]
        for k in _PROFILE_SCALARS:
            if fields and fields.get(k) is not None:
                sets.append(f"{k} = ?")
                params.append(fields[k])
        if clear_dirty:
            sets.append("dirty = 0")
        params.append(slug)
        self.conn.execute(
            "INSERT OR IGNORE INTO profiles (slug, created_at, updated_at) VALUES (?, ?, ?)",
            (slug, now, now),
        )
        self.conn.execute(f"UPDATE profiles SET {', '.join(sets)} WHERE slug = ?", params)
        self._commit()
        row = self.conn.execute("SELECT * FROM profiles WHERE slug = ?", (slug,)).fetchone()
        return {"profile": _profile_row(row)}
