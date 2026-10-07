#!/usr/bin/env python3
"""Local CFB GameDay live server. Proxies ESPN scoreboard for live scores."""
from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("PORT", "8765"))
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


def fetch_json(url: str, timeout: int = 20) -> dict:
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "ignore")[:300]
        raise RuntimeError(f"ESPN {exc.code} {exc.reason} :: {body}") from exc


def fallback_dates(today: datetime | None = None) -> list[str]:
    """Tue..Mon of the slate in progress, Eastern. Only reached when games.json
    is unreadable. Deliberately duplicates scripts/refresh_week.default_dates rather
    than importing it: vercel.json excludeFiles drops scripts/** from the api/live.py
    bundle, so that import would 502 every cold start.
    """
    d = (today or datetime.now(EASTERN)).date()
    tuesday = d - timedelta(days=(d.weekday() - 1) % 7)
    return [(tuesday + timedelta(days=i)).strftime("%Y%m%d") for i in range(7)]


def load_dates() -> list[str]:
    """ESPN (Eastern) dates to poll, from the snapshot payload."""
    try:
        data = json.loads((ROOT / "games.json").read_text("utf-8"))
    except Exception as exc:
        print(f"games.json unreadable ({exc}); using fallback dates")
        return fallback_dates()
    if isinstance(data.get("dates"), list) and data["dates"]:
        return [str(d) for d in data["dates"]]
    found = set()
    for game in data.get("games") or []:
        try:
            utc = datetime.strptime(game["date"], "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
        except (KeyError, ValueError):
            continue
        found.add(utc.astimezone(EASTERN).strftime("%Y%m%d"))
    return sorted(found) or fallback_dates()


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


# Local server only. api/live.py is stateless and imports from this module, so building
# the book at import time meant every Vercel cold start read a lines.json that
# vercel.json excludes from the bundle, then reparsed games.json to seed a book that is
# never used and never flushed there.
LINES: "LineBook | None" = None


def line_book() -> LineBook:
    global LINES
    if LINES is None:
        LINES = LineBook(LINES_PATH)
    return LINES


DATE_RE = re.compile(r"^\d{8}$")


def parse_dates(query: str) -> list[str] | None:
    """?dates=20260912,20260913 -> validated list, max 7 (one Tue..Mon slate). None when absent."""
    raw = urllib.parse.parse_qs(query).get("dates")
    if not raw:
        return None
    found = []
    for d in raw[0].split(","):
        d = d.strip()
        if DATE_RE.match(d) and d not in found:
            found.append(d)
    return found[:7] or None


def live_payload(events: list, lines: "LineBook | None" = None) -> list:
    """Flatten ESPN events into the /api/live game shape."""
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
        odds = parse_odds(comp)
        if lines is not None:
            odds = lines.apply(event.get("id"), odds, status.get("state"))
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
            "odds": odds,
            "situation": {
                "text": situation.get("downDistanceText") or situation.get("possessionText"),
                "lastPlay": ((situation.get("lastPlay") or {}).get("text")),
                "possession": situation.get("possession"),
                "isRedZone": bool(situation.get("isRedZone")),
            } if situation else None,
        })
    return live


WINPROB_POINTS = 80
LEADER_CATS = (("passingYards", "Passing"), ("rushingYards", "Rushing"), ("receivingYards", "Receiving"),
               ("sacks", "Sacks"), ("totalTackles", "Tackles"))
GAME_ID = re.compile(r"\d{6,12}")


def valid_game_id(value) -> bool:
    """/api/game must not become a general ESPN fetcher: ESPN event ids only."""
    return isinstance(value, str) and bool(GAME_ID.fullmatch(value))


def pull_summary(game_id: str) -> dict:
    last = None
    for host in ("site.api.espn.com", "site.web.api.espn.com"):
        try:
            return fetch_json(f"https://{host}/apis/site/v2/sports/football/college-football/summary?event={game_id}")
        except Exception as exc:
            last = exc
    raise RuntimeError(f"summary unavailable: {last}")


def game_payload(summary: dict) -> dict:
    """Trim ESPN's ~450 KB game summary to what the game sheet renders.

    Deliberately drops odds, pickcenter, againstTheSpread and predictor: the sheet
    is a game record, not a market (CLAUDE.md product rules).
    """
    header = summary.get("header") or {}
    comp = (header.get("competitions") or [{}])[0]
    state = (((comp.get("status") or {}).get("type")) or {}).get("state")
    side_of, linescores = {}, {"away": [], "home": []}
    for team in comp.get("competitors") or []:
        side = team.get("homeAway")
        side_of[str(team.get("id"))] = side
        linescores[side] = [str(x.get("displayValue", "")) for x in team.get("linescores") or []]

    def abbr(obj):
        return ((obj or {}).get("abbreviation")) or ""

    scoring = [{
        "period": ((p.get("period") or {}).get("number")),
        "clock": ((p.get("clock") or {}).get("displayValue")),
        "team": abbr(p.get("team")),
        "type": ((p.get("type") or {}).get("text")),
        "text": p.get("text"),
        "away": p.get("awayScore"),
        "home": p.get("homeScore"),
    } for p in summary.get("scoringPlays") or []]

    stats = {}
    for team in (summary.get("boxscore") or {}).get("teams") or []:
        side = team.get("homeAway") or side_of.get(str((team.get("team") or {}).get("id")))
        for s in team.get("statistics") or []:
            row = stats.setdefault(s.get("name"), [s.get("label") or s.get("name"), "", ""])
            row[1 if side == "away" else 2] = s.get("displayValue", "")
    box = list(stats.values())

    leaders = {"away": [], "home": []}
    for team in summary.get("leaders") or []:
        side = side_of.get(str((team.get("team") or {}).get("id")))
        if side not in leaders:
            continue
        cats = {c.get("name"): c for c in team.get("leaders") or []}
        for key, label in LEADER_CATS:
            top = ((cats.get(key) or {}).get("leaders") or [None])[0]
            if top:
                athlete = top.get("athlete") or {}
                leaders[side].append({"cat": label, "name": athlete.get("shortName") or athlete.get("displayName"),
                                      "line": top.get("displayValue")})

    drives_raw = summary.get("drives") or {}
    period_of = {}

    def drive(d):
        for play in d.get("plays") or []:
            period_of[str(play.get("id"))] = (play.get("period") or {}).get("number")
        return {
            "team": abbr(d.get("team")),
            "period": ((d.get("start") or {}).get("period") or {}).get("number"),
            "start": (d.get("start") or {}).get("text"),
            "result": d.get("displayResult") or d.get("shortDisplayResult"),
            "desc": d.get("description"),
            "score": bool(d.get("isScore")),
        }
    drives = [drive(d) for d in drives_raw.get("previous") or []]
    current = drive(drives_raw["current"]) if drives_raw.get("current") else None
    if current and drives and current == drives[-1]:
        current = None

    raw_wp = summary.get("winprobability") or []
    pts, periods, period = [], [], 1
    for w in raw_wp:
        period = period_of.get(str(w.get("playId"))) or period
        pts.append(round(100 * float(w.get("homeWinPercentage") or 0)))
        periods.append(period)
    keep = sorted({round(i * (len(pts) - 1) / (WINPROB_POINTS - 1)) for i in range(WINPROB_POINTS)}) if len(pts) > WINPROB_POINTS else list(range(len(pts)))
    points = [pts[i] for i in keep]
    kept_periods = [periods[i] for i in keep]
    quarters = [[q, i] for i, q in enumerate(kept_periods) if i and q != kept_periods[i - 1]]

    return {
        "id": str(header.get("id") or ""),
        "state": state,
        "linescores": linescores,
        "scoring": scoring,
        "box": box,
        "leaders": leaders,
        "drives": drives,
        "current": current,
        "winprob": {"points": points, "quarters": quarters},
    }


class GameCache:
    """Per-game summary cache: CACHE_TTL while live or pre, frozen once final."""

    def __init__(self):
        self.lock = threading.Lock()
        self.entries = {}   # id -> (payload, fetched)

    def get(self, game_id: str) -> dict:
        with self.lock:
            hit = self.entries.get(game_id)
            if hit and (hit[0].get("state") == "post" or time.time() - hit[1] < CACHE_TTL):
                return hit[0]
        payload = game_payload(pull_summary(game_id))
        with self.lock:
            self.entries[game_id] = (payload, time.time())
        return payload


GAMES = GameCache()


def snapshot(dates: list[str] | None = None) -> dict:
    dates = dates or DATES
    events = []
    seen = set()
    errors = []
    for date in dates:
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
    book = line_book()
    live = live_payload(events, book)
    book.flush()
    return {
        "ok": True,
        "count": len(live),
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "warnings": errors,
        "dates": dates,
        "games": live,
    }


class Handler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map,
                      ".webmanifest": "application/manifest+json", ".js": "text/javascript"}

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
        path, _, query = self.path.partition("?")
        if path in ("/", "/index.html"):
            self.path = "/index.html"
            return super().do_GET()
        if path in ("/privacy", "/support"):   # cleanUrls parity with Vercel
            self.path = path + ".html"
            return super().do_GET()
        if path == "/api/live":
            try:
                self.send_json(200, snapshot(parse_dates(query)))
            except Exception as exc:
                print("LIVE ERROR:", exc)
                self.send_json(502, {"ok": False, "error": str(exc)})
            return
        if path == "/api/game":
            game_id = (urllib.parse.parse_qs(query).get("id") or [""])[0]
            if not valid_game_id(game_id):
                self.send_json(400, {"ok": False, "error": "bad id"})
                return
            try:
                self.send_json(200, {"ok": True, **GAMES.get(game_id)})
            except Exception as exc:
                print("GAME ERROR:", exc)
                self.send_json(502, {"ok": False, "error": str(exc)})
            return
        return super().do_GET()


if __name__ == "__main__":
    # Bind stays on loopback. Behind Caddy/nginx that is required (docs/DEPLOY.md).
    # For a same-Wi-Fi phone test only, change BIND to "0.0.0.0" and change it
    # back: /api/live is an unauthenticated ESPN proxy and must not face the internet.
    BIND = "127.0.0.1"
    httpd = ThreadingHTTPServer((BIND, PORT), Handler)
    print(f"CFB GameDay live board: http://127.0.0.1:{PORT}/")
    print(f"Polling ESPN dates: {', '.join(DATES)}")
    print("Leave this terminal open. Live scores need this server, not a file:// open.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
