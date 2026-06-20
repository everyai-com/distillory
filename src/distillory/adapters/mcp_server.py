"""MCP server — the distribution channel.

`mem serve --mcp` exposes distillory's four verbs as MCP tools over stdio, so
Claude Code, Claude Desktop, or any MCP client gets persistent, synthesizing
memory in one config line:

    // ~/.claude.json
    { "mcpServers": { "memory": { "command": "mem", "args": ["serve","--mcp","--db","~/brain.db"] } } }

Tools map 1:1 to the verbs (tools.py). Tool descriptions are written as standing
instructions so the model actually calls them. Needs the [mcp] extra:
`pip install "distillory[mcp]"`.
"""

from __future__ import annotations

from . import tools


def build_server(mem):
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as e:  # pragma: no cover - exercised only without the extra
        raise RuntimeError(
            "MCP support needs the extra: pip install \"distillory[mcp]\""
        ) from e

    server = FastMCP("distillory")

    @server.tool(
        description="Store a durable fact about an entity (a person, company, project). "
        "Call this whenever the user states something worth remembering long-term. "
        "Synthesis into the entity's living profile runs automatically."
    )
    def memory_add(text: str, entity: str, event_date: str | None = None,
                   entity_type: str = "prospect") -> dict:
        return tools.add(mem, text, entity=entity, event_date=event_date, entity_type=entity_type)

    @server.tool(
        description="Search memory and get back cited hits — synthesized profiles first "
        "(the already-reasoned answer), then raw chunks. Call before answering anything "
        "that might depend on remembered context."
    )
    def memory_search(query: str, k: int = 8, kind: str | None = None) -> dict:
        return tools.search(mem, query, k=k, kind=kind)

    @server.tool(
        description="Read ONE entity's full synthesized profile by human name or slug. "
        "Use when the user asks about a specific person/company you may have notes on."
    )
    def memory_profile(name_or_slug: str) -> dict:
        return tools.profile(mem, name_or_slug)

    @server.tool(description="List the entities currently stored in memory.")
    def memory_entities(stage: str | None = None) -> dict:
        return tools.entities(mem, stage=stage)

    @server.tool(
        description="(Re)synthesize an entity's profile from its sources, or every "
        "dirty profile with all_dirty=true. The one expensive call."
    )
    def memory_synthesize(entity: str | None = None, all_dirty: bool = False) -> dict:
        return tools.synthesize(mem, entity=entity, all_dirty=all_dirty)

    @server.tool(description="Traverse the [[wikilink]] graph from one entity out to N hops.")
    def memory_graph(name_or_slug: str, depth: int = 2) -> dict:
        return tools.graph(mem, name_or_slug, depth=depth)

    @server.resource("memory://profile/{slug}")
    def profile_resource(slug: str) -> str:
        """A synthesized profile, mountable straight into a client's context."""
        h = mem.profile(slug)
        return h.body if h else f"(no profile for {slug!r})"

    return server


def serve(mem, *, http: bool = False, host: str = "127.0.0.1", port: int = 7878) -> None:
    server = build_server(mem)
    if http:
        server.settings.host = host
        server.settings.port = port
        server.run(transport="streamable-http")
    else:
        server.run()  # stdio (default; no network, no port)
