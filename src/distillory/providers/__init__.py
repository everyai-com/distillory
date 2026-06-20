"""Provider resolution ladders.

A string or an object goes in; a concrete provider comes out. Both ladders end
in an always-available floor and trigger on RUNTIME failure, not just selection
(the cost-offline guarantee): a bare offline machine with no key and no model
still gets a working engine.
"""

from __future__ import annotations

import os
import sys

from .base import Embedder, EmbedderInfo, LLMProvider, Synthesizer
from .embed_hash import HashEmbedder, NoEmbedder
from .llm_none import NullLLM

__all__ = [
    "Embedder", "EmbedderInfo", "LLMProvider", "Synthesizer",
    "HashEmbedder", "NoEmbedder", "NullLLM",
    "resolve_llm", "resolve_embedder",
]


def resolve_llm(spec, model: str | None = None):
    """spec: "auto"|"none"|"claude"|"anthropic"|"anthropic:<m>"|"ollama:<m>"|object.

    Returns an object exposing `.complete()` + `.name`, OR a BYO object exposing
    `.synthesize()` (passed straight through — the synthesizer detects it).
    """
    # BYO object (LLMProvider or Synthesizer) — pass through.
    if not isinstance(spec, str) and spec is not None:
        return spec

    s = (spec or "auto").strip().lower()

    if s == "none":
        return NullLLM()

    if s in ("claude", "anthropic") or s.startswith("anthropic:"):
        chosen = model
        if s.startswith("anthropic:"):
            chosen = s.split(":", 1)[1] or model
        from .llm_anthropic import AnthropicProvider
        return AnthropicProvider(model=chosen)

    if s == "auto":
        # Probe-and-degrade: API key -> Anthropic; else no synthesis (CLI/Ollama
        # providers arrive in slice 3). Never hard-fail on a bare machine.
        if os.environ.get("ANTHROPIC_API_KEY"):
            try:
                from .llm_anthropic import AnthropicProvider
                return AnthropicProvider(model=model)
            except Exception:
                pass
        print("[distillory] no LLM configured; synthesis is extractive "
              "(set ANTHROPIC_API_KEY or pass synth=...).", file=sys.stderr)
        return NullLLM()

    # ollama:* / openai:* land in slice 3 — degrade rather than crash.
    print(f"[distillory] synth='{spec}' not available yet; running extractive.", file=sys.stderr)
    return NullLLM()


def resolve_embedder(spec):
    """spec: "fastembed"|"potion"|"hash"|"none"|"auto"|object.

    Ladder: requested -> (fastembed -> potion) -> hash (always available).
    """
    if not isinstance(spec, str) and spec is not None:
        return spec  # BYO Embedder

    s = (spec or "fastembed").strip().lower()

    if s == "none":
        return NoEmbedder()
    if s == "hash":
        return HashEmbedder()

    # fastembed / potion / auto — try the real model, fall through on any failure
    # (not installed in slice 1, so this falls to hash; slice 4 ships the module).
    if s in ("fastembed", "auto"):
        try:
            from .embed_fastembed import FastEmbedEmbedder  # type: ignore
            return FastEmbedEmbedder()
        except Exception:
            pass
    if s in ("potion", "auto", "fastembed"):
        try:
            from .embed_potion import PotionEmbedder  # type: ignore
            return PotionEmbedder()
        except Exception:
            pass
    return HashEmbedder()
