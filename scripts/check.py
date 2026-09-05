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

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from refresh_week import CHICAGO, compass, default_dates, impact, kick_ct  # noqa: E402

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
    check("hot 90 note", impact(False, wx(temp=90.4), 0, "Clear")["impact_notes"], ["Clean outdoor conditions"])
    check("heat 95", impact(False, wx(temp=95.0), 0, "Clear")["flags"], ["EXTREME HEAT"])
    check("heat 93 note", impact(False, wx(temp=92.7), 0, "Clear")["impact_notes"],
          ["93° and sunny — hydration / rotation game"])
    check("heat 98 note", impact(False, wx(temp=98.4), 0, "Clear")["impact_notes"],
          ["98° heat — early-season pace can stay fast; monitor late-game fade"])
    check("heat overcast note", impact(False, wx(temp=94, weathercode=3), 0, "Overcast")["impact_notes"],
          ["94° and overcast — hydration / rotation game"])

    check("cold", impact(False, wx(temp=38), 0, "Clear")["flags"], ["COLD"])
    check("cold level", impact(False, wx(temp=38), 0, "Clear")["impact_level"], "CLEAR")
    check("freezing", impact(False, wx(temp=30), 0, "Clear")["flags"], ["FREEZING"])
    check("freezing level", impact(False, wx(temp=30), 0, "Clear")["impact_level"], "WATCH")

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


def test_live_math():
    node = shutil.which("node")
    if not node:
        print("node not found; skipping liveMath check")
        return
    src = (ROOT / "app.js").read_text("utf-8")
    fns = []
    for name in ("num", "liveMath", "betterRecord"):
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
console.log(JSON.stringify(out));
"""
    res = subprocess.run([node, "-e", script], capture_output=True, text=True)
    if res.returncode != 0:
        FAILS.append(f"node failed: {res.stderr.strip()[:300]}")
        return
    got = json.loads(res.stdout)
    for c, g in zip(cases, got):
        check(f"liveMath {c['a']}-{c['h']} {c['s']}/{c['t']}", g, c["want"])
    check("betterRecord", got[-1], ["1-0", "1-1", "", "2-1"])


def test_snapshot_shape():
    try:
        data = json.loads((ROOT / "games.json").read_text("utf-8"))
    except Exception as exc:
        FAILS.append(f"games.json unreadable: {exc}")
        return
    games = data.get("games") or []
    check("count matches", data.get("count"), len(games))
    need = {"id", "date", "home", "away", "odds", "implied", "flags", "impact_level", "kick_ct", "gameState"}
    for g in games[:5]:
        missing = need - set(g)
        check(f"fields {g.get('shortName')}", missing, set())
    js = (ROOT / "games.js").read_text("utf-8")
    check("games.js prefix", js.startswith("window.CFB_DATA = {"), True)


if __name__ == "__main__":
    for t in (test_impact, test_time, test_live_math, test_snapshot_shape):
        t()
    if FAILS:
        print("\n".join("FAIL " + f for f in FAILS))
        sys.exit(1)
    print("ok")
