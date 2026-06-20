"""AnthropicProvider — Claude synthesis via the Messages API.

Zero-dependency by default: a stdlib `urllib` POST, so `pip install distillory`
+ an ANTHROPIC_API_KEY is enough to synthesize — no SDK required. If the
`anthropic` package is installed (the [llm-anthropic] extra) it is used instead.

Default model is Haiku (cheap, fast — synthesis is a ~$1/M-token job). Override
with synth="anthropic:<model-id>" or MemoryConfig(model=...).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
_API_VERSION = "2023-06-01"


class AnthropicProvider:
    def __init__(self, model: str | None = None, api_key: str | None = None,
                 base_url: str = "https://api.anthropic.com"):
        self.model = model or DEFAULT_MODEL
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set")

    def complete(self, prompt: str, *, system: str | None = None,
                 max_tokens: int = 4096, timeout: int = 240) -> str:
        # Prefer the official SDK when present; else stdlib urllib.
        try:
            import anthropic  # type: ignore

            client = anthropic.Anthropic(api_key=self.api_key)
            kwargs = {"model": self.model, "max_tokens": max_tokens,
                      "messages": [{"role": "user", "content": prompt}]}
            if system:
                kwargs["system"] = system
            msg = client.messages.create(**kwargs)
            return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        except ImportError:
            return self._complete_urllib(prompt, system, max_tokens, timeout)

    def _complete_urllib(self, prompt: str, system: str | None,
                         max_tokens: int, timeout: int) -> str:
        body: dict = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            body["system"] = system
        req = urllib.request.Request(
            f"{self.base_url}/v1/messages",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "content-type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": _API_VERSION,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            raise RuntimeError(f"Anthropic API error {e.code}: {detail}") from e
        return "".join(
            b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"
        )

    @property
    def name(self) -> str:
        return f"anthropic:{self.model}"
