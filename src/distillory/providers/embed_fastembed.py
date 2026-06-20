"""FastEmbedEmbedder — bge-small-en-v1.5 via ONNX (fastembed). The recommended
embedder: real semantic vectors, ONNX not torch (~hundred MB, not gigabytes).

Behind the [embed-fastembed] extra. The resolver falls through to potion -> hash
if fastembed isn't installed or the model can't download, so nothing here is a
hard requirement.
"""

from __future__ import annotations

from .base import EmbedderInfo

_MODEL = "BAAI/bge-small-en-v1.5"
_DIM = 384


class FastEmbedEmbedder:
    def __init__(self, model: str = _MODEL):
        from fastembed import TextEmbedding  # raises if the extra isn't installed
        self._model_name = model
        self._model = TextEmbedding(model_name=model)
        self._dim = _DIM

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(x) for x in v] for v in self._model.embed(list(texts))]

    @property
    def info(self) -> EmbedderInfo:
        return EmbedderInfo(model_id=self._model_name, dim=self._dim, normalized=True)
