"""Repo-level guards: the CFB board stays untouched and NFL files stay clean."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

# CFB files the NFL work must never change (relative to the merge-base with main).
PROTECTED = (
    "server.py", "api/live.py", "api/game.py", "app.js", "sw.js", "index.html", "site.css",
    "games.json", "games.js", "sitemap.xml", "manifest.webmanifest", "privacy.html", "support.html",
    "scripts/refresh_week.py", "scripts/check.py", "scripts/ci_heal.py", "scripts/run_summary.py",
    "scripts/promo_text.py", "data/rivalries.json", ".vercelignore",
)
PROTECTED_PREFIXES = (".well-known/", "ios/", "icons/")
NFL_PATHS = ("nflcore/", "nfl/", "api/nfl/", "scripts/nfl/", "scripts/check_nfl.py", "scripts/fixtures/nfl/",
             ".github/workflows/nfl-", ".github/workflows/pr-check")

# Built from fragments so this file never matches itself.
PRIVATE = [re.compile(p, re.I) for p in (
    "nfl" + "_2026", "fan" + "duel_scr", "daily" + "locks", "sports" + "kit", "drunk" + "ryan",
    "/Us" + "ers/", "gm" + r"ail\.com", "bet" + "_slips", "page" + "_grabber",
)]
BETTING = re.compile(r"\b(" + "|".join((
    "odds", "spreads?", "moneylines?", "over/under", "parlays?", "betting", "wagers?", "sportsbooks?",
    "draft" + "kings", "fan" + "duel", "bet" + "mgm", "pick" + "center", "against" + "the" + "spread", "over" + "under",
    "implied", "vig", "handicap",
)) + r")\b", re.I)


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def merge_base() -> str | None:
    for ref in ("origin/main", "main"):
        try:
            return git("merge-base", ref, "HEAD").strip()
        except subprocess.CalledProcessError:
            continue
    return None


def changed_vs_base(base: str) -> set[str]:
    names = set(git("diff", "--name-only", base).split())  # committed + working tree vs base
    names |= set(git("ls-files", "--others", "--exclude-standard").split())
    return names


def nfl_files() -> list[Path]:
    tracked = git("ls-files").split() + git("ls-files", "--others", "--exclude-standard").split()
    return [ROOT / p for p in sorted(set(tracked)) if p.startswith(NFL_PATHS) and (ROOT / p).is_file()]


def test_cfb_untouched(check):
    base = merge_base()
    check.true("merge-base with main found", base is not None)
    if not base:
        return
    changed = changed_vs_base(base)
    hit = sorted(p for p in changed if p in PROTECTED or p.startswith(PROTECTED_PREFIXES))
    check("protected CFB files changed vs merge-base", hit, [])
    if "vercel.json" in changed:
        old = json.loads(git("show", f"{base}:vercel.json"))
        new = json.loads((ROOT / "vercel.json").read_text())
        for k, v in old.items():
            if k in ("functions", "headers"):
                continue
            check(f"vercel.json {k} unchanged", new.get(k), v)
        for fn, cfg in old.get("functions", {}).items():
            got = new.get("functions", {}).get(fn, {})
            check(f"vercel.json {fn} maxDuration", got.get("maxDuration"), cfg.get("maxDuration"))
            o = set(cfg.get("excludeFiles", "").strip("{}").split(","))
            n = set(got.get("excludeFiles", "").strip("{}").split(","))
            check.true(f"vercel.json {fn} excludeFiles only grows", o <= n, f"dropped {sorted(o - n)}")
            check.true(f"vercel.json {fn} only NFL excludes added", all(x.startswith(("nfl", "api/nfl")) for x in n - o),
                       f"added {sorted(n - o)}")
        for h in old.get("headers", []):
            check.true(f"vercel.json header kept {h.get('source')}", h in new.get("headers", []))
    wf = ".github/workflows/refresh.yml"
    if wf in changed:
        diff = git("diff", base, "--", wf)
        removed = [l[1:].strip() for l in diff.splitlines() if l.startswith("-") and not l.startswith("---")]
        check("refresh.yml removed lines", removed, ["git push"] if removed else [])


def test_public_hygiene(check):
    for path in nfl_files():
        text = path.read_text(errors="replace")
        for pat in PRIVATE:
            m = pat.search(text)
            check.true(f"no private name in {path.relative_to(ROOT)}", m is None, m.group(0) if m else "")


def test_stats_only_files(check):
    """Client files and committed fixtures carry no betting vocabulary."""
    for path in nfl_files():
        rel = str(path.relative_to(ROOT))
        tool = path.parent.name == "nfl" and path.parent.parent.name == "scripts" and path.suffix == ".py"
        if not (tool or (rel.startswith(("nfl/", "scripts/fixtures/nfl/")) and path.suffix in (".html", ".js", ".css", ".json", ".md"))):
            continue
        m = BETTING.search(path.read_text(errors="replace"))
        check.true(f"no betting words in {rel}", m is None, m.group(0) if m else "")
