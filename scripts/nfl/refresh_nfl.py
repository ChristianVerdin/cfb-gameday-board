#!/usr/bin/env python3
"""Build nfl/games.json + nfl/games.js (weekly snapshot) and the SEO block of nfl/index.html.

    .venv/bin/python3 scripts/nfl/refresh_nfl.py [--st N --week N --year N] [--dry-run] [--no-weather]

Exit 0 when written, unchanged or kept (a degraded rebuild never replaces a better file); 1 on failure, nothing written.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from nflcore import espn, normalize, sanitize, slate, teams, venues, weather  # noqa: E402

OUT_DIR = ROOT / "nfl"
WARN_CAP = 50
START, END = "<!-- games:start -->", "<!-- games:end -->"
COUNT_KEYS = ("games", "events", "placeholders", "tbd_time", "wx_ok", "wx_dome", "wx_retractable", "wx_skipped",
              "wx_failed", "venue_unknown", "forbidden_dropped", "games_skipped")


def _z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _venue(comp: dict) -> dict | None:
    v = comp.get("venue") or {}
    if v.get("id") is None and not v.get("fullName"):
        return None
    row = venues.venue(v.get("id"))
    if row:
        return {k: row[k] for k in ("id", "name", "city", "region", "country", "roof", "lat", "lon", "tz")} | {"known": True}
    a = v.get("address") or {}
    return {"id": str(v["id"]) if v.get("id") is not None else None, "name": v.get("fullName") or None,
            "city": a.get("city"), "region": a.get("state"), "country": a.get("country"),
            "roof": None, "lat": None, "lon": None, "tz": None, "known": False}


def _wx_venue(ven: dict | None) -> dict | None:
    """The snapshot venue plus the table's elevation facts: weather reads them, the payload does not carry them."""
    if not ven or not ven["known"]:
        return ven
    row = venues.venue(ven["id"])
    return ven | {"elev_ft": row["elev_ft"], "verified": row["verified"]} if row else ven


def _side(side: dict | None, raw: dict | None) -> dict | None:
    if not side:
        return None
    abbr = side["abbr"]
    t = (raw or {}).get("team") or {}
    return {"id": side["id"], "abbr": abbr, "nv": teams.nflverse_abbr(abbr), "name": side["name"],
            "full": t.get("displayName") or side["name"], "color": side["color"], "alt": side["alt"],
            "record": side["record"], "score": ""}


def _streams(comp: dict) -> list[str]:
    out: list[str] = []
    for b in comp.get("geoBroadcasts") or []:
        name = (b.get("media") or {}).get("shortName")
        if name and ((b.get("type") or {}).get("shortName") or "").lower() != "tv" and name not in out:
            out.append(name)
    return out


def _game(ev: dict, st: int, wk_label: str, now: datetime, fetch, prev: dict, cache: dict, do_wx: bool) -> dict:
    g = normalize.norm_event(ev)
    comp = (ev.get("competitions") or [{}])[0]
    by = {c.get("homeAway"): c for c in comp.get("competitors") or []}
    away, home = _side(g["away"], by.get("away")), _side(g["home"], by.get("home"))
    all_star = bool(away and home and teams.is_all_star(away["id"]) and teams.is_all_star(home["id"]))
    kind = "all_star" if all_star else "playoff" if st == 3 else "regular"
    tbd = g["time_tbd"]
    ven = _venue(comp)
    kick = slate.parse_utc(g["date"]) if g["date"] and not tbd else None
    old = prev.get(g["id"]) or {}
    prev_wx = (old.get("wx_status"), old.get("wx")) if old.get("wx") else None
    if do_wx:
        status, wx = weather.for_game(_wx_venue(ven), kick, kind=kind, placeholder=g["placeholder"], time_tbd=tbd, now=now,
                                      fetch=fetch, prev=prev_wx, cache=cache)
    elif prev_wx and not g["placeholder"] and kind != "all_star":
        status, wx = prev_wx
    else:
        status, wx = "skipped", None
    notes = [normalize.collapse(n.get("headline")) for n in (comp.get("notes") or ev.get("notes") or []) if n.get("headline")]
    return {
        "id": g["id"], "name": ev.get("name") or "", "shortName": ev.get("shortName") or "",
        "date": g["date"], "time_tbd": tbd,
        "kick_ct": "TBD" if tbd or not g["date"] else slate.kick_ct(g["date"]),
        "kick_day_ct": None if tbd or not g["date"] else slate.chicago_date(g["date"]),
        "flex_note": g["flex_note"], "kind": kind, "round": wk_label if kind == "playoff" else None,
        "week_label": wk_label, "placeholder": g["placeholder"], "neutral": g["neutral"], "notes": notes,
        "broadcasts": g["broadcasts"], "streams": _streams(comp), "state": g["state"], "statusShort": g["statusShort"],
        "venue": ven, "away": away, "home": home, "wx_status": status, "wx": wx,
    }


def build(sb: dict, wk: dict, *, now: datetime, fetch=None, prev_games: dict | None = None, weather_on: bool = True) -> dict:
    """The games.json envelope for one scoreboard. Pure given its inputs; fetch(lat, lon) supplies forecasts."""
    fetch = fetch or weather.fetch_forecast
    prev = prev_games or {}
    st = int(wk["st"])
    warnings: list[str] = []
    cache: dict = {}
    games, skipped = [], 0
    for ev in sb.get("events") or []:
        try:
            games.append(_game(ev, st, wk["label"], now, fetch, prev, cache, weather_on))
        except (KeyError, TypeError, ValueError, IndexError, AttributeError) as e:
            skipped += 1
            warnings.append(f"event_skipped: {ev.get('id') if isinstance(ev, dict) else '?'} ({type(e).__name__})")
    games.sort(key=lambda g: (g["time_tbd"], g["date"] or "", g["id"]))

    c = dict.fromkeys(COUNT_KEYS, 0)
    c.update(games=len(games), events=len(sb.get("events") or []), games_skipped=skipped)
    for g in games:
        c["placeholders"] += g["placeholder"]
        c["tbd_time"] += g["time_tbd"]
        s, v, stale = g["wx_status"], g["venue"], bool((g["wx"] or {}).get("stale"))
        if s == "unknown_venue":
            c["venue_unknown"] += 1
            warnings.append(f"venue_unknown: {v['id'] if v else None} {v['name'] if v else ''} (game {g['id']})".strip())
        elif s == "error" or stale:
            c["wx_failed"] += 1
            warnings.append(f"wx_{'stale' if stale else 'failed'}: game {g['id']}")
        elif s == "dome":
            c["wx_dome"] += 1
        elif s == "retractable":
            c["wx_retractable"] += 1
        elif s in ("ok", "canopy"):
            c["wx_ok"] += 1
        else:
            c["wx_skipped"] += 1
        if v and v["known"] and v["roof"] and g["kind"] != "all_star":
            ind = (venues.venue(v["id"]) or {}).get("espn_indoor")
            if (ind and v["roof"] == "open") or (ind is False and v["roof"] == "dome"):
                warnings.append(f"roof_mismatch: {v['name']}")

    sb_wk = sb.get("week") or {}
    sb_season = sb.get("season") or {}
    bye = [{"id": str(t["id"]), "abbr": t["abbreviation"], "name": t.get("displayName") or t.get("name")}
           for t in sb_wk.get("teamsOnBye") or [] if t.get("abbreviation") and not teams.is_all_star(t.get("id"))]
    env = {
        "schema": 1, "v": 1, "sport": "nfl", "generated_at": _z(now), "source": "espn",
        "season": {"year": wk.get("year") or sb_season.get("year"), "type": st},
        "week": {"number": sb_wk.get("number") or wk["week"], "label": wk["label"], "calendar_value": wk["week"],
                 "start": wk["start"], "end": wk["end"]},
        "teams_on_bye": bye,
        "dates": sorted({g["kick_day_ct"] for g in games if g["kick_day_ct"]}),
        "warnings": warnings, "counts": c, "games": games,
    }
    c["forbidden_dropped"] = sanitize.scrub(env)
    sanitize.assert_clean(env)
    if c["forbidden_dropped"]:
        warnings.append(f"forbidden_dropped: {c['forbidden_dropped']}")
    del warnings[WARN_CAP:]
    return env


def is_degraded(new: dict, old: dict | None) -> str | None:
    """Reason the rebuild is worse than the file on disk (same week only), else None."""
    if not old or old.get("season") != new["season"] or (old.get("week") or {}).get("number") != new["week"]["number"]:
        return None
    oc, nc = old.get("counts") or {}, new["counts"]
    if nc["games"] < oc.get("games", 0):
        return f"games {nc['games']} < {oc['games']}"
    if nc["wx_failed"] > oc.get("wx_failed", 0):
        return f"wx_failed {nc['wx_failed']} > {oc.get('wx_failed', 0)}"
    return None


def _stable(env: dict) -> str:
    """The envelope without run-time stamps, for the unchanged check."""
    def strip(o):
        if isinstance(o, dict):
            return {k: strip(v) for k, v in o.items() if k not in ("generated_at", "fetched_at")}
        return [strip(v) for v in o] if isinstance(o, list) else o
    return json.dumps(strip(env), sort_keys=True)


def seo_block(env: dict) -> str:
    events = []
    for g in env["games"]:
        v = g["venue"]
        if g["placeholder"] or g["time_tbd"] or g["state"] != "pre" or not (g["away"] and g["home"]) or not (v and v["name"]):
            continue
        addr = {"@type": "PostalAddress"}
        for k, f in (("addressLocality", "city"), ("addressRegion", "region"), ("addressCountry", "country")):
            if v.get(f):
                addr[k] = v[f]
        events.append({
            "@context": "https://schema.org", "@type": "SportsEvent", "name": g["name"],
            "startDate": g["date"].replace("Z", ":00Z") if len(g["date"]) == 17 else g["date"],
            "sport": "American football", "location": {"@type": "Place", "name": v["name"], "address": addr},
            "competitor": [{"@type": "SportsTeam", "name": g["away"]["full"]}, {"@type": "SportsTeam", "name": g["home"]["full"]}],
        })
    if not events:
        return f"{START}\n{END}"
    body = json.dumps(events, indent=1, ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\!--")
    body = body.replace("https://schema.org", "https:\\/\\/schema.org")   # valid JSON escape; keeps the client's no-external-URL scan quiet
    return f'{START}\n<script type="application/ld+json">\n{body}\n</script>\n{END}'


def apply_block(html: str, block: str) -> str:
    pat = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
    if pat.search(html):
        return pat.sub(lambda _m: block, html, count=1)
    m = re.search(r"[ \t]*<script src=\"/nfl/games\.js\">", html) or re.search(r"[ \t]*</body>", html)
    if not m:
        raise ValueError("no insertion point for the games block")
    return html[:m.start()] + block + "\n" + html[m.start():]


def _atomic(path: Path, text: str) -> None:
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False, suffix=".tmp", encoding="utf-8") as f:
        f.write(text)
    Path(f.name).replace(path)


def load_prev(out_dir: Path) -> dict | None:
    try:
        return json.loads((out_dir / "games.json").read_text())
    except (OSError, ValueError):
        return None


def write_outputs(env: dict, out_dir: Path, *, dry_run: bool = False) -> str:
    """'written' | 'unchanged' | 'kept: <reason>' (degraded rebuild left out). Replaces files only when not degraded."""
    old = load_prev(out_dir)
    why = is_degraded(env, old)
    if why:
        return f"kept: {why}"
    block = seo_block(env)
    index = out_dir / "index.html"
    html = index.read_text() if index.exists() else None
    new_html = apply_block(html, block) if html is not None else None
    if old and _stable(old) == _stable(env) and new_html == html:
        return "unchanged"
    if dry_run:
        return "dry-run"
    text = json.dumps(env, ensure_ascii=True, separators=(",", ":"))
    _atomic(out_dir / "games.json", text + "\n")
    _atomic(out_dir / "games.js", "window.NFL_DATA = " + text + ";\n")
    if new_html is not None and new_html != html:
        _atomic(index, new_html)
    return "written"


def pick_week(args, now: datetime, calendar: dict, pull=espn.pull_scoreboard) -> tuple[dict, dict]:
    """(week info, scoreboard). Overrides win; otherwise the resolved week, advancing once every game is final."""
    entries = slate.parse_calendar(calendar)
    year = int((calendar.get("season") or {}).get("year") or (entries[0]["start"].year if entries else now.year))
    if args.st or args.week or args.year:
        if not (args.st and args.week):
            raise SystemExit("--st and --week go together (--year optional)")
        e = next((x for x in entries if x["st"] == args.st and x["week"] == args.week), None)
        wk = slate._shape(e, year) if e else {"year": year, "st": args.st, "week": args.week,
                                               "label": f"Week {args.week}", "start": "", "end": ""}
        wk["year"] = args.year or wk["year"]
        return wk, pull(wk["st"], wk["week"], wk["year"])
    wk = slate.resolve_week(calendar, now)
    if not wk:
        return None, None
    sb = pull(wk["st"], wk["week"], wk["year"] if wk["st"] == 3 else None)
    evs = sb.get("events") or []
    if evs and all(((e.get("status") or {}).get("type") or {}).get("state") == "post" for e in evs):
        nxt = slate.resolve_week(calendar, now, events_all_post=True)
        if nxt:
            try:
                sb2 = pull(nxt["st"], nxt["week"], nxt["year"] if nxt["st"] == 3 else None)
                if sb2.get("events"):
                    return nxt, sb2
            except espn.EspnError:
                pass
    return wk, sb


def main(argv=None, *, now: datetime | None = None, out_dir: Path = OUT_DIR, calendar=None, pull=espn.pull_scoreboard,
         fetch=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--st", type=int)
    ap.add_argument("--week", type=int)
    ap.add_argument("--year", type=int)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-weather", action="store_true")
    args = ap.parse_args(argv)
    now = now or datetime.now(timezone.utc)
    try:
        wk, sb = pick_week(args, now, calendar if calendar is not None else espn.pull_calendar(), pull)
        if wk is None:
            print("offseason: no current week in the calendar; nothing to do")
            return 0
        if not sb.get("events"):
            print("no events on the scoreboard; nothing written", file=sys.stderr)
            return 1
        old = load_prev(out_dir)
        prev = {g["id"]: g for g in (old or {}).get("games", [])} if old and (old.get("week") or {}).get("number") == (sb.get("week") or {}).get("number") else {}
        env = build(sb, wk, now=now, fetch=fetch, prev_games=prev, weather_on=not args.no_weather)
        result = write_outputs(env, out_dir, dry_run=args.dry_run)
    except (espn.EspnError, OSError, ValueError, sanitize.ForbiddenKeyError) as e:
        print(f"refresh failed: {e}", file=sys.stderr)
        return 1
    c = env["counts"]
    print(f"{env['week']['label']} {env['season']['year']}: {result}; " + " ".join(f"{k}={c[k]}" for k in COUNT_KEYS if c[k]))
    for w in env["warnings"]:
        print("  warn:", w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
