"""The default profile schema — the "outcomes.md" grading contract.

Lifted verbatim from the AIOS Desktop app's `host._PROFILE_SCHEMA`. This is what
makes synthesis *graded* rather than freeform: every write is told to obey this
exact shape. Builders override it by passing `schema="./outcomes.md"` to
`Memory.open()` — that is the core differentiator over hand-authored skills.
"""

from __future__ import annotations

DEFAULT_SCHEMA = """\
A complete profile is YAML front matter then a two-tier body. Output EXACTLY this shape.

--- FRONT MATTER (machine-read; keep these keys) ---
slug · entity_type (client|prospect|vendor) · status (active|paused|won|lost|dormant) ·
stage (new|discovery|proposal|won|lost  OR for clients: onboarding|delivery|live|paused) ·
owner · deal_value_usd (number or null) · next_action_date (YYYY-MM-DD or null) ·
last_contact (YYYY-MM-DD) · dirty: false · last_synthesized (today, YYYY-MM-DD)

--- BODY (in this order) ---
# <Name — Company>
## Identity            name, role, email(s), LinkedIn — one line each
## Company             what they do, size, domain/industry, location
## Durable constraints & preferences   things ALWAYS true (data-residency, human-in-the-loop, cadence)
## Where we are        2-3 sentences: stage, deal, momentum (the headline)
## Deal                value, status, terms/milestones
## Open commitments    table: Owner | Item | Due | Status  (both sides)
## Next action         exactly ONE, dated, with an owner (mirror next_action_date)
## Decisions made      bulleted, each dated
## Objections / risks  pushback, blockers, with status
## Open questions / gaps   what we don't know yet
## Ledger              newest first; each: - [YYYY-MM-DD · source] (assert|update|extend|derive) statement. {event: YYYY-MM-DD} [status]
## Sources             the source pointers this profile was built from

RULES: Compound, never restart — UPDATE the existing profile, don't overwrite it.
Only state what the sources support; never invent an email/number/date (unknowns -> Open questions).
Resolve contradictions with an `update` ledger entry that supersedes the old fact.
Cite every ledger line with its source. Never merge two different people.
"""
