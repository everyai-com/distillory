# distillory

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![CI](https://github.com/everyai-com/distillory/actions/workflows/ci.yml/badge.svg)](https://github.com/everyai-com/distillory/actions/workflows/ci.yml)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

**The local-first memory engine that synthesizes at ingestion — not just stores.**

Most "AI memory" is a logging layer with a vector index bolted on: it accumulates
facts and re-derives meaning on every query. `distillory` reasons **once, at
ingestion** — each new source updates one *living, schema-graded profile per
entity*, resolving contradictions and grounding facts in time, so every later read
is cheap and already-reasoned.

One embeddable **SQLite file**. No server, no Docker, no Postgres, no hosted
reranker. Runs **offline with no API key** out of the box; bring your own model
(Claude, an API key, or local) when you want real synthesis. **MIT, engine included.**

```python
from distillory import Memory

mem = Memory.open("brain.db")          # one file. works with zero config.
mem.add("Met David at LucidWay — wants the GTSI automation, ~$10k", entity="David Chen")
print(mem.profile("David Chen").body)  # a synthesized profile, not a raw echo
```

---

## Install

> Not on PyPI yet — install from the repo (works today). `pip install distillory` lands with the first release.

```bash
# core (numpy is the only dependency): FTS5 keyword + hash-embed + offline synthesis
pip install "distillory @ git+https://github.com/everyai-com/distillory"

# with the MCP server (for Claude / agents)
pip install "distillory[mcp] @ git+https://github.com/everyai-com/distillory"

# with real embeddings (bge-small ONNX) + Anthropic synthesis  [hybrid retrieval: slice 4]
pip install "distillory[embed-fastembed,llm-anthropic] @ git+https://github.com/everyai-com/distillory"
```

| Extra | Adds |
|---|---|
| _(none)_ | FTS5 keyword search, hash-embed, extractive synthesis — fully offline |
| `mcp` | the `mem serve --mcp` server for Claude / any MCP client |
| `llm-anthropic` | the `anthropic` SDK (a stdlib fallback works without it) |
| `embed-fastembed` | `bge-small` ONNX embeddings (≈130 MB model on first run) |
| `llm-ollama` · `llm-openai` | other synthesis providers |
| `vec` | `sqlite-vec` accelerator for large corpora |

## 60-second tour (offline, no key)

```python
from distillory import Memory

mem = Memory.open("brain.db", synth="none", embed="hash")   # true air-gap floor

# Two notes, dropped as they happen — they COMPOUND into one profile.
mem.add("David at LucidWay wants the GTSI automation, ~$10k", entity="David Chen")
mem.add("Follow-up: confirmed, also wants a dashboard. Based in New York.", entity="David Chen")

print(mem.profile("David Chen").body)        # one living profile
for h in mem.search("GTSI dashboard"):       # cited recall, profile first
    print(h.kind, h.title, "<-", h.citations)
```

With a key, the profile is genuinely synthesized and **self-corrects**:

```python
mem = Memory.open("brain.db", synth="auto")  # uses ANTHROPIC_API_KEY if present
mem.add("David is based in New York",  entity="David Chen", event_date="2026-05-01")
mem.add("David just moved to London",  entity="David Chen", event_date="2026-06-18")
mem.synthesize(entity="David Chen")
# profile now reads "London (moved 2026-06, was NY)" — not two contradictory facts
mem.ledger("David Chen")   # the NY 'assert' is now [superseded] by a London 'update' — queryable
```

More in [`examples/`](examples/).

## The four verbs

| Verb | What it does |
|---|---|
| `add(text, entity=...)` | Append an **immutable** source, chunk + embed + index, mark dirty. Deterministic, no LLM. |
| `search(query, k=8)` | Cited recall — synthesized profiles first, then raw chunks. (Dense + RRF hybrid: slice 4.) |
| `profile(name_or_slug)` | Read **one** entity's full living profile — the cheap, already-reasoned answer. |
| `synthesize(entity=...)` | The dreamer: (re)synthesize a profile against the schema. The one expensive verb. |

Plus `entities()`, `ledger()` (the structured edge-typed facts behind a profile),
`ingest(path)`, `graph()`, `doctor()`, and the `mem` CLI (1:1 with the API).

## Plug it into Claude / agents (MCP)

`distillory` speaks [MCP](https://modelcontextprotocol.io), so Claude Code, Claude
Desktop, or any MCP client gets persistent, *synthesizing* memory in one line:

```jsonc
// ~/.claude.json
{ "mcpServers": { "memory": {
    "command": "mem",
    "args": ["serve", "--mcp", "--db", "~/brain.db"]
} } }
```

Tools `memory_add / search / profile / entities / synthesize / graph` + a
`memory://profile/{slug}` resource. stdio by default — no network, no port, no key.
Full guide: [`examples/mcp_with_claude.md`](examples/mcp_with_claude.md). Non-Python
callers can use the zero-dep HTTP API: `mem serve --http`.

## The schema is the trick

Every synthesis is graded against a schema — a definition of what a *complete*
profile looks like, read before every write. Pass your own:

```python
mem = Memory.open("brain.db", schema="./outcomes.md")
```

Without it, synthesis drifts to a generic standard. With it, every write is held to
*your* rules. That's the difference from a notes file, and from hand-authored skills.

## Bring your own model

```python
mem = Memory.open("brain.db", synth=MyOllamaSynth(), embed=MyEmbedder())
```

`synth` takes `"auto" | "none" | "claude" | "anthropic:<model>" | "ollama:<model>"`
or any object with `.complete()` / `.synthesize()`. `embed` takes
`"fastembed" | "potion" | "hash" | "none"` or any object with `.embed()`. Both fall
through to an always-available floor, so a bare offline machine still works.

## How it compares

Architecture, not benchmarks (we don't claim a recall number until we've run one —
see [the roadmap](CHANGELOG.md)). Full table + caveats + sources in
[`docs/COMPARISON.md`](docs/COMPARISON.md).

|  | distillory | mem0 | supermemory | Letta |
|---|---|---|---|---|
| Embeddable (no server) | ✅ one SQLite file | ✅ pip + Qdrant | ❌ local server | ❌ server |
| Default offline, no key | ✅ | ❌ (OpenAI default) | ❌ (LLM at ingest) | ❌ |
| Infra to run | none | pip + LLM key | self-host binary + LLM | Postgres/pgvector + LLM |
| Approach | one per-entity profile | atomic facts | synthesize | store-and-retrieve |

All of these are good tools — the distinctions are about **defaults and
architecture** (embeddable, offline, single-file), not capability ceilings. See the
caveats doc; we keep it fair and up to date.

## Status

**v0.1**: the keyword core, **schema-graded synthesis with a fact-ledger grader**
(validate→repair→retry, then contradiction resolution persisted as structured,
edge-typed rows — `mem ledger`), one SQLite file, the `mem` CLI, and an **MCP +
HTTP server** so any Claude / agent gets persistent memory today. Roadmap, in
order: dense (fastembed) + RRF hybrid retrieval, the nightly "dreaming" gap pass,
and LongMemEval / LOCOMO benchmarks. We don't pitch "hybrid" or numbers we haven't run.

Heir to [mbrain](https://github.com/everyai-com/mbrain) (keyword-only); the
synthesis engine is extracted from a production desktop app.

## Contributing

Small, typed, honest — see [CONTRIBUTING.md](CONTRIBUTING.md). `make install && make test`
(22 tests, all offline, no key). Issues and PRs welcome.

## License

[MIT](LICENSE).
