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


def plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def matchup(g):
    # "at" claims a home team; bowls and neutral-site rivalries (Red River, Florida-Georgia) have none
    return f"{g['away']['name']} {'vs' if g.get('neutral') else 'at'} {g['home']['name']}"


def ranked(g):
    return sum(1 for t in (g["away"], g["home"]) if 0 < (t.get("rank") or 99) < 99)


def build(games, label=None):
    m = re.match(r"Week (\d+)\b", label or "")
    name = f"Week {m.group(1)}" if m else ((label or "").split(" · ")[0] or None)
    n = len(games)
    sat = sum(1 for g in games if g.get("kick_ct", "").startswith("Sat"))
    # The text stays up all week, so weather and the marquee only speak about kickoffs still
    # to come, and they count the board's own flags (heat used to be >85F, the board's is 90F).
    ahead = [g for g in games if g.get("gameState") != "post"]
    outdoor = [g for g in ahead if not g.get("indoor")]   # indoor weather is off the board
    flagged = lambda *names: sum(1 for g in outdoor if set(names) & set(g.get("flags") or []))
    rain, heat, wind = flagged("RAIN RISK"), flagged("HOT", "EXTREME HEAT"), flagged("WIND", "HIGH WIND")
    lined = [g for g in ahead if (g.get("odds") or {}).get("spread") is not None]
    lined = [g for g in lined if g.get("kick_ct", "").startswith("Sat")] or lined
    close = None
    if lined:
        lo = min(abs(g["odds"]["spread"]) for g in lined)
        tight = [g for g in lined if abs(g["odds"]["spread"]) <= lo + 0.5]
        # among the tightest lines prefer the game with ranked teams
        tight.sort(key=lambda g: -ranked(g))
        close = tight[0]

    lead = f"{name}: " if name else ""
    if n == 1:      # title-game week: the game is the headline
        g = games[0]
        head = f"{lead}{matchup(g)}, {g.get('kick_ct') or 'kickoff TBD'}."
    else:
        days = []
        for g in sorted(games, key=lambda g: g.get("date") or ""):
            d = (g.get("kick_ct") or "").split(" ")[0]
            if d and d not in days:
                days.append(d)
        # "on Saturday" only when Saturday is the slate; bowl weeks spread over every day
        when = f", {sat} on Saturday" if sat and 2 * sat >= n else (f", {days[0]} to {days[-1]}" if len(days) > 1 else "")
        head = f"{lead}{plural(n, 'game')}{when}."

    trophy = []      # rivalry phrasings, richest first
    rivals = sorted((g for g in ahead if g.get("rivalry")),
                    key=lambda g: (-ranked(g), g.get("group") != "P4/P5", g.get("date") or ""))
    top = rivals[0] if rivals and n > 1 else None
    if top is not None:
        names = [g["rivalry"] for g in rivals]
        if len(rivals) > 1:
            trophy.append(f"{top['rivalry']}: {matchup(top)}, plus {plural(len(rivals) - 1, 'more trophy game')}.")
            for j in (4, 3, 2):
                if len(names) > j:
                    trophy.append(f"{', '.join(names[:j])} and {plural(len(names) - j, 'more trophy game')}.")
                elif len(names) == j:
                    trophy.append(f"Trophy games: {', '.join(names[:-1])} and {names[-1]}.")
        trophy.append(f"{top['rivalry']}: {matchup(top)}.")
    line = ""
    if close is not None and n > 1 and close is not top:   # never name the same game twice
        line = f"{matchup(close)} is a {abs(close['odds']['spread']):g}-point line."
    marquees = []
    for mq in trophy:
        marquees += ([f"{mq} {line}"] if line else []) + [mq]
    if line:
        marquees.append(line)

    wx_full, wx_short = [], ""
    if rain:
        wx_full.append(f"rain risk at {plural(rain, 'kickoff')}")
        wx_short = f"Rain risk at {plural(rain, 'kickoff')}."
    if heat:
        wx_full.append(f"heat flags at {heat}")
    if wind:
        wx_full.append(f"wind at {wind}")
    wx_full = (", ".join(wx_full)).capitalize() + "." if wx_full else ""
    tails = ["Venue, forecast, TV, and posted line for every game.",
             "Forecast, TV, and posted line for every game."]
    if n == 1:
        tails = ["Venue, forecast, TV, and posted line.", "Forecast, TV, and posted line."]

    # Weather is the board's point, so a marquee only wins when the weather still fits beside it.
    weather = [w for w in (wx_full, wx_short) if w]
    for wx_pass in (weather, [""]):
        for mq in marquees + [""]:
            for wx in wx_pass:
                for tail in tails:
                    text = " ".join(p for p in (head, mq, wx, tail) if p)
                    if len(text) <= LIMIT:
                        return text
    return FALLBACK


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="push to App Store Connect via asc")
    ap.add_argument("--version", default=None, help="App Store version string (default: latest editable)")
    args = ap.parse_args()
    with open(os.path.join(ROOT, "games.json")) as f:
        data = json.load(f)
    text = build(data["games"], data.get("week_label"))
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
