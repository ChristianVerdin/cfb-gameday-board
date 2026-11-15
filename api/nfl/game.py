"""Vercel function: GET /api/nfl/game (see nflcore/api.py)."""
from __future__ import annotations

import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from nflcore import api  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        api.handle(self)

    def do_HEAD(self):
        api.handle(self, head=True)

    def log_message(self, fmt, *args):
        print("[api/nfl/game] " + fmt % args)
