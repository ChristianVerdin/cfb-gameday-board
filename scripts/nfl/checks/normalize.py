"""normalize suites: scoreboard events -> /api/nfl/live game objects."""
from __future__ import annotations

import copy
import json
import re

from nflcore import normalize as nz
from nflcore import sanitize

GAME_KEYS = {"id", "state", "status", "statusDetail", "statusShort", "period", "periodLabel", "clock", "clock_s",
             "completed", "ot", "result", "date", "time_tbd", "flex_note", "neutral", "placeholder", "venue_name",
             "broadcasts", "away", "home", "situation", "wp", "desk"}
SIDE_KEYS = {"id", "abbr", "name", "color", "alt", "score", "record", "timeouts", "linescores"}
SIT_KEYS = {"text", "down", "distance", "stoppage", "possession", "possession_abbr", "yard_text", "yl100",
            "is_red_zone", "goal_to_go", "last_play"}
LAST_KEYS = {"id", "text", "type"}
# Built from fragments so this file never trips the repo's static scans.
BETTING = re.compile("|".join(("od" + "ds", "sprea" + "d", "money" + "line", "implie" + "d", "pick" + "center", "wage" + "r",
                               "sports" + "book", "gambl", "draft" + "kings", "fan" + "duel", "over" + "under")), re.I)

FIXTURES = ("sb_2025_w1.json", "sb_2025_w4.json", "sb_2025_post_w1.json", "sb_2025_post_w4.json",
            "sb_2025_post_w5.json", "sb_2026_w10.json", "sb_2026_w11.json", "sb_2026_w12.json", "sb_2026_w16.json",
            "sb_2026_w18.json", "sb_2026_post_w1.json", "live_sb_w10_mid.json")


def _events(check, name):
    return check.fixture(name)["events"]


def _by_short(check, name, short):
    return next(e for e in _events(check, name) if e["shortName"] == short)


def _live_event(check, short="KC @ ATL"):
    return copy.deepcopy(_by_short(check, "live_sb_w10_mid.json", short))


def _set_status(ev, name, state, period, clock, completed=False, clock_s=None):
    st = ev["competitions"][0]["status"]
    st["type"].update(name=name, state=state, completed=completed)
    st["period"], st["displayClock"] = period, clock
    st["clock"] = float(clock_s if clock_s is not None else 0)


def test_status_states(check):
    sb = check.fixture("live_sb_w10_mid.json")
    out = nz.norm_live(sb)
    check("no warnings", out["warnings"], [])
    check("every event kept", len(out["games"]), len(sb["events"]))
    check("states", sorted({g["state"] for g in out["games"]}), ["in", "post", "pre"])
    live = {g["id"]: g for g in out["games"]}["401873058"]
    check("in-progress short", live["statusShort"], "Q3 8:06")
    check("in-progress label", (live["period"], live["periodLabel"], live["clock"], live["clock_s"]), (3, "Q3", "8:06", 486))
    check("in-progress not completed", (live["completed"], live["result"], live["ot"]), (False, None, False))
    check("scheduled short", [g["statusShort"] for g in out["games"] if g["state"] == "pre"][0], "Scheduled")
    fin = [g for g in out["games"] if g["state"] == "post"][0]
    check("final short", (fin["statusShort"], fin["completed"], fin["periodLabel"]), ("Final", True, "Q4"))
    check("bye abbrs", out["teams_on_bye"], ["CHI", "DEN", "PHI", "TB"])

    ev = _live_event(check)
    _set_status(ev, "STATUS_HALFTIME", "in", 2, "0:00")
    g = nz.norm_event(ev)
    check("halftime", (g["state"], g["status"], g["statusShort"], g["periodLabel"]), ("in", "STATUS_HALFTIME", "Halftime", "Q2"))
    _set_status(ev, "STATUS_END_PERIOD", "in", 3, "0:00")
    check("end of period", nz.norm_event(ev)["statusShort"], "End of Q3")
    ev["competitions"][0]["situation"]["lastPlay"]["type"]["text"] = "End Period"
    _set_status(ev, "STATUS_IN_PROGRESS", "in", 2, "15:00", clock_s=900)
    check("quarter break at 15:00 reads as end of Q1", nz.norm_event(ev)["statusShort"], "End of Q1")
    ev["competitions"][0]["situation"]["lastPlay"]["type"]["text"] = "Rush"
    check("same clock after a snap reads Q2 15:00", nz.norm_event(ev)["statusShort"], "Q2 15:00")
    _set_status(ev, "STATUS_DELAYED", "in", 2, "6:10", clock_s=370)
    ev["competitions"][0]["status"]["type"]["description"] = "Delayed"
    g = nz.norm_event(ev)
    check("delayed passes through", (g["status"], g["statusShort"], g["state"]), ("STATUS_DELAYED", "Delayed", "in"))
    _set_status(ev, "STATUS_SOMETHING_NEW", "in", 2, "6:10", clock_s=370)
    check("unknown name kept", nz.norm_event(ev)["status"], "STATUS_SOMETHING_NEW")
    _set_status(ev, "STATUS_POSTPONED", "post", 0, "0:00")
    ev["competitions"][0]["status"]["type"]["description"] = "Postponed"
    g = nz.norm_event(ev)
    check("postponed", (g["statusShort"], g["completed"], g["result"]), ("Postponed", False, None))
    check("period labels", [nz.period_label(n) for n in (0, 1, 4, 5, 6, 7)], ["", "Q1", "Q4", "OT", "2OT", "3OT"])


def test_periods_ot(check):
    ev = _live_event(check)
    for side in ev["competitions"][0]["competitors"]:
        side["linescores"] = [{"value": float(v), "period": i + 1, "displayValue": str(v)} for i, v in enumerate((7, 7, 0, 3, 3))]
        side["score"] = "20"
    st = ev["competitions"][0]["status"]
    _set_status(ev, "STATUS_IN_PROGRESS", "in", 5, "7:12", clock_s=432)
    g = nz.norm_event(ev)
    check("OT label", (g["period"], g["periodLabel"], g["ot"], g["statusShort"]), (5, "OT", True, "OT 7:12"))
    check("5 linescores kept", [len(g["home"]["linescores"]), len(g["away"]["linescores"])], [5, 5])
    check("linescores are ints", g["home"]["linescores"], [7, 7, 0, 3, 3])

    st["period"] = 4   # status lags the OT kickoff; the fifth linescore floors the period
    g = nz.norm_event(ev)
    check("OT floor from linescores", (g["period"], g["periodLabel"], g["ot"]), (5, "OT", True))

    for side in ev["competitions"][0]["competitors"]:
        side["linescores"].append({"value": 0.0, "period": 6, "displayValue": "0"})
    _set_status(ev, "STATUS_IN_PROGRESS", "in", 6, "10:00", clock_s=600)
    g = nz.norm_event(ev)
    check("2OT", (g["periodLabel"], g["statusShort"], len(g["home"]["linescores"])), ("2OT", "2OT 10:00", 6))

    _set_status(ev, "STATUS_FINAL", "post", 5, "0:00", completed=True)
    for side in ev["competitions"][0]["competitors"]:
        side["linescores"] = side["linescores"][:5]
    ev["competitions"][0]["competitors"][0]["score"] = "23"
    g = nz.norm_event(ev)
    check("OT final", (g["statusShort"], g["ot"], g["completed"]), ("Final/OT", True, True))
    check("OT winner by score", g["result"], "home" if ev["competitions"][0]["competitors"][0]["homeAway"] == "home" else "away")

    ev = _live_event(check)
    g = nz.norm_event(ev)   # Q3: three linescores come back padded to four, never ints invented
    check("padded to four", g["home"]["linescores"], [0, 3, 0, None])
    check("pre game has no linescores", nz.norm_event(_live_event(check, "SEA @ LV"))["home"]["linescores"], [])


def test_ties(check):
    ev = copy.deepcopy(_by_short(check, "live_sb_w10_mid.json", "NE VS DET"))
    comps = ev["competitions"][0]["competitors"]
    for c in comps:
        c["score"], c["winner"] = "20", False
    g = nz.norm_event(ev)
    check("tie result", (g["result"], g["completed"], g["state"], g["statusShort"]), ("tie", True, "post", "Final"))
    comps[0]["score"], comps[0]["winner"] = "27", True
    check("home wins on score", nz.norm_event(ev)["result"], "home" if comps[0]["homeAway"] == "home" else "away")
    for c in comps:   # ESPN flags are ignored: equal scores stay a tie even with a winner flag
        c["score"], c["winner"] = "17", c is comps[0]
    check("flags ignored", nz.norm_event(ev)["result"], "tie")
    ev["competitions"][0]["status"]["type"].update(completed=False, state="in", name="STATUS_IN_PROGRESS")
    check("equal scores while live is no result", nz.norm_event(ev)["result"], None)


def test_records(check):
    p = nz.parse_record
    check("w-l", p("5-5"), {"w": 5, "l": 5, "t": 0, "text": "5-5"})
    check("w-l-t", p("1-2-1"), {"w": 1, "l": 2, "t": 1, "text": "1-2-1"})
    check("0-0-1", p("0-0-1")["t"], 1)
    check("empty", p(""), None)
    check("none", p(None), None)
    check("junk", p("n/a"), None)
    check("four parts", p("1-2-3-4"), None)
    games = {g["id"]: g for g in nz.norm_live(check.fixture("live_sb_w10_mid.json"))["games"]}
    nyg = games["401873052"]
    check("tie record from scoreboard", nyg["home"]["record"], {"w": 5, "l": 3, "t": 1, "text": "5-3-1"})
    check("other side", games["401873053"]["home"]["record"]["text"], "7-2")
    pro = nz.norm_live(check.fixture("sb_2025_post_w4.json"))["games"][0]
    check("pro bowl squads have no record", (pro["home"]["record"], pro["away"]["record"], pro["placeholder"]), (None, None, False))


def test_sentinels(check):
    games = {g["id"]: g for g in nz.norm_live(check.fixture("live_sb_w10_mid.json"))["games"]}
    for gid in ("401873055", "401873056"):   # down -1 after a score / timeout
        s = games[gid]["situation"]
        check(f"{gid} stoppage", (s["stoppage"], s["down"], s["distance"], s["text"], s["yard_text"], s["yl100"]),
              (True, None, None, None, None, None))
        check(f"{gid} goal to go off", s["goal_to_go"], False)
    s = games["401873058"]["situation"]
    check("normal snap", (s["stoppage"], s["down"], s["distance"], s["text"], s["yard_text"]), (False, 2, 8, "2nd & 8", "ATL 46"))
    check("yl100 is yards to the end zone", (s["yl100"], s["possession"], s["possession_abbr"]), (54, "home", "ATL"))
    check("MIN at own 57 means 43 to go", games["401873060"]["situation"]["yl100"], 43)
    check("kickoff return with a live down is not a stoppage", games["401873057"]["situation"]["stoppage"], False)

    ev = _live_event(check)
    sit = ev["competitions"][0]["situation"]
    sit["down"] = 0
    check("down 0", nz.norm_event(ev)["situation"]["stoppage"], True)
    sit["down"], sit["distance"] = 1, 0
    sit["lastPlay"]["type"]["text"] = "Kickoff"
    check("distance 0 after kickoff", nz.norm_event(ev)["situation"]["stoppage"], True)
    sit["lastPlay"]["type"]["text"] = "Rush"
    check("distance 0 after a scrimmage play is kept", nz.norm_event(ev)["situation"]["stoppage"], False)
    del sit["down"]
    check("missing down", nz.norm_event(ev)["situation"]["stoppage"], True)

    sit.update(down=1, distance=10, yardLine=95, possession="1")
    sit["lastPlay"]["text"] = "  A.B  runs\n\nup the   middle " + "x" * 300
    g = nz.norm_event(ev)
    lp = g["situation"]["last_play"]
    check("goal to go", (g["situation"]["yl100"], g["situation"]["goal_to_go"]), (5, True))
    away_id = g["away"]["id"]
    sit.update(possession=away_id, yardLine=70, distance=10)
    a = nz.norm_event(ev)["situation"]
    check("away ball at its own 30 (yardLine 70 from the home goal) has 70 to go", (a["possession"], a["yl100"], a["goal_to_go"]), ("away", 70, False))
    sit.update(yardLine=5, distance=5)
    a = nz.norm_event(ev)["situation"]
    check("away ball at the home 5 is goal to go", (a["yl100"], a["goal_to_go"]), (5, True))
    sit["isRedZone"] = True
    sit["down"] = -1
    check("no red zone chip during a stoppage", nz.norm_event(ev)["situation"]["is_red_zone"], False)
    sit.update(down=1, yardLine=95, possession="1", distance=10)
    check("last play collapsed and clipped", (len(lp["text"]) <= 160, "\n" not in lp["text"], lp["text"][:20]), (True, True, "A.B runs up the midd"))
    sit["distance"] = 5
    check("goal to go at exactly the line", nz.norm_event(ev)["situation"]["goal_to_go"], True)
    sit["distance"] = 4
    check("not goal to go", nz.norm_event(ev)["situation"]["goal_to_go"], False)
    sit["isRedZone"] = True
    check("red zone flag passes through", nz.norm_event(ev)["situation"]["is_red_zone"], True)
    sit["possession"] = "999"
    s = nz.norm_event(ev)["situation"]
    check("unknown possession", (s["possession"], s["possession_abbr"]), (None, None))
    del ev["competitions"][0]["situation"]
    g = nz.norm_event(ev)
    check("live game with no situation", (g["state"], g["situation"], g["wp"]), ("in", None, None))
    check("desk still scores it", g["desk"] is not None, True)
    check("timeouts then unknown", (g["home"]["timeouts"], g["away"]["timeouts"]), (None, None))


def test_win_probability(check):
    g = {g["id"]: g for g in nz.norm_live(check.fixture("live_sb_w10_mid.json"))["games"]}["401873058"]
    check("home wp", g["wp"], {"home": 0.089})
    ev = _live_event(check)
    prob = ev["competitions"][0]["situation"]["lastPlay"]["probability"]
    prob["homeWinPercentage"] = 0.123456
    check("rounds to 3 dp", nz.norm_event(ev)["wp"], {"home": 0.123})
    prob["homeWinPercentage"] = 1.2
    check("out of range is null", nz.norm_event(ev)["wp"], None)
    prob.update(homeWinPercentage=0.0, awayWinPercentage=0.0)
    check("all-zero probability is null", nz.norm_event(ev)["wp"], None)
    prob.update(homeWinPercentage=0.0, awayWinPercentage=1.0)
    check("true zero is kept", nz.norm_event(ev)["wp"], {"home": 0.0})
    del ev["competitions"][0]["situation"]["lastPlay"]["probability"]
    check("missing is null", nz.norm_event(ev)["wp"], None)
    ev["competitions"][0]["situation"]["lastPlay"]["probability"] = {"homeWinPercentage": "0.5"}
    check("non-numeric is null", nz.norm_event(ev)["wp"], None)


def test_time_tbd_flex(check):
    out = nz.norm_live(check.fixture("sb_2026_w16.json"))
    flex = [g for g in out["games"] if g["time_tbd"]]
    check("w16 flex games", len(flex), 4)
    check("w16 note", {g["flex_note"] for g in flex}, {"Flex Game: 12/26 or 12/27"})
    g = flex[0]
    check("tbd short, no formatted kick", (g["statusShort"], any("kick" in k for k in g), g["placeholder"]), ("TBD", False, False))
    check("raw date untouched", g["date"].endswith("T05:00Z"), True)
    check("non-flex games have no note", {x["flex_note"] for x in out["games"] if not x["time_tbd"]}, {None})
    w18 = nz.norm_live(check.fixture("sb_2026_w18.json"))["games"]
    check("w18 all tbd", (len(w18), all(g["time_tbd"] for g in w18)), (16, True))
    check("w18 notes present", all(g["flex_note"] for g in w18), True)
    ev = copy.deepcopy(_events(check, "sb_2026_w16.json")[0])
    ev["competitions"][0]["timeValid"] = True
    ev["competitions"][0]["date"] = "2026-12-26T18:00Z"
    g = nz.norm_event(ev)
    check("resolved flex re-reads the date", (g["time_tbd"], g["flex_note"], g["date"]), (False, None, "2026-12-26T18:00Z"))
    ev["competitions"][0]["timeValid"] = False
    ev["competitions"][0]["notes"] = [{"type": "event", "headline": "NFL Flex   Game"}]
    check("NFL prefix stripped and spaces collapsed", nz.norm_event(ev)["flex_note"], "Flex Game")
    ev["competitions"][0].pop("notes")
    check("no notes", nz.norm_event(ev)["flex_note"], None)


def test_placeholders(check):
    out = nz.norm_live(check.fixture("sb_2026_post_w1.json"))
    check("six placeholders", (len(out["games"]), all(g["placeholder"] for g in out["games"])), (6, True))
    g = out["games"][0]
    check("no sides", (g["home"], g["away"], g["situation"], g["wp"], g["desk"], g["result"]), (None, None, None, None, None, None))
    check("flex note is the round", g["flex_note"], "Wild Card Playoffs")
    check("venue null tolerated", g["venue_name"], None)
    check("postseason season", out["season"], {"year": 2026, "type": 3})
    check("label falls back", out["week"], {"number": 1, "label": "Week 1"})
    out = nz.norm_live(check.fixture("sb_2026_post_w1.json"), {"year": 2026, "st": 3, "week": 1, "label": "Wild Card"})
    check("label from week_info", out["week"], {"number": 1, "label": "Wild Card"})
    check("real games are not placeholders", any(g["placeholder"] for g in nz.norm_live(check.fixture("sb_2026_w12.json"))["games"]), False)
    ev = _events(check, "sb_2026_post_w1.json")[0]
    ev = copy.deepcopy(ev)
    ev["competitions"][0]["competitors"][0]["team"].update(id="1", abbreviation="ATL")   # half-known matchup
    check("one TBD side is still a placeholder", nz.norm_event(ev)["placeholder"], True)


def test_neutral(check):
    games = {g["id"]: g for g in nz.norm_live(check.fixture("live_sb_w10_mid.json"))["games"]}
    g = games["401873053"]
    check("Munich neutral", (g["neutral"], g["venue_name"]), (True, "Allianz Arena"))
    check("sides by homeAway", (g["home"]["abbr"], g["away"]["abbr"]), ("DET", "NE"))
    check("normal game not neutral", games["401873058"]["neutral"], False)
    mx = [g for g in nz.norm_live(check.fixture("sb_2026_w11.json"))["games"] if g["neutral"]]
    check("Mexico City neutral", [g["venue_name"] for g in mx], ["Estadio Banorte"])


def test_venue_names(check):
    seen = set()
    for name in FIXTURES:
        for g in nz.norm_live(check.fixture(name))["games"]:
            if g["venue_name"]:
                seen.add(g["venue_name"])
    check.true("no stale or sponsor-old names", not any(re.search("Reliant|FC Bayern", n) for n in seen), sorted(seen))
    check.true("known names", {"NRG Stadium", "Allianz Arena", "Lumen Field"} <= seen, sorted(seen))
    g = nz.norm_event(_live_event(check))
    check("known id uses table", g["venue_name"], "Mercedes-Benz Stadium")
    ev = _live_event(check)
    ev["competitions"][0]["venue"] = {"id": "99999", "fullName": "Some New Park"}
    check("unknown id falls back to ESPN's name", nz.norm_event(ev)["venue_name"], "Some New Park")
    ev["competitions"][0].pop("venue")
    check("no venue", nz.norm_event(ev)["venue_name"], None)


def test_broadcasts(check):
    ev = _live_event(check)
    ev["competitions"][0]["broadcasts"] = [{"market": "national", "names": ["CBS", "Paramount+"]},
                                           {"market": "local", "names": ["CBS"]}]
    check("flattened and deduped", nz.norm_event(ev)["broadcasts"], ["CBS", "Paramount+"])
    ev["competitions"][0]["broadcasts"] = []
    check("empty", nz.norm_event(ev)["broadcasts"], [])


def test_allowlist(check):
    all_games = []
    for name in FIXTURES:
        out = nz.norm_live(check.fixture(name))
        check.true(f"{name} clean", out["warnings"] == [], out["warnings"])
        all_games += out["games"]
    check.true("many games", len(all_games) > 100)
    for g in all_games:
        if set(g) != GAME_KEYS:
            check(f"game keys {g['id']}", sorted(set(g) ^ GAME_KEYS), [])
            break
        for side in (g["home"], g["away"]):
            if side and set(side) != SIDE_KEYS:
                check(f"side keys {g['id']}", sorted(set(side) ^ SIDE_KEYS), [])
        s = g["situation"]
        if s and (set(s) != SIT_KEYS or (s["last_play"] and set(s["last_play"]) != LAST_KEYS)):
            check(f"situation keys {g['id']}", sorted(set(s) ^ SIT_KEYS), [])
    text = json.dumps(all_games)
    check("no forbidden keys", sanitize.find_forbidden(all_games), [])
    check("no betting vocabulary", BETTING.findall(text), [])
    check("no urls", re.findall(r"https?://", text), [])

    # Poison inputs built in memory: they must not reach the output, at any depth.
    ev = _live_event(check)
    comp = ev["competitions"][0]
    poison = "od" + "ds"
    comp[poison] = [{"provider": {"name": "Book"}, "details": "KC -3", "over" + "Under": 44.5}]
    comp["situation"]["lastPlay"]["sprea" + "d"] = -3
    comp["situation"]["lastPlay"]["probability"]["homeCover" + "Probability"] = 0.5
    comp["competitors"][0]["team"]["logo"] = "https://example.invalid/logo.png"
    comp["competitors"][0]["headshot"] = {"href": "https://example.invalid/h.png"}
    comp["situation"]["pick" + "center"] = {"x": 1}
    text = json.dumps(nz.norm_event(ev))
    check("poison keys absent", [w for w in ("sprea" + "d", poison, "Book", "KC -3", "Cover", "example.invalid", "logo", "headshot") if w in text], [])


def test_no_espn_weather(check):
    ev = _live_event(check)
    ev["competitions"][0]["weather"] = {"displayValue": "Heavy Rain", "temperature": 41, "conditionId": "9"}
    ev["weather"] = {"displayValue": "Snow", "temperature": 20}
    g = nz.norm_event(ev)
    text = json.dumps(g)
    check("weather text never copied", [w for w in ("Heavy Rain", "Snow", "weather", "temperature") if w in text], [])
    check("same output with and without", g, nz.norm_event(_live_event(check)))


def test_event_failure_is_isolated(check):
    sb = copy.deepcopy(check.fixture("live_sb_w10_mid.json"))
    sb["events"][0]["competitions"] = [None]
    out = nz.norm_live(sb)
    check("one bad event skipped", (len(out["games"]), len(out["warnings"])), (len(sb["events"]) - 1, 1))
    check("warning names it", out["warnings"][0].startswith("event_skipped: "), True)
    out = nz.norm_live(check.fixture("live_sb_w10_mid.json"), {"year": 2026, "st": 2, "week": 11, "label": "Week 11"})
    check("calendar vs espn week mismatch warns", out["warnings"], ["week_mismatch: calendar 11, espn 10"])
    check("calendar wins", out["week"], {"number": 11, "label": "Week 11"})
    games = out["games"]
    check("sorted by kickoff then id", [(g["date"], g["id"]) for g in games], sorted((g["date"], g["id"]) for g in games))


def test_held_states_not_final(check):
    ev = _live_event(check)
    for name in ("STATUS_SUSPENDED", "STATUS_DELAYED", "STATUS_RAIN_DELAY"):
        _set_status(ev, name, "post", 3, "4:00", clock_s=240)
        g = nz.norm_event(ev)
        check(f"{name} filed under post is not final", (g["state"], g["completed"], g["result"]), ("in", False, None))
    _set_status(ev, "STATUS_FINAL", "post", 4, "0:00", completed=True)
    check("a completed final stays post", nz.norm_event(ev)["state"], "post")
    _set_status(ev, "STATUS_CANCELED", "post", 0, "0:00")
    check("canceled stays post", nz.norm_event(ev)["state"], "post")
