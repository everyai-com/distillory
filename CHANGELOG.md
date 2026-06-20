# Changelog

All notable changes to distillory are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); versions follow
[SemVer](https://semver.org/).

## [Unreleased]

### Planned (sliced, highest-leverage first)
- **Slice 7** — nightly "dreaming": dirty-only re-synthesis, decay, gap-hunting.
- **Slice 10** — LongMemEval / LOCOMO benchmark harness.

## [0.1.0] — 2026-06-20

First public cut. One embeddable SQLite file; numpy is the only base dependency.

### Added
- **Core engine** — four verbs (`add`, `search`, `profile`, `synthesize`) plus
  `entities`, `ledger`, `ingest`, `graph`, `doctor` over a single SQLite file.
- **Schema-graded synthesis** — one living, two-tier profile per entity; bring an
  LLM (Anthropic via stdlib urllib, or any `.complete()`/`.synthesize()` object)
  or run the offline extractive floor with no key.
- **Fact-ledger grader** — synthesis is *validated* against the schema, with one
  repair-retry before falling back to extractive (never stores a corrupt profile).
  The `## Ledger` section is parsed into structured, **edge-typed**
  (`assert/update/extend/derive`), temporally-grounded rows with a status, so
  contradiction resolution (a superseded fact) is queryable via `ledger()` /
  `mem ledger` — covered by an offline CI gate.
- **Probe-and-degrade providers** — `synth="auto"` and the embedder ladder fall
  through to an always-available floor; works fully offline (`synth="none"`,
  `embed="hash"`).
- **Hybrid retrieval** — FTS5 BM25 keyword + dense cosine, fused with Reciprocal
  Rank Fusion (outer-join). Dense is brute-force numpy over BLOB vectors (no
  sqlite extension needed), backed by a resident matrix with a generation counter
  so a just-added chunk is searchable immediately. Embedders: bge-small ONNX
  (`fastembed`) / potion (`model2vec`) / an always-available hash floor, with a
  fall-through ladder. `doctor()` reports vector count + resident MB. Profiles
  rank first (the already-reasoned answer), then fused chunks, cited.
- **MCP server** (`mem serve --mcp`) — `memory_add/search/profile/entities/`
  `synthesize/graph` + a `memory://profile/{slug}` resource, for Claude / agents.
- **HTTP server** (`mem serve --http`) — zero-dependency JSON API (`/v1/*`).
- **`mem` CLI**, 1:1 with the API. Typed package (`py.typed`).

### Notes
- Retrieval is keyword-only in 0.1.0; dense + RRF hybrid is slice 4. No benchmark
  numbers are claimed until that ships and is measured.
