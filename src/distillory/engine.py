"""Memory — the facade. Four core verbs (add / search / profile / synthesize)
plus a few secondary reads, over one SQLite file.

Write path (`add`) is deterministic and LLM-free: resolve entity -> slug, append
an immutable source, chunk + embed + index, mark dirty. Judgment happens only in
`synthesize` (the dreamer). Read path (`search` / `profile`) never mutates.
"""

from __future__ import annotations

import hashlib
import threading
from pathlib import Path

from .config import MemoryConfig, load_schema
from .models import AddResult, Hit, Scope
from .providers import resolve_embedder, resolve_llm
from .render.graph import build_graph
from .render.markdown import preview, slugify
from .retrieval import NumpyBruteForce, hybrid_retrieve
from .store import ChunkStore, LedgerStore, ProfileStore, connect, get_meta, init_db, set_meta
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
        self.ledger_store = LedgerStore(self.conn)
        self.dense = NumpyBruteForce(self.conn, self.embedder)
        self.synth = ProfileSynthesizer(self.llm, schema=self.schema)
        self.auto_synth = bool(cfg.auto_synth)
        self._lock = threading.RLock()   # serialize writes (server shares one conn across threads)

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

        with self._lock:
            # One atomic unit: ensure + add_source + add_chunk commit together, so
            # a crash mid-add can't leave a citation pointing at an unwritten chunk.
            # The lock also protects the stores' shared autocommit toggle.
            self.profiles.autocommit = self.chunks.autocommit = False
            try:
                self.profiles.ensure(slug, name=name, entity_type=entity_type)
                src = self.profiles.add_source(
                    slug, source_ref, source_kind=(meta or {}).get("kind", "note"),
                    event_date=event_date, summary=text[:2000],
                )
                source_added = bool(src.get("added"))
                self.chunks.add_chunk(slug, source_ref, text, event_date=event_date)
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise
            finally:
                self.profiles.autocommit = self.chunks.autocommit = True

            # add_source already set dirty=1 IFF the source was new; a no-op add does
            # NOT re-dirty (keeps the "idle nights ~ 0 tokens" guarantee honest).
            dirty = source_added
            if self.auto_synth and source_added:
                self.synthesize(entity=slug)   # RLock is reentrant
                dirty = False
            return AddResult(slug=slug, dirty=dirty, source_added=source_added)

    def ingest(self, path: str, *, entity: str | None = None,
               max_bytes: int = 2_000_000) -> dict:
        """Read a file (or every text file in a folder) and add it. Folder name
        (or file stem) is the entity unless `entity` is given. Skips files over
        `max_bytes` and anything that looks binary, so a stray PNG or a huge log
        can't poison the index or OOM the process. (Token-bounded chunking lands
        in slice 4 — for now each file is one chunk.)"""
        p = Path(path).expanduser()
        added, files, skipped = 0, 0, 0
        targets = sorted(p.rglob("*")) if p.is_dir() else [p]
        for f in targets:
            if not f.is_file():
                continue
            try:
                if f.stat().st_size > max_bytes:
                    skipped += 1
                    continue
                raw = f.read_bytes()
                if b"\x00" in raw[:8192]:        # NUL in the head -> binary, skip
                    skipped += 1
                    continue
                content = raw.decode("utf-8", errors="replace").strip()
            except Exception:
                skipped += 1
                continue
            # Too many replacement chars -> not really text.
            if not content or content.count("�") > max(20, len(content) // 20):
                skipped += 1
                continue
            ent = entity or (p.name if p.is_dir() else f.stem)
            res = self.add(content, entity=ent, source_ref=f"file:{f}", meta={"kind": "file"})
            files += 1
            added += 1 if res.source_added else 0
        return {"files": files, "added": added, "skipped": skipped}

    # ── read path ───────────────────────────────────────────────────────────
    def search(self, query: str, *, k: int = 8, scope: Scope = "personal",
               kind: str | None = None, body: bool = False) -> list[Hit]:
        return hybrid_retrieve(self.conn, self.chunks, self.profiles, self.dense, query,
                               k=max(1, int(k)), kind=kind, body=body)

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
            slug=slug, title=name, score=1.0, snippet=preview(body), body=body,
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
        from .synthesis import parse_front_matter, parse_ledger
        with self._lock:
            if all_dirty:
                slugs = [p["slug"] for p in self.profiles.list(dirty_only=True)["profiles"]]
            elif entity:
                slug = self._resolve_slug(entity)
                if not self.profiles.exists(slug):
                    # Don't fabricate a phantom profile from a typo'd name.
                    raise KeyError(f"no such entity: {entity!r} — add a source for it first")
                slugs = [slug]
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
                fields = parse_front_matter(md)
                fields.setdefault("entity_type", etype)
                # Persist the profile markdown and its structured ## Ledger mirror
                # in ONE transaction, so the prose and the queryable rows can't diverge.
                self.profiles.autocommit = self.ledger_store.autocommit = False
                try:
                    self.profiles.set_content(slug, md, fields, clear_dirty=True)
                    self.ledger_store.set_for_slug(slug, parse_ledger(md))
                    self.conn.commit()
                except Exception:
                    self.conn.rollback()
                    raise
                finally:
                    self.profiles.autocommit = self.ledger_store.autocommit = True
                done.append(slug)
            return done

    def ledger(self, name_or_slug: str) -> list[dict]:
        """The structured, edge-typed fact ledger for one entity (newest first in
        the profile; insertion order here). Each row: edge, statement, source_ref,
        doc_date, event_date, status — so superseded facts are queryable."""
        return self.ledger_store.for_slug(self._resolve_slug(name_or_slug))

    def graph(self, name_or_slug: str, *, depth: int = 2) -> dict:
        """Traverse the [[wikilink]] graph between profiles, from one entity."""
        rows = [
            (r["slug"], r["name"] or r["slug"], r["content_md"])
            for r in self.conn.execute("SELECT slug, name, content_md FROM profiles").fetchall()
        ]
        g = build_graph(rows)
        slug = self._resolve_slug(name_or_slug)
        if slug not in g.nodes:
            return {"error": f"no such entity: {name_or_slug!r}", "stats": g.stats()}
        return {
            "start": slug, "depth": depth,
            "neighbors": sorted(g.neighbors(slug)),
            "layers": g.traverse(slug, depth=depth),
            "stats": g.stats(),
        }

    # ── introspection ─────────────────────────────────────────────────────────
    def doctor(self) -> dict:
        info = getattr(self.embedder, "info", None)
        uids, _mat, _ = self.dense.cache.get()
        return {
            "db_path": str(self.config.db_path),
            "profiles": len(self.profiles.list()["profiles"]),
            "chunks": self.chunks.count(),
            "ledger": self.ledger_store.count(),
            "vectors": len(uids),
            "dense_backend": "numpy-bruteforce",
            "resident_mb": self.dense.cache.resident_mb(),
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
                f"'{model_id}'; the vectors are incompatible and dense recall will "
                f"silently degrade. Until `mem reembed` lands (slice 5), use the "
                f"original embedder or rebuild the db.",
                stacklevel=2,
            )
