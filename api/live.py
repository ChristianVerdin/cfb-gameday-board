"""Vercel function: GET /api/live?dates=YYYYMMDD,... -> same payload as server.py.

No in-process cache here; the CDN caches each URL for 20 s (s-maxage), so one
ESPN pull serves every viewer in that window. Closing lines are kept by the
client (localStorage), not on this stateless function.
"""
from __future__ import annotations

import json
import sys
import time
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from server import DATES, live_payload, parse_dates, pull_date  # noqa: E402


def build(dates: list[str]) -> dict:
    events, seen, errors = [], set(), []
    for date in dates:
        try:
            batch = pull_date(date)
        except Exception as exc:
            errors.append(f"{date}: {exc}")
            continue
        for event in batch:
            eid = event.get("id")
            if eid and eid not in seen:
                seen.add(eid)
                events.append(event)
    if not events:
        raise RuntimeError(" | ".join(errors) or "ESPN returned no games")
    return {
        "ok": True,
        "count": len(events),
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "warnings": errors,
        "dates": dates,
        "games": live_payload(events),
    }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        _, _, query = self.path.partition("?")
        dates = parse_dates(query) or DATES
        try:
            payload, code = build(dates), 200
            cache = "public, max-age=0, s-maxage=20, stale-while-revalidate=40"
        except Exception as exc:
            payload, code = {"ok": False, "error": str(exc)}, 502
            cache = "no-store"
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", cache)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print("[api/live] " + fmt % args)
