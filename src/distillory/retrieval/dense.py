"""Dense retrieval — brute-force cosine over the resident matrix.

The DEFAULT backend: pure numpy, no sqlite extension required (the app's bundled
Python can't `enable_load_extension`, so the sqlite-vec accelerator is an opt-in
for large corpora in a later slice). Exact, simple, fast to ~100k chunks.
"""

from __future__ import annotations

import sqlite3

import numpy as np

from .matrix_cache import MatrixCache


class NumpyBruteForce:
    def __init__(self, conn: sqlite3.Connection, embedder, cache: MatrixCache | None = None):
        self.embedder = embedder
        self.cache = cache or MatrixCache(conn)

    def search(self, query: str, k: int = 8) -> list[tuple[str, float]]:
        """Return [(chunk_uid, cosine)] best-first. Empty when there's no embedder
        (embed='none'), no vectors yet, or a dim mismatch (e.g. the index was built
        with a different embedder — degrade to keyword rather than crash)."""
        vecs = self.embedder.embed([query])
        if not vecs or not vecs[0]:
            return []
        q = np.asarray(vecs[0], dtype=np.float32)
        qn = float(np.linalg.norm(q))
        if qn == 0.0:
            return []   # no embeddable content (e.g. punctuation-only) -> no dense hits
        q = q / qn
        uids, mat, norms = self.cache.get()
        if mat is None or not uids or mat.shape[1] != q.shape[0]:
            return []
        scores = (mat @ q) / norms                  # cosine per chunk
        k = min(max(1, int(k)), scores.shape[0])
        idx = np.argpartition(-scores, k - 1)[:k]
        idx = idx[np.argsort(-scores[idx])]
        return [(uids[i], float(scores[i])) for i in idx]
