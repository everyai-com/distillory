"""Keyword retrieval — the always-on base read path.

Two rankers, both lifted from validated code:
  • profile ranker  ⇐ the app's `workspace.retrieve_profiles` (distinct-term
    ranking, identity-weighted head, min-terms gate) — verbatim.
  • chunk ranker    ⇐ mbrain's FTS5 BM25 (via ChunkStore.search_fts).

slice 1 merges them simply: synthesized profiles first (the already-reasoned
answer), then raw chunks (the literal/cross-entity tail). Dense cosine + RRF
fusion over the same data lands in slice 4 — this stays the keyword floor.
"""

from __future__ import annotations

import re
import sqlite3

from ..models import Hit


def retrieve_profiles(conn: sqlite3.Connection, query: str, limit: int = 3,
                      min_terms: int = 1) -> list[dict]:
    """Keyword-rank synthesized profiles by relevance to a query. Local, no deps,
    no embeddings. Ranks by DISTINCT query terms matched first (then frequency,
    identity-weighted), dropping profiles under `min_terms` distinct matches."""
    terms = list(dict.fromkeys(re.findall(r"[a-z0-9]{3,}", (query or "").lower())))[:24]
    if not terms:
        return []
    floor = max(1, int(min_terms))
    rows = conn.execute(
        "SELECT slug, name, entity_type, stage, next_action_date, content_md "
        "FROM profiles WHERE content_md != ''"
    ).fetchall()
    scored: list[tuple[int, int, sqlite3.Row]] = []
    for r in rows:
        text = (r["content_md"] or "").lower()
        if not text:
            continue
        matched = [t for t in terms if t in text]
        if len(matched) < floor:
            continue
        head = text[:240]  # identity/company live up top — weight those matches
        score = sum(text.count(t) for t in matched) + 4 * sum(head.count(t) for t in matched)
        scored.append((len(matched), score, r))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [{
        "slug": r["slug"], "name": r["name"], "entity_type": r["entity_type"],
        "stage": r["stage"], "next_action_date": r["next_action_date"],
        "content_md": r["content_md"], "score": score, "matched_terms": distinct,
    } for distinct, score, r in scored[:max(1, int(limit))]]


def retrieve(conn, chunk_store, profile_store, query: str, *, k: int = 8,
             kind: str | None = None, body: bool = False) -> list[Hit]:
    """Hybrid-shaped read (keyword-only in slice 1): profiles first, then chunks."""
    hits: list[Hit] = []
    seen_slugs: set[str] = set()

    if kind in (None, "profile"):
        for r in retrieve_profiles(conn, query, limit=k, min_terms=1):
            slug = r["slug"]
            seen_slugs.add(slug)
            md = r.get("content_md") or ""
            sources = profile_store.get(slug).get("sources", [])
            hits.append(Hit(
                slug=slug,
                title=r.get("name") or slug,
                score=float(r.get("score", 0)),
                snippet=md[:200],
                body=md if body else "",
                kind="profile",
                citations=[s["source_ref"] for s in sources],
                meta={"entity_type": r.get("entity_type"), "stage": r.get("stage")},
            ))

    if kind in (None, "chunk"):
        for ch in chunk_store.search_fts(query, limit=k):
            hits.append(Hit(
                slug=ch.slug,
                title=ch.source_ref or (ch.slug or "chunk"),
                score=ch.score,
                snippet=ch.text[:200],
                body=ch.text if body else "",
                kind="chunk",
                source_ref=ch.source_ref,
                citations=[ch.source_ref],
            ))

    return hits[:k]
