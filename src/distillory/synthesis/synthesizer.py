"""ProfileSynthesizer — turn schema + existing profile + new sources into one
synthesized profile.

The judgment step. Lifted from the app's `synthesize_profile` (fence-strip,
schema-graded prompt), generalized to any LLMProvider — and given an EXTRACTIVE
fallback so the engine produces a useful profile even with no model configured.

The structured grader (validate -> repair -> retry, write ledger rows) is slice
2; this slice does the prompt -> complete -> strip -> store loop honestly,
degrading to extractive when there's no LLM or the call fails.
"""

from __future__ import annotations

import re

from ..store.db import today
from .prompt import build_synthesis_prompt
from .schema_md import DEFAULT_SCHEMA

_FENCE_RE = re.compile(r"^```[a-zA-Z]*\n|\n```$")


class ProfileSynthesizer:
    def __init__(self, llm, schema: str | None = None):
        self.llm = llm
        self.schema = schema or DEFAULT_SCHEMA

    @property
    def _is_null(self) -> bool:
        return self.llm is None or getattr(self.llm, "name", "none") == "none"

    def run(self, entity_name: str, entity_type: str, existing_md: str, sources_text: str) -> str:
        # BYO Synthesizer object: has .synthesize(schema, existing, sources).
        if hasattr(self.llm, "synthesize") and not hasattr(self.llm, "complete"):
            try:
                md = self.llm.synthesize(schema=self.schema, existing=existing_md,
                                         sources=sources_text)
                md = _FENCE_RE.sub("", (md or "").strip()).strip()
                return md or self._extractive(entity_name, entity_type, sources_text)
            except Exception:
                return self._extractive(entity_name, entity_type, sources_text)

        if self._is_null:
            return self._extractive(entity_name, entity_type, sources_text)

        prompt = build_synthesis_prompt(entity_name, entity_type, existing_md,
                                        sources_text, self.schema)
        try:
            md = self.llm.complete(prompt, max_tokens=4096, timeout=240)
        except Exception:
            return self._extractive(entity_name, entity_type, sources_text)
        md = _FENCE_RE.sub("", (md or "").strip()).strip()
        return md or self._extractive(entity_name, entity_type, sources_text)

    def _extractive(self, entity_name: str, entity_type: str, sources_text: str) -> str:
        """No-LLM floor: a schema-shaped profile assembled from the raw sources.
        Honest about being extractive; still useful and still searchable."""
        blocks = [b.strip() for b in (sources_text or "").split("\n\n") if b.strip()]
        ledger_lines, source_lines, body_excerpts = [], [], []
        for b in blocks:
            lines = b.splitlines()
            ref = lines[0].lstrip("# ").strip() if lines and lines[0].startswith("###") else ""
            content = "\n".join(lines[1:]).strip() if ref else b
            first = content.splitlines()[0].strip() if content else ""
            if ref:
                source_lines.append(f"- {ref}")
                if first:
                    ledger_lines.append(f"- [{today()} · {ref}] (assert) {first[:200]}")
            if content:
                body_excerpts.append(content[:600])
        body = "\n\n".join(body_excerpts) or "(no source text)"
        return (
            f"---\n"
            f"entity_type: {entity_type}\n"
            f"status: active\n"
            f"stage: new\n"
            f"last_synthesized: {today()}\n"
            f"dirty: false\n"
            f"---\n"
            f"# {entity_name}\n\n"
            f"## Where we are\n"
            f"_Extractive summary — no LLM configured. Set ANTHROPIC_API_KEY (or pass "
            f"synth=...) for a synthesized profile._\n\n"
            f"## Notes from sources\n{body}\n\n"
            f"## Ledger\n" + ("\n".join(ledger_lines) or "- (none)") + "\n\n"
            "## Sources\n" + ("\n".join(source_lines) or "- (none)") + "\n"
        )
