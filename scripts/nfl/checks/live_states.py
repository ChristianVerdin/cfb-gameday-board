"""Live states captured on 2026-11-15: end of quarter, two-minute warning, a fresh final, a kickoff-opened drive."""
from __future__ import annotations

from nflcore.gamesheet import norm_summary
from nflcore.normalize import norm_live

WEEK = {"year": 2026, "st": 2, "week": 10, "label": "Week 10"}


def _plays(o):
    return [p for d in o["drives"] for p in d["plays_list"]]


def test_end_period_scoreboard(check):
    g = norm_live(check.fixture("sb_live_end_period_w10.json"), WEEK)["games"][0]
    check("end of quarter stays live", [g["state"], g["status"], g["statusShort"]], ["in", "STATUS_END_PERIOD", "End of Q3"])
    check.true("desk damped at a break", g["desk"] is not None and g["desk"]["score"] < 20, str(g["desk"]))
    check("down carries into the next quarter", [g["situation"]["down"], g["situation"]["stoppage"]], [2, False])


def test_kickoff_opened_drive(check):
    o = norm_summary(check.fixture("summary_live_end_period_min_gb.json"))
    tr = o["tracker"]
    check("drive with no plays yet", tr["plays"], 0)
    check("no phantom drive line from a placeholder start", tr["start_yl"], tr["cur_yl"])


def test_two_minute_warning(check):
    o = norm_summary(check.fixture("summary_live_two_minute_hou_cle.json"))
    last = max(_plays(o), key=lambda p: p["seq"])
    check("two-minute warning is folded", [last["type"], last["kind"]], ["Two-minute warning", "admin"])
    check.true("its down is the real pending down, not a sentinel", last["down"] in (1, 2, 3, 4), str(last["down"]))
    check("clock at the warning", [o["state"], o["periodLabel"], o["clock"]], ["in", "Q4", "2:00"])


def test_fresh_final(check):
    o = norm_summary(check.fixture("summary_final_fresh_hou_cle.json"))
    away, home = o["teams"]["away"]["score"], o["teams"]["home"]["score"]
    check("final decided by score", [o["state"], o["result"]], ["post", "home" if home > away else "away" if away > home else "tie"])
    check("no tracker after the final", o["tracker"], None)
    check("end of game is the last play and folded", [max(_plays(o), key=lambda p: p["seq"])[k] for k in ("type", "kind")],
          ["End of Game", "admin"])
