"""Recipe: a tiny relationship memory (CRM) from raw notes.

Drop notes as they happen; distillory keeps one living, queryable profile per
contact — the kind of context you'd otherwise scatter across a CRM, your inbox,
and voice memos. Runs offline; swap synth="auto" (+ a key) for real synthesis.
"""

from distillory import Memory

mem = Memory.open("crm.db", synth="none", embed="hash")

NOTES = [
    ("Acme Corp", "Intro call — 40-person agency, wants to automate client onboarding."),
    ("Acme Corp", "Sent proposal: $25k pilot. Champion is their COO, Dana."),
    ("Beta LLC",  "Inbound from the blog. Solo founder, evaluating us vs a competitor."),
    ("Acme Corp", "Dana verbally agreed. Legal review next week; decision by 2026-07-01."),
]
for entity, note in NOTES:
    mem.add(note, entity=entity)

print("== entities ==")
for e in mem.entities():
    print(f" - {e.title:12}  {e.snippet}")

print("\n== who's close to deciding? ==")
for h in mem.search("decision agreed proposal pilot"):
    print(f"   {h.title}: {h.snippet[:80].strip()}")

print("\n== full profile for Acme Corp ==")
print(mem.profile("Acme Corp").body)

mem.close()
