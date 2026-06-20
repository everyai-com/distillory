"""Real synthesis with your own model — Claude, an API key, or local Ollama.

distillory never locks you to a provider. `synth=` takes a string ("auto",
"none", "claude", "anthropic:<model>", "ollama:<model>") OR any object with a
`.complete()` or `.synthesize()` method.
"""

import os

from distillory import Memory

# ── 1) Anthropic (default Haiku) — zero extra deps (stdlib urllib) ──────────
if os.environ.get("ANTHROPIC_API_KEY"):
    mem = Memory.open("synth.db", synth="auto")          # uses your key if present
    mem.add("David is based in New York.", entity="David Chen", event_date="2026-05-01")
    mem.add("David just moved to London.", entity="David Chen", event_date="2026-06-18")
    mem.synthesize(entity="David Chen")
    print(mem.profile("David Chen").body)                # resolves NY -> London with provenance
    mem.close()
else:
    print("Set ANTHROPIC_API_KEY to see real synthesis. Falling back to BYO demo below.\n")


# ── 2) Bring your own LLM — e.g. a local Ollama model. One method. ──────────
class OllamaLLM:
    name = "ollama:llama3"

    def complete(self, prompt, *, system=None, max_tokens=4096, timeout=240):
        import json
        import urllib.request
        req = urllib.request.Request(
            "http://localhost:11434/api/generate",
            data=json.dumps({"model": "llama3", "prompt": prompt, "stream": False}).encode(),
            headers={"content-type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)["response"]


# mem = Memory.open("synth.db", synth=OllamaLLM())     # uncomment if Ollama is running
print("BYO provider wired:", OllamaLLM().name)
