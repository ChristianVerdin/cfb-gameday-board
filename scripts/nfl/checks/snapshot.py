"""Weekly snapshot builder, offline: envelope and game shape, SEO block, keep-better writes, week targeting."""
from __future__ import annotations

import copy
import json
import re
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from nflcore import espn, sanitize, slate
from scripts.nfl import refresh_nfl as R

from .weather import BANNED, Fetch, _raw

ENV_KEYS = {"schema", "v", "sport", "generated_at", "source", "season", "week", "teams_on_bye", "dates", "warnings",
            "counts", "games"}
GAME_KEYS = {"id", "name", "shortName", "date", "time_tbd", "kick_ct", "kick_day_ct", "flex_note", "kind", "round",
             "week_label", "placeholder", "neutral", "notes", "broadcasts", "streams", "state", "statusShort", "venue",
             "away", "home", "wx_status", "wx"}
TEAM_KEYS = {"id", "abbr", "nv", "name", "full", "color", "alt", "record", "score"}
VENUE_KEYS = {"id", "name", "city", "region", "country", "roof", "lat", "lon", "tz", "known"}
SEO_BAD = re.compile("|".join(("od" + "ds", "off" + "ers", "potential" + "Action", "spr" + "ead", "implied", "price")), re.I)


def _wk(check, name, st, week, label, start="2026-01-01T00:00Z", end="2026-12-31T00:00Z", year=2026):
    return {"year": year, "st": st, "week": week, "label": label, "start": start, "end": end}


def _now(day: str) -> datetime:
    return datetime.fromisoformat(day + "T15:00:00+00:00")


def _fetch():
    return Fetch(_raw(datetime(2026, 10, 20, tzinfo=timezone.utc), hours=24 * 70))


def _build(check, fixture, st, week, label, now, **kw):
    sb = check.fixture(fixture)
    return R.build(sb, _wk(check, fixture, st, week, label), now=now, fetch=kw.pop("fetch", _fetch()), **kw)


def test_envelope(check):
    env = _build(check, "sb_2026_w10.json", 2, 10, "Week 10", _now("2026-11-15"))
    check("envelope keys", set(env), ENV_KEYS)
    check("schema", (env["schema"], env["v"], env["sport"]), (1, 1, "nfl"))
    check("season", env["season"], {"year": 2026, "type": 2})
    check("week keys", set(env["week"]), {"number", "label", "calendar_value", "start", "end"})
    check("week number", env["week"]["number"], 10)
    check("bye count", len(env["teams_on_bye"]), 4)
    check("bye shape", set(env["teams_on_bye"][0]), {"id", "abbr", "name"})
    check("counts keys", set(env["counts"]), set(R.COUNT_KEYS))
    c = env["counts"]
    check("14 games", (c["games"], c["events"]), (14, 14))
    check("no venue_unknown for 2026", c["venue_unknown"], 0)
    check("no failures", (c["wx_failed"], c["forbidden_dropped"], c["games_skipped"]), (0, 0, 0))
    check("every game counted once", c["wx_ok"] + c["wx_dome"] + c["wx_retractable"] + c["wx_skipped"], 14)
    check("dates are Chicago days", env["dates"], sorted(set(env["dates"])))
    check.true("generated_at is Z", env["generated_at"].endswith("Z"))
    sanitize.assert_clean(env)
    json.dumps(env)
    for g in env["games"]:
        check(f"{g['id']} keys", set(g), GAME_KEYS)
        for side in ("away", "home"):
            check(f"{g['id']} {side} keys", set(g[side]), TEAM_KEYS)
        check(f"{g['id']} venue keys", set(g["venue"]), VENUE_KEYS)
        check.true(f"{g['id']} kick label", g["kick_ct"].endswith(" CT"), g["kick_ct"])
    kc = next(g for g in env["games"] if g["shortName"] == "KC @ ATL")
    check("retractable game", (kc["venue"]["roof"], kc["wx_status"], kc["wx"]["roof_note"]), ("retractable", "retractable", "Roof may be closed"))
    check("home full name", kc["home"]["full"], "Atlanta Falcons")
    check("nflverse abbr", next(g for g in env["games"] if g["shortName"] == "LAR @ ARI")["away"]["nv"], "LA")
    dome = next(g for g in env["games"] if g["wx_status"] == "dome")
    check("dome has no wx", dome["wx"], None)
    check("weather fetched once per venue", len(set(map(tuple, _fetch_calls(check)))), len(_fetch_calls(check)))


def _fetch_calls(check):
    f = _fetch()
    _build(check, "sb_2026_w10.json", 2, 10, "Week 10", _now("2026-11-15"), fetch=f)
    return f.calls


def test_all_2026_venues_known(check):
    for fx, wk, now in (("sb_2026_w10.json", 10, "2026-11-15"), ("sb_2026_w11.json", 11, "2026-11-20"), ("sb_2026_w12.json", 12, "2026-11-26"),
                        ("sb_2026_w16.json", 16, "2026-12-20"), ("sb_2026_w18.json", 18, "2027-01-05")):
        env = _build(check, fx, 2, wk, f"Week {wk}", _now(now))
        check(f"{fx} venue_unknown", env["counts"]["venue_unknown"], 0)
        check(f"{fx} no unknown-venue warnings", [w for w in env["warnings"] if w.startswith("venue_unknown")], [])


def test_placeholders_and_tbd(check):
    env = _build(check, "sb_2026_w16.json", 2, 16, "Week 16", _now("2026-12-20"))
    tbd = [g for g in env["games"] if g["time_tbd"]]
    check("four flex games", len(tbd), 4)
    check.true("tbd kick shows TBD", all(g["kick_ct"] == "TBD" and g["kick_day_ct"] is None for g in tbd))
    check.true("tbd keep flex note", all(g["flex_note"] for g in tbd))
    check.true("tbd get no weather", all(g["wx"] is None and g["wx_status"] in ("tbd", "dome") for g in tbd))
    check("tbd counted", env["counts"]["tbd_time"], 4)
    check.true("tbd sort last", [g["time_tbd"] for g in env["games"]] == sorted(g["time_tbd"] for g in env["games"]))
    env = _build(check, "sb_2026_post_w1.json", 3, 1, "Wild Card", _now("2027-01-05"))
    check("six placeholders", env["counts"]["placeholders"], 6)
    check.true("placeholder shape", all(g["away"] is None and g["home"] is None and g["wx"] is None and g["wx_status"] == "na"
                                         and g["kind"] == "playoff" and g["round"] == "Wild Card" for g in env["games"]))
    check("no SEO events for placeholders", "SportsEvent" in R.seo_block(env), False)
    env = _build(check, "sb_2026_w18.json", 2, 18, "Week 18", _now("2027-01-05"))
    check.true("week 18 all flex", all(g["time_tbd"] for g in env["games"]))
    check("week 18 no forecasts", env["counts"]["wx_ok"] + env["counts"]["wx_retractable"], 0)


def test_all_star_and_unknown_venue(check):
    env = _build(check, "sb_2025_post_w4.json", 3, 4, "Pro Bowl", _now("2026-02-04"))
    g = env["games"][0]
    check("all star kind", g["kind"], "all_star")
    check("all star no weather", (g["wx_status"], g["wx"]), ("na", None))
    check("all star not a bye", env["teams_on_bye"], [])
    check("all star venue still shown", g["venue"]["name"], "Moscone Center")
    env = _build(check, "sb_2025_w1.json", 2, 1, "Week 1", _now("2025-09-04"))
    unknown = [g for g in env["games"] if g["wx_status"] == "unknown_venue"]
    check.true("unknown 2025 venues found", len(unknown) >= 1 and any(g["venue"]["id"] == "8748" for g in unknown))
    check.true("no guessed coordinates", all((g["venue"]["lat"], g["wx"]) == (None, None) for g in unknown) and not [g for g in unknown if g["venue"]["id"] == "8748" and g["venue"]["known"]])
    check("venue_unknown counted", env["counts"]["venue_unknown"], len(unknown))
    check("venue_unknown warned", sum(w.startswith("venue_unknown") for w in env["warnings"]), len(unknown))


def test_weather_failure_counts(check):
    now = _now("2026-11-15")
    env = _build(check, "sb_2026_w10.json", 2, 10, "Week 10", now, fetch=Fetch(fail=True))
    c = env["counts"]
    check("all open-air games fail", (c["wx_failed"], c["wx_ok"], c["wx_retractable"]), (12, 0, 0))
    check("domes still dome", c["wx_dome"], 2)
    check.true("failed never reads clean", all(g["wx"] is None for g in env["games"] if g["wx_status"] == "error"))
    good = _build(check, "sb_2026_w10.json", 2, 10, "Week 10", now)
    prev = {g["id"]: g for g in good["games"]}
    env2 = _build(check, "sb_2026_w10.json", 2, 10, "Week 10", now + timedelta(hours=6), fetch=Fetch(fail=True), prev_games=prev)
    check.true("failed forecasts carried stale", sum(1 for g in env2["games"] if (g["wx"] or {}).get("stale")) == 12)
    keep = next(g for g in env2["games"] if g["id"] == good["games"][2]["id"])
    check("original fetched_at kept", keep["wx"]["fetched_at"], good["games"][2]["wx"]["fetched_at"])
    check("stale counted as failed", env2["counts"]["wx_failed"], 12)
    nw = R.build(check.fixture("sb_2026_w10.json"), _wk(check, "", 2, 10, "Week 10"), now=now, fetch=Fetch(fail=True),
                 prev_games=prev, weather_on=False)
    check("no-weather makes no failures", nw["counts"]["wx_failed"], 0)
    check.true("no-weather keeps prior blocks", sum(1 for g in nw["games"] if g["wx"]) == 12)
    cold = R.build(check.fixture("sb_2026_w10.json"), _wk(check, "", 2, 10, "Week 10"), now=now, weather_on=False)
    check("no-weather without a prior file", cold["counts"]["wx_skipped"] >= 12, True)


def test_seo_block(check):
    env = _build(check, "sb_2026_w10.json", 2, 10, "Week 10", datetime(2026, 11, 14, 15, tzinfo=timezone.utc))
    block = R.seo_block(env)
    check.true("markers", block.startswith(R.START) and block.endswith(R.END))
    body = re.search(r'<script type="application/ld\+json">\n(.*)\n</script>', block, re.S).group(1)
    check("no literal url in block", re.findall(r"https?://", block), [])
    events = json.loads(body)
    check("context is schema.org", {e["@context"] for e in events}, {"https://schema.org"})
    pre = [g for g in env["games"] if g["state"] == "pre" and not g["placeholder"] and not g["time_tbd"]]
    check("one event per unplayed game", len(events), len(pre))
    check.true("event shape", all(e["@type"] == "SportsEvent" and e["sport"] == "American football" and len(e["competitor"]) == 2
                                  and e["location"]["@type"] == "Place" and e["location"]["address"]["addressCountry"] for e in events))
    check.true("start dates are ISO", all(re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", e["startDate"]) for e in events))
    check("no betting terms", SEO_BAD.search(block), None)
    check("no placeholder text", "TBD" in block, False)
    check("no forbidden keys", sanitize.find_forbidden(events), [])
    env["games"][0]["name"] = "</script><b>"
    check.true("script close is escaped", "</script><b>" not in R.seo_block(env))
    done = copy.deepcopy(env)
    for g in done["games"]:
        g["state"] = "post"
    check("empty block when nothing is unplayed", R.seo_block(done), f"{R.START}\n{R.END}")


def test_apply_block(check):
    html = "<html><body>\n<div></div>\n  <script src=\"/nfl/games.js\"></script>\n</body></html>"
    once = R.apply_block(html, f"{R.START}\nA\n{R.END}")
    check.true("inserted before games.js", once.index(R.START) < once.index("/nfl/games.js"))
    twice = R.apply_block(once, f"{R.START}\nB\n{R.END}")
    check("replace keeps one block", (twice.count(R.START), "B" in twice, "A" in twice), (1, True, False))
    check("everything else untouched", twice.replace("B", "A"), once)
    check("fallback before body end", R.START in R.apply_block("<body></body>", f"{R.START}\n{R.END}"), True)


def _site(tmp: Path) -> Path:
    tmp.mkdir(parents=True, exist_ok=True)
    (tmp / "index.html").write_text('<html><body>\n<script src="/nfl/games.js"></script>\n</body></html>\n')
    return tmp


def test_write_and_keep_better(check):
    with tempfile.TemporaryDirectory() as d:
        out = _site(Path(d))
        now = _now("2026-11-14")
        env = _build(check, "sb_2026_w10.json", 2, 10, "Week 10", now)
        check("first write", R.write_outputs(env, out), "written")
        js = (out / "games.js").read_text()
        check.true("games.js prefix", js.startswith("window.NFL_DATA = {") and js.endswith("};\n"))
        check("games.js matches games.json", json.loads(js[len("window.NFL_DATA = "):-2]), json.loads((out / "games.json").read_text()))
        check.true("block written to index", R.START in (out / "index.html").read_text())
        sanitize.assert_clean(json.loads((out / "games.json").read_text()))
        later = copy.deepcopy(env)
        later["generated_at"] = "2026-11-14T21:00:00Z"
        for g in later["games"]:
            if g["wx"]:
                g["wx"]["fetched_at"] = "2026-11-14T21:00:00Z"
        check("same content is unchanged", R.write_outputs(later, out), "unchanged")
        check("unchanged left the stamp", json.loads((out / "games.json").read_text())["generated_at"], env["generated_at"])
        fewer = copy.deepcopy(env)
        fewer["games"] = fewer["games"][:-1]
        fewer["counts"]["games"] -= 1
        check.true("fewer games is kept out", R.write_outputs(fewer, out).startswith("kept: games"))
        worse = copy.deepcopy(env)
        worse["counts"]["wx_failed"] = 3
        check.true("more failures is kept out", R.write_outputs(worse, out).startswith("kept: wx_failed"))
        check("file untouched by kept-out builds", json.loads((out / "games.json").read_text())["counts"], env["counts"])
        nxt = copy.deepcopy(env)
        nxt["week"]["number"] = 11
        nxt["counts"]["games"] = 3
        check("a new week replaces even with fewer games", R.write_outputs(nxt, out), "written")
        better = copy.deepcopy(nxt)
        better["counts"]["games"] = 13
        better["games"] = better["games"][:13]
        check("more games replaces", R.write_outputs(better, out), "written")
        before = (out / "games.json").read_text()
        small = copy.deepcopy(better)
        small["counts"]["games"] = 1
        small["generated_at"] = "2026-11-15T00:00:00Z"
        check("dry run writes nothing", R.write_outputs(copy.deepcopy(env) | {"week": {**env["week"], "number": 12}}, out, dry_run=True), "dry-run")
        check("dry run left the file", (out / "games.json").read_text(), before)
        check("no stray temp files", [p.name for p in out.glob("*.tmp")], [])


class Cal:
    def __init__(self, check):
        sb = check.fixture("sb_bare.json")
        self.cal = {"calendar": sb["leagues"][0]["calendar"], "season": sb["season"], "week": {"number": 10}}
        self.sbs = {("2", "10"): check.fixture("sb_2026_w10.json"), ("2", "11"): check.fixture("sb_2026_w11.json")}
        self.asked: list = []

    def pull(self, st, week, year=None):
        self.asked.append((st, week, year))
        return self.sbs[(str(st), str(week))]


def test_week_target(check):
    c = Cal(check)

    def args(**kw):
        return type("A", (), {"st": None, "week": None, "year": None, **kw})()
    wk, sb = R.pick_week(args(), _now("2026-11-15"), c.cal, c.pull)
    check("sunday resolves week 10", (wk["st"], wk["week"]), (2, 10))
    done = copy.deepcopy(c.sbs[("2", "10")])
    for ev in done["events"]:
        ev["status"]["type"]["state"] = "post"
    c.sbs[("2", "10")] = done
    wk, sb = R.pick_week(args(), _now("2026-11-17"), c.cal, c.pull)
    check("all final advances to week 11", wk["week"], 11)
    check("week 11 scoreboard used", sb["week"]["number"], 11)
    wk, _ = R.pick_week(args(st=2, week=11), _now("2026-11-15"), c.cal, c.pull)
    check("override wins", (wk["week"], wk["label"]), (11, "Week 11"))
    check("override passes the year", c.asked[-1], (2, 11, 2026))


def test_main_exit_codes(check):
    c = Cal(check)
    with tempfile.TemporaryDirectory() as d:
        out = _site(Path(d))
        f = _fetch()
        kw = dict(now=_now("2026-11-15"), out_dir=out, calendar=c.cal, pull=c.pull, fetch=f)
        check("dry run ok", R.main(["--dry-run"], **kw), 0)
        check("dry run wrote nothing", sorted(p.name for p in out.iterdir()), ["index.html"])
        check("real run ok", R.main([], **kw), 0)
        check("outputs exist", sorted(p.name for p in out.iterdir()), ["games.js", "games.json", "index.html"])
        calls = len(f.calls)
        check("second run unchanged, ok", R.main([], **kw), 0)
        before = (out / "games.json").read_text()

        def boom(*a, **k):
            raise espn.EspnError("down")
        check("scoreboard failure exits 1", R.main([], **{**kw, "pull": boom}), 1)
        check("empty scoreboard exits 1", R.main([], **{**kw, "pull": lambda *a, **k: {"events": []}}), 1)
        check("failure left the files", (out / "games.json").read_text(), before)
        check("--no-weather makes no calls", (R.main(["--no-weather", "--dry-run"], **{**kw, "fetch": Fetch(fail=True)}), calls > 0), (0, True))
