"""MemoryConfig — the explicit construction path.

`Memory.open(db_path, synth=..., embed=...)` is ergonomic sugar over this. Both
share the same `synth=` / `embed=` kwargs so graduating from sugar to config
needs no relearning. Precedence: explicit kwargs > env (DISTILLORY_*) > defaults.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class MemoryConfig:
    db_path: str | Path = "brain.db"
    synth: object = "auto"          # "auto"|"none"|"claude"|"anthropic:<m>"|"ollama:<m>"|object
    embed: object = "fastembed"     # "fastembed"|"potion"|"hash"|"none"|object
    schema: str | None = None       # path to an outcomes.md grading contract
    model: str | None = None        # synthesis model override (e.g. a Haiku id)
    dense_backend: str = "auto"     # auto|numpy|sqlite-vec (read path; slice 4+)
    auto_synth: bool = True         # add() schedules synthesize() for touched entities

    @classmethod
    def resolve(cls, db_path, **kwargs) -> "MemoryConfig":
        env = {
            "synth": os.environ.get("DISTILLORY_SYNTH"),
            "embed": os.environ.get("DISTILLORY_EMBED"),
            "schema": os.environ.get("DISTILLORY_SCHEMA"),
            "model": os.environ.get("DISTILLORY_MODEL"),
        }
        base = cls(db_path=db_path)
        for k in ("synth", "embed", "schema", "model"):
            if kwargs.get(k) is not None:
                setattr(base, k, kwargs[k])
            elif env.get(k):
                setattr(base, k, env[k])
        for k in ("dense_backend", "auto_synth"):
            if kwargs.get(k) is not None:
                setattr(base, k, kwargs[k])
        return base


def load_schema(schema: str | None) -> str | None:
    """A schema arg may be a path to an outcomes.md OR the contract text itself."""
    if not schema:
        return None
    p = Path(schema).expanduser()
    if p.is_file():
        return p.read_text(encoding="utf-8")
    return schema  # treat as inline contract text
