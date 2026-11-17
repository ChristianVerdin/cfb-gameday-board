"""Platform wiring: vercel.json, workflows, and the NFL service worker."""
from __future__ import annotations

import json
import re

from scripts.nfl.checks.repo import ROOT, git, merge_base

WF = ROOT / ".github" / "workflows"
LOOP = ("ok=0; for i in 1 2 3 4; do if git pull --rebase origin main && git push; then ok=1; break; fi; "
        "git rebase --abort 2>/dev/null || true; if [ \"$i\" -lt 4 ]; then sleep $((i*7)); fi; done; "
        "[ \"$ok\" = 1 ] || { echo \"push failed after 4 attempts\"; exit 1; }")
REFRESH_CRONS = ["0 12 * * 2", "0 18 * * 2", "0 10 * * 3", "0 14 * * 3", "0 18 * * 3", "0 22 * * 3",
                 "0 6 * * 4", "0 12 * * 4", "0 6 * * 5", "0 14 * * 5", "0 12 * * 6", "0 2 * * 0", "0 6 * * 0", "0 10 * * 0", "0 12 * * 1"]
GUARD = "if: github.event_name == 'workflow_dispatch' || vars.NFL_REFRESH_ENABLED == 'true'"


def crons(text: str) -> list[str]:
    return re.findall(r'- cron: "([^"]+)"', text)


def excludes(cfg: dict) -> set[str]:
    return set(cfg.get("excludeFiles", "").strip("{}").split(","))


def test_vercel(check):
    v = json.loads((ROOT / "vercel.json").read_text())
    fns = v["functions"]
    for name in ("live", "game"):
        cfg = fns.get(f"api/nfl/{name}.py")
        check.true(f"api/nfl/{name}.py present", cfg is not None)
        if cfg is None:
            continue
        check(f"{name} maxDuration", cfg.get("maxDuration"), 30)
        ex = excludes(cfg)
        check.true(f"{name} excludes nfl/**", "nfl/**" in ex)
        check.true(f"{name} keeps nflcore", not any(x.startswith("nflcore") for x in ex))
        check.true(f"{name} keeps its own api", "api/nfl/**" not in ex)
    for fn in ("api/live.py", "api/game.py"):
        ex = excludes(fns[fn])
        check.true(f"{fn} excludes NFL paths", {"nfl/**", "nflcore/**", "api/nfl/**"} <= ex)
    base = merge_base()
    if base:
        old = json.loads(git("show", f"{base}:vercel.json"))
        for fn, cfg in old["functions"].items():
            added = excludes(fns[fn]) - excludes(cfg)
            check.true(f"{fn} extended only with NFL paths", all(x.startswith(("nfl", "api/nfl")) for x in added), str(sorted(added)))
    hdrs = {h["source"]: {x["key"]: x["value"] for x in h["headers"]} for h in v["headers"]}
    check("api stays noindex", hdrs.get("/api/nfl/(.*)", {}).get("X-Robots-Tag"), "noindex, nofollow")
    for src in ("/nfl", "/nfl/(.*)"):  # launched 2026-11-15: the board pages are indexable
        check(f"board page indexable {src}", hdrs.get(src, {}).get("X-Robots-Tag"), None)
    check("nfl sw no-cache", hdrs.get("/nfl/sw.js", {}).get("Cache-Control"), "no-cache")


def test_workflows(check):
    refresh = (WF / "nfl-refresh.yml").read_text()
    metrics = (WF / "nfl-metrics.yml").read_text()
    pr = (WF / "pr-check.yml").read_text()
    check("refresh crons", crons(refresh), REFRESH_CRONS)
    check("metrics crons", crons(metrics), ["0 14 * * 2", "0 14 * * 3"])
    for name, text, group in (("refresh", refresh, "nfl-snapshot"), ("metrics", metrics, "nfl-metrics")):
        check.true(f"{name} guard", GUARD in text)
        check.true(f"{name} concurrency", f"group: {group}\n  cancel-in-progress: false" in text)
        check.true(f"{name} dispatch", "workflow_dispatch" in text)
        check.true(f"{name} push loop", LOOP in text)
        check.true(f"{name} no bare push", not re.search(r"^\s*git push\s*$", text, re.M))
        check.true(f"{name} uses v7 actions", "actions/checkout@v7" in text and "actions/setup-python@v7" in text)
        adds = re.findall(r"git add (.+)", text)
        check.true(f"{name} adds only nfl/ paths", bool(adds) and all(p.startswith("nfl/") for a in adds for p in a.split()), str(adds))
    check.true("refresh dispatch inputs", all(f"      {i}:" in refresh for i in ("st", "week", "year")))
    check.true("refresh diff guard", "git diff --quiet -- nfl/games.json nfl/games.js nfl/index.html" in refresh)
    check.true("refresh commit message", 'NFL snapshot: $label' in refresh)
    check.true("refresh runs checks", "scripts/nfl/refresh_nfl.py" in refresh and "scripts/check_nfl.py" in refresh)
    check.true("refresh no telegram", "telegram" not in refresh.lower())
    check.true("metrics adds only metrics.json", re.findall(r"git add (.+)", metrics) == ["nfl/metrics.json"])
    check.true("metrics runs build", "scripts/nfl/build_metrics.py" in metrics and "scripts/check_nfl.py" in metrics)
    check.true("pr-check triggers", "pull_request:" in pr and "branches: [nfl]" in pr)
    check.true("pr-check read-only", "contents: read" in pr and "contents: write" not in pr)
    check.true("pr-check full history", "fetch-depth: 0" in pr and "git fetch origin main" in pr)
    check.true("pr-check runs both", "scripts/check.py" in pr and "scripts/check_nfl.py" in pr)
    check.true("pr-check node", "actions/setup-node@v" in pr)


def test_refresh_yml(check):
    text = (WF / "refresh.yml").read_text()
    check.true("refresh.yml push loop", LOOP in text)
    check.true("refresh.yml no bare push", not re.search(r"^\s*git push\s*$", text, re.M))


def test_sw(check):
    sw = (ROOT / "nfl" / "sw.js").read_text()
    check.true("cache name", 'const VERSION = "pfb-v2"' in sw)
    check.true("activate only prunes pfb- caches", 'k.startsWith("pfb-") && k !== VERSION' in sw)
    check.true("never caches api", 'url.pathname.startsWith("/api/")) return' in sw)
    check.true("scope guard", 'startsWith("/nfl/")' in sw)
    check.true("offline fallback", 'caches.match("/nfl/index.html")' in sw and '"navigate"' in sw)
    check.true("network first", sw.index("fetch(e.request)") < sw.index("caches.match(e.request"))
    shell = re.search(r"const SHELL = \[(.*?)\];", sw, re.S).group(1)
    want = ["/nfl/", "/nfl/index.html", "/nfl/app.js", "/nfl/sheet.js", "/nfl/nfl.css", "/nfl/sheet.css", "/site.css"]
    check("shell", re.findall(r'"([^"]+)"', shell), want)
    check.true("no api in shell", "/api/" not in shell)
