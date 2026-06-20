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

This is **v0.1 (slice 1)**: the keyword core, the schema-graded synthesis loop
(LLM or extractive), one SQLite file, the `mem` CLI. On the roadmap, in order:
the structured fact ledger + contradiction grader, dense (fastembed) + RRF hybrid
retrieval, the nightly "dreaming" gap pass, and an **MCP server** so any Claude /
agent gets persistent memory. Comparison benchmarks (LongMemEval / LOCOMO) ship
with the hybrid retriever — we don't pitch numbers we haven't run.

Heir to [mbrain](https://github.com/everyai-com/mbrain) (keyword-only); the
synthesis engine is extracted from a production desktop app.

## License

MIT.
