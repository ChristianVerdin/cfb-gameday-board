"""Vercel function: GET /api/game?id=<espn event id> -> same payload as server.py.

CDN-cached per URL: 20 s while a game is live, an hour once final, so one ESPN
summary pull serves every viewer of that game in the window.
"""
from __future__ import annotations

import json
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from server import game_payload, pull_summary, valid_game_id  # noqa: E402

MAX_AGE = {"in": 20, "post": 3600}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        _, _, query = self.path.partition("?")
        game_id = (urllib.parse.parse_qs(query).get("id") or [""])[0]
        if not valid_game_id(game_id):
            payload, code, cache = {"ok": False, "error": "bad id"}, 400, "public, s-maxage=3600"
        else:
            try:
                payload, code = {"ok": True, **game_payload(pull_summary(game_id))}, 200
                age = MAX_AGE.get(payload.get("state"), 300)
                cache = f"public, max-age=0, s-maxage={age}, stale-while-revalidate={age * 2}"
            except Exception as exc:
                payload, code, cache = {"ok": False, "error": str(exc)}, 502, "no-store"
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", cache)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def log_message(self, fmt, *args):
        print("[api/game] " + fmt % args)
