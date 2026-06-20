"""distillory quickstart — runs offline, no API key, in ~10 seconds.

    pip install "distillory @ git+https://github.com/everyai-com/distillory"
    python examples/quickstart.py
"""

from distillory import Memory

# One embeddable SQLite file. synth="none" => offline extractive (no key needed).
mem = Memory.open("quickstart.db", synth="none", embed="hash")

# Two notes about the same person, dropped as they happen. They COMPOUND into
# ONE living profile — not two rows you have to reconcile later.
mem.add("Met David at LucidWay — wants the GTSI automation, budget ~$10k",
        entity="David Chen", event_date="2026-06-04")
mem.add("Follow-up: David confirmed and wants a dashboard too. Based in New York.",
        entity="David Chen", event_date="2026-06-11")

print("── the living profile (synthesized at ingestion) ──")
print(mem.profile("David Chen").body)

print("\n── cheap retrieval, cited (profile first, then raw chunks) ──")
for hit in mem.search("GTSI dashboard"):
    print(f"  [{hit.kind}] {hit.title}  <- {', '.join(hit.citations)}")

mem.close()
# Tip: set ANTHROPIC_API_KEY and use Memory.open("quickstart.db", synth="auto")
# for a real synthesized profile (Haiku, ~$1/M tokens) instead of the extractive floor.
