#!/usr/bin/env python3
"""Print a Markdown digest of the last snapshot build for $GITHUB_STEP_SUMMARY.

Kept as a file rather than an inline heredoc because a quoted heredoc inside a
YAML block scalar cannot be indented, and the workflow body is.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

with open(os.path.join(ROOT, "games.json")) as f:
    d = json.load(f)

print(f"### {d.get('week_label') or 'slate'} — {d.get('count')} games\n")
counts = d.get("counts") or {}
if counts:
    print("| metric | n |")
    print("| --- | --- |")
    for k, v in sorted(counts.items()):
        print(f"| {k} | {v} |")
for w in d.get("warnings") or []:
    print(f"\n- warn: {w}")
if not counts and not d.get("warnings"):
    print("_no counts recorded_")
