"""Slice 1 acceptance — a working pip install + the 3-line demo, offline.

Runs with synth="none" / embed="hash" so there are NO network calls and NO API
key: pure FTS5 keyword + extractive synthesis. This is the survival floor that
must always pass.
"""

from __future__ import annotations

import pytest

from distillory import AddResult, Hit, Memory


@pytest.fixture()
def mem(tmp_path):
    m = Memory.open(tmp_path / "brain.db", synth="none", embed="hash")
    yield m
    m.close()


def test_three_line_demo_produces_a_profile(mem):
    mem.add("Met David at LucidWay — wants the GTSI automation, budget ~$10k", entity="David Chen")
    p = mem.profile("David Chen")
    assert p is not None
    assert p.slug == "david-chen"
    assert "GTSI" in p.body                      # source content made it into the profile
    assert p.body.lstrip().startswith("---")     # schema-shaped (front matter)


def test_profile_resolves_by_human_name_and_slug(mem):
    mem.add("Acme is evaluating us for Q3", entity="Acme Corp")
    assert mem.profile("Acme Corp") is not None
    assert mem.profile("acme-corp") is not None  # slug also works


def test_search_returns_a_cited_hit(mem):
    mem.add("David at LucidWay wants the GTSI automation built", entity="David Chen")
    hits = mem.search("GTSI")
    assert hits, "expected at least one hit"
    assert any(h.citations for h in hits), "every hit should carry a citation"
    assert any("gtsi" in (h.snippet + h.body).lower() or h.kind == "profile" for h in hits)


def test_entities_lists_what_was_added(mem):
    mem.add("note one", entity="David Chen")
    mem.add("note two", entity="Acme Corp")
    names = {h.title for h in mem.entities()}
    assert "David Chen" in names
    assert "Acme Corp" in names


def test_add_is_idempotent_by_source_ref(mem):
    r1 = mem.add("same source text", entity="Repeat Co", source_ref="meeting:42")
    r2 = mem.add("same source text", entity="Repeat Co", source_ref="meeting:42")
    assert isinstance(r1, AddResult) and isinstance(r2, AddResult)
    assert r1.source_added is True
    assert r2.source_added is False             # second add is a no-op
    assert mem.chunks.count() == 1


def test_compounding_two_sources_one_profile(mem):
    mem.add("David is based in New York", entity="David Chen", source_ref="m1")
    mem.add("David just moved to London", entity="David Chen", source_ref="m2")
    p = mem.profile("David Chen")
    assert p is not None
    body = p.body.lower()
    assert "new york" in body and "london" in body   # both sources are present
    # one profile, two sources
    assert len(p.citations) == 2


def test_doctor_reports_state(mem):
    mem.add("hello world", entity="World")
    d = mem.doctor()
    assert d["profiles"] >= 1
    assert d["chunks"] >= 1
    assert d["synth"] == "none"
    assert d["embed_model"].startswith("hash")


def test_search_returns_hit_objects(mem):
    mem.add("retrieval augmented generation notes", entity="RAG Notes")
    hits = mem.search("retrieval", body=True)
    assert all(isinstance(h, Hit) for h in hits)


# ── regressions for the v0.1 adversarial review ──────────────────────────────

def test_synthesize_unknown_entity_does_not_fabricate(mem):
    """A typo in `mem synthesize` must error, not create a phantom profile."""
    before = {h.slug for h in mem.entities()}
    with pytest.raises(KeyError):
        mem.synthesize(entity="Totally Unknown Person")
    assert {h.slug for h in mem.entities()} == before


def test_search_dedups_profile_and_its_own_chunk(mem):
    mem.add("David at LucidWay wants the GTSI automation", entity="David Chen")
    slugs = [h.slug for h in mem.search("GTSI") if h.slug]
    assert slugs.count("david-chen") == 1   # profile once; its chunk not duplicated


def test_noop_add_does_not_redirty(mem):
    mem.add("first", entity="Steady Co", source_ref="s1")        # auto-synth clears dirty
    r2 = mem.add("first", entity="Steady Co", source_ref="s1")   # idempotent no-op
    assert r2.source_added is False
    assert r2.dirty is False
    dirty = mem.profiles.list(dirty_only=True)["profiles"]
    assert all(p["slug"] != "steady-co" for p in dirty)          # not re-dirtied -> no wasted synth


def test_nul_byte_query_does_not_crash(mem):
    mem.add("hello world", entity="Hello")
    assert mem.search("\x00") == []                              # no unhandled OperationalError
    assert isinstance(mem.search("hello\x00world"), list)        # NUL stripped, still searches


def test_negative_k_is_clamped(mem):
    mem.add("alpha beta gamma", entity="AB")
    assert isinstance(mem.search("alpha", k=-1), list)           # no confusing LIMIT -1 behavior


def test_explicit_claude_without_key_errors_cleanly(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ValueError):
        Memory.open(tmp_path / "b.db", synth="claude")


def test_unicode_query_matches_profile(mem):
    r = mem.add("Signed for the Zürich rollout this quarter", entity="Müller GmbH")
    assert mem.profile("Müller GmbH") is not None               # name resolves
    hits = mem.search("zürich")
    assert any(h.slug == r.slug for h in hits)                  # non-ASCII query participates
