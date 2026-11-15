#!/usr/bin/env python3
"""Offline checks for the NFL board. No network.

    .venv/bin/python3 scripts/check_nfl.py            # every suite
    .venv/bin/python3 scripts/check_nfl.py desk venues # named suites only

Each module in scripts/nfl/checks/ defines suites as functions named test_*
taking one argument, a Check. Fixtures live in scripts/fixtures/nfl/.
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "scripts" / "fixtures" / "nfl"
sys.path.insert(0, str(ROOT))


class Check:
    def __init__(self):
        self.fails: list[str] = []
        self.count = 0
        self.suite = ""

    def __call__(self, name: str, got, want):
        self.count += 1
        if got != want:
            self.fails.append(f"{self.suite}: {name}: got {got!r}, want {want!r}")

    def true(self, name: str, cond, detail=""):
        self.count += 1
        if not cond:
            self.fails.append(f"{self.suite}: {name}" + (f" ({detail})" if detail else ""))

    @staticmethod
    def fixture(name: str):
        return json.loads((FIXTURES / name).read_text())


def main(argv: list[str]) -> int:
    chk = Check()
    wanted = set(argv)
    for path in sorted((ROOT / "scripts" / "nfl" / "checks").glob("*.py")):
        if path.name.startswith("_"):
            continue
        mod = importlib.import_module(f"scripts.nfl.checks.{path.stem}")
        for name in sorted(n for n in dir(mod) if n.startswith("test_")):
            suite = name[5:]
            if wanted and suite not in wanted and path.stem not in wanted:
                continue
            chk.suite = f"{path.stem}.{suite}"
            try:
                getattr(mod, name)(chk)
            except Exception as e:  # noqa: BLE001 - a crashing suite is a failure, not an abort
                chk.fails.append(f"{chk.suite}: raised {type(e).__name__}: {e}")
    if chk.fails:
        print("\n".join("FAIL " + f for f in chk.fails))
        print(f"{len(chk.fails)} failed, {chk.count} checks")
        return 1
    print(f"ok ({chk.count} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
