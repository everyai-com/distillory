# distillory vs. other memory engines

An **architecture** comparison — what you have to run, what it depends on, and how
it treats memory. **No performance or recall numbers here**: distillory hasn't run
the public benchmarks yet, so it doesn't claim a score (that lands with the hybrid
retriever + a LongMemEval/LOCOMO harness — see the [CHANGELOG](../CHANGELOG.md)).
Every cell below was fact-checked against each project's own docs in June 2026;
where a project's docs don't say, it's marked `*`.

|  | distillory | mem0 | supermemory | gbrain | Zep / Graphiti | Letta |
|---|---|---|---|---|---|---|
| **Embeddable (no server)** | ✅ single in-process SQLite file | ✅ pip library | ❌ local HTTP server (`:6767`) | ✅ in-process (PGLite/WASM) | ❌ server + graph DB | ❌ server / agent runtime |
| **Default path runs offline, no key** | ✅ hash-embed + extractive | ❌ default LLM/embed = OpenAI | ❌ ingestion needs an LLM | ❌ default embed/rerank hosted | ❌ default OpenAI | ❌ needs LLM + embedder |
| **Storage** | one SQLite file | vector store (local Qdrant default) | embedded graph engine* | PGLite (Postgres-in-WASM) | external graph DB (Neo4j/FalkorDB/Neptune) | Postgres + pgvector |
| **Infra to run** | none — embed the file | pip + LLM key (+ bundled Qdrant) | self-host binary + an LLM | Bun runtime + a model | graph DB + LLM key | server + Postgres/pgvector + LLM |
| **License** | MIT (engine) | Apache-2.0 (engine) + paid cloud | MIT (engine) + paid cloud | MIT (engine) | Graphiti Apache-2.0; full Zep = cloud | Apache-2.0 (engine) + cloud |
| **Approach** | synthesize-at-ingestion, one per-entity profile | synthesize-at-ingestion, atomic facts | synthesize-at-ingestion | store-and-retrieve (synthesis on-demand/scheduled) | synthesize-at-ingestion (temporal graph) | store-and-retrieve |

## How distillory differs

- **In-process single file, not a server.** distillory links one SQLite file into
  your process. supermemory, Zep, and Letta run as separate servers; mem0 and
  gbrain are embeddable but carry a vector store (Qdrant) or PGLite under the hood.
- **Works with no key and no model server** on its default path (hash-embed +
  extractive synthesis). Every other engine here needs an LLM at ingestion by
  default — a cloud key or a separately-run local model.
- **No external database to stand up.** No Qdrant, no Postgres/pgvector, no Neo4j —
  just the file.
- **One schema-graded profile per entity, consolidated at write time** — versus
  mem0's atomic facts in a vector/graph store, or the store-and-retrieve engines
  that synthesize on demand.

## Be fair — caveats

This space moves fast and every project here is good at what it targets. Specifically:

- **mem0** is *not* a raw-log store — it runs an LLM-driven extract +
  ADD/UPDATE/DELETE/NOOP consolidation at ingestion, and it *can* run offline by
  swapping in Ollama + a local embedder. The "needs a key" note is about its
  **default** path. Its output is atomic facts, not one per-entity profile.
- **supermemory** is genuinely **open source (MIT)** and free to self-host — any
  older "closed core" framing is stale. Local embeddings run on-machine; only the
  ingestion pipeline needs an LLM. Its storage engine isn't disclosed, so we don't
  label it.
- **gbrain** runs in default mode with no server/Docker (PGLite is in-process) and
  can go offline with a local model. Its synthesis is on-demand/scheduled ("dream"),
  not per-entity at write.
- **Zep / Graphiti** — *Graphiti* (the temporal KG framework) is Apache-2.0; only
  the full managed Zep service is commercial cloud.
- **Letta** (ex-MemGPT) has an Apache-2.0 core; it's a server/agent runtime, an
  architectural difference, not a quality judgment.
- **cognee** (not in the table) is also pip-installable with embedded stores
  (Kuzu + LanceDB + SQLite), Apache-2.0, and needs an LLM by default — another good
  option in the embeddable camp.

Every "offline / no key" cell refers to each tool's **default** path. Most support
local operation through reconfiguration — the distinctions are about defaults and
architecture, not capability ceilings.

### Sources
mem0 · <https://docs.mem0.ai/open-source/overview> ·
supermemory · <https://github.com/supermemoryai/supermemory> ·
gbrain · <https://github.com/garrytan/gbrain> ·
Graphiti/Zep · <https://github.com/getzep/graphiti> ·
Letta · <https://github.com/letta-ai/letta> ·
cognee · <https://github.com/topoteretes/cognee>

Spot something out of date? [Open an issue](https://github.com/everyai-com/distillory/issues) — we'll fix it fast.
