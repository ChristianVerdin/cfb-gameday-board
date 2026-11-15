#!/usr/bin/env python3
"""Build nfl/metrics.json from the nflverse play-by-play release (stdlib only).

    build_metrics.py [--season 2026] [--force] [--out nfl/metrics.json]

HEAD first: an unchanged ETag exits 0 with no change. Any failure or gate miss
keeps the old file and exits non-zero.
"""
from __future__ import annotations

import argparse
import gzip
import io
import json
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from nflcore import metrics  # noqa: E402

BASE = "https://github.com/nflverse/nflverse-data/releases/download/pbp/"
UA = "cfb-gameday-board nfl metrics (+https://cfbgameday.app)"


def asset(season: int) -> tuple[str, str]:
    name = f"play_by_play_{season}.csv.gz"
    return name, BASE + name


def http_head(url: str) -> dict:
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return {"etag": r.headers.get("ETag"), "last_modified": r.headers.get("Last-Modified")}


def http_open(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=120)


def build_doc(stream, season: int, name: str, head: dict, now: datetime | None = None) -> dict:
    """stream: binary gzip file-like. Raises ValueError on a gate miss."""
    with gzip.open(stream, "rt", encoding="utf-8", newline="") as fh:
        agg = metrics.aggregate(metrics.read_plays(fh))
    block = metrics.build(agg)
    errs = metrics.gate(agg, block)
    if errs:
        raise ValueError("; ".join(errs))
    now = now or datetime.now(ZoneInfo("America/Chicago"))
    return {
        "v": 1, "generated_at": now.isoformat(timespec="seconds"), "season": season, "through_week": agg["through_week"],
        "source": {"name": "nflverse", "file": name, "last_modified": head.get("last_modified"), "etag": head.get("etag"),
                   "rows": agg["rows"], "games": agg["game_count"], "license": "CC-BY-4.0"},
        "filters": metrics.FILTERS,
        "league": {"epa_play": round(agg["league_epa"], 3), "sr": round(agg["league_sr"], 3)},
        "teams": block}


def run(season: int, out: Path, force: bool = False, head_fn=http_head, open_fn=http_open) -> int:
    name, url = asset(season)
    try:
        head = head_fn(url)
        if not force and out.exists() and head.get("etag"):
            try:
                if json.loads(out.read_text())["source"]["etag"] == head["etag"]:
                    print(f"unchanged ({head['etag']})")
                    return 0
            except (ValueError, KeyError):
                pass
        with open_fn(url) as resp:
            doc = build_doc(io.BytesIO(resp.read()), season, name, head)
    except Exception as e:  # noqa: BLE001 - any failure keeps the old file
        print(f"metrics build failed, keeping {out.name}: {e}", file=sys.stderr)
        return 1
    tmp = out.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1) + "\n")
    tmp.replace(out)
    print(f"wrote {out} through week {doc['through_week']} ({doc['source']['rows']} plays)")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--out", type=Path, default=ROOT / "nfl" / "metrics.json")
    a = ap.parse_args(argv)
    season = a.season
    if season is None:
        try:
            season = json.loads((ROOT / "nfl" / "games.json").read_text())["season"]["year"]
        except (OSError, KeyError, ValueError):
            season = datetime.now(ZoneInfo("America/Chicago")).year
    return run(season, a.out, a.force)


if __name__ == "__main__":
    sys.exit(main())
