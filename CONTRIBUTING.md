# Contributing to distillory

Thanks for being here. distillory aims to be the memory engine you can read in an
afternoon and trust in production — small, typed, honest. Contributions that keep
it that way are very welcome.

## Dev setup

```bash
git clone https://github.com/everyai-com/distillory
cd distillory
python3.10 -m venv .venv && source .venv/bin/activate
make install        # editable install with dev + mcp extras
make test           # 22 tests, all offline
make lint
```

No API key is needed to develop or test — the suite runs on the offline floor
(`synth="none"`, `embed="hash"`).

## Project layout

```
src/distillory/
  engine.py        the Memory facade — the four verbs live here
  store/           SQLite: db, schema (DDL), profiles, chunks
  retrieval/       keyword.py (FTS5 + profile ranker); dense + RRF land in slice 4
  synthesis/       schema (the grading contract), prompt, frontmatter, synthesizer
  providers/       pluggable LLM + embedder, with probe-and-degrade resolvers
  adapters/        thin wrappers onto the verbs: mcp_server, http_server, tools
  render/          slug/frontmatter/wikilink + graph (lifted from mbrain)
```

The roadmap is sliced — see [CHANGELOG.md](CHANGELOG.md) and the build spec. Open
slices: structured fact-ledger grader (2), dense+RRF hybrid (4), dreaming/gaps (7),
LongMemEval/LOCOMO bench (10).

## Two rules that keep the design honest

1. **Adapters are thin.** Anything in `adapters/` must be a translation onto the
   four verbs. If you're writing logic there, it belongs in the engine.
2. **No claim outruns the code.** Don't add a comparison cell, a benchmark number,
   or a README promise for something that isn't shipped and tested. The repo is
   scoped to what runs today on purpose.

## Adding a provider (LLM or embedder)

Implement the one-method protocol in `providers/base.py` and add a branch to the
resolver in `providers/__init__.py`. Every resolver path must end in an
always-available floor — never raise on a bare machine for the `"auto"` path.

## Pull requests

- `make lint && make test` must pass; add a test for the behavior you change.
- Keep diffs focused; match the surrounding style.
- New runtime dependencies need a strong reason — `numpy` is the only base dep,
  everything else is an extra.

## Reporting bugs

Open an issue with the smallest snippet that reproduces it and the output of
`mem doctor`. Security-sensitive reports: please email rather than open a public
issue.
