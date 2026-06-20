# distillory

**The local-first memory engine that synthesizes at ingestion — not just stores.**

Most "AI memory" is a logging layer with a vector index bolted on: it accumulates
facts and re-derives meaning on every query. `distillory` reasons **once, at
ingestion** — each new source updates one *living, schema-graded profile per
entity*, resolving contradictions and grounding facts in time, so every later
read is cheap and already-reasoned.

One embeddable **SQLite file**. No server, no Docker, no Postgres, no hosted
reranker. Bring your own model (Claude, an API key, or local) — or none. **MIT,
engine included.**

```bash
pip install distillory      # one base dep (numpy). FTS5 + hash-embed + extractive synthesis work offline, zero config.
```

```python
from distillory import Memory

mem = Memory.open("brain.db")
mem.add("Met David at LucidWay — wants the GTSI automation, budget ~$10k", entity="David Chen")
print(mem.profile("David Chen").body)     # a synthesized profile, not a raw echo
```

Add a second source and the profile **compounds** instead of duplicating:

```python
mem.add("David is based in New York", entity="David Chen", event_date="2026-05-01")
mem.add("David just moved to London", entity="David Chen", event_date="2026-06-18")
mem.synthesize(entity="David Chen")
# the profile updates "New York → London" with provenance, instead of storing two contradictory facts
```

Fully offline, no key, nothing downloaded:

```python
mem = Memory.open("brain.db", synth="none", embed="hash")   # keyword + extractive, true air-gap floor
```

With synthesis (set `ANTHROPIC_API_KEY`, or pass `synth="anthropic:<model>"` / your own):

```python
mem = Memory.open("brain.db", synth="auto")   # uses your Anthropic key if present; degrades gracefully if not
```

## The four verbs

| Verb | What it does |
|---|---|
| `add(text, entity=...)` | Append an **immutable** source, chunk + embed + index, mark dirty. Deterministic, no LLM. |
| `search(query, k=8)` | Keyword (FTS5 BM25) read; dense + RRF hybrid lands next. Returns cited `Hit`s. |
| `profile(name_or_slug)` | Read **one** entity's full living profile — the cheap, already-reasoned answer. |
| `synthesize(entity=...)` | The dreamer: (re)synthesize a profile against the schema. The one expensive verb. |

Plus `entities()`, `ingest(path)`, `doctor()`, and the `mem` CLI (1:1 with the API).

## Plug it into Claude / agents (MCP)

`distillory` speaks [MCP](https://modelcontextprotocol.io), so Claude Code, Claude
Desktop, or any MCP client gets persistent, *synthesizing* memory in one line:

```bash
pip install "distillory[mcp]"
```

```jsonc
// ~/.claude.json
{ "mcpServers": { "memory": {
    "command": "mem",
    "args": ["serve", "--mcp", "--db", "~/brain.db"]
} } }
```

It exposes `memory_add`, `memory_search`, `memory_profile`, `memory_entities`,
`memory_synthesize`, and `memory_graph`, plus a `memory://profile/{slug}`
resource. stdio by default — no network, no port, no key.

Not on Python? A zero-dependency HTTP API mirrors the same verbs:

```bash
mem serve --http --port 7878    # POST /v1/add · /v1/search · /v1/profile · /v1/synthesize · GET /v1/health
```

## The schema is the trick

Every synthesis is graded against a schema — a definition of what a *complete*
profile looks like — read before every write. Pass your own:

```python
mem = Memory.open("brain.db", schema="./outcomes.md")
```

Without it, synthesis drifts to a generic standard. With it, every write is held
to *your* rules. That's the difference from a notes file, and from hand-authored
skills.

## Bring your own internals

```python
mem = Memory.open("brain.db", synth=MyOllamaSynth(), embed=MyEmbedder())
```

`synth` accepts `"auto" | "none" | "claude" | "anthropic:<model>" | "ollama:<model>"`
or any object with `.complete()` / `.synthesize()`. `embed` accepts
`"fastembed" | "potion" | "hash" | "none"` or any object with `.embed()`. Both
fall through to an always-available floor, so a bare offline machine still works.

## Status

This is **v0.1**: the keyword core, the schema-graded synthesis loop (LLM or
extractive), one SQLite file, the `mem` CLI, and an **MCP + HTTP server** so any
Claude / agent gets persistent memory today. On the roadmap, in order: the
structured fact ledger + contradiction grader (makes contradiction-resolution a
*mechanism*, not a claim), dense (fastembed) + RRF hybrid retrieval, the nightly
"dreaming" gap pass, and LongMemEval / LOCOMO benchmarks. We don't pitch
"hybrid" or numbers we haven't run yet.

Heir to [mbrain](https://github.com/everyai-com/mbrain) (keyword-only); the
synthesis engine is extracted from a production desktop app.

## License

MIT.
