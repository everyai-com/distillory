"""distillory — the local-first memory engine that synthesizes at ingestion.

One schema-graded, contradiction-resolved profile per entity, in a single
embeddable SQLite file. No server, no Docker, no hosted reranker. MIT.

    from distillory import Memory
    mem = Memory.open("brain.db")
    mem.add("Met David at LucidWay — wants the GTSI automation, ~$10k", entity="David Chen")
    print(mem.profile("David Chen").body)
"""

from __future__ import annotations

from .config import MemoryConfig
from .engine import Memory
from .models import AddResult, Hit, Scope
from .providers import Embedder, EmbedderInfo, LLMProvider, Synthesizer

__version__ = "0.1.0"
__all__ = [
    "Memory", "MemoryConfig", "Hit", "AddResult", "Scope",
    "LLMProvider", "Synthesizer", "Embedder", "EmbedderInfo", "__version__",
]
