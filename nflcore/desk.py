"""Whip-around desk: one 0-100 "watch now" score per live game, from a scoreboard poll alone.

Descriptive only: closeness x lateness plus a few situational bonuses. No outcome predictions.
Input is a game dict from normalize.norm_event.
"""
from __future__ import annotations

# All weights live here.
FLOOR = 0.20           # base weight of a tied game at kickoff
RED = 6                # red zone bonus; goal to go gets RED_GOAL
RED_GOAL = 9
TWO_MIN = 8            # last two minutes of the half, scaled by closeness
LATE = 8               # Q4, last 5 minutes, one score, offence trailing or tied
OT_BONUS = 15
BREAK_DAMP = 0.35      # halftime / end of period
BLOWOUT_DAMP = 0.5     # period >= 3 and margin >= BLOWOUT
BLOWOUT = 24
MARGIN_SPAN = 21       # closeness fallback when win probability is missing

WHY = ("Red zone", "Goal to go", "2-minute", "One score, Q4", "OT")


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _is_break(game: dict) -> bool:
    if game.get("status") in ("STATUS_HALFTIME", "STATUS_END_PERIOD"):
        return True
    lp = ((game.get("situation") or {}).get("last_play") or {}).get("type") or ""
    return lp.lower() == "end period"


def score(game: dict) -> dict | None:
    """{'score': int 0-100, 'why': [up to two pinned strings]}, or None unless the game is live."""
    if game.get("state") != "in" or not game.get("home") or not game.get("away"):
        return None
    period = int(game.get("period") or 0)
    clock_s = int(game.get("clock_s") or 0)
    margin = game["home"]["score"] - game["away"]["score"]
    ot = period > 4
    secs = 0 if ot else (4 - period) * 900 + clock_s
    lateness = 1.0 if ot else 1 - min(secs, 3600) / 3600
    wp = (game.get("wp") or {}).get("home")
    closeness = 1 - abs(2 * wp - 1) if wp is not None else _clamp(1 - abs(margin) / MARGIN_SPAN)

    sit = game.get("situation") or {}
    live_ball = bool(sit) and not sit.get("stoppage")
    brk = _is_break(game)

    base = 100 * closeness * (FLOOR + (1 - FLOOR) * lateness ** 2)
    red = 0.0
    if live_ball and sit.get("is_red_zone"):
        red = (RED_GOAL if sit.get("goal_to_go") else RED) * (0.5 + 0.5 * closeness)
    two = TWO_MIN * closeness if period in (2, 4) and 0 < clock_s <= 120 and not brk else 0.0
    side = sit.get("possession")
    trailing_or_tied = (side == "home" and margin <= 0) or (side == "away" and margin >= 0)
    late = LATE if period == 4 and secs <= 300 and abs(margin) <= 8 and trailing_or_tied else 0.0
    otb = OT_BONUS if ot else 0.0

    total = base + red + two + late + otb
    if brk and period <= 4 and not (period == 4 and margin == 0):
        total *= BREAK_DAMP
    if period >= 3 and abs(margin) >= BLOWOUT:
        total *= BLOWOUT_DAMP

    parts = [("Goal to go" if sit.get("goal_to_go") else "Red zone", red), ("2-minute", two),
             ("One score, Q4", late), ("OT", otb)]
    why = [label for label, v in sorted((p for p in parts if p[1] > 0), key=lambda p: -p[1])[:2]]
    return {"score": int(round(_clamp(total, 0, 100))), "why": why}
