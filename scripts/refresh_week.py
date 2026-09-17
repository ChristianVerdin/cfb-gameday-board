#!/usr/bin/env python3
"""Rebuild games.json / games.js for a new slate.

    python3 scripts/refresh_week.py                      # next Thu..Mon slate
    python3 scripts/refresh_week.py --start 20260911 --end 20260914

Pulls the ESPN scoreboard per date, geocodes each venue city with Open-Meteo,
pulls the hourly forecast at the local kickoff hour, derives the board fields,
and writes both snapshot files. Stdlib only. See docs/ARCHITECTURE.md.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from server import endpoints, events_from, fetch_json, parse_odds  # noqa: E402

CHICAGO = ZoneInfo("America/Chicago")
CONFERENCES_URL = (
    "https://site.web.api.espn.com/apis/site/v2/sports/football/"
    "college-football/scoreboard/conferences"
)
SUMMARY_URL = (
    "https://site.web.api.espn.com/apis/site/v2/sports/football/"
    "college-football/summary"
)   # site.api.espn.com 403s on this path; site.web.api does not
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
HOURLY = ",".join([
    "temperature_2m", "relative_humidity_2m", "precipitation_probability",
    "precipitation", "weather_code", "wind_speed_10m", "wind_gusts_10m",
    "wind_direction_10m", "cloud_cover",
])
P4_IDS = {"1", "4", "5", "8", "9"}          # ACC, Big 12, Big Ten, SEC, Pac-12
FALLBACK_CONFS = {
    "1": "ACC", "4": "Big 12", "5": "Big Ten", "8": "SEC", "9": "Pac-12",
    "12": "CUSA", "15": "MAC", "17": "Mountain West", "18": "Independent",
    "37": "Sun Belt", "151": "American",
}
STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
    "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
    "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia",
    "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}
WMO = {
    0: ("Clear", "☀️"), 1: ("Mostly clear", "\U0001f324️"),
    2: ("Partly cloudy", "⛅"), 3: ("Overcast", "☁️"),
    45: ("Fog", "\U0001f32b️"), 48: ("Icy fog", "\U0001f32b️"),
    51: ("Light drizzle", "\U0001f326️"), 53: ("Drizzle", "\U0001f326️"),
    55: ("Heavy drizzle", "\U0001f327️"), 56: ("Freezing drizzle", "\U0001f9ca"),
    57: ("Freezing drizzle", "\U0001f9ca"), 61: ("Light rain", "\U0001f327️"),
    63: ("Rain", "\U0001f327️"), 65: ("Heavy rain", "\U0001f327️"),
    66: ("Freezing rain", "\U0001f9ca"), 67: ("Freezing rain", "\U0001f9ca"),
    71: ("Light snow", "\U0001f328️"), 73: ("Snow", "\U0001f328️"),
    75: ("Heavy snow", "❄️"), 77: ("Snow grains", "\U0001f328️"),
    80: ("Showers", "\U0001f326️"), 81: ("Showers", "\U0001f327️"),
    82: ("Heavy showers", "⛈️"), 85: ("Snow showers", "\U0001f328️"),
    86: ("Snow showers", "\U0001f328️"), 95: ("Thunderstorm", "⛈️"),
    96: ("Thunderstorm w/ hail", "⛈️"), 99: ("Thunderstorm w/ hail", "⛈️"),
}
COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
           "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


def get(url: str, params: dict) -> dict:
    return fetch_json(url + "?" + urllib.parse.urlencode(params))


def date_range(start: str, end: str) -> list[str]:
    a = datetime.strptime(start, "%Y%m%d")
    b = datetime.strptime(end, "%Y%m%d")
    if b < a:
        raise SystemExit("--end is before --start")
    return [(a + timedelta(days=i)).strftime("%Y%m%d") for i in range((b - a).days + 1)]


def default_dates(today: datetime | None = None) -> tuple[str, str]:
    """Thursday through Monday of the slate that is current or next.
    Tue/Wed roll forward to the coming Thursday; Thu-Mon stay on the slate in progress."""
    today = (today or datetime.now(CHICAGO)).date()
    back = (today.weekday() - 3) % 7          # days since the last Thursday
    thursday = today - timedelta(days=back) if back <= 4 else today + timedelta(days=7 - back)
    return thursday.strftime("%Y%m%d"), (thursday + timedelta(days=4)).strftime("%Y%m%d")


def parse_utc(iso: str) -> datetime:
    return datetime.strptime(iso, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)


def load_conferences() -> tuple[dict, set]:
    try:
        rows = fetch_json(CONFERENCES_URL).get("conferences") or []
        names = {}
        fbs = set()
        for row in rows:
            gid = str(row.get("groupId"))
            if row.get("parentGroupId") == "80":
                fbs.add(gid)
                short = row.get("shortName") or row.get("name")
                names[gid] = "Independent" if "Indep" in short else short
        if fbs:
            return names, fbs
    except Exception as exc:
        print(f"conferences lookup failed ({exc}); using built-in list")
    return dict(FALLBACK_CONFS), set(FALLBACK_CONFS)


def has_line(odds: dict | None) -> bool:
    return bool(odds) and (odds.get("spread") is not None or odds.get("total") is not None)


class Run:
    """Per-run tally so the envelope can say what quietly failed.

    Before this, warnings[] only ever held whole-date scoreboard failures, so an
    empty warnings list was not evidence of a clean build: a geocode failure
    produced no forecast, and impact() then reported "Clean outdoor conditions"
    for a game we simply knew nothing about.
    """
    MAX_WARNINGS = 50

    def __init__(self):
        self.warnings = []
        self.counts = {}

    def warn(self, msg: str) -> None:
        print(f"  WARN {msg}")
        if len(self.warnings) < self.MAX_WARNINGS:
            self.warnings.append(msg)
        elif len(self.warnings) == self.MAX_WARNINGS:
            self.warnings.append("… further warnings suppressed")

    def bump(self, key: str, n: int = 1) -> None:
        self.counts[key] = self.counts.get(key, 0) + n


class Geocoder:
    def __init__(self, existing: dict, sleep: float, run: Run):
        self.cache = {}
        self.sleep = sleep
        self.run = run
        for game in existing.get("games") or []:
            if game.get("geo") and game.get("city"):
                self.cache[(game["city"], game.get("state"))] = game["geo"]

    def lookup(self, city: str | None, state: str | None) -> dict | None:
        if not city:
            return None
        key = (city, state)
        if key in self.cache:
            return self.cache[key]
        geo = None
        try:
            rows = get(GEOCODE_URL, {"name": city, "count": 10, "language": "en", "format": "json"}).get("results") or []
            us = [r for r in rows if r.get("country_code") == "US"]
            want = STATES.get((state or "").upper())
            pick = next((r for r in us if want and r.get("admin1") == want), None) or (us[0] if us else None)
            if pick:
                geo = {
                    "lat": pick["latitude"], "lon": pick["longitude"],
                    "elev": pick.get("elevation"), "geo_name": pick.get("name"),
                    "admin1": pick.get("admin1"), "timezone": pick.get("timezone"),
                }
        except Exception as exc:
            self.run.warn(f"geocode {city}, {state}: {exc}")
            self.run.bump("geocode_failed")
        time.sleep(self.sleep)
        self.cache[key] = geo
        return geo


def forecast(geo: dict, kick: datetime, sleep: float, run: Run) -> dict | None:
    day = kick.strftime("%Y-%m-%d")
    try:
        data = get(FORECAST_URL, {
            "latitude": geo["lat"], "longitude": geo["lon"], "hourly": HOURLY,
            "temperature_unit": "fahrenheit", "wind_speed_unit": "mph",
            "precipitation_unit": "inch", "timezone": "auto",
            "start_date": (kick - timedelta(days=1)).strftime("%Y-%m-%d"),
            "end_date": (kick + timedelta(days=1)).strftime("%Y-%m-%d"),
        })
    except Exception as exc:
        run.warn(f"forecast {geo.get('geo_name')} {day}: {exc}")
        run.bump("forecast_failed")
        return None
    finally:
        time.sleep(sleep)
    offset = int(data.get("utc_offset_seconds") or 0)
    local = kick + timedelta(seconds=offset)
    want = local.strftime("%Y-%m-%dT%H:00")
    hourly = data.get("hourly") or {}
    times = hourly.get("time") or []
    if want not in times:
        run.warn(f"forecast {geo.get('geo_name')}: no hourly row for {want}")
        run.bump("forecast_missing")
        return None
    i = times.index(want)

    def col(name):
        vals = hourly.get(name) or []
        return vals[i] if i < len(vals) else None

    return {
        "timezone": data.get("timezone"),
        "utc_offset_seconds": offset,
        "kick_local": local.strftime("%Y-%m-%d %H:%M"),
        "temp": col("temperature_2m"),
        "humidity": col("relative_humidity_2m"),
        "pop": col("precipitation_probability"),
        "precip": col("precipitation"),
        "weathercode": col("weather_code"),
        "wind": col("wind_speed_10m"),
        "gusts": col("wind_gusts_10m"),
        "winddir": col("wind_direction_10m"),
        "cloud": col("cloud_cover"),
    }


def compass(deg) -> str | None:
    if deg is None:
        return None
    return COMPASS[int((float(deg) + 11.25) // 22.5) % 16]


def kick_ct(kick: datetime) -> str:
    local = kick.astimezone(CHICAGO)
    hour = local.hour % 12 or 12
    return f"{local.strftime('%a')} {hour}:{local.strftime('%M %p')} CT"


def impact(indoor: bool, wx: dict | None, elev_ft: int | None, label: str) -> dict:
    """Two scores, one level.

    impact_score is total weather magnitude: heat counts, because a 101 degree
    kickoff is weather. under_score is only the part that historically suppresses
    scoring - wind, rain, cold - and drives impact_level, because heat does not
    play like wind and rain. Without the split a calm 102 degree game reads
    "UNDER", which contradicts this function's own heat note.
    """
    if indoor:
        return {"flags": ["INDOOR"], "impact_score": 0, "under_score": 0,
                "impact_level": "NONE", "impact_notes": ["Indoor — weather off the board"]}
    wx = wx or {}
    flags, notes, score, under = [], [], 0, 0
    temp, wind, pop = wx.get("temp"), wx.get("wind"), wx.get("pop")
    if temp is not None:
        t = round(temp)
        if temp >= 90:
            flags.append("EXTREME HEAT" if temp >= 95 else "HOT")
            score += 2 if temp >= 95 else 1
            # Note bands ride the flag, never the rounding: t is rounded, temp is not.
            if t >= 98:
                notes.append(f"{t}° heat — early-season pace can stay fast; monitor late-game fade")
            elif t >= 93:
                sky = "sunny" if (wx.get("weathercode") in (0, 1)) else label.lower()
                notes.append(f"{t}° and {sky} — hydration / rotation game")
            else:
                notes.append(f"{t}° at kick — heat, hydration and rotation, not a total read")
        elif temp <= 32:
            flags.append("FREEZING")
            score += 2
            under += 2
            notes.append(f"{t}° at kick — freezing, ball and hands suffer")
        elif temp <= 40:
            flags.append("COLD")
            score += 1
            under += 1
            notes.append(f"{t}° at kick — cold-weather check on the total")
    if wind is not None:
        if wind >= 20:
            flags.append("HIGH WIND")
            score += 2
            under += 2
            notes.append(f"Wind {round(wind)} mph — passing / kicking game, lean under")
        elif wind >= 15:
            flags.append("WIND")
            score += 1
            under += 1
            notes.append(f"Wind {round(wind)} mph — check total")
    if pop is not None:
        if pop >= 60:
            flags.append("RAIN RISK")
            score += 2
            under += 2
            notes.append(f"{pop}% rain — lean under if it arrives")
        elif pop >= 40:
            flags.append("SHOWERS")
            score += 1
            under += 1
            notes.append(f"{pop}% shower chance — watch radar at kick")
    if not notes and score == 0:
        notes.append("Clean outdoor conditions")
    if elev_ft is not None and elev_ft >= 4000:
        flags.append("ALTITUDE")
        notes.append(f"Elevation {elev_ft:,} ft — kicking / conditioning note")
    level = "UNDER" if under >= 2 else "WATCH" if (under or score) else "CLEAR"
    return {"flags": flags, "impact_score": score, "under_score": under,
            "impact_level": level, "impact_notes": notes}


def team_block(comp_team: dict, conf_names: dict) -> dict:
    team = comp_team.get("team") or {}
    recs = comp_team.get("records") or []
    record = next((r.get("summary") for r in recs
                   if r.get("type") == "total" or r.get("name") == "overall"), None)
    cid = str(team.get("conferenceId") or "")
    return {
        "id": team.get("id"),
        "abbr": team.get("abbreviation"),
        "name": team.get("shortDisplayName") or team.get("name"),
        "full": team.get("displayName"),
        "logo": team.get("logo") or f"https://a.espncdn.com/i/teamlogos/ncaa/500/{team.get('id')}.png",
        "color": team.get("color"),
        "alt": team.get("alternateColor"),
        "rank": (comp_team.get("curatedRank") or {}).get("current", 99),
        "record": record,
        "score": str(comp_team.get("score") or "0"),
        "homeAway": comp_team.get("homeAway"),
        "conferenceId": cid,
        "conference": conf_names.get(cid, "FCS"),
    }


def build_game(event: dict, conf_names: dict, fbs_ids: set, geocoder: Geocoder, sleep: float,
               run: Run, prior_odds: dict | None = None) -> dict:
    comp = (event.get("competitions") or [{}])[0]
    status = event.get("status") or {}
    stype = status.get("type") or {}
    venue = comp.get("venue") or {}
    addr = venue.get("address") or {}
    kick = parse_utc(event["date"])
    teams = {t.get("homeAway"): team_block(t, conf_names) for t in comp.get("competitors") or []}
    home, away = teams.get("home") or {}, teams.get("away") or {}

    names = [n for b in comp.get("broadcasts") or [] for n in (b.get("names") or [])]
    streams = [((g.get("media") or {}).get("shortName")) for g in comp.get("geoBroadcasts") or []
               if ((g.get("type") or {}).get("shortName") == "Streaming")]
    streams = [s for s in streams if s]
    gamecast = next((l.get("href") for l in event.get("links") or [] if "summary" in (l.get("rel") or [])), None)
    tickets = ((comp.get("tickets") or [{}])[0]).get("summary")
    notes = [n.get("headline") for n in comp.get("notes") or [] if n.get("headline")]
    ew = event.get("weather") or {}
    espn_weather = {"text": ew.get("displayValue"), "temp": ew.get("temperature"),
                    "high": ew.get("highTemperature"), "link": (ew.get("link") or {}).get("href")} if ew else None

    indoor = bool(venue.get("indoor"))
    city, state = addr.get("city"), addr.get("state")
    geo = geocoder.lookup(city, state)
    elev = geo.get("elev") if geo else None
    elev_ft = round(elev * 3.28084) if elev is not None else None
    wx = forecast(geo, kick, sleep, run) if geo else None

    code = wx.get("weathercode") if wx else None
    if indoor:
        label, emoji = "Indoor climate", "\U0001f3df️"
    elif code is not None and int(code) in WMO:
        label, emoji = WMO[int(code)]
    else:
        label, emoji = ((espn_weather or {}).get("text") or "Weather"), "\U0001f321️"
    temp = wx.get("temp") if wx and wx.get("temp") is not None else (espn_weather or {}).get("temp")

    odds = parse_odds(comp)
    if not has_line(odds) and has_line(prior_odds):
        odds = prior_odds          # ESPN drops odds at kickoff; keep the last posted line as the close
        run.bump("lines_carried")
    spread = odds.get("spread") if odds else None
    total = odds.get("total") if odds else None
    if spread is not None and total is not None:
        implied = {"home": round((total - spread) / 2, 1), "away": round((total + spread) / 2, 1)}
    else:
        implied = {"home": None, "away": None}
    spread_abs = abs(spread) if spread is not None else 0

    ids = {home.get("conferenceId"), away.get("conferenceId")}
    if ids & P4_IDS:
        group = "P4/P5"
    elif any(cid not in fbs_ids for cid in ids):
        group = "FCS mix"
    else:
        group = "G5"

    # ESPN states this outright and gets the hard cases right - notably Notre Dame,
    # which is Independent (id 18) but plays ACC opponents and is correctly not a
    # conference game. Derive it only when the cdn payload shape omits the key.
    hc, ac = home.get("conferenceId"), away.get("conferenceId")
    derived = bool(hc) and hc == ac and hc != "18" and hc in fbs_ids
    conf_game = comp.get("conferenceCompetition")
    conf_game = derived if conf_game is None else bool(conf_game)

    game = {
        "id": event.get("id"),
        "name": event.get("name"),
        "shortName": event.get("shortName"),
        "date": event.get("date"),
        "status": stype.get("name"),
        "state": state,
        "statusDetail": stype.get("detail"),
        "statusShort": stype.get("shortDetail"),
        "neutral": bool(comp.get("neutralSite")),
        "notes": notes,
        "venue": venue.get("fullName"),
        "city": city,
        "indoor": indoor,
        "broadcasts": names,
        "home": home,
        "away": away,
        "odds": odds,
        "espn_weather": espn_weather,
        "geo": geo,
        "wx": wx,
        "wx_label": label,
        "wx_emoji": emoji,
        "wind_dir": compass(wx.get("winddir")) if wx and not indoor else None,
        "temp": temp,
        "streams": streams,
        "gamecast": gamecast,
        "tickets": tickets,
        "implied": implied,
        "kick_ct": kick_ct(kick),
        "elev": elev,
        "group": group,
        "conf_game": conf_game,
        "conf_label": home.get("conference") if conf_game else None,
        "spread_abs": spread_abs,
        "blowout": spread_abs >= 28,
        "networks": names,
        "venueState": state,
        "gameState": stype.get("state"),
        "elev_ft": elev_ft,
    }
    game.update(impact(indoor, wx, elev_ft, label))
    return game


def _standing(summary: dict, team_id: str | None, stat: str) -> str | None:
    if not team_id:
        return None
    for group in (summary.get("standings") or {}).get("groups") or []:
        for entry in (group.get("standings") or {}).get("entries") or []:
            if str(entry.get("id")) == str(team_id):
                for row in entry.get("stats") or []:
                    if row.get("type") == stat:
                        return row.get("displayValue")
    return None


def _ats(summary: dict, team_id: str | None) -> str | None:
    for row in summary.get("againstTheSpread") or []:
        if str((row.get("team") or {}).get("id")) == str(team_id):
            recs = row.get("records") or []
            return (recs[0] or {}).get("summary") if recs else None
    return None


def enrich(games: list, prior: dict, sleep: float, run: Run) -> None:
    """Per-game ESPN summary detail. Never raises, never drops a game.

    Kept out of build_game because an exception there drops the game entirely, and a
    detail lookup must never cost us a fixture. A new null never overwrites a good
    prior value: ESPN drops attendance and ATS records intermittently.
    """
    misses = 0
    for game in games:
        gid = game.get("id")
        was = prior.get(gid) or {}
        try:
            summary = fetch_json(f"{SUMMARY_URL}?event={gid}", timeout=8)
        except Exception as exc:
            run.warn(f"enrich {game.get('shortName')} ({gid}): {exc}")
            run.bump("enrich_failed")
            game["enrich"] = was or None
            misses += 1
            if misses >= 5:
                run.warn("enrich: 5 consecutive failures, skipping the rest of the pass")
                for rest in games[games.index(game) + 1:]:
                    rest["enrich"] = prior.get(rest.get("id")) or None
                return
            continue
        finally:
            time.sleep(sleep)
        misses = 0
        info = summary.get("gameInfo") or {}
        venue = info.get("venue") or {}
        pred = summary.get("predictor") or {}
        hid = (game.get("home") or {}).get("id")
        aid = (game.get("away") or {}).get("id")
        grass = venue.get("grass")
        fresh = {
            "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "surface": None if grass is None else ("grass" if grass else "turf"),
            "capacity": venue.get("capacity"),
            "attendance": info.get("attendance"),
            "predictor": {
                "home": (pred.get("homeTeam") or {}).get("gameProjection"),
                "away": (pred.get("awayTeam") or {}).get("gameProjection"),
            },
            "ats": {"home": _ats(summary, hid), "away": _ats(summary, aid)},
            "conf_record": {"home": _standing(summary, hid, "vsconf"),
                            "away": _standing(summary, aid, "vsconf")},
        }
        for key, value in fresh.items():
            if key == "at":
                continue
            if isinstance(value, dict):
                for sub, sv in value.items():
                    if sv is None and (was.get(key) or {}).get(sub) is not None:
                        value[sub] = was[key][sub]
            elif value is None and was.get(key) is not None:
                fresh[key] = was[key]
        game["enrich"] = fresh
        run.bump("enriched")


def pull(date: str, run: Run) -> tuple[list, dict, bool]:
    """Returns (events, payload, groups80). The last endpoint drops groups=80, so a
    date served by it carries the whole D1 slate; the caller filters it back to FBS."""
    last = None
    for i, url in enumerate(endpoints(date)):
        try:
            data = fetch_json(url)
            events = events_from(data)
            print(f"  {date} {url.split('/')[2]} -> {len(events)} events")
            if i:
                run.bump("fallback_url_used")
                run.warn(f"{date}: primary scoreboard failed, served by {url.split('/')[2]} (#{i + 1})")
            return events, data, "groups=80" in url
        except Exception as exc:
            last = exc
            print(f"  {date} fail {url.split('/')[2]}: {exc}")
    raise RuntimeError(f"{date}: {last}")


def week_label(payload: dict, events: list) -> str | None:
    lg = (payload.get("leagues") or [{}])[0]
    season = lg.get("season") or {}
    year = season.get("year") or (events[0].get("season") or {}).get("year") if events else None
    number = (payload.get("week") or {}).get("number") or (events[0].get("week") or {}).get("number") if events else None
    stype = (season.get("type") or {})
    if stype.get("type") not in (None, 2):
        return f"{stype.get('name') or 'Postseason'} · {year}" if year else None
    if number and year:
        return f"Week {number} · {year}"
    return f"{year} season" if year else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", help="first ESPN (Eastern) date, YYYYMMDD (default: this/next Thursday)")
    ap.add_argument("--end", help="last ESPN date, inclusive, YYYYMMDD (default: start + 4 days, Monday)")
    ap.add_argument("--out", default=str(ROOT), help="directory for games.json / games.js (default: repo root)")
    ap.add_argument("--sleep", type=float, default=0.2, help="seconds between Open-Meteo calls")
    ap.add_argument("--enrich", action=argparse.BooleanOptionalAction, default=True,
                    help="pull per-game ESPN summary detail (surface, predictor, ATS, conf record)")
    args = ap.parse_args()

    run = Run()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    existing = {}
    try:
        existing = json.loads((out / "games.json").read_text("utf-8"))
    except Exception:
        pass

    start, end = default_dates()
    start = args.start or start
    end = args.end or (end if not args.start else args.start)
    dates = date_range(start, end)
    print(f"ESPN scoreboard for {', '.join(dates)}")
    events, seen, label = [], set(), None
    conf_names, fbs_ids = load_conferences()   # needed inside the loop to refilter a groups-less pull
    for date in dates:
        try:
            batch, payload, groups80 = pull(date, run)
        except Exception as exc:
            run.warn(str(exc))
            run.bump("dates_failed")
            continue
        if not groups80:
            # Filter rather than reject: dropping the date would lose a whole slate day.
            before = len(batch)
            batch = [e for e in batch
                     if any((c.get("team") or {}).get("conferenceId") in fbs_ids
                            or str((c.get("team") or {}).get("conferenceId")) in fbs_ids
                            for c in ((e.get("competitions") or [{}])[0].get("competitors") or []))]
            run.bump("no_groups_fallback")
            run.warn(f"{date}: fallback URL has no groups=80; filtered {before} -> {len(batch)} to FBS")
        label = label or week_label(payload, batch)
        for event in batch:
            if event.get("id") and event["id"] not in seen:
                seen.add(event["id"])
                events.append(event)
    if not events:
        print("no games found; nothing written")
        return 1

    geocoder = Geocoder(existing, args.sleep, run)
    prior = {g["id"]: g.get("odds") for g in existing.get("games") or [] if g.get("id")}
    games = []
    print(f"Building {len(events)} games (geocode + kickoff-hour forecast)")
    for i, event in enumerate(events, 1):
        try:
            game = build_game(event, conf_names, fbs_ids, geocoder, args.sleep, run, prior.get(event.get("id")))
        except Exception as exc:
            run.warn(f"skip {event.get('shortName')} ({event.get('id')}): {exc}")
            run.bump("games_skipped")
            continue
        games.append(game)
        wx = "wx ok" if game["wx"] else ("indoor" if game["indoor"] else "no wx")
        print(f"  [{i}/{len(events)}] {game['shortName']:<14} {game['kick_ct']:<15} {game['city'] or '?'}, {game['state'] or '?'}  {wx}")
    if args.enrich:
        prior_enrich = {g["id"]: g.get("enrich") for g in existing.get("games") or [] if g.get("id")}
        print(f"Enriching {len(games)} games (ESPN summary)")
        enrich(games, prior_enrich, args.sleep, run)

    games.sort(key=lambda g: (g["date"] or "", g["shortName"] or ""))

    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "ESPN scoreboard + Open-Meteo kickoff hour",
        "week_label": label,
        "dates": dates,
        "warnings": run.warnings,
        "counts": dict(run.counts, games=len(games), events=len(events)),
        "count": len(games),
        "games": games,
    }
    (out / "games.json").write_text(json.dumps(payload), "utf-8")
    (out / "games.js").write_text("window.CFB_DATA = " + json.dumps(payload, separators=(",", ":")) + ";\n", "utf-8")
    missing_wx = sum(1 for g in games if not g["wx"] and not g["indoor"])
    print(f"\nWrote {out / 'games.json'} and {out / 'games.js'}")
    print(f"{len(games)} games · {label or 'week label unknown'} · {missing_wx} without forecast")
    if run.counts:
        print("counts: " + ", ".join(f"{k}={v}" for k, v in sorted(run.counts.items())))
    if run.warnings:
        print(f"{len(run.warnings)} warning(s) recorded in the snapshot envelope")
    return 0


if __name__ == "__main__":
    sys.exit(main())
