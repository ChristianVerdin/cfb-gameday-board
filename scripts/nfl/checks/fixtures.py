"""Fixture inventory and hygiene: every fixture parses, is sanitized and shows the edge state it is kept for."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.nfl.make_fixture import DROP_KEYS, MANIFEST, drop_key, find_denied

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "nfl"
MAX_FILE = 300 * 1024
MAX_TOTAL = 4 * 1024 * 1024


def load(name: str):
    return json.loads((FIXTURES / f"{name}.json").read_text())


def walk_keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from walk_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk_keys(v)


def comp(event: dict) -> dict:
    return event["competitions"][0]


def test_inventory(check):
    names = sorted(n for n, _, _ in MANIFEST)
    on_disk = sorted(p.stem for p in FIXTURES.glob("*.json"))
    check("fixtures on disk match the manifest", on_disk, names)
    check.true("README.md exists", (FIXTURES / "README.md").is_file())
    readme = (FIXTURES / "README.md").read_text() if (FIXTURES / "README.md").is_file() else ""
    for n in names:
        check.true(f"README mentions {n}", f"{n}.json" in readme or n in readme)
    sizes = {p.name: p.stat().st_size for p in FIXTURES.glob("*.json")}
    check.true("total size under 4 MB", sum(sizes.values()) < MAX_TOTAL, sum(sizes.values()))
    for n, s in sizes.items():
        check.true(f"{n} under {MAX_FILE // 1024} KB", s < MAX_FILE, s)
    check.true("live core plays, summaries and 5+ triggers present",
               sum(n.startswith("live_trigger_") for n in names) >= 5 and "live_core_plays_late" in names)


def test_sanitized(check):
    for p in sorted(FIXTURES.glob("*.json")):
        data = json.loads(p.read_text())
        check.true(f"{p.name} is minified", "\n" not in p.read_text().rstrip("\n") and ": " not in p.read_text()[:200])
        keys = set(walk_keys(data))
        bad = sorted(k for k in keys if drop_key(k))
        check(f"{p.name} dropped keys", bad, [])
        check.true(f"{p.name} drop list is non-trivial", len(DROP_KEYS) > 20)
        left = find_denied(data)
        check(f"{p.name} URLs or betting words", left[:3], [])


def test_static_shapes(check):
    ot = load("summary_ot_final_2025w2_nyg_dal")
    c = ot["header"]["competitions"][0]
    check("OT final status", c["status"]["type"]["name"], "STATUS_FINAL")
    check.true("OT final went past regulation", any(p.get("period", {}).get("number", 0) >= 5
               for d in ot["drives"]["previous"] for p in d["plays"] if isinstance(p.get("period"), dict)))
    check("OT final scores", sorted(t["score"] for t in c["competitors"]), ["37", "40"])
    tie = load("summary_tie_final_2025w4_gb_dal")
    check("tie final scores equal", len({t["score"] for t in tie["header"]["competitions"][0]["competitors"]}), 1)
    check.true("tie final keeps winprobability", len(tie["winprobability"]) > 100)
    sb = load("summary_superbowl_lx")
    check.true("super bowl is neutral", sb["header"]["competitions"][0].get("neutralSite") is True)
    check.true("pro bowl has no drives", "drives" not in load("summary_probowl_2025"))
    for n in ("summary_ot_final_2025w2_nyg_dal", "summary_superbowl_lx", "summary_probowl_2025"):
        check.true(f"{n} keeps gameInfo venue", bool(load(n)["gameInfo"]["venue"].get("fullName")))
    check.true("live summary keeps gameInfo weather (the board ignores it)", "weather" in load("live_summary_early")["gameInfo"])

def test_scoreboard_shapes(check):
    w1 = load("sb_2025_w1")
    neutral = [e for e in w1["events"] if comp(e).get("neutralSite")]
    check("2025 W1 neutral venue", [comp(e)["venue"]["id"] for e in neutral], ["8748"])
    check.true("2025 W4 Dublin neutral", any(comp(e).get("neutralSite") for e in load("sb_2025_w4")["events"]))
    check("2025 postseason game counts", [len(load(f"sb_2025_post_w{i}")["events"]) for i in range(1, 6)], [6, 4, 2, 1, 1])
    check("2026 W16 flex placeholders", sum(bool(comp(e)["status"].get("isTBDFlex")) for e in load("sb_2026_w16")["events"]), 4)
    check("2026 W18 all flex", sum(bool(comp(e)["status"].get("isTBDFlex")) for e in load("sb_2026_w18")["events"]), 16)
    check.true("2026 wild card is placeholders", all(t["team"]["abbreviation"] == "TBD"
               for e in load("sb_2026_post_w1")["events"] for t in comp(e)["competitors"]))
    w10 = load("sb_2026_w10")
    check("W10 byes", sorted(t["abbreviation"] for t in w10["week"]["teamsOnBye"]), ["CHI", "DEN", "PHI", "TB"])
    check.true("bare scoreboard has calendar", len(load("sb_bare")["leagues"][0]["calendar"]) > 0)
    check.true("teams fixture has 32 teams", len(load("teams")["sports"][0]["leagues"][0]["teams"]) == 32)
    w12 = sorted(e["date"] for e in load("sb_2026_w12")["events"])
    check.true("W12 has the Wednesday game", w12[0].startswith("2026-11-26T01"))


def test_live_shapes(check):
    sb = load("live_sb_w10_mid")
    states = [comp(e)["status"]["type"]["state"] for e in sb["events"]]
    check("live scoreboard in-progress count", states.count("in"), 7)
    downs = [(comp(e).get("situation") or {}).get("down") for e in sb["events"] if comp(e)["status"]["type"]["state"] == "in"]
    check.true("a stoppage sentinel (down -1) is present", -1 in downs)
    for n in ("live_summary_early", "live_summary_late"):
        s = load(n)
        check.true(f"{n} is in progress", s["header"]["competitions"][0]["status"]["type"]["state"] == "in")
        check.true(f"{n} has current drive", bool(s["drives"].get("current")))
    early, late = load("live_core_plays_early"), load("live_core_plays_late")
    check.true("core plays grow between captures", late["count"] > early["count"])
    check.true("core plays carry no urls", not find_denied(early))
    trig = sorted(p.stem for p in FIXTURES.glob("live_trigger_*.json"))
    for n in trig:
        cur = load(n)["drives"]["current"]["plays"]
        check.true(f"{n} has plays", len(cur) > 0)
    stop = [n for n in trig if load(n)["drives"]["current"]["plays"][-1]["type"]["text"] == "Official Timeout"]
    check.true("official timeout trigger present", len(stop) >= 2, stop)
