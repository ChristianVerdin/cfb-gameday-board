"""nflverse metrics: hand-computed values, ranks, mapping, ETag short-circuit, gate failure, clean output."""
from __future__ import annotations

import csv
import gzip
import io
import json
import tempfile
from pathlib import Path

from nflcore import metrics as M, teams
from scripts.nfl import build_metrics as B
from scripts.nfl.checks.repo import BETTING

ROOT = Path(__file__).resolve().parents[3]
MINI = ROOT / "scripts" / "fixtures" / "nfl" / "pbp_mini.csv"
HEAD = {"etag": '"abc"', "last_modified": "Sun, 15 Nov 2026 16:00:00 GMT"}


def _mini_agg():
    with MINI.open(newline="") as fh:
        return M.aggregate(M.read_plays(fh))


def _ring_gz() -> bytes:
    """32 clubs in nflverse abbreviations, two plays each (+0.1 / -0.1): tiny but gate-clean."""
    abbrs = [teams.nflverse_abbr(a) for a in sorted(teams.BY_ABBR)]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(M.COLUMNS)
    for i, pos in enumerate(abbrs):
        de = abbrs[(i + 1) % 32]
        for epa in (0.1, -0.1):
            w.writerow([f"g{i}", 1, "REG", pos, de, "pass", 1, 0, 1, 0, 0, epa, 1 if epa > 0 else 0, 5, ])
    return gzip.compress(buf.getvalue().encode())


def _near(a, b):
    return abs(a - b) < 1e-9


def test_metrics_hand_computed(check):
    agg = _mini_agg()
    check("plays kept", agg["rows"], 6)
    check("games kept", agg["game_count"], 2)
    check("through week", agg["through_week"], 2)
    check("league epa", round(agg["league_epa"], 4), round(1.9 / 6, 4))
    was_o, was_d = agg["off"]["WAS"], agg["def"]["WAS"]
    check("WAS off plays", was_o[0], 3)
    check("WAS off epa", round(was_o[1] / was_o[0], 4), round(0.7 / 3, 4))
    check("WAS off sr", round(was_o[3] / was_o[2], 4), round(2 / 3, 4))
    check("WAS proe only where present", was_o[5] / was_o[4], 10.0)
    check("WAS def epa", round(was_d[1] / was_d[0], 4), 0.4)
    check("LA off proe", agg["off"]["LA"][5] / agg["off"]["LA"][4], -4.0)
    check("KC def epa", agg["def"]["KC"][1], 0.3)
    check("WAS games", agg["games"]["WAS"], 2)
    check("post-season play dropped", agg["games"].get("LA"), 1)


def test_metrics_allowlist(check):
    check.true("decoys not allowlisted", not any(c.startswith("decoy") for c in M.COLUMNS))
    with MINI.open(newline="") as fh:
        row = next(csv.DictReader(fh))
    check.true("fixture carries decoy columns", "decoy_a" in row)
    check("projection keeps only the allowlist", sorted(M.project(row)), sorted(M.COLUMNS))
    check.true("no market columns allowlisted", not BETTING.search(" ".join(M.COLUMNS)))
    try:
        list(M.read_plays(iter(["game_id,epa", "g,1"])))
        check.true("missing columns raise", False)
    except ValueError:
        check.true("missing columns raise", True)


def test_metrics_ranks(check):
    vals = {"a": 1, "b": 2, "c": 2, "d": 3}
    check("high is best, ties share the lower rank", M.rank(vals, True), {"d": 1, "b": 2, "c": 2, "a": 4})
    check("low is best", M.rank(vals, False), {"a": 1, "b": 2, "c": 2, "d": 4})


def test_metrics_build(check):
    doc = B.build_doc(io.BytesIO(_ring_gz()), 2026, "play_by_play_2026.csv.gz", HEAD)
    t = doc["teams"]
    check("32 clubs", len(t), 32)
    check.true("WSH and LAR mapped", "WSH" in t and "LAR" in t and "WAS" not in t and "LA" not in t)
    check("two plays each", t["KC"]["off"]["plays"], 2)
    check.true("small sample flagged", all(v["small_sample"] for v in t.values()))
    check("ties share rank 1", t["KC"]["off"]["epa_rank"], 1)
    check("league epa", doc["league"]["epa_play"], 0.0)
    check("source etag", doc["source"]["etag"], '"abc"')
    check("license", doc["source"]["license"], "CC-BY-4.0")
    full = M.build({"off": {teams.nflverse_abbr(a): [200, 0.0, 200, 90.0, 100, 50.0] for a in teams.BY_ABBR},
                    "def": {teams.nflverse_abbr(a): [200, 0.0, 200, 90.0] for a in teams.BY_ABBR},
                    "games": {teams.nflverse_abbr(a): 9 for a in teams.BY_ABBR}})
    check("big sample not small", full["KC"]["small_sample"], False)
    check("proe rounding", full["KC"]["off"]["proe"], 0.5)
    try:
        M.build(_mini_agg())
        check.true("missing clubs raise", False)
    except ValueError:
        check.true("missing clubs raise", True)


def _keys(o, out):
    if isinstance(o, dict):
        for k, v in o.items():
            out.add(k)
            _keys(v, out)
    return out


def test_metrics_clean_output(check):
    doc = B.build_doc(io.BytesIO(_ring_gz()), 2026, "f.csv.gz", HEAD)
    docs = [doc]
    real = ROOT / "nfl" / "metrics.json"
    if real.exists():
        docs.append(json.loads(real.read_text()))
    for d in docs:
        keys = _keys(d, set())
        check("no forbidden keys", [k for k in keys if BETTING.search(k) or "line" in k.lower()], [])
        check.true("no forbidden words in text", not BETTING.search(json.dumps(d)))
        check("top-level keys", sorted(d), sorted(["v", "generated_at", "season", "through_week", "source", "filters", "league", "teams"]))


def test_metrics_etag_and_gate(check):
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "metrics.json"
        gz = _ring_gz()
        opened = []

        def open_ok(url):
            opened.append(url)
            return io.BytesIO(gz)

        class _R(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def opener(data):
            def f(url):
                opened.append(url)
                return _R(data)
            return f

        check("first build", B.run(2026, out, head_fn=lambda u: HEAD, open_fn=opener(gz)), 0)
        check("fetched once", len(opened), 1)
        before = out.read_text()
        check("same etag short-circuits", B.run(2026, out, head_fn=lambda u: HEAD, open_fn=opener(gz)), 0)
        check("no second fetch", len(opened), 1)
        check("file unchanged", out.read_text(), before)
        new = {"etag": '"def"', "last_modified": HEAD["last_modified"]}
        check("new etag rebuilds", B.run(2026, out, head_fn=lambda u: new, open_fn=opener(gz)), 0)
        check("etag stored", json.loads(out.read_text())["source"]["etag"], '"def"')
        check("force refetches", B.run(2026, out, force=True, head_fn=lambda u: new, open_fn=opener(gz)), 0)
        check("force fetched", len(opened), 3)
        keep = out.read_text()
        with MINI.open("rb") as fh:
            bad = gzip.compress(fh.read())
        check("gate failure exits non-zero", B.run(2026, out, force=True, head_fn=lambda u: new, open_fn=opener(bad)), 1)
        check("gate failure keeps old file", out.read_text(), keep)
        skew = io.StringIO()
        w = csv.writer(skew)
        w.writerow(M.COLUMNS)
        ab = [teams.nflverse_abbr(a) for a in sorted(teams.BY_ABBR)]
        for i, a in enumerate(ab):
            for _ in range(3):
                w.writerow(["g", 1, "REG", a, ab[(i + 1) % 32], "pass", 1, 0, 1, 0, 0, 0.5, 1, ""])
        try:
            B.build_doc(io.BytesIO(gzip.compress(skew.getvalue().encode())), 2026, "f", new)
            check.true("league EPA gate raises", False)
        except ValueError as e:
            check.true("league EPA gate raises on EPA", "league EPA" in str(e), str(e))
        check("league EPA gate", B.run(2026, out, force=True, head_fn=lambda u: new, open_fn=opener(gzip.compress(skew.getvalue().encode()))), 1)
        check("epa gate keeps old file", out.read_text(), keep)

        def boom(url):
            raise OSError("down")

        check("fetch error keeps old file", B.run(2026, out, force=True, head_fn=lambda u: new, open_fn=boom), 1)
        check("still intact", out.read_text(), keep)
