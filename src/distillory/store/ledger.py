"""LedgerStore — the structured, queryable mirror of each profile's fact ledger.

Synthesis writes a `## Ledger` section into the profile markdown (newest-first,
edge-typed, cited). The grader parses that section into structured rows here, so
the facts — and which ones are superseded — are queryable, not buried in prose.

The profile's Ledger section is canonical (it compounds across syntheses); this
table mirrors the current view, replaced on each synthesis.
"""

from __future__ import annotations

import sqlite3

from .db import utc_now


class LedgerStore:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.autocommit = True

    def _commit(self) -> None:
        if self.autocommit:
            self.conn.commit()

    def set_for_slug(self, slug: str, entries: list[dict]) -> None:
        """Replace the structured ledger for a slug with the parsed entries."""
        self.conn.execute("DELETE FROM ledger WHERE slug = ?", (slug,))
        now = utc_now()
        for e in entries:
            self.conn.execute(
                "INSERT INTO ledger (slug, edge, statement, source_ref, doc_date, "
                "event_date, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (slug, e["edge"], e["statement"], e.get("source_ref", ""),
                 e.get("doc_date") or "", e.get("event_date"),
                 e.get("status", "active"), now),
            )
        self._commit()

    def for_slug(self, slug: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT edge, statement, source_ref, doc_date, event_date, status "
            "FROM ledger WHERE slug = ? ORDER BY id", (slug,),
        ).fetchall()
        return [dict(r) for r in rows]

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM ledger").fetchone()[0]
