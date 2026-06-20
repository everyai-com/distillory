"""Public result types returned by the four core verbs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Scope = Literal["personal", "team", "both"]


@dataclass
class Hit:
    slug: str | None
    title: str
    score: float
    snippet: str = ""
    body: str = ""               # populated by profile() always; by search(body=True) on demand
    kind: str = "profile"        # profile | chunk
    source_ref: str = ""
    event_date: str | None = None
    citations: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)


@dataclass
class AddResult:
    slug: str
    dirty: bool                  # True -> a synthesize() pass is warranted
    source_added: bool           # False -> idempotent no-op (source_ref already present)
