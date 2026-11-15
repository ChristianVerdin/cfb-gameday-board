#!/usr/bin/env python3
"""Local server for the NFL board: static files from the repo root plus /api/nfl/live and /api/nfl/game.

    PORT=8766 .venv/bin/python3 scripts/nfl/dev_server.py     # http://127.0.0.1:8766/nfl
"""
from __future__ import annotations

import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from nflcore import api  # noqa: E402

HOST = "127.0.0.1"
DEFAULT_PORT = 8766
RESERVED = 8765
HIDDEN = ("scripts", "nflcore", "api", "ios", "docs", "deploy")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT), **kw)

    def _blocked(self, path: str) -> bool:
        segs = [s for s in unquote(path).split("/") if s]
        return any((s.startswith(".") and s != ".well-known") or s == "__pycache__" for s in segs) or (
            bool(segs) and segs[0] in HIDDEN)

    def translate_path(self, path):
        p = urlsplit(path).path
        if p in ("/nfl", "/nfl/"):
            path = "/nfl/index.html"
        elif p != "/" and not Path(ROOT, p.lstrip("/")).exists() and Path(ROOT, p.lstrip("/") + ".html").is_file():
            path = p + ".html"
        return super().translate_path(path)

    def _serve(self, head: bool):
        p = urlsplit(self.path).path
        if p.startswith("/api/nfl/"):
            return api.handle(self, head=head)
        if self._blocked(p):
            return self.send_error(404)
        return (super().do_HEAD if head else super().do_GET)()

    def do_GET(self):
        self._serve(False)

    def do_HEAD(self):
        self._serve(True)

    def log_message(self, fmt, *args):
        print("[nfl-dev] " + fmt % args)


def make_server(port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    if port == RESERVED:
        raise SystemExit(f"port {RESERVED} belongs to another service")
    return ThreadingHTTPServer((HOST, port), Handler)


if __name__ == "__main__":
    srv = make_server(int(os.environ.get("PORT", DEFAULT_PORT)))
    print(f"NFL board dev server on http://{HOST}:{srv.server_address[1]}/nfl")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
