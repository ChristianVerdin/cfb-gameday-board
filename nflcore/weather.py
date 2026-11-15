"""Kickoff-hour forecasts from Open-Meteo. Builder only: api/ never imports this (no request-time weather)."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

URL = "https://api.open-meteo.com/v1/forecast"
HOURLY = ("temperature_2m", "apparent_temperature", "wind_speed_10m", "wind_gusts_10m", "wind_direction_10m",
          "precipitation_probability", "precipitation", "snowfall", "weather_code", "cloud_cover")
TIMEOUT = 10
HORIZON_DAYS = 16
WINDOW_HOURS = 3
ROOF_NOTES = {"retractable": "Roof may be closed", "canopy": "Roof over seats"}
SNOW_CODES = frozenset((71, 73, 75, 77, 85, 86))


class WeatherError(Exception):
    pass


def _get(url: str, timeout: float) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "nfl-board/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch_forecast(lat: float, lon: float, http_get=_get, sleep=time.sleep) -> dict:
    """One venue's hourly forecast. 10 s timeout, one retry, a longer pause after a 429."""
    q = urllib.parse.urlencode({
        "latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}", "hourly": ",".join(HOURLY),
        "temperature_unit": "fahrenheit", "wind_speed_unit": "mph", "precipitation_unit": "inch",
        "timeformat": "unixtime", "timezone": "auto", "past_days": 7, "forecast_days": HORIZON_DAYS,
    })
    last = "unknown"
    for attempt in range(2):
        try:
            data = json.loads(http_get(f"{URL}?{q}", TIMEOUT))
            if isinstance(data, dict) and isinstance(data.get("hourly"), dict) and data["hourly"].get("time"):
                return data
            last = "no hourly data"
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            if attempt == 0:
                sleep(5 if e.code == 429 else 1)
                continue
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            last = f"{type(e).__name__}: {e}"
        if attempt == 0:
            sleep(1)
    raise WeatherError(last)


def label(code) -> str:
    if code is None:
        return ""
    c = int(code)
    if c == 0:
        return "Clear"
    if c in (1, 2):
        return "Partly cloudy"
    if c == 3:
        return "Overcast"
    if c in (45, 48):
        return "Fog"
    if 51 <= c <= 57:
        return "Drizzle"
    if c in (61, 63, 65, 66, 67):
        return "Rain"
    if c in (80, 81, 82):
        return "Showers"
    if c in SNOW_CODES:
        return "Snow"
    if c >= 95:
        return "Thunderstorms"
    return ""


def _at(h: dict, key: str, i: int):
    arr = h.get(key) or []
    return arr[i] if i < len(arr) else None


def _vals(h: dict, key: str, idxs) -> list[float]:
    return [v for v in (_at(h, key, i) for i in idxs) if v is not None]


def _r(v, n=1):
    return None if v is None else round(float(v), n)


def tags(agg: dict, elev_ft=None) -> tuple[list[str], str]:
    """Neutral factual tags and a level from window aggregates; ALTITUDE is a venue fact and never raises the level."""
    f: list[str] = []
    wind, gust = agg.get("wind") or 0, agg.get("gust") or 0
    if wind >= 20:
        f.append("HIGH WIND")
    elif wind >= 15 or gust >= 25:
        f.append("WIND")
    if agg.get("tmin") is not None and agg["tmin"] <= 32:
        f.append("COLD")
    if agg.get("tmax") is not None and agg["tmax"] >= 90:
        f.append("HEAT")
    if (agg.get("pop") or 0) >= 60 or (agg.get("precip") or 0) >= 0.1:
        f.append("WET")
    if agg.get("snow"):
        f.append("SNOW")
    severe = ("HIGH WIND" in f or "SNOW" in f or gust >= 35 or (agg.get("tmin") is not None and agg["tmin"] <= 15)
              or (agg.get("precip") or 0) >= 0.25 or (agg.get("tmax") is not None and agg["tmax"] >= 100))
    level = "severe" if severe else "notable" if f else "none"
    if elev_ft is not None and elev_ft >= 4000:
        f.append("ALTITUDE")
    return f, level


def notes_for(agg: dict, flags: list[str], elev_ft=None) -> list[str]:
    out = []
    if "WIND" in flags or "HIGH WIND" in flags:
        out.append(f"Wind {round(agg['wind'])} mph, gusts {round(agg['gust'])} mph")
    if "COLD" in flags:
        out.append(f"Low {round(agg['tmin'])} F")
    if "HEAT" in flags:
        out.append(f"High {round(agg['tmax'])} F")
    if "SNOW" in flags:
        out.append("Snow in the forecast")
    if "WET" in flags:
        bits = [f"{round(agg['pop'])}% chance of precipitation"] if (agg.get("pop") or 0) >= 60 else []
        if (agg.get("precip") or 0) >= 0.1:
            bits.append(f"{agg['precip']:.2f} in expected")
        out.append(", ".join(bits))
    if "ALTITUDE" in flags and elev_ft:
        out.append(f"Elevation {elev_ft:,} ft")
    return out


def kick_local(kick_utc: datetime, tz: str) -> str:
    d = kick_utc.astimezone(ZoneInfo(tz))
    return f"{d.hour % 12 or 12}:{d.minute:02d} {'PM' if d.hour >= 12 else 'AM'}"


def build_wx(venue: dict, kick_utc: datetime, raw: dict, fetched_at: str) -> dict:
    """The wx block for one game from a raw Open-Meteo response. Raises WeatherError if the kick hour is missing."""
    h = raw.get("hourly") or {}
    times = h.get("time") or []
    ts = int(kick_utc.timestamp())
    idx = max((i for i, t in enumerate(times) if t <= ts), default=None)
    if idx is None or ts - times[idx] >= 3600 or _at(h, "temperature_2m", idx) is None:
        raise WeatherError("kick hour not in forecast")
    win = [i for i, t in enumerate(times) if times[idx] <= t <= times[idx] + WINDOW_HOURS * 3600]
    # precipitation, wind and probability are preceding-hour values: the game hours are labelled one hour later
    pw = [i for i, t in enumerate(times) if times[idx] < t <= times[idx] + WINDOW_HOURS * 3600]
    code = _at(h, "weather_code", idx)
    agg = {
        "wind": max(_vals(h, "wind_speed_10m", pw), default=None), "gust": max(_vals(h, "wind_gusts_10m", pw), default=None),
        "tmin": min(_vals(h, "temperature_2m", win), default=None), "tmax": max(_vals(h, "temperature_2m", win), default=None),
        "pop": max(_vals(h, "precipitation_probability", pw), default=None), "precip": sum(_vals(h, "precipitation", pw)),
        "snow": any(c in SNOW_CODES for c in _vals(h, "weather_code", win)) or sum(_vals(h, "snowfall", win)) > 0,
    }
    for k in ("wind", "gust"):
        agg[k] = agg[k] or 0
    roof = venue.get("roof")
    elev = venue.get("elev_ft") if venue.get("verified") in ("2src", "1src") else None
    flags, level = ([], "none") if roof == "retractable" else tags(agg, elev)
    return {
        "fetched_at": fetched_at, "kick_utc": kick_utc.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "kick_local": kick_local(kick_utc, venue["tz"]),
        "temp": _r(_at(h, "temperature_2m", idx)), "apparent": _r(_at(h, "apparent_temperature", idx)),
        "wind": _r(_at(h, "wind_speed_10m", idx)), "gusts": _r(_at(h, "wind_gusts_10m", idx)),
        "winddir": _r(_at(h, "wind_direction_10m", idx), 0), "pop": _r(_at(h, "precipitation_probability", idx), 0),
        "precip": _r(_at(h, "precipitation", idx), 2), "code": None if code is None else int(code),
        "cloud": _r(_at(h, "cloud_cover", idx), 0), "label": label(code),
        "roof_note": ROOF_NOTES.get(roof),
        "flags": flags, "level": level, "notes": [] if roof == "retractable" else notes_for(agg, flags, elev),
        "window": {"hours": WINDOW_HOURS, "max_gust": _r(agg["gust"]), "min_temp": _r(agg["tmin"]),
                   "max_pop": _r(agg["pop"], 0), "precip_sum": _r(agg["precip"], 2)},
    }


def for_game(venue: dict | None, kick_utc: datetime | None, *, kind="regular", placeholder=False, time_tbd=False,
             now: datetime, fetch, prev: tuple[str, dict] | None = None, cache: dict | None = None):
    """(wx_status, wx) for one game. fetch(lat, lon) -> raw response; a dome or a skipped game never calls it.

    prev is the (status, wx) from the last snapshot; a failed fetch carries it forward as stale.
    """
    if placeholder or kind == "all_star":
        return "na", None
    if not venue or venue.get("lat") is None or venue.get("lon") is None or not venue.get("tz"):
        return "unknown_venue", None
    if venue["roof"] == "dome":
        return "dome", None
    if time_tbd or kick_utc is None:
        return "tbd", None
    if kick_utc - now > timedelta(days=HORIZON_DAYS):
        return "beyond_horizon", None
    status = venue["roof"] if venue["roof"] in ROOF_NOTES else "ok"
    cache = cache if cache is not None else {}
    key = (venue["lat"], venue["lon"])
    try:
        if key not in cache:
            try:
                cache[key] = fetch(venue["lat"], venue["lon"])
            except WeatherError as e:
                cache[key] = e
        if isinstance(cache[key], WeatherError):
            raise cache[key]
        return status, build_wx(venue, kick_utc, cache[key], now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    except (WeatherError, KeyError, TypeError, ValueError):
        if prev and prev[1] and prev[1].get("kick_utc") == kick_utc.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"):
            return prev[0], {**prev[1], "stale": True}
        return "error", None
