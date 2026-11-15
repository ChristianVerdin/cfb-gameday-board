"""ESPN game summary -> the /api/nfl/game payload. Output is built field by field, never copied from ESPN."""
from __future__ import annotations

import re
from datetime import datetime, timezone

ADMIN = frozenset({"Coin Toss", "End Period", "End of Half", "End of Regulation", "End of Game", "Official Timeout",
                   "Timeout", "Two-minute warning"})
TEXT_MAX = 220
WP_MAX = 120

# (ESPN stat name, label); a name may repeat in ESPN's list ("interceptions"), so the first occurrence wins.
BOX = (
    ("firstDowns", "1st downs"), ("thirdDownEff", "3rd down"), ("fourthDownEff", "4th down"),
    ("totalYards", "Total yards"), ("netPassingYards", "Passing yards"), ("completionAttempts", "Comp/Att"),
    ("rushingYards", "Rushing yards"), ("rushingAttempts", "Rush att"), ("yardsPerPlay", "Yards per play"),
    ("sacksYardsLost", "Sacks-yards lost"), ("redZoneAttempts", "Red zone"), ("totalPenaltiesYards", "Penalties"),
    ("turnovers", "Turnovers"), ("interceptions", "Interceptions"), ("fumblesLost", "Fumbles lost"),
    ("possessionTime", "Time of possession"),
)
LEADERS = ("passingYards", "rushingYards", "receivingYards", "sacks", "totalTackles")

_WS = re.compile(r"\s+")
_URL = re.compile(r"https?://\S+|\S*\.pvt\S*|\$ref\S*")


def period_label(n) -> str:
    if not isinstance(n, int) or n <= 0:
        return ""
    return f"Q{n}" if n <= 4 else "OT" if n == 5 else f"{n - 4}OT"


def clean_text(s, limit: int = TEXT_MAX) -> str:
    s = _WS.sub(" ", _URL.sub("", s or "")).strip()
    return s if len(s) <= limit else s[: limit - 1].rstrip() + "…"


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _clock_s(display) -> int | None:
    m = re.fullmatch(r"(\d+):(\d{2})", str(display or ""))
    return int(m[1]) * 60 + int(m[2]) if m else None


def _yl100(yard_line, side) -> int | None:
    # yardLine is the distance from the home goal; yl100 is yards to the goal the offense attacks
    if not isinstance(yard_line, int) or isinstance(yard_line, bool) or not 0 <= yard_line <= 100 or side is None:
        return None
    return yard_line if side == "away" else 100 - yard_line


def _side(c) -> str:
    return "home" if c.get("homeAway") == "home" else "away"


def _team(c) -> dict:
    t = c.get("team") or {}
    abbr = t.get("abbreviation") or ""
    return {"id": str(t.get("id") or c.get("id") or ""), "abbr": abbr,
            "name": t.get("name") or t.get("nickname") or t.get("shortDisplayName") or abbr,
            "color": t.get("color") or None}


def _competition(summary: dict) -> dict:
    comps = (summary.get("header") or {}).get("competitions") or [{}]
    return comps[0]


def _linescore(c) -> list[int]:
    out = []
    for ls in c.get("linescores") or []:
        v = _int(ls.get("displayValue"))
        if v is None and ls.get("value") is not None:
            v = _int(round(ls["value"]))
        out.append(v or 0)
    return out


def _state(status: dict) -> str:
    st = ((status or {}).get("type") or {}).get("state")
    return st if st in ("pre", "in", "post") else "pre"


def _flatten_drives(summary: dict) -> tuple[list[dict], int, int]:
    """Merge previous + current by drive id (current wins). Returns (drives, raw play count, duplicate drive count)."""
    d = summary.get("drives") or {}
    merged: dict[str, dict] = {}
    raw = dupes = 0
    cur = d.get("current")
    for dr in list(d.get("previous") or []) + ([cur] if cur else []):
        if not isinstance(dr, dict) or dr.get("id") is None:
            continue
        raw += len(dr.get("plays") or [])
        did = str(dr["id"])
        if did in merged:
            dupes += 1
        merged[did] = dr
    return list(merged.values()), raw, dupes


def _play_seq(p) -> int | None:
    return _int(p.get("sequenceNumber"))


def _collect_plays(drives: list[dict]) -> list[tuple[dict, dict, int]]:
    """Unique plays (global dedupe by string id) as (drive, play, seq), in sequence order."""
    seen: set[str] = set()
    out = []
    for di, dr in enumerate(drives):
        last = -1
        for p in dr.get("plays") or []:
            pid = str(p.get("id"))
            if pid in seen:
                continue
            seen.add(pid)
            seq = _play_seq(p)
            seq = last if seq is None else seq
            last = seq
            out.append((dr, p, seq, di))
    out.sort(key=lambda t: (t[2], t[3]))
    return [(dr, p, seq) for dr, p, seq, _ in out]


def _effective_periods(rows) -> list[int]:
    eff = []
    for dr, p, _ in rows:
        start = (((dr.get("start") or {}).get("period") or {}).get("number")) or 0
        eff.append(max(_int((p.get("period") or {}).get("number")) or 0, _int(start) or 0))
    floor = 0
    for i, (_, p, _) in enumerate(rows):
        eff[i] = max(eff[i], floor)
        typ = (p.get("type") or {}).get("text")
        nxt = eff[i + 1] if i + 1 < len(rows) else 0
        if typ == "End of Regulation" or (typ == "End Period" and eff[i] == 4 and nxt >= 5):
            floor = 5
    return eff


def _t_elapsed(period: int, clock) -> int | None:
    cs = _clock_s(clock)
    if period <= 0 or cs is None:
        return None
    if period <= 4:
        return (period - 1) * 900 + max(0, 900 - cs)
    return 3600 + (period - 5) * 600 + max(0, 600 - cs)


def _play_out(dr, p, eff, wp, prev_total) -> dict:
    s = p.get("start") or {}
    down = s.get("down") if isinstance(s.get("down"), int) and 1 <= s["down"] <= 4 else None
    typ = (p.get("type") or {}).get("text") or ""
    away, home = _int(p.get("awayScore")), _int(p.get("homeScore"))
    scoring = bool(p.get("scoringPlay"))
    sv = _int(p.get("scoreValue")) or 0
    if scoring and not sv and None not in (away, home) and prev_total is not None:
        sv = max(0, away + home - prev_total)
    out = {
        "id": str(p.get("id")), "seq": _play_seq(p), "period": eff, "periodLabel": period_label(eff),
        "clock": (p.get("clock") or {}).get("displayValue"),
        "down": down, "distance": s.get("distance") if down is not None else None,
        "yard_text": s.get("possessionText") or None, "text": clean_text(p.get("text")), "type": typ,
        "kind": "admin" if typ in ADMIN else "play", "away": away, "home": home, "wp": wp,
        "yards": _int(p.get("statYardage")) or 0,
    }
    # flags are omitted when false (and score_value when 0) to stay inside the payload budget
    if scoring:
        out["scoring"], out["score_value"] = True, sv
    if p.get("isPenalty"):
        out["penalty"] = True
    if p.get("isTurnover"):
        out["turnover"] = True
    return out


def _point(d, side=None) -> dict:
    return {"yard_text": d.get("text") or None, "yl100": _yl100(d.get("yardLine"), side)}


def _downsample(points: list[dict], keep_pids: set[str]) -> list[dict]:
    if len(points) <= WP_MAX:
        return points
    must = {0, len(points) - 1}
    prev = None
    for i, pt in enumerate(points):
        if pt["pid"] in keep_pids or (pt["_per"] and pt["_per"] != prev):
            must.add(i)
        prev = pt["_per"] or prev
    rest = [i for i in range(len(points)) if i not in must]
    room = max(0, WP_MAX - len(must))
    if room and rest:
        step = len(rest) / room
        must |= {rest[int(k * step)] for k in range(min(room, len(rest)))}
    return [points[i] for i in sorted(must)]


def _winprob(summary: dict, play_info: dict[str, dict], keep_pids: set[str]) -> dict:
    points = []
    t = 0
    for w in summary.get("winprobability") or []:
        p = w.get("homeWinPercentage")
        if not isinstance(p, (int, float)):
            continue
        pid = str(w.get("playId"))
        info = play_info.get(pid)
        if info and info["t"] is not None:
            t = info["t"]
        points.append({"p": round(float(p), 4), "pid": pid, "seq": info["seq"] if info else None, "t": t,
                       "_per": info["period"] if info else None})
    points = _downsample(points, keep_pids)
    quarters, seen = [], set()
    ot_at = None
    for i, pt in enumerate(points):
        per = pt["_per"]
        if per and per not in seen:
            seen.add(per)
            quarters.append([period_label(per), i])
            if per >= 5 and ot_at is None:
                ot_at = i
    if quarters:
        quarters[0][1] = 0
    for pt in points:
        del pt["_per"]
    return {"points": points, "quarters": quarters, "ot_at": ot_at}


def _box(summary: dict, ids: dict[str, str]) -> list[list]:
    stats: dict[str, dict[str, str]] = {"away": {}, "home": {}}
    for t in (summary.get("boxscore") or {}).get("teams") or []:
        side = ids.get(str((t.get("team") or {}).get("id")))
        if not side:
            continue
        for s in t.get("statistics") or []:
            stats[side].setdefault(s.get("name"), s.get("displayValue"))
    return [[label, stats["away"][n], stats["home"][n]] for n, label in BOX if n in stats["away"] and n in stats["home"]]


def _leaders(summary: dict, ids: dict[str, str]) -> dict:
    out = {"away": [], "home": []}
    for t in summary.get("leaders") or []:
        side = ids.get(str((t.get("team") or {}).get("id")))
        if not side:
            continue
        by_name = {c.get("name"): c for c in t.get("leaders") or []}
        for key in LEADERS:
            cat = by_name.get(key)
            top = ((cat or {}).get("leaders") or [None])[0]
            if not top or top.get("value") is None:
                continue
            a = top.get("athlete") or {}
            out[side].append({"key": key, "label": cat.get("displayName") or key,
                              "name": a.get("shortName") or a.get("displayName") or "",
                              "pos": ((a.get("position") or {}).get("abbreviation")) or None,
                              "value": top["value"], "line": top.get("displayValue") or ""})
    return out


def norm_summary(summary: dict, event: dict | None = None, fetched_at: str | None = None) -> dict:
    warnings: list[str] = []
    comp = _competition(summary)
    comps = comp.get("competitors") or []
    sides = {_side(c): c for c in comps}
    away_c, home_c = sides.get("away") or {}, sides.get("home") or {}
    ev_comp = ((event or {}).get("competitions") or [{}])[0]
    ev_scores = {_side(c): _int(c.get("score")) for c in ev_comp.get("competitors") or []}
    ev_status = (event or {}).get("status") or ev_comp.get("status")
    sum_status = comp.get("status") or {}
    status = sum_status if (sum_status.get("type") or {}).get("state") else (ev_status or sum_status)
    state = _state(status)
    ids = {str((c.get("team") or {}).get("id") or c.get("id")): _side(c) for c in comps}

    lines = {"away": _linescore(away_c), "home": _linescore(home_c)}
    if not any(lines.values()) and ev_comp:
        lines = {_side(c): _linescore(c) for c in ev_comp.get("competitors") or []}
        lines.setdefault("away", []), lines.setdefault("home", [])
    n_ls = max(len(lines["away"]), len(lines["home"]))
    scores = {s: _int((sides.get(s) or {}).get("score")) if _int((sides.get(s) or {}).get("score")) is not None else ev_scores.get(s)
              for s in ("away", "home")}
    teams = {s: {**_team(sides.get(s) or {}), "score": scores[s]} for s in ("away", "home")}

    result = None
    if state == "post" and None not in scores.values():
        result = "tie" if scores["away"] == scores["home"] else "home" if scores["home"] > scores["away"] else "away"

    drives, raw_plays, dup_drives = _flatten_drives(summary)
    rows = _collect_plays(drives)
    if raw_plays != len(rows):
        warnings.append(f"duplicate_plays:{raw_plays - len(rows)}")
    eff = _effective_periods(rows)

    wp_by_id = {str(w.get("playId")): w.get("homeWinPercentage") for w in summary.get("winprobability") or []
                if isinstance(w.get("homeWinPercentage"), (int, float))}
    unmatched_wp = [pid for pid in wp_by_id if pid not in {str(p.get("id")) for _, p, _ in rows}]
    if rows and len(unmatched_wp) > 1:
        warnings.append(f"wp_without_play:{len(unmatched_wp)}")

    plays_by_drive: dict[str, list[dict]] = {}
    play_info: dict[str, dict] = {}
    wp = None
    prev_total = None
    for (dr, p, seq), e in zip(rows, eff):
        pid = str(p.get("id"))
        wp = round(wp_by_id[pid], 4) if pid in wp_by_id else wp
        out = _play_out(dr, p, e, wp, prev_total)
        away, home = out["away"], out["home"]
        prev_total = away + home if None not in (away, home) else prev_total
        plays_by_drive.setdefault(str(dr["id"]), []).append(out)
        play_info[pid] = {"id": pid, "seq": seq, "period": e, "t": _t_elapsed(e, out["clock"]), "drive": str(dr["id"]),
                          "clock": out["clock"], "text": out["text"],
                          "end_yl": (p.get("end") or {}).get("yardLine"), "admin": out["kind"] == "admin"}

    cur = (summary.get("drives") or {}).get("current")
    cur_id = str(cur["id"]) if cur and cur.get("id") is not None and state == "in" else None

    abbr_side = {t["abbr"]: s for s, t in teams.items() if t.get("abbr")}
    drives_out = []
    for dr in drives:
        did = str(dr["id"])
        pl = plays_by_drive.get(did, [])
        if not pl and dr.get("plays"):
            continue
        st, en = dr.get("start") or {}, dr.get("end") or {}
        team = dr.get("team") or {}
        dside = abbr_side.get(team.get("abbreviation"))
        nplays = _int(dr.get("offensivePlays"))
        drives_out.append({
            "id": did, "team": team.get("abbreviation") or "", "desc": dr.get("description") or "",
            "result": dr.get("result") or None, "result_text": dr.get("displayResult") or None, "live": did == cur_id,
            "start": {"period": _int((st.get("period") or {}).get("number")),
                      "clock": (st.get("clock") or {}).get("displayValue"), **_point(st, dside)},
            "end": {"period": _int((en.get("period") or {}).get("number")),
                    "clock": (en.get("clock") or {}).get("displayValue"), **_point(en, dside)},
            "plays": nplays if nplays is not None else len(pl), "yards": _int(dr.get("yards")) or 0,
            "time": (dr.get("timeElapsed") or {}).get("displayValue"), "scoring": bool(dr.get("isScore")),
            "plays_list": pl, "_seq": pl[0]["seq"] if pl and pl[0]["seq"] is not None else 1 << 60,
        })
    drives_out.sort(key=lambda d: d["_seq"])
    for d in drives_out:
        del d["_seq"]

    by_key = {(i["period"], i["clock"], i["text"]): pid for pid, i in play_info.items()}
    scoring_out, keep = [], set()
    n_unmatched = 0
    for s in summary.get("scoringPlays") or []:
        sid = str(s.get("id"))
        text = clean_text(s.get("text"))
        sper = _int((s.get("period") or {}).get("number")) or 0
        sclock = (s.get("clock") or {}).get("displayValue")
        info = play_info.get(sid)
        if info is None:
            mid = by_key.get((sper, sclock, text))
            info = play_info.get(mid) if mid else None
            if info is None:
                n_unmatched += 1
        if info:
            keep.add(info["id"])
        per = info["period"] if info else sper
        st = s.get("scoringType") or {}
        scoring_out.append({
            "id": sid, "drive_id": info["drive"] if info else None, "period": per, "periodLabel": period_label(per),
            "clock": sclock, "team": (s.get("team") or {}).get("abbreviation") or "",
            "kind": st.get("abbreviation") or st.get("name") or "", "text": text,
            "away": _int(s.get("awayScore")), "home": _int(s.get("homeScore")),
        })
    if n_unmatched:
        warnings.append(f"scoring_unmatched:{n_unmatched}")
    for _, p, _ in rows:
        if p.get("scoringPlay"):
            keep.add(str(p.get("id")))

    # period / clock: the summary header (fresher than the cached gate board) wins; the event is the fallback
    period = _int(status.get("period")) or (max(4, n_ls) if state == "post" else 0)
    clock = status.get("displayClock") or ("0:00" if state == "post" else None)
    if state == "post" and eff:
        period = max(period, eff[-1])
    if state == "pre":
        period, clock = 0, None
    tracker = None
    if cur_id and cur:
        cur_plays = [play_info[p["id"]] for p in plays_by_drive.get(cur_id, [])]
        drive_end = _int((cur.get("end") or {}).get("yardLine"))
        newest = max((i for i in cur_plays if not i["admin"]), key=lambda i: i["seq"], default=None)
        # A finished drive sits at ESPN's drive end spot: a made field goal's own end spot reads 100
        # (it would draw the ball on the goal line) and a punt's is the receiving team's spot.
        end_yl = drive_end if cur.get("result") and drive_end is not None else (newest["end_yl"] if newest else None)
        if not isinstance(end_yl, int):
            end_yl = drive_end
        d_out = next((d for d in drives_out if d["id"] == cur_id), None)
        tracker = {"drive_id": cur_id, "team": ((cur.get("team") or {}).get("abbreviation")) or "",
                   "start_yl": (cur.get("start") or {}).get("yardLine"), "cur_yl": end_yl if isinstance(end_yl, int) else None,
                   "plays": d_out["plays"] if d_out else 0, "yards": _int(cur.get("yards")) or 0,
                   "elapsed": (cur.get("timeElapsed") or {}).get("displayValue")}

    last_wall = (summary.get("meta") or {}).get("lastPlayWallClock")
    if not last_wall:
        walls = [p.get("wallclock") for _, p, _ in rows if p.get("wallclock")]
        last_wall = max(walls) if walls else None

    return {
        "ok": True, "v": 1, "id": str((summary.get("header") or {}).get("id") or (event or {}).get("id") or ""),
        "fetched_at": fetched_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "state": state, "status": (status.get("type") or {}).get("name"), "period": period,
        "periodLabel": period_label(period), "clock": clock, "last_play_wallclock": last_wall,
        "teams": teams, "linescores": lines, "ot_periods": max(0, n_ls - 4), "result": result,
        "scoring": scoring_out, "drives": drives_out, "current_drive_id": cur_id, "tracker": tracker,
        "winprob": _winprob(summary, play_info, keep), "box": _box(summary, ids), "leaders": _leaders(summary, ids),
        "warnings": warnings,
    }
