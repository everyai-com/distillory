"""Thin translations of distillory's four verbs onto other surfaces.

- tools       — the shared JSON wrappers every adapter calls
- mcp_server  — MCP (Claude Code / Desktop / any MCP client)  [extra: mcp]
- http_server — zero-dep HTTP JSON API (Node/Go/shell/n8n)
"""

from . import tools

__all__ = ["tools"]
