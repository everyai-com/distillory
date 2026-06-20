"""The shared adapter surface — JSON-serializable wrappers over the four verbs.

Every adapter (MCP, HTTP, agent hooks) is a thin translation onto THESE functions
so there's exactly one place the verbs live. If an adapter grows logic, the logic
belongs back in the engine.
"""

from __future__ import annotations

from ..models import Hit


def _hit(h: Hit) -> dict:
    return {
        "slug": h.slug,
        "title": h.title,
        "kind": h.kind,
        "score": round(h.score, 4),
        "snippet": h.snippet,
        "body": h.body or None,
        "citations": h.citations,
        "event_date": h.event_date,
        "meta": h.meta,
    }


def add(mem, text: str, entity: str, source_ref: str = "", event_date: str | None = None,
        entity_type: str = "prospect") -> dict:
    r = mem.add(text, entity=entity, source_ref=source_ref, event_date=event_date,
                entity_type=entity_type)
    return {"slug": r.slug, "source_added": r.source_added, "dirty": r.dirty}


def search(mem, query: str, k: int = 8, kind: str | None = None) -> dict:
    return {"results": [_hit(h) for h in mem.search(query, k=k, kind=kind)]}


def profile(mem, name_or_slug: str) -> dict:
    h = mem.profile(name_or_slug)
    if not h:
        return {"error": f"no profile for {name_or_slug!r}"}
    return {"profile": _hit(h)}


def entities(mem, stage: str | None = None) -> dict:
    return {"entities": [{"slug": h.slug, "name": h.title, **h.meta} for h in mem.entities(stage=stage)]}


def synthesize(mem, entity: str | None = None, all_dirty: bool = False) -> dict:
    try:
        return {"synthesized": mem.synthesize(entity=entity, all_dirty=all_dirty)}
    except (KeyError, ValueError) as e:
        return {"error": str(e)}


def graph(mem, name_or_slug: str, depth: int = 2) -> dict:
    return mem.graph(name_or_slug, depth=depth)


def ledger(mem, name_or_slug: str) -> dict:
    return {"ledger": mem.ledger(name_or_slug)}
