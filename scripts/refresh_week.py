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


class Geocoder:
    def __init__(self, existing: dict, sleep: float):
        self.cache = {}
        self.sleep = sleep
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
            print(f"  geocode fail {city}, {state}: {exc}")
        time.sleep(self.sleep)
        self.cache[key] = geo
        return geo


def forecast(geo: dict, kick: datetime, sleep: float) -> dict | None:
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
        print(f"  forecast fail {geo.get('geo_name')} {day}: {exc}")
        return None
    finally:
        time.sleep(sleep)
    offset = int(data.get("utc_offset_seconds") or 0)
    local = kick + timedelta(seconds=offset)
    want = local.strftime("%Y-%m-%dT%H:00")
    hourly = data.get("hourly") or {}
    times = hourly.get("time") or []
    if want not in times:
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
    if indoor:
        return {"flags": ["INDOOR"], "impact_score": 0, "impact_level": "NONE",
                "impact_notes": ["Indoor — weather off the board"]}
    wx = wx or {}
    flags, notes, score = [], [], 0
    temp, wind, pop = wx.get("temp"), wx.get("wind"), wx.get("pop")
    if temp is not None:
        t = round(temp)
        if temp >= 95:
            flags.append("EXTREME HEAT")
        elif temp >= 90:
            flags.append("HOT")
        elif temp <= 32:
            flags.append("FREEZING")
            score += 1
            notes.append(f"{t}° at kick — freezing, ball and hands suffer")
        elif temp <= 40:
            flags.append("COLD")
            notes.append(f"{t}° at kick — cold-weather check on the total")
        if t >= 98:
            notes.append(f"{t}° heat — early-season pace can stay fast; monitor late-game fade")
        elif t >= 93:
            sky = "sunny" if (wx.get("weathercode") in (0, 1)) else label.lower()
            notes.append(f"{t}° and {sky} — hydration / rotation game")
    if wind is not None:
        if wind >= 20:
            flags.append("HIGH WIND")
            score += 2
            notes.append(f"Wind {round(wind)} mph — passing / kicking game, lean under")
        elif wind >= 15:
            flags.append("WIND")
            score += 1
            notes.append(f"Wind {round(wind)} mph — check total")
    if pop is not None:
        if pop >= 60:
            flags.append("RAIN RISK")
            score += 2
            notes.append(f"{pop}% rain — lean under if it arrives")
        elif pop >= 40:
            flags.append("SHOWERS")
            score += 1
            notes.append(f"{pop}% shower chance — watch radar at kick")
    if not notes and score == 0:
        notes.append("Clean outdoor conditions")
    if elev_ft is not None and elev_ft >= 4000:
        flags.append("ALTITUDE")
        notes.append(f"Elevation {elev_ft:,} ft — kicking / conditioning note")
    level = "CLEAR" if score == 0 else "WATCH" if score == 1 else "UNDER"
    return {"flags": flags, "impact_score": score, "impact_level": level, "impact_notes": notes}


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


def build_game(event: dict, conf_names: dict, fbs_ids: set, geocoder: Geocoder, sleep: float) -> dict:
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
    wx = forecast(geo, kick, sleep) if geo else None

    code = wx.get("weathercode") if wx else None
    if indoor:
        label, emoji = "Indoor climate", "\U0001f3df️"
    elif code is not None and int(code) in WMO:
        label, emoji = WMO[int(code)]
    else:
        label, emoji = ((espn_weather or {}).get("text") or "Weather"), "\U0001f321️"
    temp = wx.get("temp") if wx and wx.get("temp") is not None else (espn_weather or {}).get("temp")

    odds = parse_odds(comp)
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
        "spread_abs": spread_abs,
        "blowout": spread_abs >= 28,
        "networks": names,
        "venueState": state,
        "gameState": stype.get("state"),
        "elev_ft": elev_ft,
    }
    game.update(impact(indoor, wx, elev_ft, label))
    return game


def pull(date: str) -> tuple[list, dict]:
    last = None
    for url in endpoints(date):
        try:
            data = fetch_json(url)
            events = events_from(data)
            print(f"  {date} {url.split('/')[2]} -> {len(events)} events")
            return events, data
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
    args = ap.parse_args()

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
    events, seen, label, warnings = [], set(), None, []
    for date in dates:
        try:
            batch, payload = pull(date)
        except Exception as exc:
            warnings.append(str(exc))
            print(f"  WARN {exc}")
            continue
        label = label or week_label(payload, batch)
        for event in batch:
            if event.get("id") and event["id"] not in seen:
                seen.add(event["id"])
                events.append(event)
    if not events:
        print("no games found; nothing written")
        return 1

    conf_names, fbs_ids = load_conferences()
    geocoder = Geocoder(existing, args.sleep)
    games = []
    print(f"Building {len(events)} games (geocode + kickoff-hour forecast)")
    for i, event in enumerate(events, 1):
        try:
            game = build_game(event, conf_names, fbs_ids, geocoder, args.sleep)
        except Exception as exc:
            print(f"  skip {event.get('shortName')} ({event.get('id')}): {exc}")
            continue
        games.append(game)
        wx = "wx ok" if game["wx"] else ("indoor" if game["indoor"] else "no wx")
        print(f"  [{i}/{len(events)}] {game['shortName']:<14} {game['kick_ct']:<15} {game['city'] or '?'}, {game['state'] or '?'}  {wx}")
    games.sort(key=lambda g: (g["date"] or "", g["shortName"] or ""))

    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "ESPN scoreboard + Open-Meteo kickoff hour",
        "week_label": label,
        "dates": dates,
        "warnings": warnings,
        "count": len(games),
        "games": games,
    }
    (out / "games.json").write_text(json.dumps(payload), "utf-8")
    (out / "games.js").write_text("window.CFB_DATA = " + json.dumps(payload, separators=(",", ":")) + ";\n", "utf-8")
    missing_wx = sum(1 for g in games if not g["wx"] and not g["indoor"])
    print(f"\nWrote {out / 'games.json'} and {out / 'games.js'}")
    print(f"{len(games)} games · {label or 'week label unknown'} · {missing_wx} without forecast")
    return 0


if __name__ == "__main__":
    sys.exit(main())
