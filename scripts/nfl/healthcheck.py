#!/usr/bin/env python3
"""Production health check for the pro football board (stdlib only).

Compares https://cfbgameday.app/api/nfl/live with ESPN's scoreboard for the same
week, game by game, and checks the snapshot, metrics, game sheet and headers.
Prints one JSON line (append it to a log for a game-day record) and exits 1 on a
hard failure.

    healthcheck.py [--base https://cfbgameday.app] [--log FILE]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

ESPN = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?seasontype={st}&week={week}"
UA = {"User-Agent": "pfb-healthcheck", "Cache-Control": "no-cache"}


def get(url: str, timeout: float = 15) -> tuple[int, dict, bytes]:
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read()
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read()


def espn_games(sb: dict) -> dict[str, dict]:
    out = {}
    for ev in sb.get("events") or []:
        c = (ev.get("competitions") or [{}])[0]
        st = c.get("status") or ev.get("status") or {}
        sides = {t.get("homeAway"): t for t in c.get("competitors") or []}
        out[str(ev.get("id"))] = {
            "state": (st.get("type") or {}).get("state"),
            "period": st.get("period"),
            "away": int(float((sides.get("away") or {}).get("score") or 0)),
            "home": int(float((sides.get("home") or {}).get("score") or 0)),
        }
    return out


def ours(live: dict) -> dict[str, dict]:
    out = {}
    for g in live.get("games") or []:
        out[str(g.get("id"))] = {
            "state": g.get("state"),
            "period": g.get("period"),
            "away": int((g.get("away") or {}).get("score") or 0),
            "home": int((g.get("home") or {}).get("score") or 0),
        }
    return out


def compare(mine: dict[str, dict], theirs: dict[str, dict]) -> list[str]:
    """Mismatches as short strings; an empty list means the board agrees with ESPN."""
    issues = []
    if set(mine) != set(theirs):
        issues.append(f"ids: missing {sorted(set(theirs) - set(mine))} extra {sorted(set(mine) - set(theirs))}")
    for gid in sorted(set(mine) & set(theirs)):
        a, b = mine[gid], theirs[gid]
        for k in ("state", "away", "home"):
            if a[k] != b[k] and not (k == "state" and b[k] == "pre" and a[k] is None):
                issues.append(f"{gid} {k} ours={a[k]} espn={b[k]}")
    return issues


def run(base: str) -> dict:
    now = datetime.now(timezone.utc)
    rec: dict = {"at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "ok": True, "fail": [], "warn": []}

    def fail(msg):
        rec["ok"] = False
        rec["fail"].append(msg)

    code, h, body = get(f"{base}/api/nfl/live")
    if code != 200:
        fail(f"/api/nfl/live {code}")
        return rec
    live = json.loads(body)
    st, week = (live.get("season") or {}).get("type") or 2, (live.get("week") or {}).get("number")
    rec.update(week=(live.get("week") or {}).get("label"), games=live.get("count"),
               live=sum(g.get("state") == "in" for g in live.get("games") or []), stale=live.get("stale"))
    if live.get("stale"):
        rec["warn"].append("live payload served stale")
    _, _, sb = get(ESPN.format(st=st, week=week))
    issues = compare(ours(live), espn_games(json.loads(sb)))
    if issues:  # one retry: the CDN (15 s) and ESPN (1-10 s) can be a poll apart
        time.sleep(20)
        _, _, body2 = get(f"{base}/api/nfl/live")
        _, _, sb2 = get(ESPN.format(st=st, week=week))
        issues = compare(ours(json.loads(body2)), espn_games(json.loads(sb2)))
    rec["mismatches"] = issues
    if issues:
        fail(f"{len(issues)} mismatches vs ESPN")

    code, _, snap = get(f"{base}/nfl/games.json")
    if code == 200:
        s = json.loads(snap)
        gen = datetime.strptime(s["generated_at"][:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        rec["snapshot_age_h"] = round((now - gen).total_seconds() / 3600, 1)
        rec["snapshot_week"] = (s.get("week") or {}).get("label")
        if rec["snapshot_week"] != rec["week"]:
            rec["warn"].append(f"snapshot {rec['snapshot_week']} vs live {rec['week']}")
        if (s.get("counts") or {}).get("wx_failed"):
            rec["warn"].append(f"wx_failed={s['counts']['wx_failed']}")
    else:
        fail(f"/nfl/games.json {code}")

    code, _, met = get(f"{base}/nfl/metrics.json")
    if code == 200:
        rec["metrics_through_week"] = json.loads(met).get("through_week")
    else:
        rec["warn"].append(f"/nfl/metrics.json {code}")

    gid = next((g["id"] for g in live.get("games") or [] if g.get("state") == "in"), None) or \
        next((g["id"] for g in live.get("games") or [] if g.get("state") == "post"), None)
    if gid:
        code, _, sheet = get(f"{base}/api/nfl/game?id={gid}")
        plays = sum(len(d.get("plays_list") or []) for d in (json.loads(sheet).get("drives") or [])) if code == 200 else 0
        rec["sheet"] = {"id": gid, "code": code, "plays": plays}
        if code != 200 or not plays:
            fail(f"/api/nfl/game?id={gid} code={code} plays={plays}")

    code, h, _ = get(f"{base}/nfl/")
    if code != 200 or "noindex" not in h.get("x-robots-tag", ""):
        fail(f"/nfl/ code={code} x-robots={h.get('x-robots-tag')}")
    code, h, _ = get(f"{base}/")
    if code != 200 or "x-robots-tag" in h:
        fail(f"CFB / code={code} x-robots={h.get('x-robots-tag')}")
    return rec


def main() -> int:
    p = argparse.ArgumentParser(description="Pro football board production health check.")
    p.add_argument("--base", default="https://cfbgameday.app")
    p.add_argument("--log")
    a = p.parse_args()
    try:
        rec = run(a.base.rstrip("/"))
    except Exception as e:  # noqa: BLE001 - a crash is a failed check, recorded like any other
        rec = {"at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "ok": False, "fail": [f"crash: {e}"]}
    line = json.dumps(rec, separators=(",", ":"))
    print(line)
    if a.log:
        with open(a.log, "a") as f:
            f.write(line + "\n")
    return 0 if rec["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
