#!/usr/bin/env python3
"""Smoke test for the rules that matter on a Saturday. No network.

    python3 scripts/check.py

Covers the weather flag / impact table, CT kickoff formatting, compass, default
dates, and the client's liveMath() (run under node when node is on PATH).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from refresh_week import CHICAGO, compass, default_dates, has_line, impact, kick_ct  # noqa: E402

FAILS = []


def check(name: str, got, want):
    if got != want:
        FAILS.append(f"{name}: got {got!r}, want {want!r}")


def wx(**kw):
    base = {"temp": 75.0, "wind": 5.0, "pop": 5, "weathercode": 0}
    base.update(kw)
    return base


def test_impact():
    r = impact(True, wx(temp=100), 200, "Clear")
    check("indoor flags", r["flags"], ["INDOOR"])
    check("indoor level", r["impact_level"], "NONE")

    r = impact(False, wx(), 200, "Clear")
    check("clean flags", r["flags"], [])
    check("clean notes", r["impact_notes"], ["Clean outdoor conditions"])
    check("clean level", r["impact_level"], "CLEAR")

    check("hot 90", impact(False, wx(temp=90.4), 0, "Clear")["flags"], ["HOT"])
    check("hot 90 note", impact(False, wx(temp=90.4), 0, "Clear")["impact_notes"],
          ["90° at kick — heat, hydration and rotation, not a total read"])
    check("heat 95", impact(False, wx(temp=95.0), 0, "Clear")["flags"], ["EXTREME HEAT"])
    check("heat 93 note", impact(False, wx(temp=92.7), 0, "Clear")["impact_notes"],
          ["93° and sunny — hydration / rotation game"])
    check("heat 98 note", impact(False, wx(temp=98.4), 0, "Clear")["impact_notes"],
          ["98° heat — early-season pace can stay fast; monitor late-game fade"])
    check("heat overcast note", impact(False, wx(temp=94, weathercode=3), 0, "Overcast")["impact_notes"],
          ["94° and overcast — hydration / rotation game"])

    # Heat is weather (scores) but not an under signal (under_score stays 0).
    # A calm 101 degree kickoff must read WATCH: never CLEAR, never UNDER.
    check("heat 95 level", impact(False, wx(temp=95.0), 0, "Clear")["impact_level"], "WATCH")
    check("heat 95 score", impact(False, wx(temp=95.0), 0, "Clear")["impact_score"], 2)
    check("hot 90 level", impact(False, wx(temp=90.4), 0, "Clear")["impact_level"], "WATCH")
    r = impact(False, wx(temp=101.4, wind=4.9, pop=7), 0, "Overcast")
    check("calm heat not under", r["impact_level"], "WATCH")
    check("calm heat under_score", r["under_score"], 0)
    check("heat plus wind under", impact(False, wx(temp=101.4, wind=22), 0, "Clear")["impact_level"], "UNDER")
    check("indoor under_score", impact(True, wx(temp=100), 200, "Clear")["under_score"], 0)

    check("cold", impact(False, wx(temp=38), 0, "Clear")["flags"], ["COLD"])
    check("cold level", impact(False, wx(temp=38), 0, "Clear")["impact_level"], "WATCH")
    check("freezing", impact(False, wx(temp=30), 0, "Clear")["flags"], ["FREEZING"])
    check("freezing level", impact(False, wx(temp=30), 0, "Clear")["impact_level"], "UNDER")

    r = impact(False, wx(wind=17.8), 4505, "Clear")
    check("wind flags", r["flags"], ["WIND", "ALTITUDE"])
    check("wind level", r["impact_level"], "WATCH")
    check("wind notes", r["impact_notes"],
          ["Wind 18 mph — check total", "Elevation 4,505 ft — kicking / conditioning note"])
    check("high wind level", impact(False, wx(wind=22), 0, "Clear")["impact_level"], "UNDER")
    check("wind 14 no flag", impact(False, wx(wind=14.6), 0, "Clear")["flags"], [])

    r = impact(False, wx(pop=75), 203, "Overcast")
    check("rain flags", r["flags"], ["RAIN RISK"])
    check("rain level", r["impact_level"], "UNDER")
    check("rain notes", r["impact_notes"], ["75% rain — lean under if it arrives"])
    check("showers", impact(False, wx(pop=45), 0, "Clear")["flags"], ["SHOWERS"])
    check("showers level", impact(False, wx(pop=45), 0, "Clear")["impact_level"], "WATCH")

    r = impact(False, wx(), 6030, "Clear")
    check("altitude", r["flags"], ["ALTITUDE"])
    check("altitude notes", r["impact_notes"],
          ["Clean outdoor conditions", "Elevation 6,030 ft — kicking / conditioning note"])
    check("altitude 3907 none", impact(False, wx(), 3907, "Clear")["flags"], [])

    r = impact(False, None, None, "Weather")
    check("no wx", (r["flags"], r["impact_level"], r["impact_notes"]), ([], "CLEAR", ["Clean outdoor conditions"]))


def test_time():
    utc = lambda s: datetime.strptime(s, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
    check("kick_ct evening", kick_ct(utc("2026-09-04T22:30Z")), "Fri 5:30 PM CT")
    check("kick_ct neutral", kick_ct(utc("2026-09-05T19:30Z")), "Sat 2:30 PM CT")
    check("kick_ct noon", kick_ct(utc("2026-09-12T17:00Z")), "Sat 12:00 PM CT")
    check("kick_ct hawaii", kick_ct(utc("2026-09-13T03:59Z")), "Sat 10:59 PM CT")
    check("kick_ct january", kick_ct(utc("2027-01-02T18:00Z")), "Sat 12:00 PM CT")

    day = lambda s: datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=CHICAGO)
    check("default sat", default_dates(day("2026-09-05")), ("20260903", "20260907"))
    check("default mon", default_dates(day("2026-09-07")), ("20260903", "20260907"))
    check("default tue", default_dates(day("2026-09-08")), ("20260910", "20260914"))
    check("default thu", default_dates(day("2026-09-10")), ("20260910", "20260914"))

    check("compass n", compass(0), "N")
    check("compass nw", compass(307), "NW")
    check("compass wrap", compass(359), "N")
    check("compass none", compass(None), None)
    check("has_line", [has_line(None), has_line({"spread": None, "total": None}), has_line({"spread": -3, "total": None})],
          [False, False, True])

    import server  # noqa: E402  - cheap now that the LineBook is built lazily
    est = ZoneInfo("America/New_York")
    check("fallback sat", server.fallback_dates(datetime(2026, 9, 5, 12, tzinfo=est)),
          ["20260903", "20260904", "20260905", "20260906", "20260907"])
    check("fallback tue rolls forward", server.fallback_dates(datetime(2026, 9, 8, 12, tzinfo=est))[0], "20260910")
    check("fallback mon stays", server.fallback_dates(datetime(2026, 9, 21, 12, tzinfo=est))[0], "20260917")
    check("no line book at import", server.LINES, None)


def test_live_math():
    node = shutil.which("node")
    if not node:
        print("node not found; skipping liveMath check")
        return
    src = (ROOT / "app.js").read_text("utf-8")
    fns = []
    for name in ("num", "liveMath", "betterRecord", "chooseOdds", "hashFilters"):
        m = re.search(rf"\n  function {name}\(.*?\n  }}\n", src, re.S)
        if not m:
            FAILS.append(f"could not extract {name} from app.js")
            return
        fns.append(m.group(0))
    cases = [
        # away, home, spread(home), total -> coverState, coverBy, totalState, overNeed
        {"a": 13, "h": 31, "s": -40.5, "t": 56.5, "want": ["AWAY COVER", -22.5, "UNDER", 12.5]},
        {"a": 45, "h": 6, "s": 24.5, "t": 46.5, "want": ["AWAY COVER", -14.5, "OVER", -4.5]},
        {"a": 20, "h": 24, "s": -3.5, "t": 44, "want": ["HOME COVER", 0.5, "PUSH", 0]},
        {"a": 21, "h": 24, "s": -3, "t": 50.5, "want": ["PUSH", 0, "UNDER", 5.5]},
        {"a": 0, "h": 0, "s": None, "t": None, "want": [None, None, None, None]},
    ]
    script = "\n".join(fns) + f"""
const cases = {json.dumps(cases)};
const out = cases.map(c => {{
  const g = {{ away: {{ score: String(c.a) }}, home: {{ score: String(c.h) }}, odds: {{ spread: c.s, total: c.t }} }};
  const m = liveMath(g);
  return [m.coverState ?? null, m.coverBy ?? null, m.totalState ?? null, m.overNeed ?? null];
}});
out.push([betterRecord("1-0", "0-0"), betterRecord("0-0", "1-1"), betterRecord("", null), betterRecord("2-0", "2-1")]);
const close = {{ spread: -3, total: 50 }}, opened = {{ spread: -2.5, total: 49.5 }}, snap = {{ spread: -1, total: 48 }};
out.push([
  chooseOdds(undefined, opened, "pre", snap) === opened,   // fresh line wins
  chooseOdds(close, opened, "in", snap) === opened,        // still moving while live
  chooseOdds(close, opened, "post", snap) === close,       // frozen once final
  chooseOdds(close, null, "post", snap) === close,         // ESPN nulls odds on finals
  chooseOdds(undefined, null, "post", snap) === snap,      // never seen live: snapshot line
  chooseOdds(undefined, {{ spread: null, total: null }}, "pre", null) === null,
]);
out.push(["#live", "#starred", "#all", "", "#LIVE", "#bogus", "#lines"].map(h => {{ const f = hashFilters(h); return [f.liveOnly, f.starredOnly, f.known, f.view]; }}));
console.log(JSON.stringify(out));
"""
    res = subprocess.run([node, "-e", script], capture_output=True, text=True)
    if res.returncode != 0:
        FAILS.append(f"node failed: {res.stderr.strip()[:300]}")
        return
    got = json.loads(res.stdout)
    for c, g in zip(cases, got):
        check(f"liveMath {c['a']}-{c['h']} {c['s']}/{c['t']}", g, c["want"])
    check("betterRecord", got[-3], ["1-0", "1-1", "", "2-1"])
    check("chooseOdds", got[-2], [True] * 6)
    check("hashFilters", got[-1], [[True, False, True, "cards"], [False, True, True, "cards"], [False, False, True, "cards"],
                                   [False, False, True, "cards"], [True, False, True, "cards"], [False, False, False, "cards"],
                                   [False, False, True, "lines"]])
    src_dates = re.search(r"\n  function liveDatesFor\(.*?\n  }\n", src, re.S)
    check("liveDatesFor present", bool(src_dates), True)


def test_snapshot_shape():
    try:
        data = json.loads((ROOT / "games.json").read_text("utf-8"))
    except Exception as exc:
        FAILS.append(f"games.json unreadable: {exc}")
        return
    games = data.get("games") or []
    check("count matches", data.get("count"), len(games))
    # Every game, not the first five: that slice is why a half-broken build passed.
    need = {"id", "date", "home", "away", "odds", "implied", "flags", "impact_level",
            "under_score", "conf_game", "kick_ct", "gameState"}
    bad = [(g.get("shortName"), need - set(g)) for g in games if need - set(g)]
    check("all games have the required fields", bad[:3], [])
    js = (ROOT / "games.js").read_text("utf-8")
    check("games.js prefix", js.startswith("window.CFB_DATA = {"), True)


def test_run_health():
    """Catch a snapshot that built but is quietly degraded.

    Deliberately lenient: check.py gates the Action's commit, and that commit also
    carries the odds refresh, so a strict gate on an ordinary Open-Meteo wobble would
    strand the board on a stale snapshot. Hard-fail only when it is unusable.
    """
    try:
        data = json.loads((ROOT / "games.json").read_text("utf-8"))
    except Exception:
        return                                  # test_snapshot_shape already reported it
    games = data.get("games") or []
    counts = data.get("counts") or {}
    check("warnings is a list", isinstance(data.get("warnings"), list), True)
    if not games:
        FAILS.append("snapshot has no games")
        return
    outdoor = [g for g in games if not g.get("indoor")]
    missing = sum(1 for g in outdoor if not g.get("wx"))
    # Open-Meteo only forecasts ~16 days out; a far-future --start legitimately has none.
    try:
        gen = datetime.strptime(data["generated_at"], "%Y-%m-%dT%H:%M:%SZ")
        first = datetime.strptime((data.get("dates") or ["19700101"])[0], "%Y%m%d")
        in_range = (first - gen).days <= 14
    except Exception:
        in_range = False
    if outdoor and len(games) >= 20 and in_range:
        pct = 100 * missing / len(outdoor)
        if pct > 25:
            FAILS.append(f"{missing}/{len(outdoor)} outdoor games have no forecast ({pct:.0f}%)")
        elif pct > 10:
            print(f"warn: {missing}/{len(outdoor)} outdoor games without forecast ({pct:.0f}%)")
    if counts.get("no_groups_fallback"):
        print(f"warn: {counts['no_groups_fallback']} date(s) served by the groups-less fallback URL")
    if counts.get("games_skipped"):
        print(f"warn: {counts['games_skipped']} game(s) skipped during build")
    if counts.get("geocode_failed"):
        print(f"warn: {counts['geocode_failed']} geocode failure(s)")


def test_pwa():
    try:
        m = json.loads((ROOT / "manifest.webmanifest").read_text("utf-8"))
    except Exception as exc:
        FAILS.append(f"manifest unreadable: {exc}")
        return
    check("manifest display", m.get("display"), "standalone")
    check("manifest start_url", m.get("start_url"), "/")
    for icon in m.get("icons") or []:
        check(f"icon exists {icon['src']}", (ROOT / icon["src"].lstrip("/")).is_file(), True)
    check("apple-touch-icon", (ROOT / "icons/apple-touch-icon.png").is_file(), True)
    check("api/live.py exists", (ROOT / "api/live.py").is_file(), True)
    vj = json.loads((ROOT / "vercel.json").read_text("utf-8"))
    check("vercel functions", "api/live.py" in (vj.get("functions") or {}), True)
    sw = (ROOT / "sw.js").read_text("utf-8")
    check("sw skips api", 'startsWith("/api/")' in sw, True)
    html = (ROOT / "index.html").read_text("utf-8")
    check("manifest linked", 'rel="manifest"' in html, True)
    check("apple icon linked", 'rel="apple-touch-icon"' in html, True)


if __name__ == "__main__":
    for t in (test_impact, test_time, test_live_math, test_snapshot_shape, test_run_health, test_pwa):
        t()
    if FAILS:
        print("\n".join("FAIL " + f for f in FAILS))
        sys.exit(1)
    print("ok")
