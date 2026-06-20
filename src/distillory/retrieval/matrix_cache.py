"""MatrixCache — the resident (n×dim) matrix of chunk vectors.

Dense search reads vectors from one in-memory numpy matrix instead of decoding
BLOBs every query. A generation counter (count + max id of chunk_vec) is checked
on each access, so a just-added chunk is reflected on the very next search and a
no-op add costs nothing.

(Rebuild-on-change is fine to ~100k chunks; incremental append + sqlite-vec for
larger corpora are slices 6/later — same results, only speed differs.)
"""

from __future__ import annotations

import sqlite3
import threading

import numpy as np


class MatrixCache:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._lock = threading.Lock()
        self._gen: tuple[int, int] | None = None
        self._uids: list[str] = []
        self._mat: np.ndarray | None = None     # (n, dim) float32
        self._norms: np.ndarray | None = None    # (n,) float32

    def _generation(self) -> tuple[int, int]:
        row = self.conn.execute(
            "SELECT COUNT(*), COALESCE(MAX(chunk_id), 0) FROM chunk_vec"
        ).fetchone()
        return (int(row[0]), int(row[1]))

    def get(self) -> tuple[list[str], np.ndarray | None, np.ndarray | None]:
        """Return (uids, matrix, norms); rebuilds iff chunk_vec changed."""
        with self._lock:
            gen = self._generation()
            if gen != self._gen:
                self._rebuild()
                self._gen = gen
            return self._uids, self._mat, self._norms

    def _rebuild(self) -> None:
        rows = self.conn.execute(
            "SELECT c.chunk_uid, v.dim, v.norm, v.vec "
            "FROM chunk_vec v JOIN chunks c ON c.id = v.chunk_id ORDER BY v.chunk_id"
        ).fetchall()
        uids: list[str] = []
        vecs: list[np.ndarray] = []
        norms: list[float] = []
        dim: int | None = None
        for r in rows:
            d = int(r["dim"])
            if dim is None:
                dim = d
            if d != dim:
                continue  # embedder-identity lock normally prevents mixed dims
            uids.append(r["chunk_uid"])
            vecs.append(np.frombuffer(r["vec"], dtype=np.float32))
            norms.append(float(r["norm"]) or 1.0)
        self._uids = uids
        self._mat = np.vstack(vecs) if vecs else None
        self._norms = np.asarray(norms, dtype=np.float32) if norms else None

    def resident_mb(self) -> float:
        return round((self._mat.nbytes / 1e6) if self._mat is not None else 0.0, 2)
