"""Synthesis prompt builder.

Lifted from the app's `host._profile_synthesis_prompt`, parameterized to take
the schema text (so a builder's `outcomes.md` flows straight in) instead of the
hardcoded constant.
"""

from __future__ import annotations


def build_synthesis_prompt(entity_name: str, entity_type: str, existing_profile: str,
                           sources_text: str, schema: str) -> str:
    have = (existing_profile or "").strip()
    base = (
        f'You maintain a living profile for "{entity_name}" ({entity_type}). '
        f"Synthesize it from the sources below — text only, do NOT use any tools.\n\n"
        f"=== PROFILE SCHEMA (obey exactly; grade your output against it) ===\n{schema}\n"
    )
    base += (
        f"\n=== EXISTING PROFILE (compound on this; don't restart) ===\n{have}\n"
        if have else
        "\n=== EXISTING PROFILE ===\n(none yet — create it from the sources)\n"
    )
    base += (
        f"\n=== SOURCES (immutable; read-only) ===\n{sources_text}\n\n"
        "Output ONLY the complete profile (front matter + body). No preamble, no code fences."
    )
    return base
