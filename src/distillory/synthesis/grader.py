"""The grader — what makes synthesis *graded*, not just generated.

After the model writes a profile, the grader:
  1. VALIDATES it against the schema's hard requirements (front matter, a title,
     body sections, and that every `## Ledger` line is cited + edge-typed).
  2. The synthesizer uses these violations to REPAIR-and-retry ONCE, then falls
     back to the extractive floor rather than storing a corrupt profile.
  3. PARSES the `## Ledger` section into structured rows (edge-typed, temporally
     grounded, with status) so contradiction resolution is a queryable mechanism.

This is the difference between "a notes file" and "memory that self-corrects".
"""

from __future__ import annotations

import re

# - [YYYY-MM-DD · source] (assert|update|extend|derive) statement {event: ...} [status]
_LEDGER_LINE = re.compile(
    r"^-\s*\[\s*(?P<date>[^\]·]*?)\s*·\s*(?P<source>[^\]]+?)\s*\]\s*"
    r"\((?P<edge>assert|update|extend|derive)\)\s*(?P<rest>.+)$"
)
_EVENT = re.compile(r"\{event:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})\}")
_STATUS = re.compile(r"\[(active|superseded|stale)\]\s*$")


def _section(md: str, name: str) -> str:
    """Text under the first `## <name>` header, up to the next `## ` header."""
    out, capturing = [], False
    for ln in (md or "").splitlines():
        s = ln.strip()
        if s.startswith("## "):
            capturing = s[3:].strip().lower().startswith(name.lower())
            continue
        if capturing:
            out.append(ln)
    return "\n".join(out)


def parse_ledger(md: str) -> list[dict]:
    """Structured rows from the `## Ledger` section (well-formed lines only)."""
    entries: list[dict] = []
    for ln in _section(md, "Ledger").splitlines():
        s = ln.strip()
        if not s.startswith("-"):
            continue
        m = _LEDGER_LINE.match(s)
        if not m:
            continue
        rest = m.group("rest").strip()
        ev = _EVENT.search(rest)
        st = _STATUS.search(rest)
        statement = _STATUS.sub("", _EVENT.sub("", rest)).strip().rstrip(".").strip()
        entries.append({
            "edge": m.group("edge"),
            "statement": statement,
            "source_ref": m.group("source").strip(),
            "doc_date": m.group("date").strip(),
            "event_date": ev.group(1) if ev else None,
            "status": st.group(1) if st else "active",
        })
    return entries


def _has_front_matter(md: str) -> bool:
    t = (md or "").lstrip()
    return t.startswith("---") and t.find("\n---", 3) != -1


def _body(md: str) -> str:
    t = (md or "").lstrip()
    if _has_front_matter(md):
        return t[t.find("\n---", 3) + 4:]
    return t


def validate(md: str) -> list[str]:
    """List schema violations; empty == valid. Lenient enough that good-faith
    model output passes, strict enough to catch corruption and the schema's
    'uncited ledger line' failure."""
    problems: list[str] = []
    if not _has_front_matter(md):
        problems.append("missing or unterminated YAML front-matter block (--- ... ---)")
    body = _body(md)
    if "# " not in body:
        problems.append("missing a '# Name' title heading")
    if "## " not in body:
        problems.append("missing body sections ('## ...')")
    for ln in _section(md, "Ledger").splitlines():
        s = ln.strip()
        if s.startswith("-") and s not in ("-", "- (none)") and not _LEDGER_LINE.match(s):
            problems.append(f"uncited or malformed ledger line: {s[:60]}")
    return problems
