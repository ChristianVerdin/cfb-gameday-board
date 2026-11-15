"""Venue table: coverage of the 2026 ids, ranges, zones, roof classes, aliases."""
from __future__ import annotations

import gzip
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from nflcore import venues as V

ROOT = Path(__file__).resolve().parents[3]
CAPTURES = Path.home() / "Documents" / "nfl_board_captures" / "2026-11-15" / "static"

# ids seen on the 2026 regular-season scoreboards, weeks 1-18
SEEN_2026 = (
    "3493 3622 3628 3673 3679 3687 3712 3719 3727 3738 3752 3798 3806 3810 3812 3814 3839 3874 3886 3891 3933 3937 "
    "3948 3970 4738 5239 5348 6501 7065 8219 11930 11938 9119 11931 5534 2455 1781 1353"
).split()

DOMES = {"3727", "6501", "5239", "3493"}
RETRACTABLE = {"3687", "3891", "3812", "5348", "3970", "1353"}
CANOPY = {"7065", "11938", "3948", "2455", "1781", "11930", "11931"}


def _scoreboard_ids(sb, out):
    for ev in sb.get("events") or []:
        for comp in ev.get("competitions") or []:
            v = comp.get("venue") or {}
            if v.get("id") is not None:
                out.add(str(v["id"]))


def _fixture_ids() -> set[str]:
    ids: set[str] = set()
    for p in (ROOT / "scripts" / "fixtures" / "nfl").glob("*sb_2026_*.json"):
        _scoreboard_ids(json.loads(p.read_text()), ids)
    if CAPTURES.is_dir():
        for p in CAPTURES.glob("sb_2026_*.json.gz"):
            _scoreboard_ids(json.loads(gzip.open(p).read()), ids)
    return ids


def test_venues_table(check):
    check("38 active venues", len(V.ACTIVE_IDS), 38)
    check("all seen ids active", sorted(set(SEEN_2026)), sorted(V.ACTIVE_IDS))
    for vid, v in V.VENUES.items():
        if v["retired"]:
            continue
        check.true(f"{vid} lat/lon", -90 <= v["lat"] <= 90 and -180 <= v["lon"] <= 180)
        check.true(f"{vid} 4dp", round(v["lat"], 4) == v["lat"] and round(v["lon"], 4) == v["lon"])
        check.true(f"{vid} verified", v["verified"] in ("2src", "1src", "unverified"))
        check.true(f"{vid} sources", bool(v["sources"]))
        check.true(f"{vid} roof class", v["roof"] in ("open", "canopy", "retractable", "dome"), v["roof"])
        check.true(f"{vid} display name", bool(v["name"]) and "Reliant" not in v["name"])
        try:
            ZoneInfo(v["tz"])
        except Exception as e:  # noqa: BLE001
            check.true(f"{vid} tz", False, repr(e))
    check("regions", {v["country"] for v in V.VENUES.values() if v["region"] == "" and not v["retired"]},
          {"BR", "GB", "FR", "ES", "DE", "MX"})


def test_venues_ids_resolve(check):
    ids = _fixture_ids()
    check.true("fixtures carry venue ids", bool(ids))
    for vid in sorted(ids):
        check.true(f"fixture venue {vid} resolves", V.venue(vid) is not None)
        check.true(f"fixture venue {vid} is active", V.venue(vid) is not None and not V.venue(vid)["retired"])


def test_venues_roof(check):
    for vid in V.ACTIVE_IDS:
        want = "dome" if vid in DOMES else "retractable" if vid in RETRACTABLE else "canopy" if vid in CANOPY else "open"
        check(f"roof {vid}", V.roof(vid), want)
    for vid in DOMES | RETRACTABLE:
        check(f"espn indoor {vid}", V.venue(vid)["espn_indoor"], True)
    for vid in CANOPY:
        check(f"espn indoor {vid}", V.venue(vid)["espn_indoor"], False)
    check("roof unknown", V.roof("8748"), None)


def test_venues_names_lookup(check):
    check("NRG display", V.display_name("3891", "Reliant Stadium"), "NRG Stadium")
    check("Allianz display", V.display_name(11930, "FC Bayern Munich Stadium"), "Allianz Arena")
    check("Maracana display", V.display_name("11931", "Maracanã Stadium"), "Maracana Stadium")
    check("unknown falls back to ESPN name", V.display_name("8748", "Corinthians Arena"), "Corinthians Arena")
    check("int id", V.venue(3937)["city"], "Denver")
    check("Denver elev", V.venue("3937")["elev_ft"], 5280)
    check("Mexico City elev", V.venue("8219")["elev_ft"], 7352)
    check("no guessed elev", V.venue("3712")["elev_ft"], None)
    check("tz Phoenix", V.venue("3970")["tz"], "America/Phoenix")
    check("tz Nashville", V.venue("3810")["tz"], "America/Chicago")


def test_venues_buffalo_and_unknown(check):
    check("new Buffalo active", V.venue("11938")["retired"], False)
    check("new Buffalo coords", (V.venue("11938")["lat"], V.venue("11938")["lon"]), (42.773, -78.7922))
    old = V.venue("3883")
    check.true("old Buffalo present", old is not None)
    check("old Buffalo retired", old["retired"], True)
    check("old Buffalo no coords", (old["lat"], old["lon"]), (None, None))
    check.true("old Buffalo not active", "3883" not in V.ACTIVE_IDS)
    check("Sao Paulo 2025 unknown", V.venue("8748"), None)
    check("None id", V.venue(None), None)
    check("empty id", V.venue(""), None)
