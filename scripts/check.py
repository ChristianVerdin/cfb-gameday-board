#!/usr/bin/env python3
"""Smoke test for the rules that matter on a Saturday. No network.

    python3 scripts/check.py

Covers the weather flag / impact table, CT kickoff formatting, compass, default
dates, and the client's liveMath() (run under node when node is on PATH).
"""
from __future__ import annotations

import json
import re
from html import escape
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from refresh_week import CHICAGO, compass, default_dates, has_line, impact, is_placeholder, kick_ct  # noqa: E402

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
    check("no wx", (r["flags"], r["impact_level"], r["impact_notes"]), ([], "CLEAR", ["Forecast unavailable"]))
    check("no wx score", (r["impact_score"], r["under_score"]), (0, 0))
    check("empty wx dict is a real clean forecast", impact(False, {}, None, "Clear")["impact_notes"], ["Clean outdoor conditions"])
    check("no wx keeps altitude", impact(False, None, 6030, "Weather")["impact_notes"],
          ["Forecast unavailable", "Elevation 6,030 ft — kicking / conditioning note"])


def test_time():
    utc = lambda s: datetime.strptime(s, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
    check("kick_ct evening", kick_ct(utc("2026-09-04T22:30Z")), "Fri 5:30 PM CT")
    check("kick_ct neutral", kick_ct(utc("2026-09-05T19:30Z")), "Sat 2:30 PM CT")
    check("kick_ct noon", kick_ct(utc("2026-09-12T17:00Z")), "Sat 12:00 PM CT")
    check("kick_ct hawaii", kick_ct(utc("2026-09-13T03:59Z")), "Sat 10:59 PM CT")
    check("kick_ct january", kick_ct(utc("2027-01-02T18:00Z")), "Sat 12:00 PM CT")

    day = lambda s: datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=CHICAGO)
    check("default sat", default_dates(day("2026-09-05")), ("20260901", "20260907"))
    check("default mon", default_dates(day("2026-09-07")), ("20260901", "20260907"))
    check("default tue", default_dates(day("2026-09-08")), ("20260908", "20260914"))
    check("default wed", default_dates(day("2026-10-07")), ("20261006", "20261012"))
    check("default thu", default_dates(day("2026-09-10")), ("20260908", "20260914"))
    check("default mon done", default_dates(day("2026-11-16"), monday_done=True), ("20261117", "20261123"))
    check("default sat done", default_dates(day("2026-11-14"), monday_done=True), ("20261110", "20261116"))

    import refresh_week
    real_pull = refresh_week.pull
    ev = lambda state: {"status": {"type": {"state": state}}}
    for name, events, want in (("all final", [ev("post"), ev("post")], True), ("none", [], True),
                               ("one to play", [ev("post"), ev("pre")], False), ("live", [ev("in")], False)):
        refresh_week.pull = lambda date, run, events=events: (events, {}, True)
        check(f"nothing_left {name}", refresh_week.nothing_left("20261116"), want)

    def down(date, run):
        raise RuntimeError("ESPN 503")
    refresh_week.pull = down
    check("nothing_left pull failed", refresh_week.nothing_left("20261116"), False)
    refresh_week.pull = real_pull

    check("compass n", compass(0), "N")
    check("compass nw", compass(307), "NW")
    check("compass wrap", compass(359), "N")
    check("compass none", compass(None), None)
    check("has_line", [has_line(None), has_line({"spread": None, "total": None}), has_line({"spread": -3, "total": None})],
          [False, False, True])

    import server  # noqa: E402  - cheap now that the LineBook is built lazily
    est = ZoneInfo("America/New_York")
    check("fallback sat", server.fallback_dates(datetime(2026, 9, 5, 12, tzinfo=est)),
          ["20260901", "20260902", "20260903", "20260904", "20260905", "20260906", "20260907"])
    check("fallback tue starts the week", server.fallback_dates(datetime(2026, 9, 8, 12, tzinfo=est))[0], "20260908")
    check("fallback mon stays", server.fallback_dates(datetime(2026, 9, 21, 12, tzinfo=est))[0], "20260915")
    week = ",".join(f"202610{d:02d}" for d in range(6, 14))
    check("parse_dates caps at 7", server.parse_dates("dates=" + week), [f"202610{d:02d}" for d in range(6, 13)])
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
out.push(["#rivalry", "#RIVALRY", "#live", ""].map(h => {{ const f = hashFilters(h); return [f.rivalryOnly, f.known, f.view]; }}));
console.log(JSON.stringify(out));
"""
    res = subprocess.run([node, "-e", script], capture_output=True, text=True)
    if res.returncode != 0:
        FAILS.append(f"node failed: {res.stderr.strip()[:300]}")
        return
    got = json.loads(res.stdout)
    for c, g in zip(cases, got):
        check(f"liveMath {c['a']}-{c['h']} {c['s']}/{c['t']}", g, c["want"])
    check("betterRecord", got[-4], ["1-0", "1-1", "", "2-1"])
    check("chooseOdds", got[-3], [True] * 6)
    check("hashFilters", got[-2], [[True, False, True, "cards"], [False, True, True, "cards"], [False, False, True, "cards"],
                                   [False, False, True, "cards"], [True, False, True, "cards"], [False, False, False, "cards"],
                                   [False, False, True, "lines"]])
    check("hashFilters rivalry", got[-1], [[True, True, "cards"], [True, True, "cards"], [False, True, "cards"],
                                           [False, True, "cards"]])
    one = [re.search(rf"\n  function {n}\(.*?\n", src) for n in ("esc", "gameHash")]
    if not all(one):
        FAILS.append("could not extract esc/gameHash from app.js")
    else:
        js = "".join(m.group(0) for m in one) + """
console.log(JSON.stringify([["#game/401858234", "#game/12", "#game/401858234x", "#live", "#game/", ""].map(gameHash),
                            esc('<img src=x onerror="a">&\\''), esc(null)]));"""
        res = subprocess.run([node, "-e", js], capture_output=True, text=True)
        got = json.loads(res.stdout) if res.returncode == 0 else None
        check("gameHash", got and got[0], ["401858234", None, None, None, None, None])
        check("esc", got and got[1:], ["&lt;img src=x onerror=&quot;a&quot;&gt;&amp;&#39;", ""])
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
            "under_score", "conf_game", "kick_ct", "gameState", "rivalry"}
    bad = [(g.get("shortName"), need - set(g)) for g in games if need - set(g)]
    check("all games have the required fields", bad[:3], [])
    js = (ROOT / "games.js").read_text("utf-8")
    check("games.js prefix", js.startswith("window.CFB_DATA = {"), True)


def forecastable(games: list) -> tuple[list, int]:
    """(outdoor games that could have a forecast, how many of those have none).

    A TBA kickoff, a TBD team or a missing venue legitimately has no forecast; counting
    them would reject a Rivalry Week snapshot full of unannounced kickoffs. Real failures
    (forecast_failed, geocode_failed) still count.
    """
    pool = [g for g in games if not g.get("indoor") and not g.get("time_tbd") and not is_placeholder(g)]
    return pool, sum(1 for g in pool if not g.get("wx"))


def health_failure(games: list):
    """The >25% rule test_run_health applies, as a pure function: message or None."""
    outdoor, missing = forecastable(games)
    if outdoor and len(games) >= 20:
        pct = 100 * missing / len(outdoor)
        if pct > 25:
            return f"{missing}/{len(outdoor)} outdoor games have no forecast ({pct:.0f}%)"
    return None


def test_health_rule():
    def g(i, **kw):
        base = {"id": str(i), "indoor": False, "time_tbd": False, "venue": "Stadium", "wx": {"temp": 60},
                "home": {"id": "1", "full": "A", "abbr": "A"}, "away": {"id": "2", "full": "B", "abbr": "B"}}
        return {**base, **kw}
    tba = [g(i, time_tbd=True, wx=None) for i in range(40)] + [g(100 + i) for i in range(60)]
    check("40% TBA kickoffs pass", health_failure(tba), None)
    tbd = [g(i, wx=None, home={"id": "-1", "full": "TBD", "abbr": "TBD"}) for i in range(20)] \
        + [g(i, wx=None, venue=None) for i in range(20, 40)] + [g(100 + i) for i in range(60)]
    check("TBD teams and no venue pass", health_failure(tbd), None)
    failed = [g(i, wx=None) for i in range(40)] + [g(100 + i) for i in range(60)]
    check("40% forecast_failed fails", bool(health_failure(failed)), True)
    check("fail message counts only real games", (health_failure(failed) or "").startswith("40/100"), True)


def test_fcs_playoff():
    from refresh_week import drop_fcs_playoff

    def ev(i, *notes):
        return {"id": str(i), "competitions": [{"notes": [{"headline": n} for n in notes]}]}
    events = [ev(1, "FCS Championship - First Round"), ev(2, "FCS CHAMPIONSHIP - Second Round"),
              ev(3), ev(4, "Big 12 Championship"), ev(5, "Celebration Bowl")]
    check("FCS playoff dropped, FBS kept", [e["id"] for e in drop_fcs_playoff(events)], ["3", "4", "5"])
    check("no-notes event kept", len(drop_fcs_playoff([{"id": "9"}])), 1)


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
    outdoor, missing = forecastable(games)
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
    if counts.get("geocode_unmatched"):
        print(f"warn: {counts['geocode_unmatched']} venue city with no geocoder match (no forecast)")


FORBIDDEN_LD = ("spread", "total", "odds", "moneyline", "implied", "offer", "price")


def test_jsonld():
    """The structured data must describe games, never a betting market.

    The forbidden-substring scan is the point of this test: it keeps the CLAUDE.md
    "never a wagering tool" rule enforced after everyone has forgotten it was a rule.
    """
    html = (ROOT / "index.html").read_text("utf-8")
    m = re.search(r"<!-- games:start -->(.*?)<!-- games:end -->", html, re.S)
    check("slate markers present", bool(m), True)
    if not m:
        return
    block = m.group(1)
    bad = [t for t in FORBIDDEN_LD if t in block.lower()]
    check("no wagering terms in structured data", bad, [])
    inner = re.search(r'<script type="application/ld\+json">(.*)</script>', block, re.S)
    check("ld+json script present", bool(inner), True)
    if not inner:
        return
    try:
        graph = json.loads(inner.group(1)).get("@graph") or []
    except Exception as exc:
        FAILS.append(f"structured data does not parse: {exc}")
        return
    data = json.loads((ROOT / "games.json").read_text("utf-8"))
    want = [g for g in data.get("games") or [] if g.get("gameState") != "post" and not is_placeholder(g)]
    check("one event per unplayed game", len(graph), len(want))
    need = {"name", "startDate", "location", "homeTeam", "awayTeam"}
    check("events have the required fields",
          [e.get("name") for e in graph if need - set(e)][:3], [])
    iso = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}([+-]\d{2}:\d{2}|Z))?$")   # date only = kickoff TBA
    check("startDate carries an offset",
          [e.get("startDate") for e in graph if not iso.match(e.get("startDate") or "")][:3], [])
    check("no event with a null place name",
          [e.get("name") for e in graph if not (e.get("location") or {}).get("name")][:3], [])
    check("events carry the share image",
          [e.get("name") for e in graph if e.get("image") != ["https://cfbgameday.app/icons/og.png"]][:3], [])
    check("no endDate guessed", [e.get("name") for e in graph if "endDate" in e][:3], [])
    kicker = re.search(r'<div class="kicker" id="kicker">(.*?)</div>', html, re.S)
    check("kicker matches the snapshot", kicker.group(1) if kicker else None,
          escape(data.get("week_label") or "College football slate"))
    from refresh_week import page_description, page_title
    title = re.search(r"<title>(.*?)</title>", html, re.S)
    check("title matches the snapshot", title.group(1) if title else None,
          escape(page_title(data.get("week_label"))))
    check("week title", page_title("Week 6 · 2026"),
          "College football Week 6 schedule, kickoff weather & TV | CFB GameDay Board")
    check("neutral title", page_title(None), "CFB GameDay Board")
    desc = re.search(r'<meta name="description" content="([^"]*)"', html)
    check("description counts the slate", bool(desc) and f"{len(data.get('games') or [])} FBS game" in desc.group(1), True)
    bad = [t for t in ("moneyline", "odds", "bet ") if t in page_description(data).lower()]
    check("no wagering terms in description", bad, [])


def test_seo_escaping():
    """ESPN text reaches index.html in four places; none may break out of its element."""
    import tempfile
    from refresh_week import write_seo
    evil = '</title></script><img src=x onerror=alert(1)>'
    game = {"id": "1", "name": evil, "date": "2026-10-10T19:30Z", "gameState": "pre", "kick_ct": "Sat 2:30 PM CT",
            "home": {"id": "1", "full": evil}, "away": {"id": "2", "full": "A"}, "networks": [], "venue": "Stadium"}
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "index.html").write_text((ROOT / "index.html").read_text("utf-8"), "utf-8")
        write_seo(Path(tmp), {"week_label": evil, "games": [game], "generated_at": "2026-10-07T00:00:00Z"})
        out = (Path(tmp) / "index.html").read_text("utf-8")
    check("escaped: no raw injected tag", "<img src=x" in out, False)
    check("escaped: one </title>", out.count("</title>"), 1)
    m = re.search(r'<script type="application/ld\+json">(.*?)</script>', out.split("<!-- games:start -->")[1], re.S)
    check("escaped: ld+json still parses", bool(m) and json.loads(m.group(1))["@graph"][0]["name"] == evil, True)


def test_game_payload():
    import server  # noqa: E402
    raw = json.loads((ROOT / "scripts/fixtures/summary_final.json").read_text("utf-8"))
    p = server.game_payload(raw)
    check("game id", p["id"], "401858234")
    check("game state", p["state"], "post")
    check("linescores", (p["linescores"]["away"], p["linescores"]["home"]), (["0", "10", "7", "7"], ["7", "0", "3", "0"]))
    check("scoring count", len(p["scoring"]), 6)
    first = p["scoring"][0]
    check("scoring first", (first["period"], first["clock"], first["team"], first["away"], first["home"]), (1, "5:15", "CAL", 0, 7))
    labels = [r[0] for r in p["box"]]
    check("box has yards", "Total Yards" in labels, True)
    check("box row shape", all(len(r) == 3 for r in p["box"]), True)
    check("leaders cats", [x["cat"] for x in p["leaders"]["away"]][:3], ["Passing", "Rushing", "Receiving"])
    check("leaders side", p["leaders"]["away"][0]["name"] != p["leaders"]["home"][0]["name"], True)
    check("drives count", len(p["drives"]), 19)
    check("drive shape", sorted(p["drives"][0]), ["desc", "period", "result", "score", "start", "team"])
    wp = p["winprob"]
    check("winprob capped", 2 <= len(wp["points"]) <= server.WINPROB_POINTS, True)
    check("winprob range", all(0 <= v <= 100 for v in wp["points"]), True)
    check("winprob ends final", wp["points"][-1], 0)
    check("winprob quarters", [q for q, _ in wp["quarters"]], [2, 3, 4])
    blob = json.dumps(p).lower()
    bad = [t for t in ("pickcenter", "againstthespread", "overunder", "spread", "odds", "moneyline", "implied")
           if t in blob]
    check("no wagering terms in game payload", bad, [])
    check("small payload", len(blob) < 20000, True)
    check("id ok", [server.valid_game_id(x) for x in ("401858234", "12345", "40185823412345", "1;ls", "", None)],
          [True, False, False, False, False, False])


def test_hosted_api():
    """api/live.py and api/game.py: one canonical URL shape per resource, rejections cached, ESPN never reached."""
    import http.server
    import threading
    import urllib.error
    import urllib.request
    from datetime import timedelta
    import server  # noqa: E402
    from api import game as api_game, live as api_live  # noqa: E402

    calls = {"date": [], "summary": []}
    keep = (api_live.pull_date, api_game.pull_summary)

    def fake_date(d):
        calls["date"].append(d)
        return [{"id": "9" + d, "status": {"type": {"state": "pre"}}, "competitions": [{"competitors": []}]}]

    snap_ids = sorted(server.GAME_IDS or [])
    fixture = json.loads((ROOT / "scripts/fixtures/summary_final.json").read_text("utf-8"))

    def fake_summary(gid):
        calls["summary"].append(gid)
        if gid == snap_ids[1]:
            raise server.UpstreamError("site.web.api.espn.com 404 Not Found :: http://sports.core.api.espn.pvt/x", 404)
        if gid == snap_ids[2]:
            raise server.UpstreamError("site.web.api.espn.com 503 Unavailable :: http://sports.core.api.espn.pvt/x", None)
        if gid == snap_ids[3]:
            raise OSError("timed out reaching site.api.espn.com")
        return fixture

    api_live.pull_date, api_game.pull_summary = fake_date, fake_summary
    servers = []

    def serve(handler_cls):
        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        servers.append(httpd)
        return f"http://127.0.0.1:{httpd.server_port}"

    def get(base, path):
        try:
            with urllib.request.urlopen(base + path, timeout=10) as r:
                return r.status, r.headers.get("Cache-Control"), r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.headers.get("Cache-Control"), e.read()

    quiet = lambda *a, **k: None  # noqa: E731
    api_live.handler.log_message = api_game.handler.log_message = quiet
    try:
        live, game = serve(api_live.handler), serve(api_game.handler)
        D = server.DATES
        lo, hi = server.date_window()
        PARAM, VAL = "public, max-age=0, s-maxage=3600", "public, max-age=0, s-maxage=300"
        OK = "public, max-age=0, s-maxage=20, stale-while-revalidate=40"

        def live_case(name, path, status, cache, body_has=None, fetched=0):
            calls["date"].clear()
            st, cc, body = get(live, path)
            check(f"live {name}", (st, cc), (status, cache))
            check(f"live {name} ESPN pulls", len(calls["date"]), fetched)
            if body_has:
                check(f"live {name} body", json.loads(body).get("error"), body_has)

        # happy paths: app.js shape (snapshot dates, joined), widget shape (sorted ET dates of snapshot games), no query
        live_case("no query", "/api/live", 200, OK, fetched=len(D))
        live_case("app.js shape", "/api/live?dates=" + ",".join(D), 200, OK, fetched=len(D))
        snap = json.loads((ROOT / "games.json").read_text("utf-8"))
        et = sorted({datetime.strptime(g["date"], "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
                     .astimezone(ZoneInfo("America/New_York")).strftime("%Y%m%d") for g in snap["games"]})
        live_case("widget shape (every game's ET date)", "/api/live?dates=" + ",".join(et), 200, OK, fetched=len(et))
        live_case("widget one date, comma-encoded", "/api/live?dates=" + D[0] + "%2C" + D[1], 200, OK, fetched=2)
        live_case("slack low edge", f"/api/live?dates={lo}", 200, OK, fetched=1)
        live_case("slack high edge", f"/api/live?dates={hi}", 200, OK, fetched=1)
        # byte-identical success payload vs the dev server's builder
        calls["date"].clear()
        st, _, body = get(live, "/api/live?dates=" + D[0])
        got = json.loads(body)
        want = {"ok": True, "count": 1, "warnings": [], "dates": [D[0]],
                "games": server.live_payload(fake_date(D[0]))}
        got.pop("fetched_at")
        check("live payload unchanged", got, want)
        # rejections: structural 400 s-maxage=3600, value 400 s-maxage=300, none reach ESPN
        live_case("unknown param", "/api/live?zz=1", 400, PARAM, "unknown parameter")
        live_case("cache buster beside dates", f"/api/live?dates={D[0]}&cb=1", 400, PARAM, "unknown parameter")
        live_case("bare param", "/api/live?x", 400, PARAM, "unknown parameter")
        live_case("repeated dates", f"/api/live?dates={D[0]}&dates={D[1]}", 400, PARAM, "dates must appear once")
        live_case("blank dates", "/api/live?dates=", 400, VAL)
        live_case("unsorted", f"/api/live?dates={D[1]},{D[0]}", 400, VAL, "dates: sorted and unique")
        live_case("duplicate", f"/api/live?dates={D[0]},{D[0]}", 400, VAL, "dates: sorted and unique")
        live_case("eight dates", "/api/live?dates=" + ",".join(
            (datetime.strptime(D[0], "%Y%m%d") + timedelta(days=i)).strftime("%Y%m%d") for i in range(8)), 400, VAL)
        live_case("not digits", "/api/live?dates=2026111a", 400, VAL, "dates: YYYYMMDD")
        live_case("unicode digits", "/api/live?dates=" + "%D9%A2" * 8, 400, VAL, "dates: YYYYMMDD")
        live_case("not a day", "/api/live?dates=20261399", 400, VAL, "dates: YYYYMMDD")
        live_case("space padded", f"/api/live?dates={D[0]}%20", 400, VAL)
        live_case("old season", "/api/live?dates=20260101", 400, VAL, "dates: outside this slate")
        low = (datetime.strptime(lo, "%Y%m%d") - timedelta(days=1)).strftime("%Y%m%d")
        high = (datetime.strptime(hi, "%Y%m%d") + timedelta(days=1)).strftime("%Y%m%d")
        live_case("one day under window", f"/api/live?dates={low}", 400, VAL)
        live_case("one day over window", f"/api/live?dates={high}", 400, VAL)
        check("window is snapshot +/- 2 days", (lo, hi), (
            (datetime.strptime(min(D), "%Y%m%d") - timedelta(days=2)).strftime("%Y%m%d"),
            (datetime.strptime(max(D), "%Y%m%d") + timedelta(days=2)).strftime("%Y%m%d")))
        check("widget dates inside window", [d for d in et if not lo <= d <= hi], [])
        # ESPN failure: generic body, short cache, no ESPN detail
        api_live.pull_date = lambda d: (_ for _ in ()).throw(server.UpstreamError("site.web.api.espn.com 500 :: x", 500))
        st, cc, body = get(live, "/api/live")
        check("live 502", (st, cc, json.loads(body)), (502, "public, max-age=0, s-maxage=10",
                                                      {"ok": False, "error": "live scores unavailable"}))

        # /api/game
        ok_id = snap_ids[0]
        calls["summary"].clear()
        st, cc, body = get(game, f"/api/game?id={ok_id}")
        parsed = json.loads(body)
        check("game ok", (st, cc, parsed["ok"]), (200, "public, max-age=0, s-maxage=3600, stale-while-revalidate=7200", True))
        parsed.pop("ok")
        check("game payload unchanged", parsed, server.game_payload(fixture))

        def game_case(name, path, status, cache, error=None, pulls=0):
            calls["summary"].clear()
            st, cc, body = get(game, path)
            check(f"game {name}", (st, cc), (status, cache))
            check(f"game {name} ESPN pulls", len(calls["summary"]), pulls)
            if error:
                check(f"game {name} body", json.loads(body), {"ok": False, "error": error})
            check(f"game {name} leaks nothing", [t for t in ("espn", ".pvt", "timed out", "Unavailable") if t in body.decode()], [])

        game_case("cache buster", f"/api/game?id={ok_id}&x=1", 400, PARAM, "unknown parameter")
        game_case("repeated id", f"/api/game?id={ok_id}&id={ok_id}", 400, PARAM, "id must appear once")
        game_case("no id", "/api/game", 400, PARAM, "bad id")
        game_case("bad id", "/api/game?id=1;ls", 400, PARAM, "bad id")
        game_case("unknown id (gate, no ESPN call)", "/api/game?id=123456789", 404, VAL, "unknown game")
        game_case("espn 4xx", f"/api/game?id={snap_ids[1]}", 404, VAL, "unknown game", pulls=1)
        game_case("espn 5xx", f"/api/game?id={snap_ids[2]}", 502, "public, max-age=0, s-maxage=30", "game detail unavailable", 1)
        game_case("network error", f"/api/game?id={snap_ids[3]}", 502, "public, max-age=0, s-maxage=30", "game detail unavailable", 1)
    finally:
        for h in servers:
            h.shutdown()
        api_live.pull_date, api_game.pull_summary = keep[0], keep[1]
    # pull_summary: 404 from both hosts is "unknown", a mixed or 5xx outcome is not
    real = server.fetch_json
    try:
        server.fetch_json = lambda url, timeout=20: (_ for _ in ()).throw(server.UpstreamError("x", 404))
        try:
            server.pull_summary("401858234")
        except server.UpstreamError as exc:
            check("pull_summary 404/404 status", exc.status, 404)
        outcomes = iter([server.UpstreamError("x", 404), server.UpstreamError("y", 503)])
        def mixed(url, timeout=20):
            raise next(outcomes)
        server.fetch_json = mixed
        try:
            server.pull_summary("401858234")
        except server.UpstreamError as exc:
            check("pull_summary 404/503 status", exc.status, None)
    finally:
        server.fetch_json = real
    check("snapshot ids loaded", len(snap_ids) > 0, True)


def ev(stype=2, week=8, date="2026-10-24T16:00Z", note="", year=2026):
    return {"season": {"year": year, "type": stype}, "week": {"number": week}, "date": date,
            "competitions": [{"notes": [{"headline": note}] if note else []}]}


def test_labels():
    """Week labels come from the events: the postseason dry run (2026-10-20) found the league
    field calls a finished season's Week 15 "Postseason"."""
    from refresh_week import page_description, page_title, thanksgiving, week_label
    post_league = {"leagues": [{"season": {"year": 2025, "type": {"type": 3, "name": "Postseason"}}}]}
    check("label regular", week_label({}, [ev(), ev()]), "Week 8 · 2026")
    check("label ignores league phase", week_label(post_league, [ev(week=15, year=2025, date="2025-12-06T17:00Z")] * 3),
          "Week 15 · 2025")
    champ = [ev(week=15, date="2026-12-05T20:00Z", note=f"{c} Championship") for c in ("SEC", "ACC", "Big Ten")]
    check("label championship week", week_label({}, champ + [ev(week=15, date="2026-12-05T20:00Z")]),
          "Championship Week · 2026")
    check("label rivalry week", week_label({}, [ev(week=14, date="2026-11-28T17:00Z")]), "Rivalry Week · 2026")
    check("label week 13 is not rivalry week", week_label({}, [ev(week=13, date="2026-11-21T17:00Z")]), "Week 13 · 2026")
    check("thanksgiving", (str(thanksgiving(2026)), str(thanksgiving(2027))), ("2026-11-26", "2027-11-25"))
    bowl = ev(3, 1, "2026-12-19T20:00Z", "StaffDNA Cure Bowl")
    cfp1 = ev(3, 1, "2026-12-19T01:00Z", "College Football Playoff First Round Game")
    check("label bowls", week_label({}, [bowl]), "Bowl season · 2026-27")
    check("label bowls + playoff", week_label({}, [bowl, cfp1]), "Bowls & Playoff · 2026-27")
    check("label cfp first round", week_label({}, [cfp1]), "CFP First Round · 2026-27")
    semis = [ev(3, 1, "2027-01-14T01:00Z", f"College Football Playoff Semifinal at the {b}") for b in ("Orange Bowl", "Sugar Bowl")]
    check("label semis", week_label({}, semis), "CFP Semifinals · 2026-27")
    final = ev(3, 1, "2027-01-26T00:30Z", "College Football Playoff National Championship Presented by AT&T")
    check("label title game", week_label({}, [final]), "National Championship · 2026-27")
    check("label army-navy + bowl", week_label({}, [ev(week=16, date="2026-12-12T20:00Z"), bowl]), "Bowl season · 2026-27")
    brand = " | CFB GameDay Board"
    check("title bowls", page_title("Bowl season · 2026-27"), "College football bowl schedule, kickoff weather & TV" + brand)
    check("title rivalry week", page_title("Rivalry Week · 2026"),
          "College football Rivalry Week schedule, kickoff weather & TV" + brand)
    check("title title game", page_title("National Championship · 2026-27"),
          "College football national championship, kickoff weather & TV" + brand)
    one = {"week_label": "National Championship · 2026-27", "games": [{"kick_ct": "Mon 6:30 PM CT"}]}
    check("description singular", ("1 FBS game " in page_description(one), "1 FBS games" in page_description(one)), (True, False))


def pg(away="Away", home="Home", kick="Sat 2:30 PM CT", spread=-7.0, **kw):
    g = {"away": {"name": away, "rank": 99}, "home": {"name": home, "rank": 99}, "kick_ct": kick,
         "date": "2026-10-24T19:30Z", "gameState": "pre", "indoor": False, "flags": [], "neutral": False,
         "odds": {"spread": spread}, "group": "P4/P5"}
    g.update(kw)
    return g


def test_promo():
    from promo_text import LIMIT, build
    week = [pg(spread=-10.5), pg("Iowa", "Minnesota", spread=-1.5), pg("Akron", "Kent St", kick="Sat 11:00 AM CT")]
    text = build(week, "Week 9 · 2026")
    check("promo week head", text.startswith("Week 9: 3 games, 3 on Saturday."), True)
    check("promo tight line", "Iowa at Minnesota is a 1.5-point line." in text, True)
    week[1]["neutral"] = True
    check("promo neutral says vs", "Iowa vs Minnesota" in build(week, "Week 9 · 2026"), True)
    week[1]["rivalry"] = "Floyd of Rosedale"
    check("promo rivalry marquee", "Floyd of Rosedale: Iowa vs Minnesota" in build(week, "Week 9 · 2026"), True)
    days = [pg(kick=k) for k in ("Tue 1:00 PM CT", "Wed 4:00 PM CT", "Sat 11:00 AM CT", "Mon 1:00 PM CT")]
    check("promo bowl head", build(days, "Bowl season · 2026-27").startswith("Bowl season: 4 games, Tue to Mon."), True)
    final = [pg("Miami", "Indiana", kick="Mon 6:30 PM CT", neutral=True)]
    check("promo title game", build(final, "National Championship · 2026-27"),
          "National Championship: Miami vs Indiana, Mon 6:30 PM CT. Venue, forecast, TV, and posted line.")
    many = [pg(f"A{i}", f"H{i}", rivalry=f"Trophy {i}", flags=["RAIN RISK"]) for i in range(18)]
    text = build(many, "Rivalry Week · 2026")
    check("promo rivalry week", ("more trophy games" in text, "Rain risk" in text, len(text) <= LIMIT), (True, True, True))
    bad = [t for t in (build(week, "Week 9 · 2026"), build(days, "Bowl season · 2026-27"), build(final, None), text)
           if len(t) > LIMIT or "1 games" in t]
    check("promo length and grammar", bad, [])


def test_rivalries():
    import refresh_week
    rows = json.loads((ROOT / "data/rivalries.json").read_text("utf-8"))
    pairs = [frozenset(r["ids"]) for r in rows]
    check("rivalry ids are pairs of ints", [r["label"] for r in rows
          if len(set(r["ids"])) != 2 or not all(isinstance(i, int) for i in r["ids"])], [])
    check("rivalry pairs unique", len(pairs), len(set(pairs)))
    check("rivalry labels short", [r["label"] for r in rows if not 0 < len(r["label"]) <= 30], [])
    words = " ".join(f"{r['label']} {r.get('trophy') or ''}" for r in rows).lower()
    check("no wagering terms in rivalry names", [t for t in FORBIDDEN_LD if t in words], [])
    refresh_week._RIVALRIES = None
    check("rivalry lookup", refresh_week.rivalry("2294", "135"), {"rivalry": "Floyd of Rosedale", "trophy": None})
    check("rivalry lookup reversed", refresh_week.rivalry(135, 2294)["rivalry"], "Floyd of Rosedale")
    check("rivalry trophy", refresh_week.rivalry(349, 2426), {"rivalry": "Army–Navy Game", "trophy": "Commander-in-Chief's Trophy"})
    check("no rivalry", refresh_week.rivalry("2294", "333"), {"rivalry": None, "trophy": None})


def test_geocode():
    """An overseas venue matches its own country, never the US town with the same name."""
    import refresh_week
    rows = {"Dublin": [{"name": "Dublin", "country": "Ireland", "country_code": "IE", "admin1": "Leinster", "latitude": 53.3, "longitude": -6.2},
                       {"name": "Dublin", "country": "United States", "country_code": "US", "admin1": "California", "latitude": 37.7, "longitude": -121.9},
                       {"name": "Dublin", "country": "United States", "country_code": "US", "admin1": "Ohio", "latitude": 40.1, "longitude": -83.1}],
            "Nowhere": [],
            # Open-Meteo gives territories country null and only the ISO code.
            "Bayamon": [{"name": "Bayamon", "country_code": "PR", "admin1": "Bayamon", "latitude": 18.4, "longitude": -66.16}],
            "San Juan": [{"name": "San Juan", "country_code": "PR", "latitude": 18.47, "longitude": -66.1},
                         {"name": "San Juan", "country": "Argentina", "country_code": "AR", "latitude": -31.5, "longitude": -68.5}],
            "Hagatna": [{"name": "Hagatna", "country_code": "GU", "latitude": 13.47, "longitude": 144.75}]}
    real = refresh_week.get
    refresh_week.get = lambda url, params, timeout=20: {"results": rows[params["name"]]}
    try:
        run = refresh_week.Run()
        geo = refresh_week.Geocoder({}, 0, run)
        check("geocode abroad", (geo.lookup("Dublin", None, "Ireland") or {}).get("admin1"), "Leinster")
        check("geocode US state", (geo.lookup("Dublin", "OH", "USA") or {}).get("admin1"), "Ohio")
        check("geocode US default", (geo.lookup("Dublin", "CA") or {}).get("admin1"), "California")
        check("geocode unmatched", (geo.lookup("Nowhere", "TX"), run.counts.get("geocode_unmatched")), (None, 1))
        check("geocode Puerto Rico Bayamon", (geo.lookup("Bayamon", None, "Puerto Rico") or {}).get("lat"), 18.4)
        check("geocode Puerto Rico San Juan", (geo.lookup("San Juan", None, "Puerto Rico") or {}).get("lat"), 18.47)
        check("geocode Guam", (geo.lookup("Hagatna", None, "Guam") or {}).get("lat"), 13.47)
        check("territory matches counted as matched", run.counts.get("geocode_unmatched"), 1)
    finally:
        refresh_week.get = real


def test_tba():
    """An unannounced kickoff (timeValid false, parked at midnight ET) is a Saturday game with
    no forecast and no invented hour, not a Friday 11 PM game with midnight weather."""
    import refresh_week

    class NoGeo:
        def lookup(self, *a):
            return {"lat": 32.6, "lon": -85.5, "elev": 200, "geo_name": "Auburn", "admin1": "Alabama"}

    def team(tid, side):
        return {"homeAway": side, "team": {"id": tid, "abbreviation": side.upper(), "displayName": side.upper() + " U", "conferenceId": "8"}}
    event = {"id": "401999999", "name": "Auburn at Alabama", "shortName": "AUB @ ALA", "date": "2026-11-28T05:00Z",
             "status": {"type": {"name": "STATUS_SCHEDULED", "state": "pre"}},
             "competitions": [{"timeValid": False, "venue": {"fullName": "Bryant-Denny Stadium",
                                                             "address": {"city": "Tuscaloosa", "state": "AL"}},
                               "competitors": [team("333", "home"), team("2", "away")]}]}
    real = refresh_week.forecast
    refresh_week.forecast = lambda *a, **k: FAILS.append("TBA game fetched a forecast") or None
    try:
        g = refresh_week.build_game(event, {"8": "SEC"}, {"8"}, NoGeo(), 0, refresh_week.Run())
    finally:
        refresh_week.forecast = real
    check("tba kick_ct", (g["kick_ct"], g["time_tbd"], g["wx"], g["wx_label"]), ("Sat TBA", True, None, "Kickoff TBA"))
    check("tba not clean", g["impact_notes"][0].startswith("Kickoff time TBA"), True)
    check("tba rivalry", g["rivalry"], "Iron Bowl")
    check("tba startDate is a date", refresh_week.event_ld(g)["startDate"], "2026-11-28")
    check("placeholder: no venue", is_placeholder({"home": {"id": "1", "full": "A"}, "away": {"id": "2", "full": "B"}}), True)
    check("placeholder: TBD team", is_placeholder({"venue": "V", "home": {"id": "-1", "full": "TBD", "abbr": "TBD"},
                                                  "away": {"id": "2", "full": "B"}}), True)
    check("placeholder: real game", is_placeholder(g), False)
    check("placeholder event skipped", refresh_week.event_ld({"id": "1", "venue": "V", "date": "2026-12-05T00:00:00Z",
          "home": {"id": "-1", "full": "TBD"}, "away": {"id": "2", "full": "B"}}), None)
    ld = refresh_week.event_ld(g)
    check("event image, no endDate", (ld["image"], "endDate" in ld), (["https://cfbgameday.app/icons/og.png"], False))
    bowl = json.loads(json.dumps(event))
    bowl["season"] = {"year": 2026, "type": 3}
    bowl["competitions"][0]["notes"] = [{"headline": "Some Bowl"}]
    g = refresh_week.build_game(bowl, {"8": "SEC"}, {"8"}, NoGeo(), 0, refresh_week.Run())
    check("no rivalry tag in a bowl", g["rivalry"], None)


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
    check("api/game.py exists", (ROOT / "api/game.py").is_file(), True)
    check("vercel game function", "api/game.py" in (vj.get("functions") or {}), True)
    sw = (ROOT / "sw.js").read_text("utf-8")
    check("sw skips api", 'startsWith("/api/")' in sw, True)
    html = (ROOT / "index.html").read_text("utf-8")
    check("manifest linked", 'rel="manifest"' in html, True)
    check("apple icon linked", 'rel="apple-touch-icon"' in html, True)
    # Universal links (iOS 1.1): Apple's CDN fetches this; a bad file silently turns the links back into web pages.
    aasa = json.loads((ROOT / ".well-known/apple-app-site-association").read_text("utf-8"))
    details = aasa["applinks"]["details"]
    check("aasa app id", [d["appIDs"] for d in details], [["3V73W9NUZ6.com.hoynelabs.cfbgameday"]])
    check("aasa claims only the board", sorted(c["/"] for d in details for c in d["components"]), ["/", "/index.html"])
    check("aasa served as json", any(h.get("source") == "/.well-known/apple-app-site-association"
                                     and {"key": "Content-Type", "value": "application/json"} in h["headers"]
                                     for h in vj.get("headers") or []), True)


def test_public_hygiene():
    """This repo is public: local notes stay off Vercel too, and no tracked text file carries a user path or a stray email."""
    ignored = {l.strip() for l in (ROOT / ".gitignore").read_text().splitlines()}
    vignored = {l.strip() for l in (ROOT / ".vercelignore").read_text().splitlines()}
    for n in ("CLAUDE.md", "AGENTS.md", "CONTEXT.md", "CONTEXT.private.md", "CONTEXT_ARCHIVE*.md"):
        check(f".gitignore has {n}", n in ignored, True)
        check(f".vercelignore has {n}", n in vignored, True)
    # The one public support address (printed on nfl/support.html) plus GitHub's no-reply form.
    allowed = {"hoynelabs" + "@" + "gm" + "ail.com"}
    email_re = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
    user_path = "/Us" + "ers/"  # fragments: this file must not match itself
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
    bad = []
    for rel in filter(None, out.decode().split("\0")):
        path = ROOT / rel
        if not path.is_file() or path.is_symlink():
            continue
        data = path.read_bytes()
        if b"\0" in data[:4096]:
            continue
        text = data.decode("utf-8", "replace")
        if user_path in text:
            bad.append(f"{rel}: local user path")
        for m in email_re.findall(text):
            if m not in allowed and not m.endswith("@users.noreply.github.com"):
                bad.append(f"{rel}: email {m}")
    check("public hygiene (paths, emails)", bad, [])


if __name__ == "__main__":
    for t in (test_impact, test_time, test_live_math, test_snapshot_shape, test_run_health, test_health_rule, test_fcs_playoff, test_jsonld, test_seo_escaping,
              test_game_payload, test_hosted_api, test_labels, test_promo, test_rivalries, test_geocode, test_tba, test_pwa,
              test_public_hygiene):
        t()
    if FAILS:
        print("\n".join("FAIL " + f for f in FAILS))
        sys.exit(1)
    print("ok")
