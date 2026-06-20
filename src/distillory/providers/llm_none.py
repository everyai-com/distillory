"""NullLLM — the no-synthesis floor.

When no LLM is configured (no API key, no CLI, no Ollama), the engine still
works: `synthesize()` falls back to an EXTRACTIVE profile (see
synthesis/synthesizer.py) rather than calling a model. NullLLM exists so the
resolver always returns *something* and callers can detect the no-synth case via
`.name == "none"`.
"""

from __future__ import annotations


class NullLLM:
    def complete(self, prompt: str, *, system: str | None = None,
                 max_tokens: int = 4096, timeout: int = 240) -> str:
        raise RuntimeError(
            "No LLM configured (synth='none'). Synthesis falls back to extractive."
        )

    @property
    def name(self) -> str:
        return "none"
