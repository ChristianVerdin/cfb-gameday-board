"""api suites: request validation, gating, cache tiers, error policy. All fetchers are fakes."""
from __future__ import annotations

import copy
import http.client
import importlib.util
import io
import json
import threading
from datetime import datetime, timedelta, timezone
from http.server import HTTPServer
from pathlib import Path

from nflcore import api, espn
from nflcore.cache import TTLCache

ROOT = Path(__file__).resolve().parents[3]
BAD = "public, s-maxage=3600"
LIVE_CC = "public, max-age=0, s-maxage=15, stale-while-revalidate=30"
IDLE_CC = "public, max-age=0, s-maxage=60, stale-while-revalidate=120"
NONE_CC = "public, max-age=0, s-maxage=300, stale-while-revalidate=600"
PAYLOAD_KEYS = {"ok", "v", "count", "fetched_at", "source_host", "stale", "season", "week", "teams_on_bye", "warnings", "games"}


def utc(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


class Fakes:
    """Scoreboards keyed by (st, week); records every call."""

    def __init__(self, check, boards=None):
        self.cal = check.fixture("sb_bare.json")["leagues"][0]["calendar"]
        self.season = {"year": 2026, "type": 2}
        self.boards = boards if boards is not None else {
            (2, 9): {"events": []},
            (2, 10): check.fixture("live_sb_w10_mid.json"),
            (2, 11): check.fixture("sb_2026_w11.json"),
            (2, 12): check.fixture("sb_2026_w12.json"),
            (3, 1): check.fixture("sb_2026_post_w1.json"),
        }
        self.sb_calls, self.cal_calls, self.sum_calls = [], 0, []
        self.fail_sb = self.fail_cal = False
        self.summary = check.fixture("live_summary_early.json")
        self.summary_error = None

    def scoreboard(self, st, week, year=None):
        self.sb_calls.append((st, week, year))
        if self.fail_sb or (st, week) not in self.boards:
            raise espn.EspnError("down")
        return copy.deepcopy(self.boards[(st, week)])

    def calendar(self):
        self.cal_calls += 1
        if self.fail_cal:
            raise espn.EspnError("no calendar")
        return {"calendar": self.cal, "season": self.season, "week": {"number": 10}}

    def get_summary(self, gid):
        self.sum_calls.append(gid)
        if self.summary_error:
            raise self.summary_error
        return copy.deepcopy(self.summary)

    def kw(self, **extra):
        d = dict(fetch_scoreboard=self.scoreboard, fetch_calendar=self.calendar, fetch_summary=self.get_summary,
                 cache=TTLCache())
        d.update(extra)
        return d


NOW = "2026-11-15T20:00Z"   # Sunday afternoon of week 10, games in progress


def live(check, f, query=None, now=NOW, **kw):
    return api.route("/api/nfl/live", query or {}, utc(now), **f.kw(**kw))


def test_live_params(check):
    f = Fakes(check)
    bad = [{"x": "1"}, {"week": "abc"}, {"week": "0"}, {"week": "19"}, {"week": "1-2"}, {"week": "1,2"}, {"week": ""},
           {"st": "2"}, {"st": "4", "week": "1"}, {"st": "1", "week": "1"}, {"st": "3", "week": "6"}, {"year": "2026"},
           {"st": "2", "week": "1", "year": "2020"}, {"st": "2", "week": "1", "year": "2027"},
           {"week": ["1", "2"]}, {"week": "1", "st": "2", "extra": "1"}, {"week": " 1"}, {"week": "-1"}]
    for q in bad:
        status, body, cc = live(check, f, q)
        check(f"400 {q}", (status, body["ok"], cc), (400, False, BAD))
    check("no ESPN call for bad params", f.sb_calls, [])
    status, body, cc = live(check, f, {"week": "11"})
    check("week alone means regular season", (status, body["week"]["number"], body["season"]), (200, 11, {"year": 2026, "type": 2}))
    check("week label from the calendar", body["week"]["label"], "Week 11")
    check("one scoreboard call", f.sb_calls, [(2, 11, None)])
    f = Fakes(check)
    live(check, f, {"st": "3", "week": "1"})
    check("postseason sends the season year", f.sb_calls, [(3, 1, 2026)])
    f = Fakes(check)
    f.boards[(3, 5)] = check.fixture("sb_2025_post_w5.json")
    status, body, _ = live(check, f, {"st": "3", "week": "5", "year": "2025"})
    check("previous season", (status, f.sb_calls, body["season"]), (200, [(3, 5, 2025)], {"year": 2025, "type": 3}))
    f = Fakes(check)
    f.boards[(2, 1)] = check.fixture("sb_2025_w1.json")
    live(check, f, {"st": "2", "week": "1", "year": "2025"})
    check("past regular season needs dates=year", f.sb_calls, [(2, 1, 2025)])
    status, body, _ = live(check, f, {"week": ["11"], "st": ["2"]})
    check("parse_qs shaped lists accepted", status, 200)
    f = Fakes(check)
    f.fail_cal = True
    status, body, _ = live(check, f, {"week": "11"})
    check("calendar down, week given", (status, body["week"]["number"]), (200, 11))
    check("hex-like and unicode digits refused", [live(check, Fakes(check), {"week": w})[0] for w in ("0x1", "١", "1e1")], [400, 400, 400])


def test_live_payload(check):
    f = Fakes(check)
    status, body, cc = live(check, f)
    check("default week", (status, cc), (200, LIVE_CC))
    check("payload keys", set(body), PAYLOAD_KEYS)
    check("shape", (body["ok"], body["v"], body["count"], body["stale"], body["source_host"], body["warnings"]),
          (True, 1, 14, False, "espn", []))
    check("fetched_at", body["fetched_at"], "2026-11-15T20:00:00Z")
    check("resolved triple echoed", (body["season"], body["week"]), ({"year": 2026, "type": 2}, {"number": 10, "label": "Week 10"}))
    check("byes", body["teams_on_bye"], ["CHI", "DEN", "PHI", "TB"])
    check("desk on live games only", sorted({(g["state"], g["desk"] is not None) for g in body["games"]}),
          [("in", True), ("post", False), ("pre", False)])
    check("calendar then one scoreboard", (f.cal_calls, f.sb_calls), (1, [(2, 10, None)]))
    f = Fakes(check)
    status, body, cc = live(check, f, now="2027-03-01T00:00Z")
    check("offseason: no slate", (status, body["games"], body["warnings"], body["week"], cc), (200, [], ["no_slate"], None, NONE_CC))
    check("no scoreboard pulled", f.sb_calls, [])


def test_ttl_tiers(check):
    def g(state, date, tbd=False):
        return {"state": state, "date": date, "time_tbd": tbd}
    n = utc(NOW)
    t = lambda games, now=n: api.live_ttl(games, now)  # noqa: E731
    check("any live game", t([g("in", "2026-11-15T18:00Z"), g("pre", "2026-11-16T01:20Z")]), (15, 30))
    check("kick within 90 minutes", t([g("pre", "2026-11-15T21:20Z")]), (15, 30))
    check("kick in 91 minutes is idle-today", t([g("pre", "2026-11-15T21:31Z")]), (60, 120))
    check("kick time already passed, not yet in", t([g("pre", "2026-11-15T19:59Z")]), (15, 30))
    check("final that just ended", t([g("post", "2026-11-15T17:00Z")]), (15, 30))
    check("final from this morning, nothing else today", t([g("post", "2026-11-15T14:30Z")], utc("2026-11-15T21:00Z")), (60, 120))
    check("games only tomorrow", t([g("pre", "2026-11-16T18:00Z")]), (300, 600))
    check("yesterday's finals", t([g("post", "2026-11-14T18:00Z")]), (300, 600))
    check("Chicago date, not UTC date", t([g("pre", "2026-11-16T04:00Z")], utc("2026-11-15T20:00Z")), (60, 120))
    check("flex TBD never counts as near kick", t([g("pre", "2026-12-27T05:00Z", tbd=True)], utc("2026-12-27T04:00Z")), (300, 600))
    check("empty slate", t([]), (300, 600))

    f = Fakes(check)
    cases = (("2026-11-18T18:00Z", NONE_CC), ("2026-11-19T15:00Z", IDLE_CC), ("2026-11-20T00:00Z", LIVE_CC))
    for now, want in cases:
        status, body, cc = live(check, f, now=now)
        check(f"route tier at {now}", (status, body["week"]["number"], cc), (200, 11, want))


def test_week_advance(check):
    f = Fakes(check)
    done = f.boards[(2, 10)]
    for ev in done["events"]:
        c = ev["competitions"][0]
        c["status"]["type"].update(name="STATUS_FINAL", state="post", completed=True)
        c.pop("situation", None)
    status, body, cc = live(check, f, now="2026-11-17T15:00Z")
    check("Tuesday after the last game moves to the next week", (status, body["week"]["number"], body["count"]), (200, 11, 13))
    check("both scoreboards were read", f.sb_calls, [(2, 10, None), (2, 11, None)])
    f = Fakes(check)
    f.boards[(2, 10)] = done
    status, body, _ = live(check, f, now="2026-11-18T09:00Z")
    check("Wednesday: the calendar rolls over by itself", (body["week"]["number"], f.sb_calls), (11, [(2, 11, None)]))
    f = Fakes(check)
    status, body, _ = live(check, f, now="2026-11-17T15:00Z")
    check("games still pending: stay on the week", body["week"]["number"], 10)
    f = Fakes(check)
    f.boards[(2, 10)] = {"events": []}
    status, body, _ = live(check, f, now="2026-11-17T15:00Z")
    check("empty week does not advance", body["week"]["number"], 10)


def test_error_policy(check):
    t = [0.0]
    cache = TTLCache(clock=lambda: t[0])
    f = Fakes(check)
    call = lambda: live(check, f, cache=cache)  # noqa: E731
    s1, b1, c1 = call()
    check("first fetch", (s1, b1["stale"], len(f.sb_calls)), (200, False, 1))
    t[0] = 5
    call()
    check("8 s in-process cache", len(f.sb_calls), 1)
    t[0] = 9
    call()
    check("refetch after ttl", len(f.sb_calls), 2)
    f.fail_sb = True
    t[0] = 30
    s2, b2, c2 = call()
    check("stale-if-error serves the old payload", (s2, b2["stale"], b2["count"]), (200, True, 14))
    check("stale keeps its original fetched_at", b2["fetched_at"], b1["fetched_at"])
    check("stale is cached briefly", c2, "public, max-age=0, s-maxage=5, stale-while-revalidate=10")
    t[0] = 9 + 299
    check("still stale at 5 minutes", call()[1]["stale"], True)
    t[0] = 9 + 301
    s3, b3, c3 = call()
    check("too old: 502 no-store", (s3, b3["ok"], c3), (502, False, "no-store"))
    check("502 body is generic", b3["error"], "upstream unavailable")
    status, body, cc = api.route("/api/nfl/live", {}, utc(NOW), **Fakes(check, boards={}).kw())
    check("cold failure", (status, cc), (502, "no-store"))
    f = Fakes(check)
    f.fail_cal = True
    check("default week needs the calendar", live(check, f)[0:3:2], (502, "no-store"))
    f = Fakes(check)
    def boom(*a, **k):
        raise espn.EspnQueryError("bad")
    check("query errors are 400", api.route("/api/nfl/live", {}, utc(NOW), **f.kw(fetch_scoreboard=boom))[0], 400)
    check("unknown path", api.route("/api/nfl/nope", {}, utc(NOW), **f.kw())[0:3:2], (404, BAD))
    check("trailing slash ok", api.route("/api/nfl/live/", {}, utc(NOW), **f.kw())[0], 200)


def test_payload_budget(check):
    sb = check.fixture("live_sb_w10_mid.json")
    live_evs = [e for e in sb["events"] if e["competitions"][0]["status"]["type"]["state"] == "in"]
    events = []
    for i in range(16):
        e = copy.deepcopy(live_evs[i % len(live_evs)])
        e["id"] = str(401880000 + i)
        e["competitions"][0]["situation"]["lastPlay"]["text"] = "x" * 400
        events.append(e)
    f = Fakes(check, boards={(2, 10): {**sb, "events": events}})
    status, body, _ = live(check, f)
    size = len(json.dumps(body, separators=(",", ":")))
    check("16 live games", (status, body["count"]), (200, 16))
    check.true(f"live payload under 30 KB ({size} bytes)", size < 30_000)
    f = Fakes(check)
    body = live(check, f)[1]
    check.true("real 14-game capture under 30 KB", len(json.dumps(body, separators=(",", ":"))) < 30_000)


def test_scrub(check):
    key = "od" + "ds"
    p = {"warnings": [], "a": {key: 1, "ok": 2, "list": [{"spread": 3}]}}
    check("scrub reports", api._scrub(p)["warnings"], ["forbidden_dropped: 2"])
    check("keys gone", p["a"], {"ok": 2, "list": [{}]})


# ---- /api/nfl/game ----

def sheet(state="in", **extra):
    return {"state": state, "teams": {}, "drives": [], "warnings": [], **extra}


def game(check, f, gid, now=NOW, ns=None, **kw):
    seen = []

    def fake_ns(summary, event):
        seen.append((summary, event))
        return ns(summary, event) if ns else sheet()
    kw.setdefault("norm_summary", fake_ns)
    out = api.route("/api/nfl/game", {} if gid is None else {"id": gid}, utc(now), **f.kw(**kw))
    return out, seen


def test_game_id(check):
    f = Fakes(check)
    for gid in ("abc", "12345678", "1234567890123", "40187305a", "", "4018730 58", "-401873058"):
        out, _ = game(check, f, gid)
        check(f"bad id {gid!r}", (out[0], out[2]), (400, BAD))
    out, _ = game(check, f, None)
    check("missing id", out[0], 400)
    out = api.route("/api/nfl/game", {"id": "401873058", "x": "1"}, utc(NOW), **f.kw())
    check("unknown param", (out[0], out[2]), (400, BAD))
    out = api.route("/api/nfl/game", {"id": ["401873058", "401873059"]}, utc(NOW), **f.kw())
    check("duplicate id", out[0], 400)
    check("no upstream calls for bad requests", (f.sb_calls, f.sum_calls), ([], []))


def test_game_gate(check):
    f = Fakes(check)
    (status, body, cc), seen = game(check, f, "401873058")
    check("listed id served", (status, body["ok"], body["id"], body["state"]), (200, True, "401873058", "in"))
    check("norm_summary got the scoreboard event", (seen[0][1] or {}).get("id"), "401873058")
    check("gate read previous, current and next week", sorted(c[:2] for c in f.sb_calls), [(2, 9), (2, 10), (2, 11)])
    next_id = f.boards[(2, 11)]["events"][0]["id"]
    (status, body, cc), seen = game(check, f, next_id, cache=f.kw()["cache"])
    check("next week's id passes", (status, (seen[0][1] or {}).get("id")), (200, next_id))
    (status, body, cc), seen = game(check, f, "401999999")
    check("id in none of the three weeks", (status, body["ok"], cc, seen), (404, False, BAD, []))
    f2 = Fakes(check)
    game(check, f2, "401999999")
    check("no summary pull for a gated id", f2.sum_calls, [])

    f = Fakes(check)
    f.fail_sb = True
    (status, body, cc), seen = game(check, f, "401999999")
    check("scoreboards down: valid id accepted on identity alone", (status, seen[0][1]), (200, None))
    f.summary = copy.deepcopy(f.summary)
    for c in f.summary["header"]["competitions"][0]["competitors"]:
        c["team"]["abbreviation"] = "XXX"
    (status, body, cc), seen = game(check, f, "401999998")
    check("identity check fails: 404 cached", (status, cc, seen), (404, BAD, []))

    f = Fakes(check)
    f.boards.pop((2, 11))   # one week unavailable: a missing id is not proof, so best effort
    (status, _, _), _ = game(check, f, "401999999")
    check("partial gate stays open", status, 200)
    f = Fakes(check)
    f.fail_cal = True
    (status, _, _), seen = game(check, f, "401999999")
    check("calendar down: identity only", (status, f.sb_calls), (200, []))

    f = Fakes(check)
    f.fail_sb = True
    f.summary = check.fixture("summary_probowl_2025.json")
    (status, _, _), _ = game(check, f, "401831718")
    check("Pro Bowl squads pass the identity check", status, 200)
    f.summary = {"header": {"competitions": [{"competitors": [{"team": {"abbreviation": "KC"}}]}]}}
    check("one team is not a game", game(check, f, "401999997")[0][0], 404)
    f.summary = {"boxscore": {}}
    check("no header", game(check, f, "401999996")[0][0], 404)


def test_game_errors_and_ttl(check):
    f = Fakes(check)
    f.summary_error = espn.EspnError("HTTP 404", status=404)
    (status, body, cc), _ = game(check, f, "401873058")
    check("ESPN 404 cached an hour", (status, cc), (404, BAD))
    f = Fakes(check)
    f.summary_error = espn.EspnError("HTTP 500", status=500)
    (status, body, cc), _ = game(check, f, "401873058")
    check("upstream failure", (status, cc, body["ok"]), (502, "no-store", False))
    f = Fakes(check)
    (status, body, cc), _ = game(check, f, "401873058", ns=lambda s, e: 1 / 0)
    check("normalizer crash", (status, cc), (502, "no-store"))

    cc = lambda state, now=NOW, event=None, **extra: api.game_ttl(sheet(state, **extra), event, utc(now))  # noqa: E731
    check("live", cc("in"), (15, 30))
    check("pre", cc("pre"), (300, 600))
    check("final just now", cc("post", last_play_wallclock="2026-11-15T19:45:00Z"), (60, 120))
    check("final 29 minutes ago", cc("post", last_play_wallclock="2026-11-15T19:31:00Z"), (60, 120))
    check("final 31 minutes ago", cc("post", last_play_wallclock="2026-11-15T19:29:00Z"), (3600, None))
    check("no wallclock, kick long ago", cc("post", event={"date": "2026-11-15T14:30Z"}), (3600, None))
    check("no wallclock, kick recently", cc("post", event={"date": "2026-11-15T17:00Z"}), (60, 120))
    check("no wallclock, no event", cc("post"), (60, 120))
    check("bad wallclock falls back", cc("post", last_play_wallclock="soon", event={"date": "2026-11-15T14:30Z"}), (3600, None))

    f = Fakes(check)
    for state, want in (("in", LIVE_CC), ("pre", "public, max-age=0, s-maxage=300, stale-while-revalidate=600"),
                        ("post", "public, max-age=0, s-maxage=3600")):
        extra = {"last_play_wallclock": "2026-11-15T10:00:00Z"} if state == "post" else {}
        (status, body, got), _ = game(check, f, "401873058", ns=lambda s, e, st=state, ex=extra: sheet(st, **ex), cache=TTLCache())
        check(f"header for {state}", (status, got), (200, want))


def test_game_payload(check):
    f = Fakes(check)
    key = "od" + "ds"
    (status, body, _), _ = game(check, f, "401873058", ns=lambda s, e: sheet(drives=[{key: 1, "ok": True}], ok=False, id="evil"))
    check("envelope wins over the sheet", (body["ok"], body["v"], body["id"], body["stale"]), (True, 1, "401873058", False))
    check("forbidden key scrubbed and reported", (body["drives"], body["warnings"]), ([{"ok": True}], ["forbidden_dropped: 1"]))
    (status, body, _), _ = game(check, f, "401873058", ns=lambda s, e: {"state": "in", "warnings": "oops"}, cache=TTLCache())
    check("warnings always a list", body["warnings"], [])
    t = [0.0]
    cache = TTLCache(clock=lambda: t[0])
    f.sum_calls.clear()
    game(check, f, "401873058", cache=cache)
    t[0] = 5
    game(check, f, "401873058", cache=cache)
    check("summary cached 8 s", len(f.sum_calls), 1)
    t[0] = 20
    f.summary_error = espn.EspnError("down", status=500)
    (status, body, cc), _ = game(check, f, "401873058", cache=cache)
    check("stale-if-error on the summary", (status, body["stale"], cc), (200, True, "public, max-age=0, s-maxage=5, stale-while-revalidate=10"))
    out = api.route("/api/nfl/game", {"id": "401873058"}, utc(NOW), **Fakes(check).kw())
    check("the real sheet module is wired lazily", out[0] in (200, 502, 503), True)


class _Fake:
    def __init__(self, path):
        self.path, self.sent, self.wfile = path, [], io.BytesIO()

    def send_response(self, code):
        self.sent.append(("status", code))

    def send_header(self, k, v):
        self.sent.append((k, v))

    def end_headers(self):
        pass


def test_handlers(check):
    h = _Fake("/api/nfl/live?week=11&st=2")
    got = {}

    def fake_route(path, query):
        got.update(path=path, query=query)
        return 200, {"ok": True, "n": 1}, LIVE_CC
    api.handle(h, route_fn=fake_route)
    check("path and parsed query", got, {"path": "/api/nfl/live", "query": {"week": ["11"], "st": ["2"]}})
    check("headers", dict(h.sent), {"status": 200, "Content-Type": "application/json", "Cache-Control": LIVE_CC,
                                    "Access-Control-Allow-Origin": "*", "Content-Length": str(len(h.wfile.getvalue()))})
    check("compact body", h.wfile.getvalue(), b'{"ok":true,"n":1}')
    h = _Fake("/api/nfl/live")
    api.handle(h, head=True, route_fn=lambda *a: 1 / 0)
    check("HEAD never routes", (dict(h.sent)["status"], h.wfile.getvalue()), (200, b""))

    for name in ("live", "game"):
        spec = importlib.util.spec_from_file_location(f"nfl_api_{name}", ROOT / "api" / "nfl" / f"{name}.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.handler.log_message = lambda self, fmt, *a: None
        srv = HTTPServer(("127.0.0.1", 0), mod.handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            conn = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=5)
            conn.request("HEAD", f"/api/nfl/{name}")
            r = conn.getresponse()
            body = r.read()
            check(f"HEAD {name}", (r.status, body, r.getheader("Content-Type"), r.getheader("Cache-Control")),
                  (200, b"", "application/json", "no-store"))
            conn.close()
            conn = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=5)
            conn.request("GET", f"/api/nfl/{name}?bogus=1")   # rejected before any ESPN call
            r = conn.getresponse()
            check(f"GET {name} rejects unknown params", (r.status, json.loads(r.read())["ok"], r.getheader("Cache-Control")), (400, False, BAD))
            conn.close()
        finally:
            srv.shutdown()
            srv.server_close()
        check(f"{name} handler has both verbs", (hasattr(mod.handler, "do_GET"), hasattr(mod.handler, "do_HEAD")), (True, True))
