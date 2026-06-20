"""Slice 4 — dense (numpy brute-force cosine over BLOB vectors) + RRF hybrid.

These run on the hash embedder (offline, no model download), so they test the
mechanics — fusion correctness, the resident-matrix generation counter, graceful
degradation — not semantic quality (that needs fastembed; covered by the bench).
"""

from __future__ import annotations

from distillory import Memory
from distillory.retrieval import rrf_fuse


def test_rrf_is_an_outer_join():
    fused = dict(rrf_fuse([["a", "b", "c"], ["b", "d"]], k=60))
    assert max(fused, key=fused.get) == "b"      # in both lists -> top
    assert "d" in fused and fused["d"] > 0        # in only one list -> still scores
    assert "a" in fused and "c" in fused          # nothing dropped


def test_rrf_dedups_within_a_list():
    fused = dict(rrf_fuse([["a", "a", "b"]], k=60))
    # 'a' first occurrence is rank 1; the duplicate doesn't add again
    assert fused["a"] == 1 / 61
    assert fused["b"] == 1 / 62


def test_dense_backend_returns_scored_uids(tmp_path):
    mem = Memory.open(tmp_path / "b.db", synth="none", embed="hash")
    mem.add("alpha beta gamma about pricing", entity="A")
    mem.add("delta epsilon zeta about shipping", entity="B")
    res = mem.dense.search("pricing", k=5)
    assert res and isinstance(res[0][0], str) and isinstance(res[0][1], float)
    mem.close()


def test_matrix_cache_reflects_a_new_add(tmp_path):
    """The generation counter: a freshly added vector is visible next query."""
    mem = Memory.open(tmp_path / "b.db", synth="none", embed="hash")
    mem.add("first chunk about apples", entity="A")
    n1 = len(mem.dense.cache.get()[0])
    mem.add("second chunk about oranges", entity="B")
    assert len(mem.dense.cache.get()[0]) == n1 + 1
    mem.close()


def test_hybrid_search_returns_chunks(tmp_path):
    mem = Memory.open(tmp_path / "b.db", synth="none", embed="hash")
    mem.add("the quarterly pricing review notes", entity="Acme")
    assert mem.search("pricing")                  # fused keyword + dense
    mem.close()


def test_doctor_reports_dense_state(tmp_path):
    mem = Memory.open(tmp_path / "b.db", synth="none", embed="hash")
    mem.add("hello world", entity="X")
    d = mem.doctor()
    assert d["vectors"] >= 1
    assert d["dense_backend"] == "numpy-bruteforce"
    assert d["resident_mb"] >= 0
    mem.close()


def test_embed_none_degrades_to_keyword(tmp_path):
    mem = Memory.open(tmp_path / "b.db", synth="none", embed="none")
    mem.add("searchable keyword content", entity="K")
    assert mem.dense.search("keyword") == []      # no vectors -> no dense path
    assert mem.search("keyword")                   # keyword still works
    mem.close()
