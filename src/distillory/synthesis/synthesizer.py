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
from .grader import validate
from .prompt import build_synthesis_prompt
from .schema_md import DEFAULT_SCHEMA

_FENCE_RE = re.compile(r"^```[a-zA-Z]*\n|\n```$")


def _clean(md: str | None) -> str | None:
    md = _FENCE_RE.sub("", (md or "").strip()).strip()
    return md or None


class ProfileSynthesizer:
    def __init__(self, llm, schema: str | None = None):
        self.llm = llm
        self.schema = schema or DEFAULT_SCHEMA

    @property
    def _is_null(self) -> bool:
        return self.llm is None or getattr(self.llm, "name", "none") == "none"

    def run(self, entity_name: str, entity_type: str, existing_md: str, sources_text: str) -> str:
        md = self._synthesize(entity_name, entity_type, existing_md, sources_text)
        if md is None:                                # no LLM, or the call failed
            return self._extractive(entity_name, entity_type, sources_text)
        if not validate(md):
            return md
        # Schema violation -> exactly one repair-retry, then fall back rather than
        # store a corrupt profile.
        fixed = self._repair(entity_name, entity_type, existing_md, sources_text, validate(md))
        if fixed is not None and not validate(fixed):
            return fixed
        return self._extractive(entity_name, entity_type, sources_text)

    def _synthesize(self, name: str, etype: str, existing: str, sources: str) -> str | None:
        if self._is_null:
            return None
        if hasattr(self.llm, "synthesize") and not hasattr(self.llm, "complete"):
            try:
                return _clean(self.llm.synthesize(schema=self.schema, existing=existing, sources=sources))
            except Exception:
                return None
        return self._complete(build_synthesis_prompt(name, etype, existing, sources, self.schema))

    def _repair(self, name: str, etype: str, existing: str, sources: str,
                problems: list[str]) -> str | None:
        note = ("\n\n=== YOUR PREVIOUS OUTPUT HAD PROBLEMS — FIX THESE AND RE-OUTPUT "
                "THE FULL PROFILE (front matter + body), no code fences ===\n"
                + "\n".join("- " + p for p in problems))
        if hasattr(self.llm, "synthesize") and not hasattr(self.llm, "complete"):
            try:
                return _clean(self.llm.synthesize(schema=self.schema, existing=existing, sources=sources + note))
            except Exception:
                return None
        return self._complete(build_synthesis_prompt(name, etype, existing, sources, self.schema) + note)

    def _complete(self, prompt: str) -> str | None:
        try:
            return _clean(self.llm.complete(prompt, max_tokens=4096, timeout=240))
        except Exception:
            return None

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
