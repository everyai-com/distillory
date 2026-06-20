"""Hybrid retrieval — the default read path from slice 4 on.

Profiles (the already-reasoned answer) come first via the keyword ranker. Raw
chunks come next, retrieved BOTH by FTS5 keyword AND by dense cosine, fused with
RRF — so a meaning-only query and a literal-token query both land. Profiles and
chunks are fused as separate granularities, never interleaved incoherently.
"""

from __future__ import annotations

from ..models import Hit
from ..render.markdown import preview
from .fuse import rrf_fuse
from .keyword import retrieve_profiles

# Pull a deeper candidate pool per sub-list than the final k, so fusion has
# material to reorder.
_POOL = 24


def hybrid_retrieve(conn, chunk_store, profile_store, dense, query: str, *,
                    k: int = 8, kind: str | None = None, body: bool = False) -> list[Hit]:
    hits: list[Hit] = []
    seen_slugs: set[str] = set()

    # 1) Profiles — keyword ranker over synthesized content.
    if kind in (None, "profile"):
        for r in retrieve_profiles(conn, query, limit=k, min_terms=1):
            slug = r["slug"]
            seen_slugs.add(slug)
            md = r.get("content_md") or ""
            sources = profile_store.get(slug).get("sources", [])
            hits.append(Hit(
                slug=slug, title=r.get("name") or slug, score=float(r.get("score", 0)),
                snippet=preview(md), body=md if body else "", kind="profile",
                citations=[s["source_ref"] for s in sources],
                meta={"entity_type": r.get("entity_type"), "stage": r.get("stage")},
            ))

    # 2) Chunks — keyword + dense, RRF-fused (exact keyword weighted a touch above
    #    fuzzy semantic).
    if kind in (None, "chunk"):
        kw_uids = [c.chunk_uid for c in chunk_store.search_fts(query, limit=_POOL)]
        dn_uids = [uid for uid, _ in (dense.search(query, k=_POOL) if dense else [])]
        fused = rrf_fuse([kw_uids, dn_uids], weights=[1.0, 0.9])
        rows = chunk_store.by_uids([uid for uid, _ in fused])
        for uid, score in fused:
            ch = rows.get(uid)
            if ch is None or (ch.slug and ch.slug in seen_slugs):
                continue   # its profile already surfaced — don't double-count
            hits.append(Hit(
                slug=ch.slug, title=ch.source_ref or (ch.slug or "chunk"),
                score=float(score), snippet=ch.text[:200], body=ch.text if body else "",
                kind="chunk", source_ref=ch.source_ref, citations=[ch.source_ref],
            ))

    return hits[:k]
