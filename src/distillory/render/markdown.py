"""Shared rendering helpers — slugs, YAML frontmatter, wikilink emission.

Lifted verbatim from mbrain (github.com/everyai-com/mbrain) — distillory's
keyword-only predecessor. Kept identical so a brain built by either tool reads
the same.
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterable

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str | None, max_len: int = 80) -> str:
    """
    'Jane Doe' -> 'jane-doe'.  Empty/None -> 'unknown'.

    Capped at `max_len` characters to stay under filesystem name limits.
    Long inputs (e.g. a description used in place of a name) are truncated at a
    word boundary and suffixed with a short hash to keep uniqueness.
    """
    if not text:
        return "unknown"
    s = _SLUG_RE.sub("-", str(text).strip().lower()).strip("-")
    if not s:
        return "unknown"
    if len(s) <= max_len:
        return s
    import hashlib

    digest = hashlib.sha1(s.encode("utf-8")).hexdigest()[:6]
    head = s[:max_len].rsplit("-", 1)[0]
    return f"{head}-{digest}"


def yaml_frontmatter(d: dict[str, Any]) -> str:
    """Minimal, escape-safe YAML frontmatter.  Skips None / empty values."""
    lines = ["---"]
    for k, v in d.items():
        if v is None or v == "":
            continue
        if isinstance(v, bool):
            lines.append(f"{k}: {'true' if v else 'false'}")
        elif isinstance(v, (int, float)):
            lines.append(f"{k}: {v}")
        elif isinstance(v, list):
            inner = ", ".join(json.dumps(str(x)) for x in v)
            lines.append(f"{k}: [{inner}]")
        else:
            s = str(v).replace("\n", " ").replace('"', "'")
            lines.append(f'{k}: "{s}"')
    lines.append("---")
    return "\n".join(lines)


def wikilink(slug_or_text: str) -> str:
    """'Acme AI' -> '[[acme-ai]]'.  Already-slug input passes through."""
    return f"[[{slugify(slug_or_text)}]]"


def wikilinks(items: Iterable[str]) -> str:
    return " · ".join(wikilink(x) for x in items if x)
