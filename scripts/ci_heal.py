#!/usr/bin/env python3
"""Rebuild the snapshot once when a run dropped kickoff forecasts, and keep the better result.

A dropped forecast is not a visible gap: impact() runs on wx=None and reports
"Clean outdoor conditions", so the board claims clean weather for a game it knows
nothing about. The 2026-09-17 CI run lost 8 of 75 that way to Open-Meteo TLS
handshake timeouts on the runner, which is flakier than a local machine.

forecast() already retries each call once. This is the whole-run safety net on top,
for the unattended gameday runs nobody is watching.

    python3 scripts/ci_heal.py            # heal if needed; always exits 0
    python3 scripts/ci_heal.py --verify   # exit 1 if the snapshot is still degraded
"""
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ("games.json", "games.js", "index.html", "sitemap.xml")


def failures(path=None):
    try:
        with open(path or os.path.join(ROOT, "games.json")) as f:
            return int((json.load(f).get("counts") or {}).get("forecast_failed", 0))
    except Exception:
        return 0


def main():
    verify = "--verify" in sys.argv
    bad = failures()

    if verify:
        if bad:
            print(f"::warning::snapshot committed with {bad} missing kickoff forecast(s); "
                  f"those games render as 'Clean outdoor conditions'. Rebuild locally and push.")
            return 1
        return 0

    if not bad:
        return 0

    print(f"::warning::{bad} forecast(s) failed; rebuilding once")
    backup = os.path.join(ROOT, ".heal-backup")
    os.makedirs(backup, exist_ok=True)
    for name in FILES:
        src = os.path.join(ROOT, name)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(backup, name))

    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "refresh_week.py")],
                   cwd=ROOT, check=False)

    now = failures()
    # A rebuild can land worse than the first attempt. Only keep it if it actually helped.
    if now > bad:
        print(f"rebuild was worse ({now} vs {bad}); restoring the first result")
        for name in FILES:
            src = os.path.join(backup, name)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(ROOT, name))
        now = bad
    else:
        print(f"rebuild: {bad} -> {now} missing forecast(s)")

    shutil.rmtree(backup, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
