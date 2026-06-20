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
