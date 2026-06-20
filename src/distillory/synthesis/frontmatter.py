"""YAML-free front-matter parser.

Lifted verbatim from the app's `host._parse_front_matter` — pulls `key: value`
scalars from a leading --- … --- block into the typed profile columns. (PyYAML
is intentionally not a dependency.)
"""

from __future__ import annotations

from typing import Any

_FM_SCALAR_KEYS = (
    "entity_type", "status", "stage", "owner", "deal_value_usd",
    "next_action_date", "last_contact",
)


def parse_front_matter(md: str) -> dict[str, Any]:
    text = (md or "").lstrip()
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    out: dict[str, Any] = {}
    for line in text[3:end].splitlines():
        if ":" not in line or line.strip().startswith("#"):
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key not in _FM_SCALAR_KEYS or val == "" or val.lower() in ("null", "none", "~"):
            continue
        if key == "deal_value_usd":
            try:
                out[key] = float(val.replace(",", "").replace("$", ""))
            except ValueError:
                continue
        else:
            out[key] = val
    return out
