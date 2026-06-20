"""PotionEmbedder — potion-base-8M static embeddings via model2vec.

The instant, CPU-only middle rung: no ONNX runtime, no download stall, much
better than the hash floor. Behind the [embed-potion] extra; the resolver uses it
as the fallback when fastembed is unavailable.
"""

from __future__ import annotations

import numpy as np

from .base import EmbedderInfo

_MODEL = "minishlab/potion-base-8M"


class PotionEmbedder:
    def __init__(self, model: str = _MODEL):
        from model2vec import StaticModel  # raises if the extra isn't installed
        self._model_name = model
        self._model = StaticModel.from_pretrained(model)
        self._dim = int(np.asarray(self._model.encode(["x"])).shape[-1])

    def embed(self, texts: list[str]) -> list[list[float]]:
        vecs = np.asarray(self._model.encode(list(texts)), dtype=np.float32)
        return [[float(x) for x in v] for v in vecs]

    @property
    def info(self) -> EmbedderInfo:
        # static embeddings aren't unit-norm; cosine uses the stored per-vector norm
        return EmbedderInfo(model_id=self._model_name, dim=self._dim, normalized=False)
