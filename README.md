# CFB GameDay Board

Local, single-user college football slate board. Built for scanning a Saturday
slate in one place: venue, kickoff-hour weather, DraftKings lines (via ESPN),
implied scores, TV/streams, then live score / cover / total state once games
start.

Dark, mobile-first, ESPN-style cards. No build step, no framework, no accounts.

## No keys, no accounts

- No API keys are required for a local run.
- ESPN's scoreboard feed and Open-Meteo are public and keyless.
- Live mode is a local proxy to ESPN on `127.0.0.1`, not a sportsbook
  connection. Nothing here logs into or scrapes DraftKings, FanDuel, or any
  book.
- Not betting advice.

## Run locally

```
python3 server.py
open http://127.0.0.1:8765/
```

`server.py` is a stdlib `ThreadingHTTPServer` bound to `127.0.0.1:8765`. It
serves the folder and exposes `GET /api/live`, which proxies the ESPN
scoreboard for the slate's dates and returns scores, clock, situation, and
current odds. The page polls it every 30 s and merges the result onto the
snapshot in `games.js`.

Opening `index.html` directly as a file works for the snapshot only. Live mode
needs the server because the browser cannot call ESPN directly.

## File map

| File | Role |
| --- | --- |
| `index.html` | UI shell and all CSS |
| `app.js` | All client logic: filters, views, live merge, cover/total math |
| `games.js` | Snapshot payload as `window.CFB_DATA = {...}` (loaded by the page) |
| `games.json` | Same payload as plain JSON |
| `server.py` | Static server + `/api/live` ESPN proxy with per-date cache |
| `scripts/refresh_week.py` | Rebuilds `games.json` / `games.js` for a new date range |
| `docs/ARCHITECTURE.md` | Snapshot vs live, ESPN endpoints, Open-Meteo process, weekly rebuild |
| `board.html` | Outdated single-file snapshot from the first build. Kept for reference, not source of truth |

## Weekly refresh

Before each Saturday, rebuild the snapshot for the coming slate:

```
python3 scripts/refresh_week.py --start 20260911 --end 20260914
```

That pulls the ESPN scoreboard for each date, geocodes each venue city with
Open-Meteo, pulls the hourly forecast at the local kickoff hour, computes the
derived fields (implied score, weather flags, impact notes, CT kickoff), and
writes both `games.json` and `games.js`. Details in `docs/ARCHITECTURE.md`.

## Cover / total math

Live cards use the posted home spread and the current margin:

```
margin   = home score - away score
coverBy  = margin + homeSpread      (> 0 means HOME is covering)
overNeed = total - (home + away)
```

The spread and total are the DraftKings numbers ESPN publishes in its
scoreboard feed, refreshed with each live poll. They are a snapshot of the
posted line, not a live steam feed.

## Limitations

- ESPN's scoreboard is an undocumented public feed. It 403s some hosts and
  changes without notice. `server.py` falls back across three ESPN hosts.
- Weather is the Open-Meteo forecast for the venue city at the kickoff hour,
  captured when the snapshot was built. It is not refreshed live.
- Geocoding is by city name, not stadium coordinates. Elevation comes from the
  geocoder, so it is the city's elevation, not the field's.
- Odds come only from what ESPN exposes (DraftKings). No sportsbook scraping.
- Times display in America/Chicago regardless of venue.
- Localhost only. See `docs/ARCHITECTURE.md` for hosting notes.

## Snapshot note

The committed `games.json` / `games.js` is the Week 1 2026 slate
(Fri Sep 4 to Mon Sep 7, 2026), generated 2026-09-04 21:10 UTC. Lines and
weather in that file are as of that moment. Run the refresh script for any
later week.

## Secrets policy

There are none. The repo must never contain `.env` files, API keys, AWS
credentials, sportsbook cookies, or model-provider tokens. `.gitignore` blocks
the usual filenames; scan the tree before adding anything new.

## License

MIT. See `LICENSE`.
