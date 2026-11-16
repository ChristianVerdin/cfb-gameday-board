"""nflcore foundation suites: week resolution, ESPN client, cache, sanitizer, teams, time formatting."""
from __future__ import annotations

import gzip
import json
import threading
import time
from datetime import datetime, timezone

from nflcore import cache, espn, sanitize, slate, teams


def _entry(label, value, start, end):
    return {"label": label, "alternateLabel": label, "value": str(value), "startDate": start, "endDate": end}


def _season_cal(post, reg_start="2026-09-06T07:00Z"):
    """Synthetic calendar shaped like ESPN's: 4 preseason, 18 regular (07:00Z then 08:00Z after DST), postseason."""
    pre = [_entry("Preseason Week 1", 2, "2026-08-13T07:00Z", "2026-08-20T06:59Z")]
    reg = [_entry("Week 7", 7, "2026-10-21T07:00Z", "2026-10-28T06:59Z"),
           _entry("Week 8", 8, "2026-10-28T07:00Z", "2026-11-04T07:59Z"),
           _entry("Week 9", 9, "2026-11-04T08:00Z", "2026-11-11T07:59Z"),
           _entry("Week 10", 10, "2026-11-11T08:00Z", "2026-11-18T07:59Z"),
           _entry("Week 11", 11, "2026-11-18T08:00Z", "2026-11-25T07:59Z"),
           _entry("Week 18", 18, "2027-01-06T08:00Z", "2027-01-13T07:59Z")]
    return [{"label": "Preseason", "value": "1", "entries": pre},
            {"label": "Regular Season", "value": "2", "entries": reg},
            {"label": "Postseason", "value": "3", "entries": post},
            {"label": "Off Season", "value": "4", "startDate": "2027-02-16T08:00Z", "endDate": "2027-08-01T06:59Z"}]


POST_2026 = [_entry("Wild Card", 1, "2027-01-13T08:00Z", "2027-01-20T07:59Z"),
             _entry("Divisional Round", 2, "2027-01-20T08:00Z", "2027-01-27T07:59Z"),
             _entry("Conference Championship", 3, "2027-01-27T08:00Z", "2027-02-03T07:59Z"),
             _entry("Super Bowl", 4, "2027-02-03T08:00Z", "2027-02-16T07:59Z")]
POST_2025 = [_entry("Wild Card", 1, "2026-01-07T08:00Z", "2026-01-14T07:59Z"),
             _entry("Divisional Round", 2, "2026-01-14T08:00Z", "2026-01-21T07:59Z"),
             _entry("Conference Championship", 3, "2026-01-21T08:00Z", "2026-01-28T07:59Z"),
             _entry("Pro Bowl", 4, "2026-01-28T08:00Z", "2026-02-04T07:59Z"),
             _entry("Super Bowl", 5, "2026-02-04T08:00Z", "2026-02-12T07:59Z")]
CAL_2026 = {"calendar": _season_cal(POST_2026), "season": {"type": 2, "year": 2026}, "week": {"number": 10}}
CAL_2025 = {"calendar": [{"label": "Postseason", "value": "3", "entries": POST_2025}],
            "season": {"type": 3, "year": 2025}, "week": {"number": 1}}
# ESPN's real 2025 calendar carries an Off Season "Week 1" entry (st 4) after the Super Bowl window.
CAL_2025_OFF = {"calendar": [
    {"label": "Regular Season", "value": "2", "entries": [_entry("Week 18", 18, "2025-12-30T08:00Z", "2026-01-07T07:59Z")]},
    {"label": "Postseason", "value": "3", "entries": POST_2025},
    {"label": "Off Season", "value": "4", "entries": [_entry("Week 1", 1, "2026-02-12T08:00Z", "2026-08-06T06:59Z")]}],
    "season": {"type": 3, "year": 2025}, "week": {"number": 5}}


def _z(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _pick(r):
    return None if r is None else (r["st"], r["week"], r["label"])


def test_week_resolution(check):
    res = lambda s, post=None, cal=CAL_2026: slate.resolve_week(cal, _z(s), post)  # noqa: E731
    r = res("2026-11-15T18:00Z")
    check("inside week 10", _pick(r), (2, 10, "Week 10"))
    check("year from season", r["year"], 2026)
    check("start/end strings", (r["start"], r["end"]), ("2026-11-11T08:00Z", "2026-11-18T07:59Z"))
    check("list calendar accepted", _pick(slate.resolve_week(CAL_2026["calendar"], _z("2026-11-15T18:00Z"))), (2, 10, "Week 10"))
    check("DST-era boundary 06:59Z still week 7", _pick(res("2026-10-28T06:59Z")), (2, 7, "Week 7"))
    check("07:00Z week 8", _pick(res("2026-10-28T07:00Z")), (2, 8, "Week 8"))
    check("07:59Z week 8", _pick(res("2026-11-04T07:59Z")), (2, 8, "Week 8"))
    check("08:00Z week 9", _pick(res("2026-11-04T08:00Z")), (2, 9, "Week 9"))
    check("Wed 08:00Z week 11", _pick(res("2026-11-18T08:00Z")), (2, 11, "Week 11"))
    check("Tue after MNF, games live: stay", _pick(res("2026-11-17T12:00Z", False)), (2, 10, "Week 10"))
    check("Tue after MNF, unknown: stay", _pick(res("2026-11-17T12:00Z", None)), (2, 10, "Week 10"))
    check("Tue after MNF, all post: advance", _pick(res("2026-11-17T12:00Z", True)), (2, 11, "Week 11"))
    check("preseason", _pick(res("2026-08-15T12:00Z")), (1, 2, "Preseason Week 1"))
    check("week 18 final advances to Wild Card", _pick(res("2027-01-12T12:00Z", True)), (3, 1, "Wild Card"))
    check("Wild Card year", res("2027-01-12T12:00Z", True)["year"], 2026)
    sb26 = res("2027-02-08T12:00Z")
    check("2026 Super Bowl is week 4", _pick(sb26), (3, 4, "Super Bowl"))
    sb25 = res("2026-02-08T12:00Z", cal=CAL_2025)
    check("2025 Super Bowl is week 5", _pick(sb25), (3, 5, "Super Bowl"))
    check("2025 year", sb25["year"], 2025)
    check("2025 Pro Bowl label kept", _pick(res("2026-01-30T12:00Z", cal=CAL_2025)), (3, 4, "Pro Bowl"))
    check("2025 string values coerced to int", isinstance(sb25["week"], int) and isinstance(sb25["st"], int), True)
    check("offseason after Super Bowl", res("2027-03-01T12:00Z"), None)
    check("Super Bowl final advances to offseason", res("2027-02-10T12:00Z", True), None)
    check("before preseason", res("2026-07-01T00:00Z"), None)
    check("empty calendar", slate.resolve_week({"calendar": []}, _z("2026-11-15T00:00Z")), None)
    check("naive datetime read as UTC", _pick(slate.resolve_week(CAL_2026, datetime(2026, 11, 15, 18, 0))), (2, 10, "Week 10"))


def test_range_rejection(check):
    seen = []
    old = espn._fetch
    espn._fetch = lambda url, timeout, profile: seen.append(url) or b'{"events": []}'
    try:
        for name, args in (("date range", (2, 10, "20261110-20261116")), ("comma list week", (2, "10,11", None)),
                           ("comma list year", (2, 10, "2025,2026")), ("bool week", (2, True, None)),
                           ("zero week", (2, 0, None)), ("bad st", (4, 1, None)), ("float", (2, 10.5, None))):
            try:
                espn.pull_scoreboard(*args)
                check.true(f"{name} rejected", False)
            except espn.EspnQueryError:
                check.true(f"{name} rejected", True)
        check("no request sent for rejected queries", seen, [])
        try:
            espn.pull_summary("401772834,401772835")
            check.true("summary id list rejected", False)
        except espn.EspnQueryError:
            check.true("summary id list rejected", True)
        espn.pull_scoreboard(3, 1, 2026)
        espn.pull_scoreboard(2, "10")
        check.true("year adds dates=", "seasontype=3&week=1&dates=2026" in seen[0], seen[0])
        check.true("no dates without year", "dates" not in seen[1], seen[1])
        check.true("only ESPN site hosts", all(u.startswith(("https://site.web.api.espn.com", "https://site.api.espn.com")) for u in seen))
        check.true("never the cdn host", not any("cdn.espn.com" in u for u in seen))
    finally:
        espn._fetch = old


def test_fetch_fallback(check):
    old_fetch, old_sleep = espn._fetch, espn._sleep
    espn._sleep = lambda s: None
    calls = []

    def run(script):
        calls.clear()

        def fake(url, timeout, profile):
            calls.append((url.split("/")[2], profile))
            step = script[min(len(calls) - 1, len(script) - 1)]
            if isinstance(step, Exception):
                raise step
            return step
        espn._fetch = fake

    err = lambda code=None: espn.EspnError("x", status=code)  # noqa: E731
    try:
        run([b'{"a": 1}'])
        check("plain json", espn.fetch_json("https://site.api.espn.com/x"), {"a": 1})
        run([gzip.compress(b'{"a": 2}')])
        check("gzip sniffed by 1f8b", espn.fetch_json("https://site.api.espn.com/x"), {"a": 2})
        run([err(403), b'{"a": 3}'])
        check("403 retried with second profile", espn.fetch_json("https://site.api.espn.com/x"), {"a": 3})
        check("profiles tried safari then default", [p for _, p in calls], ["safari", "default"])
        run([err(403), err(403)])
        try:
            espn.fetch_json("https://site.api.espn.com/x")
            check.true("double 403 raises", False)
        except espn.EspnError as e:
            check("double 403 status", e.status, 403)
        run([err(404)])
        try:
            espn.fetch_json("https://site.api.espn.com/x")
        except espn.EspnError as e:
            check("404 not retried", (e.status, len(calls)), (404, 1))
        run([b"<html>nope"])
        try:
            espn.fetch_json("https://site.api.espn.com/x")
            check.true("bad json raises EspnError", False)
        except espn.EspnError:
            check.true("bad json raises EspnError", True)

        run([err(503), err(503), b'{"ok": true}'])
        check("falls back to second host", espn.get_json("/scoreboard"), {"ok": True})
        check("first host tried twice, then second", [h for h, _ in calls],
              ["site.web.api.espn.com", "site.web.api.espn.com", "site.api.espn.com"])
        run([err(502), b'{"ok": 1}'])
        check("per-host retry succeeds on same host", (espn.get_json("/x"), {h for h, _ in calls}),
              ({"ok": 1}, {"site.web.api.espn.com"}))
        run([err(404), b'{"ok": 2}'])
        check("404 skips to other host without retry", (espn.get_json("/x"), [h for h, _ in calls]),
              ({"ok": 2}, ["site.web.api.espn.com", "site.api.espn.com"]))
        run([err()])
        try:
            espn.get_json("/x")
            check.true("all hosts failing raises", False)
        except espn.EspnError:
            check("all hosts exhausted", len(calls), 4)
        check("HOSTS order", espn.HOSTS, ("site.web.api.espn.com", "site.api.espn.com"))
        check("timeouts", (espn.LIVE_TIMEOUT, espn.CI_TIMEOUT), (8, 20))

        espn.CACHE.clear()
        payload = json.dumps({"leagues": [{"calendar": CAL_2026["calendar"]}], "season": {"type": 2, "year": 2026},
                              "week": {"number": 10, "teamsOnBye": [{"id": "3"}]}}).encode()
        run([payload])
        c = espn.pull_calendar()
        check("calendar shape", (c["season"]["year"], c["week"], len(c["calendar"])), (2026, {"number": 10}, 4))
        espn.pull_calendar()
        check("calendar cached", len(calls), 1)
        check("calendar feeds resolve_week", _pick(slate.resolve_week(c, _z("2026-11-15T18:00Z"))), (2, 10, "Week 10"))
        espn.CACHE.clear()
        run([json.dumps({"leagues": [{}]}).encode()])
        try:
            espn.pull_calendar()
            check.true("missing calendar raises", False)
        except espn.EspnError:
            check.true("missing calendar raises", True)
    finally:
        espn._fetch, espn._sleep = old_fetch, old_sleep
        espn.CACHE.clear()


def test_cache(check):
    now = [0.0]
    c = cache.TTLCache(clock=lambda: now[0])
    n = [0]

    def fn():
        n[0] += 1
        return n[0]
    check("first fetch", c.get_or_fetch("k", 10, fn), (1, False))
    check("fresh hit", c.get_or_fetch("k", 10, fn), (1, False))
    now[0] = 11
    check("expired refetch", c.get_or_fetch("k", 10, fn), (2, False))

    def boom():
        raise RuntimeError("down")
    now[0] = 25
    check("stale if error", c.get_or_fetch("k", 10, boom, stale_ok_s=300), (2, True))
    now[0] = 25 + 400
    try:
        c.get_or_fetch("k", 10, boom, stale_ok_s=300)
        check.true("too stale raises", False)
    except RuntimeError:
        check.true("too stale raises", True)
    try:
        c.get_or_fetch("never", 10, boom)
        check.true("no entry raises", False)
    except RuntimeError:
        check.true("no entry raises", True)

    c2 = cache.TTLCache()
    runs, results = [0], []

    def slow():
        runs[0] += 1
        time.sleep(0.15)
        return "v"
    ts = [threading.Thread(target=lambda: results.append(c2.get_or_fetch("s", 30, slow))) for _ in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    check("single flight ran once", runs[0], 1)
    check("all callers got the value", results, [("v", False)] * 8)
    c2.get_or_fetch("other", 30, slow)
    check("keys independent", runs[0], 2)


def _poison():
    k = sanitize
    o, p, s, m = "od" + "ds", "pick" + "center", "spr" + "ead", "money" + "line"
    return {
        "id": "1", o: [{"provider": {"name": "x"}, "details": "x"}],
        "competitions": [{"id": "2", o: [], "competitors": [{"team": {"id": "3"}, "score": "7",
                                                           "homeTeamOdds": 1, "records": [{"summary": "5-4"}]}]}],
        p: [{"a": 1}], "against" + "TheSpread": [{"b": 2}], "predictor": {"homeTeam": {}},
        "nested": [[{s: 3, "keep": 1, "pointSpread": {"c": 1}}], {"deep": {m: 5, "ok": True}}],
        "overUnder": 44.5, "homeCoverProbability": 0.5, "cover_pct": 1,
        "fumbleRecoveries": 2, "coverage": "x", "recoveredBy": "y", "yardsFromEndzone": 3,
    }


def test_sanitize(check):
    d = _poison()
    check.true("poison has hits", len(sanitize.find_forbidden(d)) == 12)
    try:
        sanitize.assert_clean(d)
        check.true("assert_clean raises on poison", False)
    except sanitize.ForbiddenKeyError:
        check.true("assert_clean raises on poison", True)
    before = json.dumps(d, sort_keys=True)
    sanitize.find_forbidden(d)
    check("find_forbidden does not mutate", json.dumps(d, sort_keys=True), before)
    n = sanitize.scrub(d)
    check("scrub count", n, 12)
    check("nothing left", sanitize.find_forbidden(d), [])
    sanitize.assert_clean(d)
    check("legal keys survive", sorted(k for k in d if not isinstance(d[k], (list, dict))),
          ["coverage", "fumbleRecoveries", "id", "recoveredBy", "yardsFromEndzone"])
    check("deep legal keys survive", d["nested"][1]["deep"], {"ok": True})
    check("sibling kept", d["nested"][0], [{"keep": 1}])
    check("team kept", d["competitions"][0]["competitors"][0]["records"], [{"summary": "5-4"}])
    check("second scrub is a no-op", sanitize.scrub(d), 0)
    check("scrub scalars/lists", (sanitize.scrub(5), sanitize.scrub([{"od" + "ds": 1}, 2])), (0, 1))
    check.true("FORBIDDEN_KEYS populated", {"od" + "ds", "pick" + "center"} <= sanitize.FORBIDDEN_KEYS)


def test_teams(check):
    check("32 ids", len(teams.TEAMS), 32)
    check("32 unique nflverse abbrs", len(set(teams.NFLVERSE_ABBR.values())), 32)
    check("WSH->WAS", teams.nflverse_abbr("WSH"), "WAS")
    check("LAR->LA", teams.nflverse_abbr("LAR"), "LA")
    check("identity", teams.nflverse_abbr("KC"), "KC")
    check("LAC stays", teams.nflverse_abbr("LAC"), "LAC")
    check("round trip", teams.espn_abbr("WAS"), "WSH")
    check("ids", sorted(teams.TEAMS, key=int), [str(i) for i in range(1, 31)] + ["33", "34"])
    check("spot ids", [teams.TEAMS[i]["abbr"] for i in ("22", "33", "34", "28", "24", "14", "10")],
          ["ARI", "BAL", "HOU", "WSH", "LAC", "LAR", "TEN"])
    check("all-star ids", teams.ALL_STAR_IDS, {"31": "AFC", "32": "NFC"})
    check.true("all-stars are not clubs", not teams.is_all_star("3") and teams.is_all_star(31))
    divs = {}
    for t in teams.TEAMS.values():
        divs.setdefault(t["div"], []).append(t["abbr"])
    check("8 divisions of 4", sorted(len(v) for v in divs.values()), [4] * 8)
    check("conference split", sorted({c: sum(t["conf"] == c for t in teams.TEAMS.values()) for c in ("AFC", "NFC")}.items()),
          [("AFC", 16), ("NFC", 16)])
    check("CHI division", teams.BY_ABBR["CHI"]["div"], "NFC North")


def test_kick_time(check):
    check("Sunday noon CST", slate.kick_ct("2026-11-15T18:00Z"), "Sun 12:00 PM CT")
    check("Monday 01:15Z is Sunday night CT", slate.kick_ct("2026-11-16T01:15Z"), "Sun 7:15 PM CT")
    check("Tuesday 01:15Z is Monday night CT", slate.kick_ct("2026-11-17T01:15Z"), "Mon 7:15 PM CT")
    check("Thursday night", slate.kick_ct("2026-11-27T01:20Z"), "Thu 7:20 PM CT")
    check("CDT offset", slate.kick_ct("2026-09-13T17:00Z"), "Sun 12:00 PM CT")
    check("placeholder 05:00Z is plain", slate.kick_ct("2026-11-16T05:00Z"), "Sun 11:00 PM CT")
    check("placeholder 05:00Z in CDT", slate.kick_ct("2026-09-14T05:00Z"), "Mon 12:00 AM CT")
    check("morning", slate.kick_ct("2026-11-15T14:30Z"), "Sun 8:30 AM CT")
    check("chicago_date crosses midnight", slate.chicago_date("2026-11-16T01:15Z"), "2026-11-15")
    check("chicago_date same day", slate.chicago_date("2026-11-15T18:00Z"), "2026-11-15")
    check("chicago tz name", slate.chicago(datetime(2026, 11, 15, 18, 0, tzinfo=timezone.utc)).tzname(), "CST")
    check("chicago naive is UTC", slate.chicago(datetime(2026, 7, 1, 18, 0)).hour, 13)


def test_offseason_entries_ignored(check):
    ents = slate.parse_calendar(CAL_2025_OFF)
    check("only seasons 1-3 parsed", sorted({e["st"] for e in ents}), [2, 3])
    res = lambda s, post=None: slate.resolve_week(CAL_2025_OFF, _z(s), post)  # noqa: E731
    check("super bowl week", _pick(res("2026-02-10T12:00Z")), (3, 5, "Super Bowl"))
    check("advance past the super bowl is the offseason", res("2026-02-10T12:00Z", True), None)
    check("2026-02-12T12:00Z is the offseason", res("2026-02-12T12:00Z"), None)
    check("mid offseason", res("2026-05-01T12:00Z"), None)
    junk = {"calendar": [{"value": "9", "entries": [_entry("X", 1, "2026-01-01T00:00Z", "2026-01-02T00:00Z")]}]}
    check("unknown season type ignored", slate.parse_calendar(junk), [])


def test_event_settled(check):
    ev = lambda name, state, done: {"status": {"type": {"name": name, "state": state, "completed": done}}}  # noqa: E731
    check("final", slate.event_settled(ev("STATUS_FINAL", "post", True)), True)
    check("canceled under post", slate.event_settled(ev("STATUS_CANCELED", "post", False)), True)
    check("suspended under post", slate.event_settled(ev("STATUS_SUSPENDED", "post", False)), False)
    check("rain delay under post", slate.event_settled(ev("STATUS_RAIN_DELAY", "post", False)), False)
    check("in progress", slate.event_settled(ev("STATUS_IN_PROGRESS", "in", False)), False)
    comp = {"competitions": [{"status": {"type": {"name": "STATUS_FINAL", "state": "post", "completed": True}}}]}
    check("competition status read", slate.event_settled(comp), True)
