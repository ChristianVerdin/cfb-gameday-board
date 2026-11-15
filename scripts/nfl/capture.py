#!/usr/bin/env python3
"""Capture raw ESPN NFL payloads for test fixtures (stdlib only).

Raw captures carry third-party link and market data, so they are never committed:
write them outside the repo (--out is required) and turn them into sanitized
fixtures with make_fixture.py.

Live mode polls one week's scoreboard every --interval seconds, follows one
game's summary (and core plays, for lag measurement) every --follow-interval
seconds, and saves an extra summary whenever a game first shows a state we have
no fixture for yet (status change, overtime, halftime, two-minute warning,
quarter boundaries, situation missing while live, stoppage sentinels).

    capture.py live --out DIR --st 2 --week 10 [--follow ID] [--until 2026-11-16T05:30Z]
    capture.py static --out DIR            # historical edge-case set, one GET each
"""

import argparse
import gzip
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

HOSTS = ("https://site.web.api.espn.com", "https://site.api.espn.com")
SITE = "/apis/site/v2/sports/football/nfl"
CORE = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15"
MAX_TRIGGERS = 120

STATIC = {
    "ot_final_2025_w2_nyg_dal": f"{SITE}/summary?event=401772834",
    "tie_final_2025_w4_gb_dal": f"{SITE}/summary?event=401772921",
    "sb_2025_w2_scoreboard": f"{SITE}/scoreboard?dates=2025&seasontype=2&week=2",
    "sb_2025_w4_scoreboard": f"{SITE}/scoreboard?dates=2025&seasontype=2&week=4",
    "sb_2025_w1_scoreboard": f"{SITE}/scoreboard?dates=2025&seasontype=2&week=1",
    "sb_2025_post_w1": f"{SITE}/scoreboard?dates=2025&seasontype=3&week=1",
    "sb_2025_post_w2": f"{SITE}/scoreboard?dates=2025&seasontype=3&week=2",
    "sb_2025_post_w3": f"{SITE}/scoreboard?dates=2025&seasontype=3&week=3",
    "sb_2025_post_w4": f"{SITE}/scoreboard?dates=2025&seasontype=3&week=4",
    "sb_2025_post_w5": f"{SITE}/scoreboard?dates=2025&seasontype=3&week=5",
    "probowl_2025_summary": f"{SITE}/summary?event=401831718",
    "superbowl_lx_summary": f"{SITE}/summary?event=401772988",
    "sb_2026_w10": f"{SITE}/scoreboard?seasontype=2&week=10",
    "sb_2026_w11": f"{SITE}/scoreboard?seasontype=2&week=11",
    "sb_2026_w12": f"{SITE}/scoreboard?seasontype=2&week=12",
    "sb_2026_w16": f"{SITE}/scoreboard?seasontype=2&week=16",
    "sb_2026_w18": f"{SITE}/scoreboard?seasontype=2&week=18",
    "sb_2026_post_w1": f"{SITE}/scoreboard?dates=2026&seasontype=3&week=1",
    "sb_bare": f"{SITE}/scoreboard",
    "teams": f"{SITE}/teams",
}


def now_utc():
    return datetime.now(timezone.utc)


def stamp():
    return now_utc().strftime("%Y%m%dT%H%M%SZ")


def get(path_or_url, timeout=12):
    """Return (bytes, host_used). Tries both site hosts for relative paths."""
    urls = [path_or_url] if path_or_url.startswith("http") else [h + path_or_url for h in HOSTS]
    last = None
    for url in urls:
        for attempt in (1, 2):
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json", "Accept-Encoding": "gzip"})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    body = r.read()
                if body[:2] == b"\x1f\x8b":
                    body = gzip.decompress(body)
                return body, url
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last = e
                if isinstance(e, urllib.error.HTTPError) and e.code not in (403, 429) and e.code < 500:
                    break
                time.sleep(2 * attempt)
    raise RuntimeError(f"fetch failed: {path_or_url}: {last}")


def save(out, sub, name, body):
    d = os.path.join(out, sub)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, name + ".json.gz")
    with gzip.open(path, "wb") as f:
        f.write(body)
    return path


def log(out, msg):
    line = f"{now_utc().strftime('%H:%M:%SZ')} {msg}"
    print(line, flush=True)
    with open(os.path.join(out, "capture.log"), "a") as f:
        f.write(line + "\n")


def comp(ev):
    return (ev.get("competitions") or [{}])[0]


def game_tuple(ev):
    c = comp(ev)
    st = c.get("status") or ev.get("status") or {}
    sit = c.get("situation")
    return {
        "name": (st.get("type") or {}).get("name"),
        "state": (st.get("type") or {}).get("state"),
        "period": st.get("period"),
        "clock": st.get("displayClock"),
        "has_sit": sit is not None,
        "down": (sit or {}).get("down"),
        "last": ((sit or {}).get("lastPlay") or {}).get("id"),
        "last_type": (((sit or {}).get("lastPlay") or {}).get("type") or {}).get("text"),
    }


def triggers(prev, cur):
    """Reasons worth a summary capture, each fired once per game per run."""
    out = []
    if prev and prev["name"] != cur["name"]:
        out.append(f"status-{cur['name']}")
    if (cur["period"] or 0) > 4 and cur["state"] == "in":
        out.append(f"ot-p{cur['period']}")
    if cur["state"] == "in" and not cur["has_sit"]:
        out.append(f"nosit-{cur['name']}")
    if cur["state"] == "in" and cur["down"] is not None and cur["down"] <= 0:
        out.append(f"down{cur['down']}-{(cur['last_type'] or 'x').replace(' ', '')}")
    if cur["state"] == "in" and cur["clock"] in ("15:00", "2:00", "0:00"):
        out.append(f"clock-p{cur['period']}-{cur['clock'].replace(':', '')}")
    if cur["last_type"] and any(k in cur["last_type"] for k in ("Two-minute", "End Period", "End of Half", "Halftime", "End of Regulation")):
        out.append(f"play-{cur['last_type'].replace(' ', '')}-p{cur['period']}")
    return out


def newest_play(summary):
    plays = {}
    drives = summary.get("drives") or {}
    for d in (drives.get("previous") or []) + ([drives["current"]] if drives.get("current") else []):
        for p in d.get("plays") or []:
            plays[str(p.get("id"))] = p
    if not plays:
        return None, None, 0
    p = max(plays.values(), key=lambda x: int(x.get("sequenceNumber") or 0))
    return str(p.get("id")), p.get("wallclock"), len(plays)


def live(a):
    out = a.out
    os.makedirs(out, exist_ok=True)
    until = datetime.strptime(a.until, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc) if a.until else None
    sb_path = f"{SITE}/scoreboard?seasontype={a.st}&week={a.week}" + (f"&dates={a.year}" if a.year else "")
    seen, fired, n_trig = {}, set(), 0
    follow = a.follow
    last_follow = 0.0
    log(out, f"start live st={a.st} week={a.week} follow={follow or 'auto'} until={a.until}")
    while True:
        t0 = time.time()
        try:
            body, host = get(sb_path)
            save(out, "scoreboard", stamp(), body)
            sb = json.loads(body)
            events = sb.get("events") or []
            states = {}
            for ev in events:
                gid = str(ev.get("id"))
                cur = game_tuple(ev)
                states[cur["state"]] = states.get(cur["state"], 0) + 1
                for reason in triggers(seen.get(gid), cur):
                    key = (gid, reason)
                    if key in fired or n_trig >= MAX_TRIGGERS:
                        continue
                    fired.add(key)
                    n_trig += 1
                    try:
                        sbody, _ = get(f"{SITE}/summary?event={gid}")
                        save(out, "triggers", f"{gid}_{reason}_{stamp()}", sbody)
                        log(out, f"trigger {ev.get('shortName')} {gid} {reason} ({n_trig}/{MAX_TRIGGERS})")
                    except Exception as e:  # noqa: BLE001 - keep capturing
                        log(out, f"trigger fetch failed {gid} {reason}: {e}")
                seen[gid] = cur
            live_ids = [str(ev["id"]) for ev in events if game_tuple(ev)["state"] == "in"]
            if not follow or follow not in [str(e["id"]) for e in events] or seen.get(follow, {}).get("state") == "post":
                follow = live_ids[0] if live_ids else follow
            if follow and seen.get(follow, {}).get("state") == "in" and time.time() - last_follow >= a.follow_interval:
                last_follow = time.time()
                try:
                    sbody, _ = get(f"{SITE}/summary?event={follow}")
                    save(out, f"follow_{follow}/summary", stamp(), sbody)
                    cbody, _ = get(f"{CORE}/events/{follow}/competitions/{follow}/plays?limit=400")
                    save(out, f"follow_{follow}/core_plays", stamp(), cbody)
                    s_id, s_wc, s_n = newest_play(json.loads(sbody))
                    core = json.loads(cbody).get("items") or []
                    c = max(core, key=lambda x: int(x.get("sequenceNumber") or 0)) if core else {}
                    sb_last = seen.get(follow, {}).get("last")
                    log(out, f"follow {follow} sb_last={sb_last} summary={s_id}@{s_wc} n={s_n} core={c.get('id')}@{c.get('wallclock')} n={len(core)}")
                except Exception as e:  # noqa: BLE001
                    log(out, f"follow fetch failed {follow}: {e}")
            log(out, f"poll {host.split('/')[2]} events={len(events)} states={states} triggers={n_trig}")
            if not states.get("in") and not states.get("pre"):
                log(out, "no live or upcoming games in this week; stopping")
                break
        except Exception as e:  # noqa: BLE001
            log(out, f"poll failed: {e}")
        if until and now_utc() >= until:
            log(out, "until reached; stopping")
            break
        time.sleep(max(1.0, a.interval - (time.time() - t0)))


def static(a):
    os.makedirs(a.out, exist_ok=True)
    for name, path in STATIC.items():
        try:
            body, _ = get(path)
            save(a.out, "static", name, body)
            log(a.out, f"static {name} {len(body)} B")
        except Exception as e:  # noqa: BLE001
            log(a.out, f"static {name} failed: {e}")
        time.sleep(1.5)


def main():
    p = argparse.ArgumentParser(description="Capture raw ESPN NFL payloads for test fixtures.")
    sub = p.add_subparsers(dest="mode", required=True)
    lp = sub.add_parser("live")
    lp.add_argument("--out", required=True)
    lp.add_argument("--st", type=int, default=2)
    lp.add_argument("--week", type=int, required=True)
    lp.add_argument("--year", type=int)
    lp.add_argument("--follow")
    lp.add_argument("--interval", type=float, default=30)
    lp.add_argument("--follow-interval", type=float, default=60)
    lp.add_argument("--until", help="UTC stop time, YYYY-MM-DDTHH:MMZ")
    sp = sub.add_parser("static")
    sp.add_argument("--out", required=True)
    a = p.parse_args()
    live(a) if a.mode == "live" else static(a)


if __name__ == "__main__":
    sys.exit(main())
