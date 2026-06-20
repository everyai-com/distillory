"""Slice 8 — adapters: the shared tool surface, the HTTP server, the graph verb,
MCP server construction, and thread-safety of writes."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

import pytest

from distillory import Memory
from distillory.adapters import tools
from distillory.adapters.http_server import make_server


@pytest.fixture()
def mem(tmp_path):
    m = Memory.open(tmp_path / "brain.db", synth="none", embed="hash")
    yield m
    m.close()


def test_tools_cover_the_four_verbs(mem):
    r = tools.add(mem, "David at LucidWay wants the GTSI automation", entity="David Chen")
    assert r["slug"] == "david-chen" and r["source_added"] is True
    assert tools.profile(mem, "David Chen")["profile"]["slug"] == "david-chen"
    assert tools.search(mem, "GTSI")["results"]
    assert any(e["slug"] == "david-chen" for e in tools.entities(mem)["entities"])


def test_tools_synthesize_unknown_returns_error_not_crash(mem):
    out = tools.synthesize(mem, entity="Nobody Here")
    assert "error" in out and "synthesized" not in out


def test_graph_verb(mem):
    tools.add(mem, "note about acme", entity="Acme Corp")
    g = tools.graph(mem, "Acme Corp")
    assert g["start"] == "acme-corp" and "stats" in g
    assert "error" in tools.graph(mem, "Ghost")


def test_http_server_roundtrip(mem):
    httpd = make_server(mem, host="127.0.0.1", port=0)   # port 0 -> OS picks a free port
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        base = f"http://127.0.0.1:{port}"
        with urllib.request.urlopen(base + "/v1/health") as r:
            assert json.load(r)["ok"] is True

        def post(path, payload):
            req = urllib.request.Request(
                base + path, data=json.dumps(payload).encode(),
                headers={"content-type": "application/json"}, method="POST")
            with urllib.request.urlopen(req) as r:
                return json.load(r)

        assert post("/v1/add", {"text": "wants GTSI", "entity": "David Chen"})["slug"] == "david-chen"
        assert post("/v1/search", {"query": "GTSI"})["results"]
        assert post("/v1/profile", {"name_or_slug": "David Chen"})["profile"]["slug"] == "david-chen"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_http_server_token_enforced(mem):
    httpd = make_server(mem, host="127.0.0.1", port=0, token="secret")
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/v1/add",
            data=json.dumps({"text": "x", "entity": "Y"}).encode(),
            headers={"content-type": "application/json"}, method="POST")
        with pytest.raises(urllib.error.HTTPError) as ei:   # no token -> 401
            urllib.request.urlopen(req)
        assert ei.value.code == 401
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_concurrent_adds_are_thread_safe(mem):
    errs: list[Exception] = []

    def worker(i: int) -> None:
        try:
            mem.add(f"note number {i}", entity=f"Entity {i}", source_ref=f"s{i}")
        except Exception as e:  # noqa: BLE001
            errs.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errs, f"concurrent adds raised: {errs}"
    assert len(mem.entities()) == 8


def test_mcp_server_builds_when_extra_present(mem):
    pytest.importorskip("mcp")
    from distillory.adapters.mcp_server import build_server
    assert build_server(mem) is not None
