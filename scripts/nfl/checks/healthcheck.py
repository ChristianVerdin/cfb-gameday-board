"""The production health check's comparison logic (offline)."""
from __future__ import annotations

from scripts.nfl.healthcheck import compare, espn_games, ours


def _ev(gid, state, away, home, period=1):
    return {"id": gid, "competitions": [{"status": {"type": {"state": state}, "period": period},
            "competitors": [{"homeAway": "away", "score": str(away)}, {"homeAway": "home", "score": str(home)}]}]}


def test_compare(check):
    espn = espn_games({"events": [_ev("1", "in", 7, 3, 2), _ev("2", "pre", 0, 0)]})
    live = {"games": [{"id": "1", "state": "in", "period": 2, "away": {"score": 7}, "home": {"score": 3}},
                      {"id": "2", "state": "pre", "period": 0, "away": {"score": None}, "home": {"score": None}}]}
    check("agreeing slate has no mismatches", compare(ours(live), espn), [])
    live["games"][0]["home"]["score"] = 0
    check("score drift is reported", compare(ours(live), espn), ["1 home ours=0 espn=3"])
    live["games"].pop()
    check.true("a missing game is reported", any(i.startswith("ids:") for i in compare(ours(live), espn)))
