"""desk suites: whip-around score vectors and pinned reasons."""
from __future__ import annotations

import copy

from nflcore import desk, normalize

WHY = {"Red zone", "Goal to go", "2-minute", "One score, Q4", "OT"}


def _game(period=1, clock_s=900, home=0, away=0, wp=None, status="STATUS_IN_PROGRESS", state="in", sit=None):
    g = {"state": state, "status": status, "period": period, "clock_s": clock_s,
         "home": {"score": home}, "away": {"score": away}, "wp": {"home": wp} if wp is not None else None,
         "situation": None}
    if sit is not None:
        base = {"is_red_zone": False, "goal_to_go": False, "stoppage": False, "possession": "home", "last_play": None}
        base.update(sit)
        g["situation"] = base
    return g


def test_vectors(check):
    s = lambda **kw: desk.score(_game(**kw))  # noqa: E731
    check("Q1 14-14 kickoff", s(period=1, clock_s=900, home=14, away=14), {"score": 20, "why": []})
    r = s(period=4, clock_s=120, home=21, away=21, sit={"is_red_zone": True})
    check.true("Q4 2:00 tied red zone is near 100", r["score"] >= 98, r)
    r = s(period=4, clock_s=120, home=35, away=7)
    check.true("Q4 2:00 up 28 is low", r["score"] < 3, r)
    check("up 28 reasons", r["why"], [])
    r = s(period=5, clock_s=600, home=24, away=24)
    check.true("OT tied", r["score"] >= 90, r)
    check("OT reason", r["why"], ["OT"])
    r = s(period=2, clock_s=0, home=10, away=10, status="STATUS_HALFTIME")
    check("halftime tied is damped", r["score"], 14)
    check.true("halftime tied is low", r["score"] < 20)
    check("Q2 two-minute drill tied", s(period=2, clock_s=100, home=10, away=10)["why"], ["2-minute"])
    check.true("same moment outside halftime scores higher", s(period=2, clock_s=100, home=10, away=10)["score"] > 14)


def test_reasons(check):
    base = dict(period=4, clock_s=240, home=20, away=17)
    check("one score Q4, offence trailing", desk.score(_game(**base, sit={"possession": "away"}))["why"], ["One score, Q4"])
    check("leader has the ball: no late bonus", desk.score(_game(**base, sit={"possession": "home"}))["why"], [])
    check("tied counts for the offence", desk.score(_game(period=4, clock_s=240, home=17, away=17, sit={"possession": "home"}))["why"],
          ["One score, Q4"])
    check("nine points is two scores", desk.score(_game(period=4, clock_s=240, home=26, away=17, sit={"possession": "away"}))["why"], [])
    check("beyond five minutes", desk.score(_game(period=4, clock_s=400, home=20, away=17, sit={"possession": "away"}))["why"], [])
    check("no possession", desk.score(_game(**base, sit={"possession": None}))["why"], [])
    r = desk.score(_game(period=3, clock_s=500, home=14, away=14, sit={"is_red_zone": True}))
    check("red zone", r["why"], ["Red zone"])
    r2 = desk.score(_game(period=3, clock_s=500, home=14, away=14, sit={"is_red_zone": True, "goal_to_go": True}))
    check("goal to go outranks plain red zone", (r2["why"], r2["score"] > r["score"]), (["Goal to go"], True))
    check("stoppage suppresses red zone", desk.score(_game(period=3, clock_s=500, home=14, away=14,
                                                           sit={"is_red_zone": True, "stoppage": True}))["why"], [])
    r = desk.score(_game(period=4, clock_s=90, home=24, away=24, sit={"is_red_zone": True, "goal_to_go": True, "possession": "home"}))
    check("two largest of several, pinned order", r["why"], ["Goal to go", "2-minute"])
    check("never more than two", len(r["why"]) <= 2, True)
    check("all reasons come from the pinned set", set(r["why"]) <= WHY, True)


def test_damping_and_edges(check):
    live = desk.score(_game(period=3, clock_s=0, home=20, away=20))["score"]
    brk = desk.score(_game(period=3, clock_s=0, home=20, away=20, status="STATUS_END_PERIOD"))["score"]
    check.true("end of period below live", brk < live)
    sit = {"last_play": {"type": "End Period"}}
    check("End Period last play counts as a break", desk.score(_game(period=2, clock_s=900, home=7, away=7, sit=sit))["score"],
          desk.score(_game(period=2, clock_s=900, home=7, away=7, status="STATUS_END_PERIOD"))["score"])
    check.true("tied end of regulation heads to OT, not damped",
               desk.score(_game(period=4, clock_s=0, home=20, away=20, status="STATUS_END_PERIOD"))["score"] >= 90)
    check.true("end of Q4 with a leader is damped",
               desk.score(_game(period=4, clock_s=0, home=34, away=20, status="STATUS_END_PERIOD"))["score"] < 20)
    big = desk.score(_game(period=3, clock_s=300, home=45, away=21, wp=0.5))["score"]
    small = desk.score(_game(period=3, clock_s=300, home=44, away=21, wp=0.5))["score"]
    check.true("24-point margin is halved (win probability held equal)", abs(big * 2 - small) <= 1, (big, small))
    check("wp drives closeness when present", desk.score(_game(period=4, clock_s=600, home=24, away=20, wp=0.5))["score"]
          > desk.score(_game(period=4, clock_s=600, home=24, away=20, wp=0.9))["score"], True)
    check("score always 0-100", [0 <= desk.score(_game(period=p, clock_s=c, home=h, away=a))["score"] <= 100
                                 for p in (1, 2, 3, 4, 5, 6) for c in (0, 100, 900) for h, a in ((0, 0), (30, 0), (7, 10))],
          [True] * 54)
    for st in ("pre", "post"):
        check(f"{st} has no desk", desk.score(_game(state=st)), None)
    check("placeholder has no desk", desk.score({"state": "in", "home": None, "away": None}), None)
    check("later in the game scores higher when tied", desk.score(_game(period=3, clock_s=300))["score"]
          > desk.score(_game(period=2, clock_s=300))["score"], True)


def test_live_fixture(check):
    sb = check.fixture("live_sb_w10_mid.json")
    games = normalize.norm_live(sb)["games"]
    live = [g for g in games if g["state"] == "in"]
    check("one desk per live game", [g["desk"] is not None for g in games], [g["state"] == "in" for g in games])
    for g in live:
        d = g["desk"]
        check.true(f"{g['id']} shape", set(d) == {"score", "why"} and isinstance(d["score"], int) and 0 <= d["score"] <= 100, d)
        check.true(f"{g['id']} reasons pinned", set(d["why"]) <= WHY and len(d["why"]) <= 2, d)
    by = {g["id"]: g["desk"]["score"] for g in live}
    check.true("tied-ish Q3 outranks a lopsided one", by["401873055"] > by["401873059"], by)
    g = copy.deepcopy(live[0])
    check("score is deterministic", desk.score(g), desk.score(copy.deepcopy(g)))
