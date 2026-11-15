"""The 32 NFL teams by ESPN id, plus the ESPN to nflverse abbreviation map."""
from __future__ import annotations

_ROWS = (
    ("22", "ARI", "Arizona Cardinals", "NFC", "West"), ("1", "ATL", "Atlanta Falcons", "NFC", "South"),
    ("33", "BAL", "Baltimore Ravens", "AFC", "North"), ("2", "BUF", "Buffalo Bills", "AFC", "East"),
    ("29", "CAR", "Carolina Panthers", "NFC", "South"), ("3", "CHI", "Chicago Bears", "NFC", "North"),
    ("4", "CIN", "Cincinnati Bengals", "AFC", "North"), ("5", "CLE", "Cleveland Browns", "AFC", "North"),
    ("6", "DAL", "Dallas Cowboys", "NFC", "East"), ("7", "DEN", "Denver Broncos", "AFC", "West"),
    ("8", "DET", "Detroit Lions", "NFC", "North"), ("9", "GB", "Green Bay Packers", "NFC", "North"),
    ("34", "HOU", "Houston Texans", "AFC", "South"), ("11", "IND", "Indianapolis Colts", "AFC", "South"),
    ("30", "JAX", "Jacksonville Jaguars", "AFC", "South"), ("12", "KC", "Kansas City Chiefs", "AFC", "West"),
    ("13", "LV", "Las Vegas Raiders", "AFC", "West"), ("24", "LAC", "Los Angeles Chargers", "AFC", "West"),
    ("14", "LAR", "Los Angeles Rams", "NFC", "West"), ("15", "MIA", "Miami Dolphins", "AFC", "East"),
    ("16", "MIN", "Minnesota Vikings", "NFC", "North"), ("17", "NE", "New England Patriots", "AFC", "East"),
    ("18", "NO", "New Orleans Saints", "NFC", "South"), ("19", "NYG", "New York Giants", "NFC", "East"),
    ("20", "NYJ", "New York Jets", "AFC", "East"), ("21", "PHI", "Philadelphia Eagles", "NFC", "East"),
    ("23", "PIT", "Pittsburgh Steelers", "AFC", "North"), ("25", "SF", "San Francisco 49ers", "NFC", "West"),
    ("26", "SEA", "Seattle Seahawks", "NFC", "West"), ("27", "TB", "Tampa Bay Buccaneers", "NFC", "South"),
    ("10", "TEN", "Tennessee Titans", "AFC", "South"), ("28", "WSH", "Washington Commanders", "NFC", "East"),
)

TEAMS: dict[str, dict] = {
    i: {"id": i, "abbr": a, "name": n, "conf": c, "div": f"{c} {d}"} for i, a, n, c, d in _ROWS
}
BY_ABBR: dict[str, dict] = {t["abbr"]: t for t in TEAMS.values()}

# ESPN abbreviation -> nflverse abbreviation; only the two that differ, identities filled below.
_DIFF = {"WSH": "WAS", "LAR": "LA"}
NFLVERSE_ABBR: dict[str, str] = {a: _DIFF.get(a, a) for a in BY_ABBR}
FROM_NFLVERSE: dict[str, str] = {v: k for k, v in NFLVERSE_ABBR.items()}

# Pro Bowl squads (not clubs): never counted as byes or standings rows.
ALL_STAR_IDS = {"31": "AFC", "32": "NFC"}


def nflverse_abbr(espn_abbr: str) -> str:
    return NFLVERSE_ABBR.get(espn_abbr, espn_abbr)


def espn_abbr(nflverse: str) -> str:
    return FROM_NFLVERSE.get(nflverse, nflverse)


def is_all_star(team_id) -> bool:
    return str(team_id) in ALL_STAR_IDS
