"""Vercel function: GET /api/game?id=<espn event id> -> same payload as server.py.

CDN-cached per URL: 20 s while a game is live, an hour once final, so one ESPN
summary pull serves every viewer of that game in the window. Only `id` is accepted,
once, and only ids in the committed snapshot; everything else is a cached 4xx that
never reaches ESPN. ESPN errors never reach the body (log only).
"""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from server import QueryError, game_payload, known_game, pull_summary, strict_game_id  # noqa: E402

MAX_AGE = {"in": 20, "post": 3600}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        _, _, query = self.path.partition("?")
        try:
            game_id = strict_game_id(query)
        except QueryError as exc:
            payload, code, cache = {"ok": False, "error": str(exc)}, 400, f"public, max-age=0, s-maxage={exc.ttl}"
        else:
            payload, code, cache = self.lookup(game_id)
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", cache)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    @staticmethod
    def lookup(game_id: str):
        unknown = {"ok": False, "error": "unknown game"}, 404, "public, max-age=0, s-maxage=300"
        if not known_game(game_id):
            return unknown
        try:
            payload = {"ok": True, **game_payload(pull_summary(game_id))}
        except Exception as exc:
            status = getattr(exc, "status", None)
            if isinstance(status, int) and 400 <= status < 500:
                return unknown
            print(f"[api/game] {game_id}: {exc}", file=sys.stderr)   # detail stays in the log
            return {"ok": False, "error": "game detail unavailable"}, 502, "public, max-age=0, s-maxage=30"
        age = MAX_AGE.get(payload.get("state"), 300)
        return payload, 200, f"public, max-age=0, s-maxage={age}, stale-while-revalidate={age * 2}"

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def log_message(self, fmt, *args):
        print("[api/game] " + fmt % args)
