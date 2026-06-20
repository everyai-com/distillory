"""Reciprocal Rank Fusion — combine ranked lists from different retrievers.

The one correctness rule that keeps hybrid from being *worse* than keyword-only:
it's an OUTER JOIN. A doc present in only one list still scores (its 1/(k+rank)
from that list, plus 0 from the others) — never an intersection, never a KeyError.
"""

from __future__ import annotations

from typing import Sequence


def rrf_fuse(ranked_lists: Sequence[Sequence[str]], *, k: int = 60,
             weights: Sequence[float] | None = None) -> list[tuple[str, float]]:
    """Fuse best-first id lists. Ranks are 1-based, dense, per-list; the first
    occurrence of an id in a list wins (dedup). Returns [(id, fused_score)] desc."""
    if weights is None:
        weights = [1.0] * len(ranked_lists)
    scores: dict[str, float] = {}
    for lst, w in zip(ranked_lists, weights):
        seen: set[str] = set()
        rank = 0
        for item in lst:
            if item in seen:
                continue
            seen.add(item)
            rank += 1
            scores[item] = scores.get(item, 0.0) + w / (k + rank)
    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
