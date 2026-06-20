"""Memory — the facade. Four core verbs (add / search / profile / synthesize)
plus a few secondary reads, over one SQLite file.

Write path (`add`) is deterministic and LLM-free: resolve entity -> slug, append
an immutable source, chunk + embed + index, mark dirty. Judgment happens only in
`synthesize` (the dreamer). Read path (`search` / `profile`) never mutates.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from .config import MemoryConfig, load_schema
from .models import AddResult, Hit, Scope
from .providers import resolve_embedder, resolve_llm
from .render.markdown import slugify
from .retrieval.keyword import retrieve
from .store import ChunkStore, ProfileStore, connect, get_meta, init_db, set_meta
from .synthesis import ProfileSynthesizer


class Memory:
    def __init__(self, config: MemoryConfig | None = None, **kwargs):
        cfg = config or MemoryConfig.resolve(kwargs.pop("db_path", "brain.db"), **kwargs)
        self.config = cfg
        self.conn = connect(cfg.db_path)
        init_db(self.conn)

        self.embedder = resolve_embedder(cfg.embed)
        self.llm = resolve_llm(cfg.synth, model=cfg.model)
        self.schema = load_schema(cfg.schema)

        self.profiles = ProfileStore(self.conn)
        self.chunks = ChunkStore(self.conn, self.embedder)
        self.synth = ProfileSynthesizer(self.llm, schema=self.schema)
        self.auto_synth = bool(cfg.auto_synth)

        self._lock_embedder_identity()

    @classmethod
    def open(cls, db_path: str | Path = "brain.db", *, synth="auto", embed="fastembed",
             schema: str | None = None, model: str | None = None,
             dense_backend: str = "auto", auto_synth: bool = True) -> "Memory":
        return cls(MemoryConfig.resolve(
            db_path, synth=synth, embed=embed, schema=schema, model=model,
            dense_backend=dense_backend, auto_synth=auto_synth,
        ))

    # ── write path ──────────────────────────────────────────────────────────
    def add(self, text: str, *, entity: str | None = None, source_ref: str = "",
            event_date: str | None = None, scope: Scope = "personal",
            entity_type: str = "prospect", meta: dict | None = None) -> AddResult:
        text = (text or "").strip()
        if not text:
            raise ValueError("text is required")
        name = (entity or "note").strip()
        slug = slugify(name)
        if not source_ref:
            source_ref = "note:" + hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]

        self.profiles.ensure(slug, name=name, entity_type=entity_type)
        src = self.profiles.add_source(
            slug, source_ref, source_kind=(meta or {}).get("kind", "note"),
            event_date=event_date, summary=text[:2000],
        )
        source_added = bool(src.get("added"))
        self.chunks.add_chunk(slug, source_ref, text, event_date=event_date)
        self.profiles.mark_dirty(slug, True)

        dirty = True
        if self.auto_synth and source_added:
            self.synthesize(entity=slug)
            dirty = False
        return AddResult(slug=slug, dirty=dirty, source_added=source_added)

    def ingest(self, path: str, *, entity: str | None = None) -> dict:
        """Read a file (or every text file in a folder) and add it. Folder name
        (or file stem) is the entity unless `entity` is given."""
        p = Path(path).expanduser()
        added, files = 0, 0
        targets = sorted(p.rglob("*")) if p.is_dir() else [p]
        for f in targets:
            if not f.is_file():
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="replace").strip()
            except Exception:
                continue
            if not content:
                continue
            ent = entity or (p.name if p.is_dir() else f.stem)
            res = self.add(content, entity=ent, source_ref=f"file:{f}",
                           meta={"kind": "file"})
            files += 1
            added += 1 if res.source_added else 0
        return {"files": files, "added": added}

    # ── read path ───────────────────────────────────────────────────────────
    def search(self, query: str, *, k: int = 8, scope: Scope = "personal",
               kind: str | None = None, body: bool = False) -> list[Hit]:
        return retrieve(self.conn, self.chunks, self.profiles, query, k=k, kind=kind, body=body)

    def profile(self, name_or_slug: str) -> Hit | None:
        """Read ONE entity's full living profile, by human name or slug."""
        slug = self._resolve_slug(name_or_slug)
        got = self.profiles.get(slug)
        p = got.get("profile")
        if not p:
            return None
        name = self.profiles.name_for(slug) or slug
        body = p.get("content_md", "") or ""
        return Hit(
            slug=slug, title=name, score=1.0, snippet=body[:200], body=body,
            kind="profile", citations=[s["source_ref"] for s in got.get("sources", [])],
            meta={"entity_type": p.get("entity_type"), "stage": p.get("stage"),
                  "dirty": p.get("dirty")},
        )

    def entities(self, *, scope: Scope = "personal", stage: str | None = None) -> list[Hit]:
        out: list[Hit] = []
        for r in self.profiles.list()["profiles"]:
            if stage and r.get("stage") != stage:
                continue
            out.append(Hit(
                slug=r["slug"], title=r.get("name") or r["slug"], score=0.0,
                snippet=f"{r.get('entity_type')} · {r.get('stage')}",
                kind="profile",
                meta={"dirty": r.get("dirty"), "stage": r.get("stage"),
                      "entity_type": r.get("entity_type")},
            ))
        return out

    # ── synthesis (the dreamer) ───────────────────────────────────────────────
    def synthesize(self, *, entity: str | None = None, all_dirty: bool = False) -> list[str]:
        if all_dirty:
            slugs = [p["slug"] for p in self.profiles.list(dirty_only=True)["profiles"]]
        elif entity:
            slugs = [self._resolve_slug(entity)]
        else:
            raise ValueError("pass entity=... or all_dirty=True")

        done: list[str] = []
        for slug in slugs:
            got = self.profiles.get(slug)
            p = got.get("profile") or {}
            existing_md = p.get("content_md", "") or ""
            name = self.profiles.name_for(slug) or slug
            etype = p.get("entity_type", "prospect")
            sources_text = self.chunks.sources_text(slug) or \
                "(no new source text; refine the existing profile only)"
            md = self.synth.run(name, etype, existing_md, sources_text)
            if not md:
                continue
            from .synthesis import parse_front_matter
            fields = parse_front_matter(md)
            fields.setdefault("entity_type", etype)
            self.profiles.set_content(slug, md, fields, clear_dirty=True)
            done.append(slug)
        return done

    # ── introspection ─────────────────────────────────────────────────────────
    def doctor(self) -> dict:
        info = getattr(self.embedder, "info", None)
        return {
            "db_path": str(self.config.db_path),
            "profiles": len(self.profiles.list()["profiles"]),
            "chunks": self.chunks.count(),
            "synth": getattr(self.llm, "name", "none"),
            "embed_model": getattr(info, "model_id", "none") if info else "none",
            "embed_dim": getattr(info, "dim", 0) if info else 0,
            "auto_synth": self.auto_synth,
            "schema": "custom" if self.schema else "default",
        }

    def close(self) -> None:
        self.conn.close()

    # ── internals ─────────────────────────────────────────────────────────────
    def _resolve_slug(self, name_or_slug: str) -> str:
        x = (name_or_slug or "").strip()
        if not x:
            raise ValueError("name or slug is required")
        if self.profiles.exists(x):
            return x
        s = slugify(x)
        return s

    def _lock_embedder_identity(self) -> None:
        info = getattr(self.embedder, "info", None)
        model_id = getattr(info, "model_id", "none") if info else "none"
        dim = getattr(info, "dim", 0) if info else 0
        existing = get_meta(self.conn, "embed_model")
        if existing is None:
            set_meta(self.conn, "embed_model", model_id)
            set_meta(self.conn, "embed_dim", str(dim))
        elif existing != model_id and model_id != "none" and existing != "none":
            # Different model than this db was built with — vectors are
            # incompatible even at the same dim. Slice 5 adds `mem reembed`.
            import warnings
            warnings.warn(
                f"db was indexed with embed_model='{existing}' but this session uses "
                f"'{model_id}'. Dense recall will degrade until you re-embed.",
                stacklevel=2,
            )
