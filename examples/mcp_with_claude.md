# Use distillory as memory for Claude (MCP)

`distillory` ships an [MCP](https://modelcontextprotocol.io) server, so Claude
Code, Claude Desktop, or any MCP client gets persistent, *synthesizing* memory.

## 1. Install with the MCP extra

```bash
pip install "distillory[mcp] @ git+https://github.com/everyai-com/distillory"
```

## 2. Point your client at it

**Claude Code / any `~/.claude.json`-style config:**

```jsonc
{
  "mcpServers": {
    "memory": {
      "command": "mem",
      "args": ["serve", "--mcp", "--db", "~/brain.db"]
    }
  }
}
```

**Claude Desktop** (`claude_desktop_config.json`) uses the same `mcpServers` block.

For real synthesis (not the offline extractive floor), add your key:

```jsonc
"args": ["serve", "--mcp", "--db", "~/brain.db", "--synth", "auto"],
"env": { "ANTHROPIC_API_KEY": "sk-ant-..." }
```

## 3. What the model can now do

Six tools, mapped 1:1 to the verbs, plus a profile resource:

| Tool | Use |
|---|---|
| `memory_add` | store a durable fact about an entity (auto-synthesizes) |
| `memory_search` | hybrid-shaped, cited recall |
| `memory_profile` | read one entity's full living profile |
| `memory_entities` | list what's stored |
| `memory_synthesize` | (re)synthesize a profile, or all dirty ones |
| `memory_graph` | walk the `[[wikilink]]` graph between entities |

Resource `memory://profile/{slug}` mounts a synthesized profile straight into the
client's context.

## 4. Verify it's wired

```bash
mem --db ~/brain.db doctor        # shows backend, model, counts
mem --db ~/brain.db entities      # whatever the assistant has remembered
```

stdio transport by default — no network, no port, no key required for the
offline floor.
