"""nflverse play-by-play to per-team EPA, success rate and PROE, ranked 1-32."""
from __future__ import annotations

import csv
from collections import defaultdict

from . import teams

COLUMNS = ("game_id", "week", "season_type", "posteam", "defteam", "play_type", "pass", "rush",
           "qb_dropback", "qb_kneel", "qb_spike", "epa", "success", "pass_oe")
REQUIRED = tuple(c for c in COLUMNS if c != "pass_oe")
FILTERS = "REG season; pass or rush plays; EPA present; no kneels or spikes; no garbage-time filter"
SMALL_PLAYS, SMALL_GAMES = 100, 3
EPA_GATE = 0.03
MAX_TEAM_PLAYS = 1500


def project(row: dict) -> dict:
    """Only allowlisted columns ever leave the reader."""
    return {c: row.get(c) for c in COLUMNS}


def _num(v):
    try:
        return float(v) if v not in (None, "") else None
    except ValueError:
        return None


def _flag(v) -> bool:
    return _num(v) == 1.0


def read_plays(lines):
    """Yield (row) for qualifying plays from an iterable of CSV text lines."""
    reader = csv.DictReader(lines)
    missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
    if missing:
        raise ValueError(f"missing columns: {', '.join(missing)}")
    for raw in reader:
        r = project(raw)
        if r["season_type"] != "REG" or not (_flag(r["pass"]) or _flag(r["rush"])):
            continue
        if _flag(r["qb_kneel"]) or _flag(r["qb_spike"]):
            continue
        epa = _num(r["epa"])
        if epa is None or not r["posteam"] or not r["defteam"]:
            continue
        yield {"game": r["game_id"], "week": int(_num(r["week"]) or 0), "pos": r["posteam"], "def": r["defteam"],
               "epa": epa, "sr": _num(r["success"]), "oe": _num(r["pass_oe"])}


def aggregate(plays) -> dict:
    off = defaultdict(lambda: [0, 0.0, 0, 0.0, 0, 0.0])  # n, epa, sr_n, sr, oe_n, oe
    de = defaultdict(lambda: [0, 0.0, 0, 0.0])
    games = defaultdict(set)
    all_games, rows, weeks, epa_sum, sr_n, sr_sum = set(), 0, [], 0.0, 0, 0.0
    for p in plays:
        rows += 1
        epa_sum += p["epa"]
        weeks.append(p["week"])
        all_games.add(p["game"])
        o, d = off[p["pos"]], de[p["def"]]
        o[0] += 1; o[1] += p["epa"]; d[0] += 1; d[1] += p["epa"]
        if p["sr"] is not None:
            o[2] += 1; o[3] += p["sr"]; d[2] += 1; d[3] += p["sr"]
            sr_n += 1; sr_sum += p["sr"]
        if p["oe"] is not None:
            o[4] += 1; o[5] += p["oe"]
        games[p["pos"]].add(p["game"]); games[p["def"]].add(p["game"])
    return {"off": dict(off), "def": dict(de), "games": {t: len(g) for t, g in games.items()},
            "rows": rows, "game_count": len(all_games), "through_week": max(weeks, default=0),
            "league_epa": epa_sum / rows if rows else 0.0, "league_sr": sr_sum / sr_n if sr_n else 0.0}


def rank(values: dict, high_is_best: bool) -> dict:
    """Competition ranking on the rounded value; ties share the lower (better) rank."""
    ordered = sorted(values.values(), reverse=high_is_best)
    return {k: ordered.index(v) + 1 for k, v in values.items()}


def build(agg: dict) -> dict:
    """Per-team block keyed by ESPN abbr. Raises if any of the 32 clubs is missing."""
    out_keys = {}
    for espn in teams.BY_ABBR:
        nv = teams.nflverse_abbr(espn)
        if nv not in agg["off"] or nv not in agg["def"]:
            raise ValueError(f"no data for {espn} ({nv})")
        out_keys[espn] = nv
    raw = {}
    for espn, nv in out_keys.items():
        o, d = agg["off"][nv], agg["def"][nv]
        raw[espn] = {
            "oe": round(o[1] / o[0], 3), "os": round(o[3] / o[2], 3) if o[2] else 0.0,
            "op": round(o[5] / o[4], 1) if o[4] else 0.0, "de": round(d[1] / d[0], 3),
            "ds": round(d[3] / d[2], 3) if d[2] else 0.0, "on": o[0], "dn": d[0]}
    rk = {
        "oe": rank({t: v["oe"] for t, v in raw.items()}, True), "os": rank({t: v["os"] for t, v in raw.items()}, True),
        "op": rank({t: v["op"] for t, v in raw.items()}, True), "de": rank({t: v["de"] for t, v in raw.items()}, False),
        "ds": rank({t: v["ds"] for t, v in raw.items()}, False)}
    res = {}
    for t, v in sorted(raw.items()):
        g = agg["games"].get(out_keys[t], 0)
        res[t] = {
            "off": {"epa": v["oe"], "epa_rank": rk["oe"][t], "sr": v["os"], "sr_rank": rk["os"][t],
                    "proe": v["op"], "proe_rank": rk["op"][t], "plays": v["on"]},
            "def": {"epa": v["de"], "epa_rank": rk["de"][t], "sr": v["ds"], "sr_rank": rk["ds"][t], "plays": v["dn"]},
            "games": g, "small_sample": min(v["on"], v["dn"]) < SMALL_PLAYS or g < SMALL_GAMES}
    return res


def gate(agg: dict, team_block: dict) -> list[str]:
    errs = []
    if len(team_block) != 32:
        errs.append(f"{len(team_block)} teams, want 32")
    if abs(agg["league_epa"]) > EPA_GATE:
        errs.append(f"league EPA/play {agg['league_epa']:+.3f} outside +/-{EPA_GATE}")
    for t, v in team_block.items():
        if not (0 < v["off"]["plays"] <= MAX_TEAM_PLAYS and 0 < v["def"]["plays"] <= MAX_TEAM_PLAYS):
            errs.append(f"{t}: implausible play count {v['off']['plays']}/{v['def']['plays']}")
    return errs
