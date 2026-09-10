#!/usr/bin/env python3
"""Weekly App Store promotional text from games.json.

    python3 scripts/promo_text.py            # print the text
    python3 scripts/promo_text.py --apply    # also push it with the asc CLI

Promotional text is the one listing field Apple lets you change without a
review, so it doubles as a weekly billboard. Limit is 170 characters.
"""
import argparse, json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_ID = "6809035228"
LIMIT = 170
FALLBACK = ("College football Saturdays on one screen: venue, kickoff weather, TV, "
            "posted lines, and live cover and total state for every FBS game.")


def build(games, week):
    n = len(games)
    sat = sum(1 for g in games if g.get("kick_ct", "").startswith("Sat"))
    rain = sum(1 for g in games if ((g.get("wx") or {}).get("pop") or 0) >= 50)
    heat = sum(1 for g in games if (g.get("temp") or 0) > 85)
    wind = sum(1 for g in games if ((g.get("wx") or {}).get("wind") or 0) >= 15)
    lined = [g for g in games if (g.get("odds") or {}).get("spread") is not None]
    close = None
    if lined:
        lo = min(abs(g["odds"]["spread"]) for g in lined)
        tight = [g for g in lined if abs(g["odds"]["spread"]) <= lo + 0.5]
        # among the tightest lines prefer the game with ranked teams
        tight.sort(key=lambda g: -sum(1 for t in (g["away"], g["home"]) if t.get("rank")))
        close = tight[0]

    head = f"Week {week}: {n} games, {sat} on Saturday." if week else f"{n} games, {sat} on Saturday."
    marquee = ""
    if close is not None:
        marquee = (f"{close['away']['name']} at {close['home']['name']} is a "
                   f"{abs(close['odds']['spread']):g}-point line.")
    wx_full, wx_short = [], ""
    if rain:
        wx_full.append(f"rain risk at {rain} kickoffs")
        wx_short = f"Rain risk at {rain} kickoffs."
    if heat:
        wx_full.append(f"heat flags at {heat}")
    if wind:
        wx_full.append(f"wind at {wind}")
    wx_full = (", ".join(wx_full)).capitalize() + "." if wx_full else ""
    tails = ["Venue, forecast, TV, and posted line for every game.",
             "Forecast, TV, and posted line for every game."]

    candidates = []
    for wx in (wx_full, wx_short, ""):
        for mq in (marquee, ""):
            for tail in tails:
                candidates.append(" ".join(p for p in (head, mq, wx, tail) if p))
    fits = [c for c in candidates if len(c) <= LIMIT]
    return max(fits, key=len) if fits else FALLBACK


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="push to App Store Connect via asc")
    ap.add_argument("--version", default=None, help="App Store version string (default: latest editable)")
    args = ap.parse_args()
    with open(os.path.join(ROOT, "games.json")) as f:
        data = json.load(f)
    m = re.search(r"Week (\d+)", data.get("week_label") or "")
    text = build(data["games"], m.group(1) if m else None)
    print(text)
    print(f"[{len(text)}/{LIMIT} chars]", file=sys.stderr)
    if not args.apply:
        return
    cmd = ["asc", "apps", "info", "edit", "--app", APP_ID, "--locale", "en-US",
           "--platform", "IOS", "--promotional-text", text]
    if args.version:
        cmd += ["--version", args.version]
    env = dict(os.environ, ASC_TELEMETRY_DISABLED="1")
    subprocess.run(cmd, check=True, env=env)


if __name__ == "__main__":
    main()
