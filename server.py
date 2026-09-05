#!/usr/bin/env python3
"""Local CFB GameDay live server. Proxies ESPN scoreboard for live scores."""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("PORT", "8765"))
FALLBACK_DATES = ["20260904", "20260905", "20260906", "20260907"]
EASTERN = ZoneInfo("America/New_York")
CACHE_TTL = 20          # seconds between ESPN pulls for a date with action
IDLE_TTL = 300          # seconds when nothing is live and no kick is near
NEAR_KICK = 90 * 60     # seconds before kickoff to switch to CACHE_TTL
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.espn.com/college-football/scoreboard",
    "Origin": "https://www.espn.com",
}


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "ignore")[:300]
        raise RuntimeError(f"ESPN {exc.code} {exc.reason} :: {body}") from exc


def load_dates() -> list[str]:
    """ESPN (Eastern) dates to poll, from the snapshot payload."""
    try:
        data = json.loads((ROOT / "games.json").read_text("utf-8"))
    except Exception as exc:
        print(f"games.json unreadable ({exc}); using fallback dates")
        return FALLBACK_DATES
    if isinstance(data.get("dates"), list) and data["dates"]:
        return [str(d) for d in data["dates"]]
    found = set()
    for game in data.get("games") or []:
        try:
            utc = datetime.strptime(game["date"], "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
        except (KeyError, ValueError):
            continue
        found.add(utc.astimezone(EASTERN).strftime("%Y%m%d"))
    return sorted(found) or FALLBACK_DATES


DATES = load_dates()


def endpoints(date: str) -> list[str]:
    return [
        (
            "https://site.web.api.espn.com/apis/site/v2/sports/football/"
            f"college-football/scoreboard?dates={date}&limit=300&groups=80"
        ),
        (
            "https://site.api.espn.com/apis/site/v2/sports/football/"
            f"college-football/scoreboard?dates={date}&limit=300&groups=80"
        ),
        (
            "https://cdn.espn.com/core/college-football/scoreboard?xhr=1"
            f"&render=true&device=desktop&country=us&lang=en&region=us"
            f"&site=espn&dates={date}&limit=300&groups=80"
        ),
        (
            "https://site.api.espn.com/apis/site/v2/sports/football/"
            f"college-football/scoreboard?dates={date}&limit=300"
        ),
    ]


def events_from(payload: dict) -> list:
    if isinstance(payload.get("events"), list):
        return payload["events"]
    content = payload.get("content") or {}
    sb = content.get("sbData") or {}
    if isinstance(sb.get("events"), list):
        return sb["events"]
    return []


def pull_date(date: str) -> list:
    last = None
    for url in endpoints(date):
        try:
            data = fetch_json(url)
            events = events_from(data)
            print(f"  {date} {url.split('/')[2]} -> {len(events)} events")
            return events
        except Exception as exc:
            last = exc
            print(f"  {date} fail {url.split('/')[2]}: {exc}")
    raise RuntimeError(str(last) if last else f"no source for {date}")


def parse_odds(comp: dict) -> dict | None:
    odds = (comp.get("odds") or [None])[0]
    if not odds:
        return None
    out = {
        "provider": ((odds.get("provider") or {}).get("displayName")
                     or (odds.get("provider") or {}).get("name")),
        "details": odds.get("details"),
        "spread": odds.get("spread"),
        "total": odds.get("overUnder"),
    }
    ps = odds.get("pointSpread") or {}
    tot = odds.get("total") or {}
    ml = odds.get("moneyline") or {}

    def close(block, who):
        node = (block.get(who) or {}).get("close") or {}
        opn = (block.get(who) or {}).get("open") or {}
        return {
            "line": node.get("line"),
            "odds": node.get("odds"),
            "open": opn.get("line"),
            "open_odds": opn.get("odds"),
        }

    out["home_spread"] = close(ps, "home")
    out["away_spread"] = close(ps, "away")
    if tot:
        out["over"] = close(tot, "over")
        out["under"] = close(tot, "under")
    out["home_ml"] = ((ml.get("home") or {}).get("close") or {}).get("odds")
    out["away_ml"] = ((ml.get("away") or {}).get("close") or {}).get("odds")
    return out


class DateCache:
    """Per-date ESPN cache. Frozen once every game on that date is final."""

    def __init__(self):
        self.lock = threading.Lock()
        self.entries = {}   # date -> {events, fetched, done, error}

    @staticmethod
    def _ttl(events: list) -> int:
        now = time.time()
        soon = False
        for event in events:
            state = ((event.get("status") or {}).get("type") or {}).get("state")
            if state == "in":
                return CACHE_TTL
            if state == "pre":
                try:
                    kick = datetime.strptime(event["date"], "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
                    if kick.timestamp() - now <= NEAR_KICK:
                        soon = True
                except (KeyError, ValueError):
                    soon = True
        return CACHE_TTL if soon else IDLE_TTL

    def get(self, date: str) -> tuple[list, str | None, bool]:
        with self.lock:
            entry = self.entries.get(date)
            if entry:
                if entry["done"]:
                    return entry["events"], None, True
                if time.time() - entry["fetched"] < self._ttl(entry["events"]):
                    return entry["events"], entry.get("error"), True
            try:
                events = pull_date(date)
                error = None
            except Exception as exc:
                events = entry["events"] if entry else []
                error = str(exc)
            states = [((e.get("status") or {}).get("type") or {}).get("state") for e in events]
            done = bool(events) and error is None and all(st == "post" for st in states)
            if done:
                print(f"  {date} all final; frozen")
            self.entries[date] = {"events": events, "fetched": time.time(), "done": done, "error": error}
            return events, error, False


CACHE = DateCache()
LINES_PATH = ROOT / "lines.json"


class LineBook:
    """Last non-null odds seen per game. ESPN drops odds once a game is final,
    so this is the closing line the client uses for finals after a reload."""

    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.Lock()
        self.dirty = False
        try:
            self.lines = json.loads(path.read_text("utf-8"))
        except Exception:
            self.lines = {}
        try:  # snapshot odds as the floor for games this process never saw live
            for game in json.loads((ROOT / "games.json").read_text("utf-8")).get("games") or []:
                if game.get("id") and game.get("odds") and game["id"] not in self.lines:
                    self.lines[game["id"]] = game["odds"]
                    self.dirty = True
        except Exception:
            pass

    def apply(self, game_id: str, odds: dict | None, state: str | None) -> dict | None:
        with self.lock:
            if odds and (odds.get("spread") is not None or odds.get("total") is not None):
                if state != "post" or game_id not in self.lines:
                    if self.lines.get(game_id) != odds:
                        self.lines[game_id] = odds
                        self.dirty = True
                return odds
            return self.lines.get(game_id)

    def flush(self):
        with self.lock:
            if not self.dirty:
                return
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.lines), "utf-8")
            tmp.replace(self.path)
            self.dirty = False


LINES = LineBook(LINES_PATH)


def snapshot() -> dict:
    events = []
    seen = set()
    errors = []
    for date in DATES:
        batch, error, _cached = CACHE.get(date)
        if error:
            errors.append(f"{date}: {error}")
        for event in batch:
            eid = event.get("id")
            if not eid or eid in seen:
                continue
            seen.add(eid)
            events.append(event)
    if not events:
        raise RuntimeError(" | ".join(errors) or "ESPN returned no games")

    live = []
    for event in events:
        comp = (event.get("competitions") or [{}])[0]
        status = (event.get("status") or {}).get("type") or {}
        situation = comp.get("situation") or {}
        teams = {}
        for team in comp.get("competitors") or []:
            side = team.get("homeAway")
            recs = team.get("records") or []
            overall = next((r.get("summary") for r in recs
                            if r.get("type") == "total" or r.get("name") == "overall"), None)
            teams[side] = {
                "id": (team.get("team") or {}).get("id"),
                "abbr": (team.get("team") or {}).get("abbreviation"),
                "score": int(team.get("score") or 0),
                "record": overall,
                "winner": bool(team.get("winner")),
            }
        live.append({
            "id": event.get("id"),
            "state": status.get("state"),
            "status": status.get("name"),
            "statusDetail": status.get("detail"),
            "statusShort": status.get("shortDetail"),
            "period": (event.get("status") or {}).get("period"),
            "clock": (event.get("status") or {}).get("displayClock"),
            "completed": bool(status.get("completed")),
            "home": teams.get("home"),
            "away": teams.get("away"),
            "odds": LINES.apply(event.get("id"), parse_odds(comp), status.get("state")),
            "situation": {
                "text": situation.get("downDistanceText") or situation.get("possessionText"),
                "lastPlay": ((situation.get("lastPlay") or {}).get("text")),
                "possession": situation.get("possession"),
                "isRedZone": bool(situation.get("isRedZone")),
            } if situation else None,
        })
    LINES.flush()
    return {
        "ok": True,
        "count": len(live),
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "warnings": errors,
        "dates": DATES,
        "games": live,
    }


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt, *args):
        print("[%s] %s" % (self.log_date_time_string(), fmt % args))

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_json(self, code: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            self.path = "/index.html"
            return super().do_GET()
        if path == "/api/live":
            try:
                self.send_json(200, snapshot())
            except Exception as exc:
                print("LIVE ERROR:", exc)
                self.send_json(502, {"ok": False, "error": str(exc)})
            return
        return super().do_GET()


if __name__ == "__main__":
    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"CFB GameDay live board: http://127.0.0.1:{PORT}/")
    print(f"Polling ESPN dates: {', '.join(DATES)}")
    print("Leave this terminal open. Do not open board.html as a file.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
