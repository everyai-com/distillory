"""The two pluggable internals: a synthesis LLM and an embedder.

Both are one-method Protocols so bringing your own is trivial. The engine never
imports a concrete provider directly — it resolves a string ("auto", "hash",
"claude", "ollama:gpt-oss", ...) or an object through the ladders in __init__.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class EmbedderInfo:
    model_id: str
    dim: int
    normalized: bool = True


@runtime_checkable
class LLMProvider(Protocol):
    def complete(self, prompt: str, *, system: str | None = None,
                 max_tokens: int = 4096, timeout: int = 240) -> str: ...

    @property
    def name(self) -> str: ...


@runtime_checkable
class Synthesizer(Protocol):
    """Highest-level BYO seam: take schema + existing profile + new sources,
    return the full synthesized profile markdown."""
    def synthesize(self, *, schema: str, existing: str, sources: str) -> str: ...


@runtime_checkable
class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...

    @property
    def info(self) -> EmbedderInfo: ...
