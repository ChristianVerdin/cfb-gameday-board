"""Request layer for /api/nfl/live and /api/nfl/game: validation, gating, cache headers, error policy.

route() is pure apart from the fetchers and cache it is given, so tests run it with fakes and a fake clock.
"""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from . import espn, normalize, sanitize, slate, teams
from .cache import TTLCache

SOURCE = "espn"
LIVE_TTL = 8            # in-process scoreboard cache, seconds
SUMMARY_TTL = 8
GATE_TTL = 60           # scoreboards used only to gate game ids
STALE_OK_S = 300        # stale-if-error window, seconds
ID_RE = re.compile(r"^[0-9]{9,12}$")
LIVE_PARAMS = ("st", "week", "year")
CACHE = TTLCache()
NEAR_KICK = timedelta(minutes=90)
RECENT_FINAL = timedelta(hours=3, minutes=45)   # scoreboards carry no final time: kick + 3h45 bounds "just ended"
FINAL_WINDOW = timedelta(minutes=30)
GAME_TTL_FALLBACK = timedelta(hours=3, minutes=30)  # assumed kick-to-final when the sheet has no wallclock


def _cc(s: int, swr: int | None = None) -> str:
    return f"public, max-age=0, s-maxage={s}" + (f", stale-while-revalidate={swr}" if swr else "")


BAD = _cc(3600).replace("max-age=0, ", "")   # "public, s-maxage=3600"
NO_STORE = "no-store"


def _err(status: int, msg: str, cache: str):
    return status, {"ok": False, "error": msg}, cache


def _iso(now: datetime) -> str:
    return now.astimezone(slate.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _one(query: dict, key: str):
    v = query.get(key)
    if isinstance(v, (list, tuple)):
        if len(v) != 1:
            raise ValueError(f"{key} must appear once")
        v = v[0]
    return v


def _season_guess(now: datetime) -> int:
    return now.year if now.month >= 7 else now.year - 1


def _check_week(st: int, week: int) -> bool:
    return (st == 2 and 1 <= week <= 18) or (st == 3 and 1 <= week <= 5)


def parse_live_query(query: dict) -> dict:
    """{'st','week','year'} (ints or None). Raises ValueError with a short reason on anything unexpected."""
    extra = sorted(set(query) - set(LIVE_PARAMS))
    if extra:
        raise ValueError(f"unknown parameter {extra[0]}")
    vals = {}
    for k in LIVE_PARAMS:
        v = _one(query, k)
        if v is None:
            vals[k] = None
            continue
        if not isinstance(v, str) or not re.fullmatch(r"[0-9]{1,4}", v):
            raise ValueError(f"bad {k}")
        vals[k] = int(v)
    if vals["st"] is None and vals["week"] is None and vals["year"] is None:
        return vals
    if vals["week"] is None:
        raise ValueError("week required")
    vals["st"] = 2 if vals["st"] is None else vals["st"]
    if not _check_week(vals["st"], vals["week"]):
        raise ValueError("week out of range")
    return vals


# ---- /api/nfl/live ----

def _kick(g: dict):
    if g.get("time_tbd") or not g.get("date"):
        return None
    try:
        return slate.parse_utc(g["date"])
    except ValueError:
        return None


def live_ttl(games: list[dict], now: datetime) -> tuple[int, int]:
    """(s-maxage, stale-while-revalidate): 15/30 when live or near kick, 60/120 on a game day, else 300/600."""
    today = slate.chicago(now).date()
    game_day = False
    for g in games:
        k = _kick(g)
        if g["state"] == "in":
            return 15, 30
        if k is not None:
            if g["state"] == "pre" and k - NEAR_KICK <= now:
                return 15, 30
            if g["state"] == "post" and now - k < RECENT_FINAL:
                return 15, 30
            if slate.chicago(k).date() == today:
                game_day = True
    return (60, 120) if game_day else (300, 600)


def _scoreboard(cache, fetch, st, week, year, ttl, now):
    def load():
        return fetch(st, week, year), _iso(now)
    return cache.get_or_fetch(("sb", st, week, year), ttl, load, stale_ok_s=STALE_OK_S - ttl)


def _scrub(payload: dict) -> dict:
    dropped = sanitize.scrub(payload)
    if dropped:
        payload.setdefault("warnings", []).append(f"forbidden_dropped: {dropped}")
    return payload


def _calendar_info(fetch_calendar, now):
    """(calendar or None, season year)."""
    try:
        cal = fetch_calendar()
    except Exception:  # noqa: BLE001 - explicit week queries can still be served without it
        return None, _season_guess(now)
    return cal, int((cal.get("season") or {}).get("year") or _season_guess(now))


def _live(query, now, fetch_scoreboard, fetch_calendar, cache):
    try:
        q = parse_live_query(query)
    except ValueError as e:
        return _err(400, str(e), BAD)
    explicit = q["week"] is not None
    stale = False
    try:
        if explicit:
            cal, cur = _calendar_info(fetch_calendar, now)
            year = q["year"] or cur
            if year not in (cur, cur - 1):
                return _err(400, "year out of range", BAD)
            dates = year if (q["st"] == 3 or year != cur) else None
            info = {"year": year, "st": q["st"], "week": q["week"], "label": None}
            if cal and year == cur:
                hit = next((e for e in slate.parse_calendar(cal) if (e["st"], e["week"]) == (q["st"], q["week"])), None)
                info["label"] = hit["label"] if hit else None
            (sb, fetched), stale = _scoreboard(cache, fetch_scoreboard, q["st"], q["week"], dates, LIVE_TTL, now)
        else:
            cal = fetch_calendar()
            info = slate.resolve_week(cal, now)
            if info is None:
                return 200, _live_payload({"season": None, "week": None, "teams_on_bye": [], "games": [],
                                           "warnings": ["no_slate"]}, _iso(now), False), _cc(300, 600)
            (sb, fetched), stale = _scoreboard(cache, fetch_scoreboard, info["st"], info["week"],
                                               info["year"] if info["st"] == 3 else None, LIVE_TTL, now)
            events = sb.get("events") or []
            if events and all(((e.get("competitions") or [{}])[0].get("status") or e.get("status") or {})
                              .get("type", {}).get("state") == "post" for e in events):
                nxt = slate.resolve_week(cal, now, events_all_post=True)
                if nxt:
                    info = nxt
                    (sb, fetched), stale = _scoreboard(cache, fetch_scoreboard, info["st"], info["week"],
                                                       info["year"] if info["st"] == 3 else None, LIVE_TTL, now)
    except espn.EspnQueryError as e:
        return _err(400, str(e), BAD)
    except Exception:  # noqa: BLE001 - any upstream failure is a 502 with nothing cached
        return _err(502, "upstream unavailable", NO_STORE)
    out = normalize.norm_live(sb, info)
    payload = _live_payload(out, fetched, stale)
    _scrub(payload)
    if stale:
        return 200, payload, _cc(5, 10)
    s, swr = live_ttl(out["games"], now)
    return 200, payload, _cc(s, swr)


def _live_payload(out: dict, fetched_at: str, stale: bool) -> dict:
    return {"ok": True, "v": 1, "count": len(out["games"]), "fetched_at": fetched_at, "source_host": SOURCE,
            "stale": stale, "season": out["season"], "week": out["week"], "teams_on_bye": out["teams_on_bye"],
            "warnings": list(out["warnings"]), "games": out["games"]}


# ---- /api/nfl/game ----

def _gate_weeks(cal: dict, now: datetime) -> list[dict]:
    """Previous, current and next calendar entries (each with a year) around now."""
    entries = slate.parse_calendar(cal)
    year = int((cal.get("season") or {}).get("year") or _season_guess(now))
    cur = next((i for i, e in enumerate(entries)
                if e["start"] <= now < (entries[i + 1]["start"] if i + 1 < len(entries) else e["end"])), None)
    if cur is None:
        return []
    return [{"st": e["st"], "week": e["week"], "year": year} for e in entries[max(0, cur - 1):cur + 2]]


def _team_ok(t: dict) -> bool:
    return (t.get("abbreviation") in teams.BY_ABBR) or str(t.get("id")) in teams.ALL_STAR_IDS


def _identity_ok(summary: dict) -> bool:
    comps = (((summary.get("header") or {}).get("competitions")) or [{}])[0].get("competitors") or []
    return len(comps) == 2 and all(_team_ok(c.get("team") or {}) for c in comps)


def _event_ok(event: dict) -> bool:
    comps = (event.get("competitions") or [{}])[0].get("competitors") or []
    return len(comps) == 2 and all(_team_ok(c.get("team") or {}) for c in comps)


class NotNfl(Exception):
    pass


def _vetted(summary: dict, now: datetime):
    """Only summaries that pass the identity check enter the cache."""
    if not _identity_ok(summary):
        raise NotNfl()
    return summary, _iso(now)


def _find_event(cache, fetch, cal, now, gid):
    """(event or None, gate) where gate is 'in' (listed), 'out' (all three weeks loaded, not listed) or 'open'."""
    weeks = _gate_weeks(cal, now) if cal else []
    if not weeks:
        return None, "open"

    def load(w):
        try:
            sb, _ = _scoreboard(cache, fetch, w["st"], w["week"], w["year"] if w["st"] == 3 else None, GATE_TTL, now)[0]
            return sb
        except Exception:  # noqa: BLE001
            return None

    with ThreadPoolExecutor(len(weeks)) as ex:
        boards = list(ex.map(load, weeks))
    for sb in boards:
        for ev in (sb or {}).get("events") or []:
            if str(ev.get("id")) == gid:
                return ev, "in"
    return None, "out" if all(boards) else "open"


def game_ttl(sheet: dict, event: dict | None, now: datetime) -> tuple[int, int | None]:
    state = sheet.get("state")
    if state == "in":
        return 15, 30
    if state == "pre":
        return 300, 600
    ref = None
    for raw in (sheet.get("last_play_wallclock"),):
        try:
            ref = slate.parse_utc(raw) if raw else None
        except ValueError:
            ref = None
    if ref is None and event and event.get("date"):
        ref = slate.parse_utc(event["date"]) + GAME_TTL_FALLBACK
    if ref is None or now - ref < FINAL_WINDOW:
        return 60, 120
    return 3600, None


def _game(query, now, fetch_scoreboard, fetch_calendar, fetch_summary, norm_summary, cache):
    extra = sorted(set(query) - {"id"})
    if extra:
        return _err(400, f"unknown parameter {extra[0]}", BAD)
    try:
        gid = _one(query, "id")
    except ValueError as e:
        return _err(400, str(e), BAD)
    if not isinstance(gid, str) or not ID_RE.fullmatch(gid):
        return _err(400, "bad id", BAD)
    try:
        cal = fetch_calendar()
    except Exception:  # noqa: BLE001 - best effort: identity check only
        cal = None
    event, gate = _find_event(cache, fetch_scoreboard, cal, now, gid)
    if gate == "out":
        return _err(404, "unknown game", BAD)
    if event is not None and not _event_ok(event):
        return _err(404, "not an NFL game", BAD)
    try:
        (summary, fetched), stale = cache.get_or_fetch(
            ("sum", gid), SUMMARY_TTL, lambda: _vetted(fetch_summary(gid), now), stale_ok_s=STALE_OK_S - SUMMARY_TTL)
    except NotNfl:
        return _err(404, "not an NFL game", BAD)
    except espn.EspnQueryError:
        return _err(400, "bad id", BAD)
    except espn.EspnError as e:
        if e.status == 404:
            return _err(404, "unknown game", BAD)
        return _err(502, "upstream unavailable", NO_STORE)
    except Exception:  # noqa: BLE001
        return _err(502, "upstream unavailable", NO_STORE)
    if not _identity_ok(summary):
        return _err(404, "not an NFL game", BAD)
    if norm_summary is None:
        try:
            from . import gamesheet
        except ImportError:
            return _err(503, "game sheet unavailable", NO_STORE)
        norm_summary = gamesheet.norm_summary
    try:
        sheet = norm_summary(summary, event)
    except Exception:  # noqa: BLE001
        return _err(502, "game sheet failed", NO_STORE)
    payload = {"ok": True, "v": 1, "id": gid, "fetched_at": fetched, "stale": stale}
    payload.update({k: v for k, v in sheet.items() if k not in payload})
    if not isinstance(payload.get("warnings"), list):
        payload["warnings"] = []
    _scrub(payload)
    if stale:
        return 200, payload, _cc(5, 10)
    s, swr = game_ttl(sheet, event, now)
    return 200, payload, _cc(s, swr)


# ---- entry points ----

def route(path: str, query: dict | None = None, now: datetime | None = None, *, fetch_scoreboard=None,
          fetch_calendar=None, fetch_summary=None, norm_summary=None, cache: TTLCache | None = None):
    """(status, payload, cache_control). query maps names to str or list[str] (urllib.parse.parse_qs shape)."""
    now = now or datetime.now(slate.UTC)
    query = query or {}
    cache = cache if cache is not None else CACHE
    fetch_scoreboard = fetch_scoreboard or espn.pull_scoreboard
    fetch_calendar = fetch_calendar or espn.pull_calendar
    fetch_summary = fetch_summary or espn.pull_summary
    p = path.rstrip("/")
    if p == "/api/nfl/live":
        return _live(query, now, fetch_scoreboard, fetch_calendar, cache)
    if p == "/api/nfl/game":
        return _game(query, now, fetch_scoreboard, fetch_calendar, fetch_summary, norm_summary, cache)
    return _err(404, "not found", BAD)


def handle(h, head: bool = False, route_fn=None) -> None:
    """Serve one request on a BaseHTTPRequestHandler. HEAD answers 200 without touching ESPN."""
    from urllib.parse import parse_qs, urlsplit
    if head:
        status, body, cache = 200, b"", NO_STORE
    else:
        parts = urlsplit(h.path)
        status, payload, cache = (route_fn or route)(parts.path, parse_qs(parts.query, keep_blank_values=True))
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    h.send_response(status)
    h.send_header("Content-Type", "application/json")
    h.send_header("Cache-Control", cache)
    h.send_header("Access-Control-Allow-Origin", "*")
    h.send_header("Content-Length", str(len(body)))
    h.end_headers()
    if not head:
        h.wfile.write(body)
