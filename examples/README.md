# Examples

All runnable. The first three need no API key and no network.

```bash
pip install "distillory @ git+https://github.com/everyai-com/distillory"
```

| File | What it shows |
|---|---|
| [`quickstart.py`](quickstart.py) | The 3-line demo: two notes compound into one synthesized profile, offline. |
| [`crm_recipe.py`](crm_recipe.py) | A tiny relationship memory — drop notes per contact, query who's close to deciding. |
| [`synthesis_byo.py`](synthesis_byo.py) | Real synthesis with Claude (a key) and bring-your-own local Ollama. |
| [`mcp_with_claude.md`](mcp_with_claude.md) | Wire distillory in as memory for Claude Code / Desktop via MCP. |

Run one:

```bash
python examples/quickstart.py
```
