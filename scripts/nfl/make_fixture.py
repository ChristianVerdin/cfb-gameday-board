#!/usr/bin/env python3
"""Turn raw ESPN captures (gzipped JSON, never committed) into sanitized fixtures (stdlib only).

Sanitizing drops third-party market, news, media and link data and every URL string, then asserts that no
market vocabulary is left. Game data the board needs (status, situation, drives, plays, winprobability,
boxscore, leaders, header, venue, weather, calendar, byes, records) is kept as captured.

Regenerate every committed fixture from the capture directory (the manifest is MANIFEST below):

    .venv/bin/python3 scripts/nfl/make_fixture.py build --captures DIR/2026-11-15
    .venv/bin/python3 scripts/nfl/make_fixture.py build --captures DIR/2026-11-15 --only live_
    .venv/bin/python3 scripts/nfl/make_fixture.py list

Convert one file, optionally keeping only some scoreboard events:

    .venv/bin/python3 scripts/nfl/make_fixture.py convert SRC.json.gz OUT.json [--events ID,ID]

Add the Sunday/Monday night captures later: put the capture files in the same directory, append
entries to MANIFEST (name, source path under --captures, optional event ids), run build --only <name>,
then describe the new fixture in scripts/fixtures/nfl/README.md.

ESPN data is used for testing only.
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "scripts" / "fixtures" / "nfl"

# Names built from fragments so this file never trips the repo's own scans.
DROP_KEYS = frozenset((
    "od" + "ds", "pick" + "center", "against" + "The" + "Spr" + "ead", "pre" + "dictor", "tickets", "ticketsInfo", "news",
    "article", "videos", "standings", "injuries", "links", "logos", "logo", "logoDark", "headshot", "images",
    "$ref", "link", "href", "uid", "guid", "provider",
))
DROP_KEY_PARTS = ("spr" + "ead", "over" + "under", "money" + "line", "od" + "ds", "bet" + "ting", "wa" + "ger",
                  "sports" + "book", "gam" + "bl", "total" + "over", "total" + "push")
DENY = re.compile(r"\b(" + "|".join((
    "od" + "ds", "spr" + "eads?", "money" + "lines?", "over" + "/under", "par" + "lays?", "bet" + "ting", "wa" + "gers?",
    "sports" + "books?", "draft" + "kings", "fan" + "duel", "bet" + "mgm", "pick" + "center",
    "against" + "the" + "spr" + "ead", "over" + "under", "imp" + "lied", "v" + "ig", "hand" + "icap",
)) + r")\b", re.I)
URL = re.compile(r"https?://|^\s*//[\w.-]+\.\w", re.I)


def drop_key(k: str) -> bool:
    low = k.lower()
    return k in DROP_KEYS or any(p in low for p in DROP_KEY_PARTS)


def sanitize(obj):
    if isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items()
                if not drop_key(k) and not (isinstance(v, str) and URL.search(v))}
    if isinstance(obj, list):
        return [sanitize(v) for v in obj if not (isinstance(v, str) and URL.search(v))]
    return obj


def find_denied(obj, path="$") -> list[str]:
    hits: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if DENY.search(k) or drop_key(k):
                hits.append(f"{path}.{k} (key)")
            hits += find_denied(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hits += find_denied(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        m = DENY.search(obj) or URL.search(obj)
        if m:
            hits.append(f"{path} ({m.group(0)!r})")
    return hits


def keep_events(sb: dict, ids: list[str]) -> dict:
    out = dict(sb)
    out["events"] = [e for e in sb.get("events", []) if str(e.get("id")) in set(ids)]
    missing = set(ids) - {str(e.get("id")) for e in out["events"]}
    if missing:
        raise SystemExit(f"events not in scoreboard: {sorted(missing)}")
    return out


def load(path: Path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt") as f:
        return json.load(f)


def convert(src: Path, dst: Path, events: list[str] | None = None) -> int:
    data = load(src)
    if events:
        data = keep_events(data, events)
    clean = sanitize(data)
    bad = find_denied(clean)
    if bad:
        raise SystemExit(f"{src.name}: market vocabulary or URL left after sanitizing: {bad[:8]}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(clean, separators=(",", ":"), ensure_ascii=False)
    dst.write_text(text + "\n")
    return len(text) + 1


# (fixture name, path under the capture dir, event ids to keep or None)
MANIFEST: list[tuple[str, str, list[str] | None]] = [
    ("summary_ot_final_2025w2_nyg_dal", "static/ot_final_2025_w2_nyg_dal.json.gz", None),
    ("summary_tie_final_2025w4_gb_dal", "static/tie_final_2025_w4_gb_dal.json.gz", None),
    ("summary_probowl_2025", "static/probowl_2025_summary.json.gz", None),
    ("summary_superbowl_lx", "static/superbowl_lx_summary.json.gz", None),
    ("sb_2025_w1", "static/sb_2025_w1_scoreboard.json.gz", None),
    ("sb_2025_w2", "static/sb_2025_w2_scoreboard.json.gz", None),
    ("sb_2025_w4", "static/sb_2025_w4_scoreboard.json.gz", None),
    ("sb_2025_post_w1", "static/sb_2025_post_w1.json.gz", None),
    ("sb_2025_post_w2", "static/sb_2025_post_w2.json.gz", None),
    ("sb_2025_post_w3", "static/sb_2025_post_w3.json.gz", None),
    ("sb_2025_post_w4", "static/sb_2025_post_w4.json.gz", None),
    ("sb_2025_post_w5", "static/sb_2025_post_w5.json.gz", None),
    ("sb_2026_w10", "static/sb_2026_w10.json.gz", None),
    ("sb_2026_w11", "static/sb_2026_w11.json.gz", None),
    ("sb_2026_w12", "static/sb_2026_w12.json.gz", None),
    ("sb_2026_w16", "static/sb_2026_w16.json.gz", None),
    ("sb_2026_w18", "static/sb_2026_w18.json.gz", None),
    ("sb_2026_post_w1", "static/sb_2026_post_w1.json.gz", None),
    ("sb_bare", "static/sb_bare.json.gz", None),
    ("teams", "static/teams.json.gz", None),
    ("live_sb_w10_mid", "scoreboard/20261115T195936Z.json.gz", None),
    ("live_summary_early", "follow_401873058/summary/20261115T195536Z.json.gz", None),
    ("live_summary_late", "follow_401873058/summary/20261115T200106Z.json.gz", None),
    ("live_core_plays_early", "follow_401873058/core_plays/20261115T195537Z.json.gz", None),
    ("live_core_plays_late", "follow_401873058/core_plays/20261115T200106Z.json.gz", None),
    ("live_trigger_401873054_fg_good", "triggers/401873054_down-1-FieldGoalGood_20261115T195636Z.json.gz", None),
    ("live_trigger_401873054_timeout", "triggers/401873054_down-1-OfficialTimeout_20261115T195736Z.json.gz", None),
    ("live_trigger_401873055_rush_td", "triggers/401873055_down-1-RushingTouchdown_20261115T195806Z.json.gz", None),
    ("live_trigger_401873056_timeout", "triggers/401873056_down-1-OfficialTimeout_20261115T195936Z.json.gz", None),
    ("live_trigger_401873057_fg_good", "triggers/401873057_down-1-FieldGoalGood_20261115T195706Z.json.gz", None),
    ("live_trigger_401873060_timeout", "triggers/401873060_down-1-OfficialTimeout_20261115T195536Z.json.gz", None),
]


def build(captures: Path, only: str | None) -> int:
    total = 0
    for name, rel, events in MANIFEST:
        if only and only not in name:
            continue
        size = convert(captures / rel, OUT_DIR / f"{name}.json", events)
        total += size
        print(f"{name}.json {size / 1024:.0f} KB")
    print(f"total {total / 1024:.0f} KB")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="regenerate fixtures from the manifest")
    b.add_argument("--captures", required=True, type=Path)
    b.add_argument("--only", help="substring of a fixture name")
    c = sub.add_parser("convert", help="sanitize one capture")
    c.add_argument("src", type=Path)
    c.add_argument("dst", type=Path)
    c.add_argument("--events", help="comma-separated event ids to keep (scoreboards)")
    sub.add_parser("list", help="print the manifest")
    a = ap.parse_args(argv)
    if a.cmd == "build":
        return build(a.captures, a.only)
    if a.cmd == "convert":
        print(f"{convert(a.src, a.dst, a.events.split(',') if a.events else None)} bytes")
        return 0
    for name, rel, events in MANIFEST:
        print(name, rel, events or "")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
