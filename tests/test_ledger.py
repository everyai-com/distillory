"""Slice 2 — the fact-ledger grader: schema validation, repair-retry, the
extractive fallback, and contradiction resolution persisted as structured rows.

A scripted fake LLM makes the whole thing deterministic and offline — this is a
real CI gate for "memory that self-corrects", no API key required.
"""

from __future__ import annotations


from distillory import Memory
from distillory.synthesis import parse_ledger, validate

# A valid synthesized profile where a later fact SUPERSEDES an earlier one.
VALID = """---
entity_type: prospect
status: active
stage: discovery
owner: Satya
last_synthesized: 2026-06-20
---
# David Chen — LucidWay
## Identity
David Chen — founder, LucidWay
## Where we are
Confirmed; building the GTSI automation.
## Ledger
- [2026-06-18 · m2] (update) David is based in London {event: 2026-06-18} [active]
- [2026-05-01 · m1] (assert) David is based in New York [superseded]
## Sources
- m1
- m2
"""

INVALID = "# David Chen\nJust some text, no front matter and no sections."


class FakeLLM:
    """Returns scripted outputs in order; repeats the last one. Counts calls."""
    name = "fake"

    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = 0

    def complete(self, prompt, *, system=None, max_tokens=4096, timeout=240):
        out = self.outputs[min(self.calls, len(self.outputs) - 1)]
        self.calls += 1
        return out


# ── grader unit tests ────────────────────────────────────────────────────────

def test_validate_passes_clean_and_parse_extracts_rows():
    assert validate(VALID) == []
    rows = parse_ledger(VALID)
    assert len(rows) == 2
    assert {r["edge"] for r in rows} == {"update", "assert"}


def test_validate_flags_missing_front_matter_and_uncited_ledger():
    assert any("front-matter" in p for p in validate(INVALID))
    uncited = VALID.replace(
        "- [2026-05-01 · m1] (assert) David is based in New York [superseded]",
        "- David used to live in New York")
    assert any("ledger line" in p for p in validate(uncited))


# ── the mechanism, end to end (fake LLM) ─────────────────────────────────────

def test_contradiction_is_resolved_into_structured_rows(tmp_path):
    """The headline: a new fact supersedes the old one, and the structured ledger
    reflects it — queryable, not buried in prose."""
    mem = Memory.open(tmp_path / "b.db", synth=FakeLLM([VALID]), embed="hash")
    mem.add("David is based in New York", entity="David Chen", source_ref="m1")
    by_stmt = {e["statement"]: e for e in mem.ledger("David Chen")}
    assert by_stmt["David is based in New York"]["status"] == "superseded"
    london = by_stmt["David is based in London"]
    assert london["edge"] == "update"
    assert london["status"] == "active"
    assert london["event_date"] == "2026-06-18"
    mem.close()


def test_invalid_output_triggers_exactly_one_repair_retry(tmp_path):
    fake = FakeLLM([INVALID, VALID])          # bad, then good
    mem = Memory.open(tmp_path / "b.db", synth=fake, embed="hash")
    mem.add("hi", entity="David Chen", source_ref="m1")
    assert fake.calls == 2                     # one repair-retry, no more
    body = mem.profile("David Chen").body
    assert "Extractive summary" not in body    # used the repaired output
    assert body.lstrip().startswith("---")
    mem.close()


def test_persistently_invalid_falls_back_to_extractive(tmp_path):
    fake = FakeLLM([INVALID, INVALID])         # bad twice
    mem = Memory.open(tmp_path / "b.db", synth=fake, embed="hash")
    mem.add("notes about acme widgets and pricing", entity="Acme", source_ref="m1")
    assert fake.calls == 2                      # tried once, repaired once, gave up
    assert "Extractive summary" in mem.profile("Acme").body   # not corrupted
    mem.close()


def test_doctor_reports_ledger_count(tmp_path):
    mem = Memory.open(tmp_path / "b.db", synth=FakeLLM([VALID]), embed="hash")
    mem.add("x", entity="David Chen", source_ref="m1")
    assert mem.doctor()["ledger"] >= 2
    mem.close()
