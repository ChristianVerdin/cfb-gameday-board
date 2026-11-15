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
    "scripts/promo_text.py", "data/rivalries.json",
)
PROTECTED_PREFIXES = (".well-known/", "ios/", "icons/")
NFL_PATHS = ("nflcore/", "nfl/", "api/nfl/", "scripts/nfl/", "scripts/check_nfl.py", "scripts/fixtures/nfl/",
             ".github/workflows/nfl-", ".github/workflows/pr-check", "ios-pfb/")
SCAN_SUFFIXES = (".html", ".js", ".css", ".json", ".md", ".swift", ".yml", ".strings", ".txt")
# The support address is already public on the CFB support page.
PUBLIC_CONTACT = "hoynelabs" + "@" + "gm" + "ail.com"

# Built from fragments so this file never matches itself.
PRIVATE = [re.compile(p, re.I) for p in (
    "nfl" + "_2026", "fan" + "duel_scr", "daily" + "locks", "sports" + "kit", "drunk" + "ryan",
    "/Us" + "ers/", "gm" + r"ail\.com", "bet" + "_slips", "page" + "_grabber", r"\b" + "c" + r"v\b",
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


NFL_LINK = ' <a href="/nfl">Pro football board</a> ·'


def approved_launch_edit(path: str, base: str) -> bool:
    """The approved launch edits (2026-11-15): the college footer gains one link, the sitemap gains /nfl URLs."""
    diff = git("diff", base, "--", path).splitlines()
    removed = [l[1:] for l in diff if l.startswith("-") and not l.startswith("---")]
    added = [l[1:] for l in diff if l.startswith("+") and not l.startswith("+++")]
    if path == "index.html":
        return len(removed) == len(added) == 1 and NFL_LINK in added[0] and added[0].replace(NFL_LINK, "", 1) == removed[0]
    if path == "sitemap.xml":
        return not removed and bool(added) and all("cfbgameday.app/nfl" in l for l in added)
    return False


def test_cfb_untouched(check):
    base = merge_base()
    check.true("merge-base with main found", base is not None)
    if not base:
        return
    changed = changed_vs_base(base)
    if not any(p.startswith(NFL_PATHS + ("ios-pfb/",)) for p in changed):
        return  # a college-board-only change: this guard covers NFL work, not the board it protects
    hit = sorted(p for p in changed if (p in PROTECTED or p.startswith(PROTECTED_PREFIXES)) and not approved_launch_edit(p, base))
    check("protected CFB files changed vs merge-base", hit, [])
    if ".vercelignore" in changed:
        old = git("show", f"{base}:.vercelignore").splitlines()
        new = (ROOT / ".vercelignore").read_text().splitlines()
        check.true(".vercelignore only gains lines", all(line in new for line in old), f"dropped {[l for l in old if l not in new]}")
        check.true(".vercelignore keeps its order", [l for l in new if l in old] == old)
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
            if not h.get("source", "").startswith(("/nfl", "/api/nfl")):
                check.true(f"vercel.json header kept {h.get('source')}", h in new.get("headers", []))
    wf = ".github/workflows/refresh.yml"
    if wf in changed:
        diff = git("diff", base, "--", wf)
        removed = [l[1:].strip() for l in diff.splitlines() if l.startswith("-") and not l.startswith("---")]
        check("refresh.yml removed lines", removed, ["git push"] if removed else [])


def test_public_hygiene(check):
    for path in nfl_files():
        if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".gz", ".ico", ".xcprivacy_bin"):
            continue
        text = path.read_text(errors="replace").replace(PUBLIC_CONTACT, "")
        for pat in PRIVATE:
            m = pat.search(text)
            check.true(f"no private name in {path.relative_to(ROOT)}", m is None, m.group(0) if m else "")


def test_stats_only_files(check):
    """Client files and committed fixtures carry no betting vocabulary."""
    for path in nfl_files():
        rel = str(path.relative_to(ROOT))
        tool = path.parent.name == "nfl" and path.parent.parent.name == "scripts" and path.suffix == ".py"
        if not (tool or (rel.startswith(("nfl/", "scripts/fixtures/nfl/", "ios-pfb/")) and path.suffix in SCAN_SUFFIXES)):
            continue
        m = BETTING.search(path.read_text(errors="replace"))
        check.true(f"no betting words in {rel}", m is None, m.group(0) if m else "")


def test_ios_pfb_privacy_manifests(check):
    for target in ("ProFootballBoard", "ProFootballBoardWidget"):
        f = ROOT / "ios-pfb" / target / "PrivacyInfo.xcprivacy"
        check.true(f"{target} privacy manifest exists", f.is_file())
        if f.is_file():
            text = f.read_text()
            check.true(f"{target} manifest declares UserDefaults CA92.1", "NSPrivacyAccessedAPICategoryUserDefaults" in text and "CA92.1" in text)
