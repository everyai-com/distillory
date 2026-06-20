"""SQLite connection + pragmas + the extension-capability probe.

distillory is a single embeddable SQLite file. The DEFAULT dense backend is a
normal BLOB table scanned with numpy (works everywhere, including Pythons built
without `enable_load_extension`). sqlite-vec is an OPTIONAL accelerator, gated
both on the extension loading AND on corpus size — see retrieval/dense.py
(slice 4+). This module only owns the connection and the capability probe.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    """ISO-8601 UTC, second precision. Used for every created_at/updated_at."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open (creating parent dirs) a distillory db with sane pragmas."""
    p = Path(db_path).expanduser()
    if p.parent and str(p.parent) not in ("", "."):
        p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def probe_sqlite_vec(conn: sqlite3.Connection) -> bool:
    """True iff this Python's sqlite3 can load the sqlite-vec extension.

    Many distributions (notably PyInstaller-bundled and some system Pythons)
    compile sqlite3 WITHOUT enable_load_extension — calling it raises. We treat
    any failure as 'no extensions' and fall back to the always-available numpy
    brute-force backend.
    """
    try:
        conn.enable_load_extension(True)  # type: ignore[attr-defined]
    except (AttributeError, sqlite3.OperationalError, sqlite3.NotSupportedError):
        return False
    try:
        import sqlite_vec  # noqa: F401  (only present with the [vec] extra)

        sqlite_vec.load(conn)
        return True
    except Exception:
        return False
    finally:
        try:
            conn.enable_load_extension(False)  # type: ignore[attr-defined]
        except Exception:
            pass
