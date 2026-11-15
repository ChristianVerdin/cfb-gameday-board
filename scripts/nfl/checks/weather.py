"""Weather builder: roof rules, kick-hour pick (offsets, DST), tags, stale carry-forward, vocabulary. Fake HTTP only."""
from __future__ import annotations

import json
import re
import urllib.error
from datetime import datetime, timedelta, timezone

from nflcore import venues, weather as W

NOW = datetime(2026, 11, 15, 18, 0, tzinfo=timezone.utc)
BANNED = re.compile(r"\b(" + "|".join(("un" + "der", "wat" + "ch", "le" + "an", "to" + "tal", "od" + "ds", "spr" + "ead")) + r")\b", re.I)


def _venue(**kw):
    base = dict(id="x", name="Test Field", roof="open", lat=40.0, lon=-80.0, tz="America/New_York", elev_ft=None, verified="2src")
    return {**base, **kw}


def _raw(start_utc: datetime, hours=30, **fields):
    """Hourly response beginning on the hour of start_utc; fields override per-hour lists or give a constant."""
    t0 = int(start_utc.replace(minute=0, second=0, microsecond=0).timestamp())
    h = {"time": [t0 + 3600 * i for i in range(hours)]}
    base = {"temperature_2m": 55, "apparent_temperature": 52, "wind_speed_10m": 5, "wind_gusts_10m": 9, "wind_direction_10m": 270,
            "precipitation_probability": 10, "precipitation": 0.0, "snowfall": 0.0, "weather_code": 1, "cloud_cover": 40}
    for k, v in base.items():
        v = fields.get(k, v)
        h[k] = list(v) if isinstance(v, (list, tuple)) else [v] * hours
    return {"hourly": h, "utc_offset_seconds": -18000}


class Fetch:
    def __init__(self, raw=None, fail=False):
        self.raw, self.fail, self.calls = raw, fail, []

    def __call__(self, lat, lon):
        self.calls.append((lat, lon))
        if self.fail:
            raise W.WeatherError("boom")
        return self.raw


def _game(venue, kick, fetch, **kw):
    return W.for_game(venue, kick, now=NOW, fetch=fetch, **kw)


def test_roof_rules(check):
    kick = NOW + timedelta(days=2)
    raw = _raw(kick - timedelta(hours=3))
    f = Fetch(raw)
    check("dome status", _game(_venue(roof="dome"), kick, f), ("dome", None))
    check("dome makes no call", f.calls, [])
    s, wx = _game(_venue(roof="retractable"), kick, Fetch(raw))
    check("retractable status", s, "retractable")
    check("retractable note", wx["roof_note"], "Roof may be closed")
    check("retractable no tags", (wx["flags"], wx["level"], wx["notes"]), ([], "none", []))
    s, wx = _game(_venue(roof="canopy"), kick, Fetch(raw))
    check("canopy status and note", (s, wx["roof_note"]), ("canopy", "Roof over seats"))
    s, wx = _game(_venue(), kick, Fetch(raw))
    check("open status", s, "ok")
    check("open has no roof note", wx["roof_note"], None)
    check("unknown venue", _game(None, kick, f), ("unknown_venue", None))
    check("venue without coordinates", _game(_venue(lat=None, lon=None), kick, f), ("unknown_venue", None))
    check("time tbd", _game(_venue(), kick, f, time_tbd=True), ("tbd", None))
    check("placeholder", _game(_venue(), kick, f, placeholder=True), ("na", None))
    check("all star", _game(_venue(), kick, f, kind="all_star"), ("na", None))
    check("beyond horizon", _game(_venue(), NOW + timedelta(days=17), f), ("beyond_horizon", None))
    check("skips made no calls", f.calls, [])
    real = venues.VENUES["3727"]
    check("table dome venue", _game(real, kick, f)[0], "dome")


def test_one_call_per_venue(check):
    kick = NOW + timedelta(days=2)
    f = Fetch(_raw(kick - timedelta(hours=3)))
    cache: dict = {}
    for k in (kick, kick + timedelta(hours=4)):
        _game(_venue(), k, f, cache=cache)
    check("shared fetch", len(f.calls), 1)


def test_kick_hour(check):
    base = datetime(2026, 11, 22, 17, 0, tzinfo=timezone.utc)
    temps = [40 + i for i in range(30)]
    raw = _raw(base - timedelta(hours=4), temperature_2m=temps)
    t0 = base - timedelta(hours=4)
    for minute in (0, 5, 15, 20, 25, 30):
        k = base.replace(minute=minute)
        wx = W.build_wx(_venue(), k, raw, "z")
        check(f"kick :{minute:02d} picks the containing hour", wx["temp"], 44.0)
        check(f"kick :{minute:02d} window starts there", wx["window"]["min_temp"], 44.0)
    wx = W.build_wx(_venue(), base.replace(minute=30), raw, "z")
    check("window runs to kick+3h", wx["window"]["hours"], 3)
    wx = W.build_wx(_venue(), base.replace(minute=30), _raw(t0, temperature_2m=[50] * 4 + [50, 50, 50, 50, 20] + [50] * 21), "z")
    check("hour at kick+3h is in the window", wx["window"]["min_temp"], 50.0)
    wx = W.build_wx(_venue(), base.replace(minute=0), _raw(t0, temperature_2m=[50] * 4 + [50, 50, 50, 20] + [50] * 22), "z")
    check("kick+3h on the hour is in the window", wx["window"]["min_temp"], 20.0)
    check("local label", W.build_wx(_venue(tz="America/Chicago"), base.replace(minute=5), raw, "z")["kick_local"], "11:05 AM")
    try:
        W.build_wx(_venue(), base + timedelta(days=5), raw, "z")
        check.true("missing hour raises", False)
    except W.WeatherError:
        check.true("missing hour raises", True)


def test_dst(check):
    # US fall-back is 2026-11-01 at 06:00 UTC: a 17:00 UTC kick is 12:00 EST, one at 05:00 UTC is 1:00 EDT.
    for iso, want in (("2026-11-01T17:00:00+00:00", "12:00 PM"), ("2026-11-01T05:30:00+00:00", "1:30 AM"),
                      ("2026-03-08T19:00:00+00:00", "3:00 PM")):
        k = datetime.fromisoformat(iso)
        wx = W.build_wx(_venue(), k, _raw(k - timedelta(hours=6), hours=12), "z")
        check(f"local kick {iso}", wx["kick_local"], want)
        check(f"hour found {iso}", wx["temp"], 55.0)
    k = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)   # EU change day, Munich
    check("Munich offset", W.kick_local(k, "Europe/Berlin"), "1:00 PM")
    check("Mexico City", W.kick_local(datetime(2026, 11, 15, 2, 30, tzinfo=timezone.utc), "America/Mexico_City"), "8:30 PM")


def test_tags(check):
    def agg(**kw):
        return {"wind": 5, "gust": 8, "tmin": 55, "tmax": 55, "pop": 0, "precip": 0, "snow": False, **kw}
    cases = [
        ("calm", agg(), [], "none"),
        ("wind 15", agg(wind=15), ["WIND"], "notable"),
        ("wind 14 gust 24", agg(wind=14, gust=24), [], "none"),
        ("gust 25", agg(wind=10, gust=25), ["WIND"], "notable"),
        ("high wind 20", agg(wind=20), ["HIGH WIND"], "severe"),
        ("cold 32", agg(tmin=32, tmax=36), ["COLD"], "notable"),
        ("cold 33", agg(tmin=33), [], "none"),
        ("heat 90", agg(tmax=90), ["HEAT"], "notable"),
        ("heat 89", agg(tmax=89), [], "none"),
        ("pop 60", agg(pop=60), ["WET"], "notable"),
        ("pop 59", agg(pop=59), [], "none"),
        ("precip .1", agg(precip=0.1), ["WET"], "notable"),
        ("snow", agg(snow=True), ["SNOW"], "severe"),
        ("deep cold", agg(tmin=10), ["COLD"], "severe"),
    ]
    for name, a, flags, level in cases:
        check(name, W.tags(a), (flags, level))
    check("altitude verified", W.tags(agg(), 5280), (["ALTITUDE"], "none"))
    check("below altitude line", W.tags(agg(), 3999), ([], "none"))
    kick = NOW + timedelta(days=1)
    for code in (71, 73, 75, 77, 85, 86):
        wx = W.build_wx(_venue(), kick, _raw(kick - timedelta(hours=2), weather_code=code), "z")
        check(f"wmo {code} is SNOW", "SNOW" in wx["flags"], True)
    check("wmo 61 is not SNOW", "SNOW" in W.build_wx(_venue(), kick, _raw(kick - timedelta(hours=2), weather_code=61), "z")["flags"], False)
    den = W.build_wx(_venue(elev_ft=5280, verified="2src"), kick, _raw(kick - timedelta(hours=2)), "z")
    check("verified elevation tags ALTITUDE", den["flags"], ["ALTITUDE"])
    una = W.build_wx(_venue(elev_ft=5280, verified="unverified"), kick, _raw(kick - timedelta(hours=2)), "z")
    check("unverified elevation never tags", una["flags"], [])
    wx = W.build_wx(_venue(), kick, _raw(kick - timedelta(hours=2), wind_speed_10m=18, wind_gusts_10m=29), "z")
    check("wind note", wx["notes"], ["Wind 18 mph, gusts 29 mph"])


def test_vocabulary(check):
    kick = NOW + timedelta(days=1)
    storm = _raw(kick - timedelta(hours=2), wind_speed_10m=25, wind_gusts_10m=40, temperature_2m=20, precipitation_probability=90,
                 precipitation=0.3, weather_code=73)
    wx = W.build_wx(_venue(), kick, storm, "z")
    text = json.dumps([wx["flags"], wx["notes"], wx["label"], wx["roof_note"], list(wx)])
    check.true("no banned words in wx output", not BANNED.search(text), BANNED.search(text) and BANNED.search(text).group(0))
    check.true("storm is severe", wx["level"] == "severe")
    check("labels", [W.label(c) for c in (0, 2, 3, 45, 53, 63, 81, 73, 95)],
          ["Clear", "Partly cloudy", "Overcast", "Fog", "Drizzle", "Rain", "Showers", "Snow", "Thunderstorms"])


def test_stale_carry(check):
    kick = NOW + timedelta(days=1)
    good = W.build_wx(_venue(), kick, _raw(kick - timedelta(hours=2)), "2026-11-14T09:00:00Z")
    s, wx = _game(_venue(), kick, Fetch(fail=True), prev=("ok", good))
    check("stale status kept", s, "ok")
    check("stale flag set", wx["stale"], True)
    check("original fetched_at kept", wx["fetched_at"], "2026-11-14T09:00:00Z")
    check("carry does not mutate the previous block", "stale" in good, False)
    check("no prior: error, never clean", _game(_venue(), kick, Fetch(fail=True)), ("error", None))
    f = Fetch(fail=True)
    cache: dict = {}
    for _ in range(2):
        _game(_venue(), kick, f, cache=cache)
    check("failed venue not refetched", len(f.calls), 1)
    s, wx = _game(_venue(), kick, Fetch({"hourly": {"time": []}}), prev=None)
    check("empty forecast is an error", (s, wx), ("error", None))


class _Resp:
    def __init__(self, body):
        self.body = body


def test_fetch_retry(check):
    good = json.dumps(_raw(NOW)).encode()
    for name, first, sleeps in (
        ("429", urllib.error.HTTPError("u", 429, "x", {}, None), [5]),
        ("500", urllib.error.HTTPError("u", 500, "x", {}, None), [1]),
        ("timeout", TimeoutError("t"), [1]),
    ):
        seen = []

        def get(url, timeout, _first=first, _seen=seen):
            _seen.append((url, timeout))
            if len(_seen) == 1:
                raise _first
            return good
        slept: list = []
        out = W.fetch_forecast(40.0, -80.0, http_get=get, sleep=slept.append)
        check(f"{name} retried once", len(seen), 2)
        check(f"{name} backoff", slept, sleeps)
        check.true(f"{name} result", "hourly" in out)
    url, timeout = seen[0]
    check("timeout 10 s", timeout, 10)
    for frag in ("temperature_unit=fahrenheit", "wind_speed_unit=mph", "precipitation_unit=inch", "timeformat=unixtime",
                 "timezone=auto", "hourly=temperature_2m%2Capparent_temperature"):
        check.true(f"url has {frag}", frag in url, url)

    def dead(url, timeout):
        raise urllib.error.HTTPError(url, 503, "x", {}, None)
    try:
        W.fetch_forecast(1.0, 2.0, http_get=dead, sleep=lambda s: None)
        check.true("two failures raise", False)
    except W.WeatherError:
        check.true("two failures raise", True)
