"""
Wikilink graph extraction and traversal — zero LLM calls.

Every `[[wikilink]]` in a profile body is a typed edge. This module parses the
profiles in a distillory db's `content_md`, builds an in-memory graph, and lets
you walk it. Lifted from mbrain; adapted to read profile rows instead of a
folder of markdown files.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

WIKILINK_RE = re.compile(r"\[\[([a-z0-9][a-z0-9\-]*)\]\]")


@dataclass
class Graph:
    # slug -> {"title": str, "kind": str}
    nodes: dict[str, dict] = field(default_factory=dict)
    out_edges: dict[str, set[str]] = field(default_factory=dict)
    in_edges: dict[str, set[str]] = field(default_factory=dict)

    def neighbors(self, slug: str) -> set[str]:
        return self.out_edges.get(slug, set()) | self.in_edges.get(slug, set())

    def stats(self) -> dict:
        edge_count = sum(len(v) for v in self.out_edges.values())
        return {
            "nodes": len(self.nodes),
            "edges": edge_count,
            "orphans": sum(1 for s in self.nodes if not self.neighbors(s)),
        }

    def traverse(self, slug: str, *, depth: int = 2) -> dict[str, list[str]]:
        """BFS to N hops.  Returns {depth: [slugs]}."""
        out: dict[int, list[str]] = {0: [slug]}
        seen: set[str] = {slug}
        frontier: set[str] = {slug}
        for d in range(1, depth + 1):
            next_frontier: set[str] = set()
            for node in frontier:
                for n in self.neighbors(node):
                    if n in seen:
                        continue
                    seen.add(n)
                    next_frontier.add(n)
            if not next_frontier:
                break
            out[d] = sorted(next_frontier)
            frontier = next_frontier
        return {str(k): v for k, v in out.items()}


def build_graph(rows: list[tuple[str, str, str]]) -> Graph:
    """rows = [(slug, title, content_md), ...]."""
    g = Graph()
    for slug, title, _ in rows:
        g.nodes[slug] = {"title": title or slug, "kind": "profile"}
    for slug, _, body in rows:
        for m in WIKILINK_RE.finditer(body or ""):
            target = m.group(1)
            if target == slug:
                continue
            g.out_edges.setdefault(slug, set()).add(target)
            g.in_edges.setdefault(target, set()).add(slug)
    return g
