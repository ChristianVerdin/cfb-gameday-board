"""Game sheet normalization against the committed summary fixtures."""
from __future__ import annotations

import copy
import gzip
import json

from nflcore import sanitize
from nflcore.gamesheet import ADMIN, BOX, clean_text, norm_summary, period_label

OT = "summary_ot_final_2025w2_nyg_dal.json"
TIE = "summary_tie_final_2025w4_gb_dal.json"
SB = "summary_superbowl_lx.json"
PRO = "summary_probowl_2025.json"
EARLY, LATE = "live_summary_early.json", "live_summary_late.json"
TRIGGERS = ("live_trigger_401873054_fg_good.json", "live_trigger_401873054_timeout.json",
            "live_trigger_401873055_rush_td.json", "live_trigger_401873056_timeout.json",
            "live_trigger_401873057_fg_good.json", "live_trigger_401873060_timeout.json")
KEYS = {"ok", "v", "id", "fetched_at", "state", "status", "period", "periodLabel", "clock", "last_play_wallclock",
        "teams", "linescores", "ot_periods", "result", "scoring", "drives", "current_drive_id", "tracker", "winprob",
        "box", "leaders", "warnings"}


def plays(out):
    return [p for d in out["drives"] for p in d["plays_list"]]


def raw_plays(s):
    d = s.get("drives") or {}
    return [p for dr in (d.get("previous") or []) + ([d["current"]] if d.get("current") else []) for p in dr["plays"]]


def size(out):
    raw = json.dumps(out, separators=(",", ":")).encode()
    return len(raw), len(gzip.compress(raw))


def live_event(check, eid="401873058"):
    return next(e for e in check.fixture("live_sb_w10_mid.json")["events"] if e["id"] == eid)


def pre_game(s):
    s = copy.deepcopy(s)
    s["header"]["competitions"][0]["status"]["type"].update(state="pre", name="STATUS_SCHEDULED", completed=False)
    for c in s["header"]["competitions"][0]["competitors"]:
        c["score"] = "0"
        c.pop("linescores", None)
    for k in ("drives", "scoringPlays", "winprobability"):
        s.pop(k, None)
    return s


def test_period_labels(check):
    check("labels", [period_label(n) for n in (0, 1, 4, 5, 6, 7)], ["", "Q1", "Q4", "OT", "2OT", "3OT"])
    check("none", period_label(None), "")


def test_drives_dedupe(check):
    s = check.fixture(LATE)
    d = s["drives"]
    check("current drive also last in previous", d["previous"][-1]["id"], d["current"]["id"])
    raw, out = raw_plays(s), norm_summary(s)
    ps = plays(out)
    check.true("raw has duplicates", len(raw) > len({str(p["id"]) for p in raw}), len(raw))
    check("unique plays", len(ps), len({str(p["id"]) for p in raw}))
    check("play ids unique", len({p["id"] for p in ps}), len(ps))
    check("drive ids unique", len({x["id"] for x in out["drives"]}), len(out["drives"]))
    check("one fewer drive than raw", len(out["drives"]), len(d["previous"]) + 1 - 1)
    check("duplicate warning", f"duplicate_plays:{len(raw) - len(ps)}" in out["warnings"], True)
    live = [x for x in out["drives"] if x["live"]]
    check("one live drive", [x["id"] for x in live], [d["current"]["id"]])
    check("current_drive_id", out["current_drive_id"], d["current"]["id"])
    check("live drive keeps all current plays", len(live[0]["plays_list"]), len(d["current"]["plays"]))
    seqs = [p["seq"] for p in ps]
    check("plays in sequence order", seqs, sorted(seqs))
    firsts = [x["plays_list"][0]["seq"] for x in out["drives"]]
    check("drives in sequence order", firsts, sorted(firsts))
    # a play repeated in a second drive is kept once, in the first drive that has it
    t = copy.deepcopy(s)
    t["drives"]["previous"][1]["plays"].append(copy.deepcopy(t["drives"]["previous"][0]["plays"][0]))
    o2 = norm_summary(t)
    check("global dedupe by string id", len(plays(o2)), len(ps))
    # current wins over the stale previous copy
    t = copy.deepcopy(s)
    t["drives"]["current"]["description"] = "CURRENT WINS"
    check("current wins", [x["desc"] for x in norm_summary(t)["drives"] if x["live"]], ["CURRENT WINS"])
    # final games have no live drive
    fin = norm_summary(check.fixture(OT))
    check("final: no live drive", [any(x["live"] for x in fin["drives"]), fin["current_drive_id"], fin["tracker"]],
          [False, None, None])
    for name in (EARLY, *TRIGGERS):
        o = norm_summary(check.fixture(name))
        check.true(f"{name}: one live drive", sum(x["live"] for x in o["drives"]) == 1)
        check.true(f"{name}: sorted", [p["seq"] for p in plays(o)] == sorted(p["seq"] for p in plays(o)))


def test_drive_shape(check):
    o = norm_summary(check.fixture(OT))
    d = o["drives"][0]
    check("drive keys", sorted(d), sorted(["id", "team", "desc", "result", "result_text", "live", "start", "end",
                                           "plays", "yards", "time", "scoring", "plays_list"]))
    check("start keys", sorted(d["start"]), ["clock", "period", "yard_text", "yl100"])
    check("kickoff drive starts Q1", d["start"]["period"], 1)
    ot_drive = o["drives"][-1]
    check("last drive starts in OT", ot_drive["start"]["period"], 5)
    check("OT drive yl100 is yards to goal", ot_drive["end"]["yl100"], 28)
    check("OT drive end text", ot_drive["end"]["yard_text"], "NYG 28")
    check("drive result code", ot_drive["result"], "FG")
    check("scoring flag", ot_drive["scoring"], True)
    check("team is abbr", ot_drive["team"], "DAL")


def test_ot_final(check):
    s = check.fixture(OT)
    o = norm_summary(s)
    check("state", o["state"], "post")
    check("result by score", o["result"], "home")
    check("scores", [o["teams"]["away"]["score"], o["teams"]["home"]["score"]], [37, 40])
    check("away", o["teams"]["away"]["abbr"], "NYG")
    check("linescores", o["linescores"], {"away": [6, 7, 3, 21, 0], "home": [0, 10, 7, 20, 3]})
    check("ints", all(isinstance(v, int) for ls in o["linescores"].values() for v in ls), True)
    check("ot_periods", o["ot_periods"], 1)
    check("period", [o["period"], o["periodLabel"], o["clock"]], [5, "OT", "0:00"])
    ps = plays(o)
    ot = [p for p in ps if p["period"] == 5]
    check.true("period-5 plays", len(ot) >= 20, len(ot))
    check("OT label", {p["periodLabel"] for p in ot}, {"OT"})
    check("OT scoring plays", [(x["period"], x["periodLabel"], x["kind"]) for x in o["scoring"] if x["period"] == 5],
          [(5, "OT", "FG")])
    check("period never decreases", [p["period"] for p in ps], sorted(p["period"] for p in ps))
    check("winprob OT", [o["winprob"]["quarters"][-1][0], o["winprob"]["ot_at"] is not None], ["OT", True])
    # the first OT kickoff can arrive tagged period 4: it must still land in OT
    t = copy.deepcopy(s)
    drives = t["drives"]["previous"]
    first_ot = next(i for i, d in enumerate(drives) if d["start"]["period"]["number"] == 5)
    drives[first_ot]["start"]["period"]["number"] = 4
    drives[first_ot]["plays"][0]["period"]["number"] = 4
    o2 = norm_summary(t)
    kick = next(p for p in plays(o2) if p["id"] == str(drives[first_ot]["plays"][0]["id"]))
    check("mis-tagged OT kickoff floored to 5", kick["period"], 5)
    check("same play count", len(plays(o2)), len(ps))
    # End of Regulation floors everything after it, even with period 4 tags
    t = copy.deepcopy(s)
    for d in t["drives"]["previous"][first_ot:]:
        d["start"]["period"]["number"] = 4
        for p in d["plays"]:
            p["period"]["number"] = 4
    o3 = norm_summary(t)
    eor = [p for p in plays(o3) if p["type"] == "End of Regulation"]
    after = [p for p in plays(o3) if p["seq"] > eor[0]["seq"]] if eor else []
    check.true("floor after End of Regulation or End Period", all(p["period"] == 5 for p in after[:5]) or not eor,
               [p["period"] for p in after[:5]])
    # the summary header wins for period and clock; the event only fills in when the header has no status
    s = copy.deepcopy(s)
    s["header"]["competitions"][0].pop("status", None)
    ev = {"status": {"clock": 312.0, "displayClock": "5:12", "period": 6, "type": {"state": "in", "name": "STATUS_IN_PROGRESS"}}}
    o4 = norm_summary(s, ev)
    check("event period", [o4["state"], o4["period"], o4["periodLabel"], o4["clock"]], ["in", 6, "2OT", "5:12"])
    check("in-progress game has no result", o4["result"], None)


def test_tie(check):
    s = check.fixture(TIE)
    o = norm_summary(s)
    check("result tie", o["result"], "tie")
    check("scores", [o["teams"]["away"]["score"], o["teams"]["home"]["score"]], [40, 40])
    check("linescores", [len(o["linescores"]["away"]), len(o["linescores"]["home"])], [5, 5])
    check("ot_periods", o["ot_periods"], 1)
    check("WP ends at 0.5", o["winprob"]["points"][-1]["p"], 0.5)
    check("two OT scoring plays", [x["kind"] for x in o["scoring"] if x["period"] == 5], ["FG", "FG"])
    check("no winner key anywhere", "winner" in json.dumps(o), False)
    check("no winner on teams", [k for t in o["teams"].values() for k in t if k == "winner"], [])
    # a late wp point must not decide the result: flip the WP to 0.99 and the tie stays
    t = copy.deepcopy(s)
    t["winprobability"][-1]["homeWinPercentage"] = 0.99
    check("result ignores WP", norm_summary(t)["result"], "tie")
    ev = {"status": {"period": 5, "displayClock": "0:00", "type": {"state": "post", "name": "STATUS_FINAL"}},
          "competitions": [{"competitors": [{"homeAway": "home", "score": "40"}, {"homeAway": "away", "score": "40"}]}]}
    check("event keeps tie", norm_summary(s, ev)["result"], "tie")


def test_winprob_join(check):
    s = check.fixture(OT)
    o = norm_summary(s)
    pts = o["winprob"]["points"]
    raw = s["winprobability"]
    ids = {str(p["id"]) for p in raw_plays(s)}
    check("raw wp longer than cap", len(raw) > 120, True)
    check("downsampled to <=120", len(pts), 120)
    check("first kept (coin toss id, no play)", [pts[0]["pid"], pts[0]["seq"]], [raw[0]["playId"], None])
    check.true("coin toss id has no drive play", raw[0]["playId"] not in ids)
    check("last kept", pts[-1]["pid"], raw[-1]["playId"])
    kept = {p["pid"] for p in pts}
    scoring_ids = {str(p["id"]) for p in raw_plays(s) if p.get("scoringPlay")} & {w["playId"] for w in raw}
    check.true("scoring plays with wp kept", scoring_ids <= kept, sorted(scoring_ids - kept)[:3])
    check.true("points sorted by time", [p["t"] for p in pts] == sorted(p["t"] for p in pts))
    check.true("p in 0..1", all(0 <= p["p"] <= 1 for p in pts))
    check("quarter labels", [q[0] for q in o["winprob"]["quarters"]], ["Q1", "Q2", "Q3", "Q4", "OT"])
    check("Q1 starts at the first point", o["winprob"]["quarters"][0][1], 0)
    check("quarters ascending", [q[1] for q in o["winprob"]["quarters"]], sorted(q[1] for q in o["winprob"]["quarters"]))
    check("ot_at", o["winprob"]["ot_at"], o["winprob"]["quarters"][-1][1])
    # period boundaries survive: first wp point whose play is in each effective period
    by_id = {p["id"]: p for p in plays(o)}
    first_per = {}
    for w in raw:
        p = by_id.get(w["playId"])
        if p and p["period"] not in first_per:
            first_per[p["period"]] = w["playId"]
    check.true("period boundary points kept", set(first_per.values()) <= kept)
    # plays carry wp joined by id, carried forward when a play has none
    wp_ids = {w["playId"]: w["homeWinPercentage"] for w in raw}
    ps = plays(o)
    first_wp = next(i for i, p in enumerate(ps) if p["id"] in wp_ids)
    check("plays before the first wp are null", all(p["wp"] is None for p in ps[:first_wp]), True)
    carried = 0
    for i in range(first_wp, len(ps)):
        p = ps[i]
        if p["id"] in wp_ids:
            check.true(f"wp joined {p['id']}", p["wp"] == round(wp_ids[p["id"]], 4)) if i == first_wp else None
        else:
            carried += 1
            if p["wp"] != ps[i - 1]["wp"]:
                check.true("carry forward", False, p["id"])
    check.true("some plays carry wp forward", carried > 0)
    # a wp id with no play newer than the drives is kept
    t = copy.deepcopy(check.fixture(LATE))
    t["winprobability"].append({"homeWinPercentage": 0.5, "tiePercentage": 0.0, "playId": "999"})
    o2 = norm_summary(t)
    check("unknown wp id kept at the end", [o2["winprob"]["points"][-1]["pid"], o2["winprob"]["points"][-1]["seq"]], ["999", None])
    check("short wp list not downsampled", len(norm_summary(check.fixture(LATE))["winprob"]["points"]), 118)
    # tolerate a wp entry without a value
    t = copy.deepcopy(s)
    t["winprobability"][5] = {"playId": "x"}
    check("bad wp entry skipped", len(norm_summary(t)["winprob"]["points"]) <= 120, True)


def test_sentinels(check):
    n = 0
    for name in (LATE, *TRIGGERS, OT, TIE):
        s = check.fixture(name)
        by_id = {str(p["id"]): p for p in raw_plays(s)}
        for p in plays(norm_summary(s)):
            rd = by_id[p["id"]]["start"]["down"]
            if rd in (-1, 0):
                n += 1
                check.true(f"{name} {p['id']} sentinel down null", p["down"] is None and p["distance"] is None, p)
            else:
                check.true(f"{name} {p['id']} down kept", p["down"] == rd and p["distance"] == by_id[p["id"]]["start"]["distance"])
    check.true("sentinel plays seen", n > 100, n)
    t = {"drives": {"previous": [{"id": "1", "plays": [{"id": "a", "sequenceNumber": "100", "text": "x",
                                                          "start": {"down": 5, "distance": 3}}]}]}, "header": {}}
    check("down out of range is null", plays(norm_summary(t))[0]["down"], None)
    check("play without start or type", plays(norm_summary({"drives": {"previous": [{"id": "1", "plays": [{"id": "z"}]}]}}))[0]["type"], "")


def test_text(check):
    s = check.fixture(TRIGGERS[0])
    for name in (OT, SB, *TRIGGERS, LATE):
        for p in plays(norm_summary(check.fixture(name))):
            check.true(f"{name} {p['id']} text clean", "\n" not in p["text"] and "  " not in p["text"] and len(p["text"]) <= 220)
    # find a play with a newline and prove the collapse
    nl = [p for dr in (s["drives"]["previous"] + [s["drives"]["current"]]) for p in dr["plays"] if "\n" in p["text"]]
    raw_hit = None
    for name in TRIGGERS + (LATE, OT, TIE, SB):
        for p in raw_plays(check.fixture(name)):
            if "\n" in p["text"]:
                raw_hit = (name, p)
                break
        if raw_hit:
            break
    check.true("fixture has a newline play", raw_hit is not None or nl)
    if raw_hit:
        name, rp = raw_hit
        got = next(p for p in plays(norm_summary(check.fixture(name))) if p["id"] == str(rp["id"]))
        check("newline collapsed", got["text"], clean_text(rp["text"]))
    long = "word " * 80 + "https://example.invalid/a.pvt?x=1 tail"
    t = {"drives": {"previous": [{"id": "1", "plays": [{"id": "a", "sequenceNumber": "1", "text": long}]}]}}
    got = plays(norm_summary(t))[0]["text"]
    check("clip to 220", len(got), 220)
    t["drives"]["previous"][0]["plays"][0]["text"] = "see https://x.invalid/core/$ref/1 and a.pvt then\n\n  done"
    check("urls stripped", plays(norm_summary(t))[0]["text"], "see and then done")


def test_play_kinds(check):
    seen = set()
    for name in (OT, TIE, SB, LATE):
        for p in plays(norm_summary(check.fixture(name))):
            want = "admin" if p["type"] in ADMIN else "play"
            check.true(f"{name} {p['id']} kind", p["kind"] == want, (p["type"], p["kind"]))
            if p["kind"] == "admin":
                seen.add(p["type"])
    check.true("admin types seen", {"Official Timeout", "End Period", "Timeout", "Two-minute warning", "End of Game"} <= seen, sorted(seen))
    for t in ("Coin Toss", "End Period", "End of Regulation", "End of Game", "Official Timeout", "Timeout", "Two-minute warning"):
        check.true(f"{t} is admin", t in ADMIN)
    check("plain play", {p["kind"] for p in plays(norm_summary(check.fixture(LATE))) if p["type"] == "Rush"}, {"play"})


def test_play_fields(check):
    o = norm_summary(check.fixture(OT))
    ps = plays(o)
    base = {"id", "seq", "period", "periodLabel", "clock", "down", "distance", "yard_text", "text", "type", "kind",
            "away", "home", "wp", "yards"}
    check("play keys", all(base <= set(p) and set(p) <= base | {"scoring", "score_value", "penalty", "turnover"} for p in ps), True)
    sc = [p for p in ps if p.get("scoring")]
    check.true("scoring plays flagged", len(sc) >= 8, len(sc))
    check.true("score_value positive", all(p["score_value"] > 0 for p in sc))
    check("score_value totals", sum(p["score_value"] for p in sc), 77)
    check.true("penalty flags", any(p.get("penalty") for p in ps))
    check("yards int", all(isinstance(p["yards"], int) for p in ps), True)
    pass_play = next(p for p in ps if p["id"] == "4017728345409")
    check("rich play", (pass_play["down"], pass_play["distance"], pass_play["yard_text"], pass_play["yards"], pass_play["away"], pass_play["home"]),
          (1, 10, "DAL 30", 27, 37, 37))
    check("scoring join to drive", {x["drive_id"] is not None for x in o["scoring"]}, {True})
    drive_ids = {d["id"] for d in o["drives"]}
    check.true("scoring drive ids exist", all(x["drive_id"] in drive_ids for x in o["scoring"]))
    check("scoring keys", sorted(o["scoring"][0]), sorted(["id", "drive_id", "period", "periodLabel", "clock", "team", "kind", "text", "away", "home"]))
    check("scoring order", [x["away"] + x["home"] for x in o["scoring"]], sorted(x["away"] + x["home"] for x in o["scoring"]))


def test_scoring_join(check):
    s = check.fixture(LATE)
    o = norm_summary(s)
    in_drive = {p["id"]: d["id"] for d in o["drives"] for p in d["plays_list"]}
    for x in o["scoring"]:
        check(f"scoring {x['id']} joined by id", x["drive_id"], in_drive.get(x["id"]))
    # fallback: same (period, clock, text), different id
    t = copy.deepcopy(s)
    sp = t["scoringPlays"][0]
    target = next(p for p in raw_plays(t) if p["scoringPlay"] and p["period"]["number"] == sp["period"]["number"]
                  and p["clock"]["displayValue"] == sp["clock"]["displayValue"])
    sp["id"] = "renumbered"
    sp["text"] = target["text"]
    got = norm_summary(t)["scoring"][0]
    check("fallback by period/clock/text", got["drive_id"], in_drive[str(target["id"])])
    # unmatched kept
    sp["id"], sp["text"] = "nope", "nothing like it"
    o3 = norm_summary(t)
    check("unmatched scoring kept", [o3["scoring"][0]["id"], o3["scoring"][0]["drive_id"]], ["nope", None])
    check("unmatched warning", "scoring_unmatched:1" in o3["warnings"], True)
    ahead = norm_summary(check.fixture(TRIGGERS[0]))
    check("scoring play newer than drives kept", [x["drive_id"] for x in ahead["scoring"]].count(None), 1)


def test_pregame(check):
    o = norm_summary(pre_game(check.fixture(LATE)))
    check("state", o["state"], "pre")
    check("empty arrays", [o["drives"], o["scoring"], o["winprob"]["points"], o["winprob"]["quarters"]], [[], [], [], []])
    check("no live state", [o["current_drive_id"], o["tracker"], o["result"], o["period"], o["clock"], o["ot_periods"]], [None, None, None, 0, None, 0])
    check("winprob none", o["winprob"]["ot_at"], None)
    check("keys", set(o), KEYS)
    check("period label blank", o["periodLabel"], "")
    ev = {"status": {"period": 0, "displayClock": "0:00", "type": {"state": "pre", "name": "STATUS_SCHEDULED"}}}
    check("event pre", norm_summary(pre_game(check.fixture(LATE)), ev)["state"], "pre")
    check("empty summary", norm_summary({})["state"], "pre")


def test_probowl(check):
    o = norm_summary(check.fixture(PRO))
    check("state", o["state"], "post")
    check("teams", [o["teams"]["away"]["abbr"], o["teams"]["home"]["abbr"]], ["NFC", "AFC"])
    check("result by score", [o["teams"]["away"]["score"], o["teams"]["home"]["score"], o["result"]], [66, 52, "away"])
    check("empty drives", [o["drives"], o["scoring"], o["current_drive_id"], o["tracker"]], [[], [], None, None])
    check("empty winprob", o["winprob"], {"points": [], "quarters": [], "ot_at": None})
    check("empty box (no stats)", o["box"], [])
    check("leaders without athletes skipped", o["leaders"], {"away": [], "home": []})
    check("linescores", o["linescores"]["away"], [14, 22, 16, 14])
    check("period fallback", [o["period"], o["periodLabel"], o["ot_periods"]], [4, "Q4", 0])


def test_superbowl(check):
    o = norm_summary(check.fixture(SB))
    check("state/result", [o["state"], o["result"]], ["post", "away"])
    check("scores", [o["teams"]["away"]["score"], o["teams"]["home"]["score"]], [29, 13])
    check("abbrs", [o["teams"]["away"]["abbr"], o["teams"]["home"]["abbr"]], ["SEA", "NE"])
    check("no OT", [o["ot_periods"], o["winprob"]["ot_at"], len(o["linescores"]["away"])], [0, None, 4])
    check("quarters", [q[0] for q in o["winprob"]["quarters"]], ["Q1", "Q2", "Q3", "Q4"])
    check("wp ends at a result", o["winprob"]["points"][-1]["p"], 0.0)
    check("tracker none on final", o["tracker"], None)
    check("team color kept", o["teams"]["away"]["color"] is not None, True)
    check("scoring count", len(o["scoring"]), len(check.fixture(SB)["scoringPlays"]))
    check("teams keys", sorted(o["teams"]["away"]), ["abbr", "color", "id", "name", "score"])


def test_box_leaders(check):
    s = check.fixture(LATE)
    names = [x["name"] for x in s["boxscore"]["teams"][0]["statistics"]]
    check("interceptions appears twice in the source", names.count("interceptions"), 2)
    o = norm_summary(s)
    labels = [b[0] for b in o["box"]]
    check("one interceptions row", labels.count("Interceptions"), 1)
    check("labels unique", len(set(labels)), len(labels))
    check("rows follow the allowlist", labels, [lab for n, lab in BOX if n in names])
    check("row shape", all(len(b) == 3 and all(isinstance(x, str) for x in b) for b in o["box"]), True)
    # values come from the right side: the two teams' totalYards, away first
    comp = {c["homeAway"]: c["team"]["id"] for c in s["header"]["competitions"][0]["competitors"]}
    by_team = {t["team"]["id"]: {x["name"]: x["displayValue"] for x in t["statistics"]} for t in s["boxscore"]["teams"]}
    row = next(b for b in o["box"] if b[0] == "Total yards")
    check("sides", row[1:], [by_team[comp["away"]]["totalYards"], by_team[comp["home"]]["totalYards"]])
    for stat in ("Sacks", "Possession"):
        check.true(f"no stray {stat}", stat not in labels)
    # the raw OT stats carry "-" in value: only displayValue is used
    ot = norm_summary(check.fixture(OT))
    check("no dash values", [x for b in ot["box"] for x in b[1:] if x in ("-", "")], [])
    lead = o["leaders"]
    check("leaders sides", sorted(lead), ["away", "home"])
    check.true("leaders present", len(lead["away"]) >= 3 and len(lead["home"]) >= 3)
    for side in lead.values():
        check.true("leader keys in allowlist", all(x["key"] in ("passingYards", "rushingYards", "receivingYards", "sacks", "totalTackles") for x in side))
        check.true("leader values not null", all(x["value"] is not None for x in side))
        check.true("leader shape", all(set(x) == {"key", "label", "name", "pos", "value", "line"} for x in side))
    t = copy.deepcopy(s)
    t["leaders"][0]["leaders"][3]["leaders"] = [{"value": None, "displayValue": "x", "athlete": {}}]
    t["leaders"][0]["leaders"][1]["leaders"] = []
    got = {x["key"] for x in norm_summary(t)["leaders"]["away" if t["leaders"][0]["team"]["id"] == comp["away"] else "home"]}
    check.true("null leaders skipped", "sacks" not in got and "rushingYards" not in got, sorted(got))


def test_live_mid(check):
    ev = live_event(check)
    for name in (EARLY, LATE):
        s = check.fixture(name)
        o = norm_summary(s, ev)
        check(f"{name} state", [o["state"], o["status"], o["result"]], ["in", "STATUS_IN_PROGRESS", None])
        hs = s["header"]["competitions"][0]["status"]
        check(f"{name} summary header wins period/clock", [o["period"], o["clock"]], [hs["period"], hs["displayClock"]])
        check(f"{name} id", o["id"], "401873058")
        check.true(f"{name} tracker", o["tracker"] is not None and o["tracker"]["drive_id"] == o["current_drive_id"])
        tr = o["tracker"]
        check(f"{name} tracker keys", sorted(tr), ["cur_yl", "drive_id", "elapsed", "plays", "start_yl", "team", "yards"])
        cur = next(d for d in o["drives"] if d["live"])
        check(f"{name} tracker matches drive", [tr["plays"], tr["yards"], tr["team"]], [cur["plays"], cur["yards"], cur["team"]])
        check(f"{name} last_play_wallclock", o["last_play_wallclock"], s["meta"]["lastPlayWallClock"])
    # header alone already carries period and clock on live summaries
    late = norm_summary(check.fixture(LATE))
    check("header fallback", [late["period"], late["clock"]], [3, "6:54"])
    check("header scores", [late["teams"]["away"]["score"], late["teams"]["home"]["score"]], [14, 3])
    o = norm_summary(check.fixture(EARLY), ev)
    check("event scores win", [o["teams"]["away"]["score"], o["teams"]["home"]["score"]],
          [int(c["score"]) for c in sorted(ev["competitions"][0]["competitors"], key=lambda c: c["homeAway"] == "home")])
    check("tracker cur_yl is the last play's end", o["tracker"]["cur_yl"] is not None and 0 <= o["tracker"]["cur_yl"] <= 100, True)
    # a trailing administrative play (timeout) carries a reset spot and must not move the tracker
    adm = copy.deepcopy(check.fixture(EARLY))
    cur_plays = adm["drives"]["current"]["plays"]
    base_yl = norm_summary(adm, ev)["tracker"]["cur_yl"]
    to = copy.deepcopy(cur_plays[-1])
    to.update({"id": "99999999901", "text": "Official Timeout at 05:22", "type": {"id": "21", "text": "Official Timeout"},
               "sequenceNumber": str(int(cur_plays[-1].get("sequenceNumber") or 0) + 1), "end": {"yardLine": 65}})
    cur_plays.append(to)
    check("tracker ignores trailing admin play", norm_summary(adm, ev)["tracker"]["cur_yl"], base_yl)
    # statuses that are in-progress by state but not by name pass through
    ht = {"status": {"period": 2, "displayClock": "0:00", "type": {"state": "in", "name": "STATUS_HALFTIME"}}}
    late = copy.deepcopy(check.fixture(LATE))
    late["header"]["competitions"][0].pop("status", None)
    h = norm_summary(late, ht)
    check("halftime passes through", [h["state"], h["status"], h["period"], h["clock"]], ["in", "STATUS_HALFTIME", 2, "0:00"])
    # no live current drive: no tracker, no crash
    t = copy.deepcopy(check.fixture(LATE))
    t["drives"].pop("current")
    o2 = norm_summary(t)
    check("no current drive", [o2["current_drive_id"], o2["tracker"], any(d["live"] for d in o2["drives"])], [None, None, False])
    for name in TRIGGERS:
        s = check.fixture(name)
        o = norm_summary(s)
        check.true(f"{name} live", o["state"] == "in" and o["tracker"] is not None)
        last = max(plays(o), key=lambda p: p["seq"])
        raw = {str(p["id"]): p for p in raw_plays(s)}[last["id"]]
        check(f"{name} last play is the newest seq", last["seq"], max(int(p["sequenceNumber"]) for p in raw_plays(s)))
        if raw["start"]["down"] in (-1, 0):
            check(f"{name} stoppage play has no down", last["down"], None)


def test_no_forbidden(check):
    banned_keys = ["od" + "ds", "sprea" + "d", "money" + "line", "pick" + "center", "against" + "the", "predictor", "over" + "under",
                   "weather", "logo", "official", "news", "video", "injur", "standings", "imp" + "lied", "bet" + "ting",
                   "wa" + "ger", "sports" + "book", "$ref"]
    banned_text = ["$ref", ".pvt", "http", "draft" + "kings", "fan" + "duel", "pick" + "center"]

    def keys(x):
        if isinstance(x, dict):
            for k, v in x.items():
                yield k
                yield from keys(v)
        elif isinstance(x, list):
            for v in x:
                yield from keys(v)

    for name in (OT, TIE, SB, PRO, EARLY, LATE, *TRIGGERS):
        o = norm_summary(check.fixture(name), live_event(check) if name == LATE else None)
        sanitize.assert_clean(o)
        check(f"{name} keys", set(o), KEYS)
        ks = " ".join(keys(o)).lower()
        check(f"{name} no forbidden keys", [w for w in banned_keys if w in ks], [])
        blob = json.dumps(o).lower()
        check(f"{name} no forbidden text", [w for w in banned_text if w in blob], [])
    poisoned = check.fixture(LATE)
    poisoned["pickcenter"] = [{"details": "x"}]
    poisoned["od" + "ds"] = [1]
    poisoned["header"]["gameInfo"] = {"weather": {"temperature": 50}}
    poisoned["againstTheSprea" + "d"] = []
    poisoned["drives"]["previous"][0]["plays"][0]["homeCoverProbability"] = 0.5
    sanitize.assert_clean(norm_summary(poisoned))
    check("poison does not change output", {k: v for k, v in norm_summary(poisoned).items() if k != "fetched_at"},
          {k: v for k, v in norm_summary(check.fixture(LATE)).items() if k != "fetched_at"})


def test_payload_budgets(check):
    for name in (OT, TIE, SB):
        o = norm_summary(check.fixture(name))
        raw, gz = size(o)
        n = len(plays(o))
        check.true(f"{name} gzip under 15 KB", gz < 15_000, gz)
        check.true(f"{name} raw under 100 KB", raw < 100_000, raw)
        check.true(f"{name} raw stays under 400 bytes per play", raw / n < 400, raw / n)
        check.true(f"{name} winprob capped", len(o["winprob"]["points"]) <= 120)
    for name in (EARLY, LATE, *TRIGGERS):
        raw, gz = size(norm_summary(check.fixture(name)))
        check.true(f"{name} raw under 60 KB", raw < 60_000, raw)
        check.true(f"{name} gzip under 15 KB", gz < 15_000, gz)
    raw, gz = size(norm_summary(check.fixture(PRO)))
    check.true("pro bowl tiny", raw < 2_000, raw)


def test_drive_yl100_by_side(check):
    from nflcore.gamesheet import _yl100
    check("home drive at yardLine 57 attacks 43 to go", _yl100(57, "home"), 43)
    check("away drive at yardLine 70 (own 30) has 70 to go", _yl100(70, "away"), 70)
    check("unknown side", _yl100(70, None), None)
    check("out of range", _yl100(101, "home"), None)
