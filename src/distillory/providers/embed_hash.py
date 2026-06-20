"""HashEmbedder — deterministic, zero-dependency, always-available embedder.

A hashed bag-of-tokens projected into a fixed-dim normalized vector. This is the
survival FLOOR, not a quality embedder: it gives the dense path *something* to
fuse even with no model and no network. fastembed (bge-small ONNX) is the
recommended embedder and ships in slice 4; the resolver falls through to this on
any failure so a bare offline machine still works.
"""

from __future__ import annotations

import hashlib
import re

import numpy as np

from .base import EmbedderInfo

_DIM = 256
_TOKEN_RE = re.compile(r"[a-z0-9]{2,}")


class HashEmbedder:
    def __init__(self, dim: int = _DIM):
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for t in texts:
            v = np.zeros(self.dim, dtype=np.float32)
            for tok in _TOKEN_RE.findall((t or "").lower()):
                h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
                v[h % self.dim] += 1.0
            n = float(np.linalg.norm(v))
            if n > 0:
                v /= n
            out.append(v.tolist())
        return out

    @property
    def info(self) -> EmbedderInfo:
        return EmbedderInfo(model_id=f"hash-{self.dim}", dim=self.dim, normalized=True)


class NoEmbedder:
    """embed='none' — keyword-only. Returns empty vectors; the chunk store skips
    writing a dense row, so search is pure FTS5."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[] for _ in texts]

    @property
    def info(self) -> EmbedderInfo:
        return EmbedderInfo(model_id="none", dim=0, normalized=False)
