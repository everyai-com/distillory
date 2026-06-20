"""`mem` — the CLI, 1:1 with the public API.

    mem add "text" --entity "David Chen"
    mem search "GTSI"
    mem profile "David Chen"
    mem entities
    mem synthesize "David Chen"
    mem doctor

Every command opens a Memory on --db (default: ./brain.db, or $DISTILLORY_DB).
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from . import __version__
from .engine import Memory


def _open(args) -> Memory:
    db = args.db or os.environ.get("DISTILLORY_DB", "brain.db")
    return Memory.open(db, synth=args.synth, embed=args.embed, schema=args.schema)


def _print_hit(h, *, body=False):
    tag = f"[{h.kind}]"
    cites = f"  ⟵ {', '.join(h.citations)}" if h.citations else ""
    print(f"{tag} {h.title}  (score {h.score:.3f}){cites}")
    if body and h.body:
        print(h.body)
    elif h.snippet:
        print(f"    {h.snippet.strip()[:160]}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="mem", description="distillory — local memory that synthesizes.")
    ap.add_argument("--version", action="version", version=f"distillory {__version__}")
    ap.add_argument("--db", default=None, help="path to the memory db (default ./brain.db)")
    ap.add_argument("--synth", default="auto", help="auto|none|claude|anthropic:<model>")
    ap.add_argument("--embed", default="fastembed", help="fastembed|potion|hash|none")
    ap.add_argument("--schema", default=None, help="path to an outcomes.md grading contract")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("add", help="add a source to an entity")
    p.add_argument("text")
    p.add_argument("--entity", "-e", required=True)
    p.add_argument("--source-ref", default="")
    p.add_argument("--event-date", default=None)
    p.add_argument("--entity-type", default="prospect")
    p.add_argument("--no-synth", action="store_true", help="don't auto-synthesize")

    p = sub.add_parser("search", help="hybrid keyword search")
    p.add_argument("query")
    p.add_argument("-k", type=int, default=8)
    p.add_argument("--kind", default=None, choices=["profile", "chunk"])
    p.add_argument("--body", action="store_true")

    p = sub.add_parser("profile", help="read one entity's living profile")
    p.add_argument("name")

    p = sub.add_parser("entities", help="list stored entities")
    p.add_argument("--stage", default=None)

    p = sub.add_parser("synthesize", help="(re)synthesize a profile")
    p.add_argument("name", nargs="?", default=None)
    p.add_argument("--all-dirty", action="store_true")

    sub.add_parser("dream", help="synthesize every dirty profile (alias: synthesize --all-dirty)")
    sub.add_parser("doctor", help="report engine state")

    p = sub.add_parser("ingest", help="ingest a file or folder")
    p.add_argument("path")
    p.add_argument("--entity", "-e", default=None)

    sp = sub.add_parser("serve", help="run as an MCP server (--mcp) or HTTP JSON API (--http)")
    sp.add_argument("--mcp", action="store_true", help="MCP server for Claude / agents (stdio)")
    sp.add_argument("--http", action="store_true", help="HTTP JSON API (or MCP-over-http with --mcp)")
    sp.add_argument("--host", default="127.0.0.1")
    sp.add_argument("--port", type=int, default=7878)
    sp.add_argument("--token", default=None, help="bearer token for the HTTP API")

    args = ap.parse_args(argv)
    try:
        mem = _open(args)
    except (ValueError, RuntimeError) as e:
        print(f"mem: {e}", file=sys.stderr)
        return 1

    try:
        if args.cmd == "add":
            if args.no_synth:
                mem.auto_synth = False
            res = mem.add(args.text, entity=args.entity, source_ref=args.source_ref,
                          event_date=args.event_date, entity_type=args.entity_type)
            print(f"added -> {res.slug}  (new_source={res.source_added}, dirty={res.dirty})")
        elif args.cmd == "search":
            hits = mem.search(args.query, k=args.k, kind=args.kind, body=args.body)
            if not hits:
                print("(no matches)")
            for h in hits:
                _print_hit(h, body=args.body)
        elif args.cmd == "profile":
            h = mem.profile(args.name)
            if not h:
                print(f"(no profile for '{args.name}')")
                return 1
            print(h.body or "(empty profile — run: mem synthesize)")
        elif args.cmd == "entities":
            ents = mem.entities(stage=args.stage)
            if not ents:
                print("(no entities yet)")
            for h in ents:
                flag = " *dirty" if h.meta.get("dirty") else ""
                print(f"- {h.title}  ({h.snippet}){flag}  [{h.slug}]")
        elif args.cmd in ("synthesize", "dream"):
            all_dirty = getattr(args, "all_dirty", False) or args.cmd == "dream"
            name = getattr(args, "name", None)
            done = mem.synthesize(entity=name, all_dirty=all_dirty) if (name or all_dirty) \
                else mem.synthesize(all_dirty=True)
            print(f"synthesized: {', '.join(done) or '(nothing)'}")
        elif args.cmd == "ingest":
            print(json.dumps(mem.ingest(args.path, entity=args.entity)))
        elif args.cmd == "doctor":
            print(json.dumps(mem.doctor(), indent=2))
        elif args.cmd == "serve":
            if args.mcp:
                from .adapters.mcp_server import serve as serve_mcp
                serve_mcp(mem, http=args.http, host=args.host, port=args.port)
            elif args.http:
                from .adapters.http_server import serve_http
                serve_http(mem, host=args.host, port=args.port, token=args.token)
            else:
                print("mem serve: pass --mcp (for Claude/agents) or --http", file=sys.stderr)
                return 2
        else:
            ap.print_help()
            return 2
    except (KeyError, ValueError, RuntimeError) as e:
        print(f"mem: {e}", file=sys.stderr)
        return 1
    finally:
        mem.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
