"""ESPN scoreboard -> /api/nfl/live game objects. Pure functions; output is built field by field."""
from __future__ import annotations

import re

from . import desk, venues

CLIP = 160
NON_SCRIMMAGE = ("kickoff", "timeout", "end period", "two-minute", "two minute", "end of", "coin toss")


def collapse(text, limit: int | None = None) -> str:
    s = re.sub(r"\s+", " ", str(text or "")).strip()
    return s[:limit].rstrip() if limit else s


def period_label(n) -> str:
    n = int(n or 0)
    if n <= 0:
        return ""
    if n <= 4:
        return f"Q{n}"
    return "OT" if n == 5 else f"{n - 4}OT"


def parse_record(summary) -> dict | None:
    """'1-2-1' -> {w:1, l:2, t:1, text}; two-part records get t=0; anything else None."""
    m = re.fullmatch(r"\s*(\d+)-(\d+)(?:-(\d+))?\s*", str(summary or ""))
    if not m:
        return None
    return {"w": int(m[1]), "l": int(m[2]), "t": int(m[3] or 0), "text": f"{m[1]}-{m[2]}" + (f"-{m[3]}" if m[3] else "")}


def _int(v, default=None):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _record(comp: dict) -> dict | None:
    recs = comp.get("records") or []
    pick = next((r for r in recs if r.get("type") == "total" or r.get("name") == "overall"), recs[0] if recs else None)
    return parse_record(pick.get("summary")) if pick else None


def _linescores(comp: dict, state: str) -> list:
    out = []
    for ls in comp.get("linescores") or []:
        v = _int(ls.get("value"), _int(ls.get("displayValue")))
        out.append(v)
    if state != "pre":
        out += [None] * (4 - len(out))   # quarters not played yet
    return out


def _is_placeholder(comps: list) -> bool:
    if len(comps) != 2:
        return True
    for c in comps:
        t = c.get("team") or {}
        tid = str(t.get("id") if t.get("id") is not None else c.get("id"))
        if tid.startswith("-") or t.get("abbreviation") in (None, "", "TBD"):
            return True
    return False


def _side(comp: dict, timeouts) -> dict:
    t = comp.get("team") or {}
    return {
        "id": str(t.get("id") or comp.get("id")), "abbr": t.get("abbreviation"),
        "name": t.get("name") or t.get("shortDisplayName"),
        "color": t.get("color"), "alt": t.get("alternateColor"),
        "score": _int(comp.get("score"), 0), "record": _record(comp), "timeouts": timeouts,
        "linescores": [],
    }


def _stoppage_play(last_type: str) -> bool:
    low = (last_type or "").lower()
    return any(k in low for k in NON_SCRIMMAGE)


def _situation(sit: dict, home: dict, away: dict) -> dict:
    lp = sit.get("lastPlay") or {}
    last_type = (lp.get("type") or {}).get("text") or ""
    down, dist = _int(sit.get("down")), _int(sit.get("distance"))
    stoppage = down is None or down <= 0 or (dist == 0 and _stoppage_play(last_type))
    yard = _int(sit.get("yardLine"))
    pos = str(sit.get("possession")) if sit.get("possession") is not None else None
    side = "home" if pos == home["id"] else "away" if pos == away["id"] else None
    # ESPN's yardLine is the distance from the home goal line; yl100 is yards to the goal being attacked
    yl100 = None if stoppage or not yard or side is None else max(0, min(100, yard if side == "away" else 100 - yard))
    return {
        "text": None if stoppage else (sit.get("shortDownDistanceText") or None),
        "down": None if stoppage else down,
        "distance": None if stoppage else dist,
        "stoppage": stoppage,
        "possession": side,
        "possession_abbr": {"home": home, "away": away}[side]["abbr"] if side else None,
        "yard_text": None if stoppage else (sit.get("possessionText") or None),
        "yl100": yl100,
        "is_red_zone": bool(sit.get("isRedZone")) and not stoppage,
        "goal_to_go": bool(not stoppage and yl100 and dist and dist >= yl100),
        "last_play": {"id": str(lp["id"]), "text": collapse(lp.get("text"), CLIP), "type": last_type or None}
        if lp.get("id") is not None else None,
    }


def _wp(sit: dict) -> dict | None:
    p = (sit.get("lastPlay") or {}).get("probability") or {}
    h, a = p.get("homeWinPercentage"), p.get("awayWinPercentage")
    if not isinstance(h, (int, float)) or isinstance(h, bool) or not 0 <= h <= 1 or (h == 0 and not a):
        return None
    return {"home": round(float(h), 3)}


def _status_short(state: str, name: str, period: int, clock: str, clock_s: int, ot_label: str,
                  desc: str, tbd: bool, last_type: str) -> str:
    if state == "pre":
        return "TBD" if tbd else (desc or "Scheduled")
    if state == "post":
        return "Final" + (f"/{ot_label}" if ot_label else "") if "FINAL" in name else desc
    if name == "STATUS_HALFTIME":
        return "Halftime"
    if name == "STATUS_END_PERIOD" or (name == "STATUS_IN_PROGRESS" and last_type.lower() == "end period" and 2 <= period <= 4 and clock_s >= 900):
        p = period if name == "STATUS_END_PERIOD" else period - 1
        return f"End of {period_label(p)}"
    if name != "STATUS_IN_PROGRESS":
        return desc or name
    return f"{period_label(period)} {clock}".strip()


def norm_event(ev: dict) -> dict:
    comp = (ev.get("competitions") or [{}])[0]
    status = comp.get("status") or ev.get("status") or {}
    stype = status.get("type") or {}
    name = stype.get("name") or ""
    state = stype.get("state") or ("post" if stype.get("completed") else "pre")
    period = _int(status.get("period"), 0)
    clock_s = _int(status.get("clock"), 0)
    comps = comp.get("competitors") or []
    placeholder = _is_placeholder(comps)
    tbd = comp.get("timeValid") is False
    notes = comp.get("notes") or ev.get("notes") or []

    home = away = None
    sit_raw = comp.get("situation") if state == "in" else None
    if not placeholder:
        by = {c.get("homeAway"): c for c in comps}
        if "home" not in by or "away" not in by:
            by = {"home": comps[0], "away": comps[1]}
        s = sit_raw or {}
        home = _side(by["home"], _int(s.get("homeTimeouts")))
        away = _side(by["away"], _int(s.get("awayTimeouts")))
        home["linescores"] = _linescores(by["home"], state)
        away["linescores"] = _linescores(by["away"], state)

    nls = max((len(s["linescores"]) for s in (home, away) if s), default=0)
    if nls > 4:
        period = max(period, nls)   # OT kickoffs can lag the status period; the linescores floor it
    ot = period > 4
    ot_label = period_label(max(period, nls)) if ot else ""
    completed = bool(stype.get("completed"))
    result = None
    if completed and home and away:
        result = "home" if home["score"] > away["score"] else "away" if away["score"] > home["score"] else "tie"

    situation = _situation(sit_raw, home, away) if sit_raw and home and away else None
    last_type = ((situation or {}).get("last_play") or {}).get("type") or ""
    ven = comp.get("venue") or {}
    broadcasts = []
    for b in comp.get("broadcasts") or []:
        for n in b.get("names") or []:
            if n and n not in broadcasts:
                broadcasts.append(n)
    clock = status.get("displayClock") or ""
    headline = collapse((notes[0] or {}).get("headline")) if notes else ""

    game = {
        "id": str(ev.get("id") or comp.get("id")),
        "state": state,
        "status": name,
        "statusDetail": stype.get("description") or "",
        "statusShort": _status_short(state, name, period, clock, clock_s, ot_label, stype.get("description") or "", tbd, last_type),
        "period": period,
        "periodLabel": period_label(period),
        "clock": clock,
        "clock_s": clock_s,
        "completed": completed,
        "ot": ot,
        "result": result,
        "date": comp.get("date") or ev.get("date"),
        "time_tbd": tbd,
        "flex_note": re.sub(r"^NFL\s+", "", headline) or None if tbd else None,
        "neutral": comp.get("neutralSite") is True,
        "placeholder": placeholder,
        "venue_name": venues.display_name(ven.get("id"), ven.get("fullName") or "") or None if ven else None,
        "broadcasts": broadcasts,
        "away": away,
        "home": home,
        "situation": situation,
        "wp": _wp(sit_raw) if situation else None,
        "desk": None,
    }
    game["desk"] = desk.score(game)
    return game


def norm_live(scoreboard: dict, week_info: dict | None = None) -> dict:
    """{season, week, teams_on_bye, warnings, games} for one scoreboard. week_info is slate.resolve_week's dict."""
    warnings: list[str] = []
    wi = week_info or {}
    sb_season, sb_week = scoreboard.get("season") or {}, scoreboard.get("week") or {}
    season = {"year": wi.get("year") or sb_season.get("year"), "type": wi.get("st") or sb_season.get("type")}
    number = wi.get("week") or sb_week.get("number")
    if week_info and sb_week.get("number") not in (None, number):
        warnings.append(f"week_mismatch: calendar {number}, espn {sb_week.get('number')}")
    games = []
    for ev in scoreboard.get("events") or []:
        try:
            games.append(norm_event(ev))
        except (KeyError, TypeError, ValueError, IndexError, AttributeError):
            warnings.append(f"event_skipped: {ev.get('id') if isinstance(ev, dict) else '?'}")
    games.sort(key=lambda g: (g["date"] or "", g["id"]))
    return {
        "season": season,
        "week": {"number": number, "label": wi.get("label") or (f"Week {number}" if number else None)},
        "teams_on_bye": [t.get("abbreviation") for t in sb_week.get("teamsOnBye") or [] if t.get("abbreviation")],
        "warnings": warnings,
        "games": games,
    }
