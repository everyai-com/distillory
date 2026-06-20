"""Thin HTTP JSON API — `mem serve --http`.

Zero-dependency (stdlib http.server) so non-Python callers (Node, Go, shell,
n8n) can use the same four verbs. Routes mirror supermemory naming for an easy
swap. Binds 127.0.0.1 with no token by default; pass --host/--token to expose.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import tools

_ROUTES = {
    "/v1/add": tools.add,
    "/v1/search": tools.search,
    "/v1/profile": tools.profile,
    "/v1/synthesize": tools.synthesize,
    "/v1/entities": tools.entities,
    "/v1/graph": tools.graph,
    "/v1/ledger": tools.ledger,
}


def make_server(mem, host: str = "127.0.0.1", port: int = 7878,
                token: str | None = None) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, obj: dict) -> None:
            body = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _authed(self) -> bool:
            if not token:
                return True
            return self.headers.get("authorization") == f"Bearer {token}"

        def do_GET(self) -> None:
            if self.path == "/v1/health":
                self._send(200, {"ok": True, **mem.doctor()})
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self) -> None:
            if not self._authed():
                return self._send(401, {"error": "unauthorized"})
            fn = _ROUTES.get(self.path)
            if not fn:
                return self._send(404, {"error": "not found"})
            n = int(self.headers.get("content-length") or 0)
            try:
                payload = json.loads(self.rfile.read(n) or b"{}")
            except Exception:
                return self._send(400, {"error": "invalid json"})
            if not isinstance(payload, dict):
                return self._send(400, {"error": "body must be a JSON object"})
            try:
                self._send(200, fn(mem, **payload))
            except TypeError as e:
                self._send(400, {"error": f"bad arguments: {e}"})
            except Exception as e:  # noqa: BLE001
                self._send(500, {"error": str(e)})

        def log_message(self, *a) -> None:  # silence default stderr spam
            pass

    return ThreadingHTTPServer((host, port), Handler)


def serve_http(mem, host: str = "127.0.0.1", port: int = 7878, token: str | None = None) -> None:
    httpd = make_server(mem, host, port, token)
    h, p = httpd.server_address
    print(f"[distillory] http://{h}:{p}  (auth {'on' if token else 'off'})  — Ctrl-C to stop")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
