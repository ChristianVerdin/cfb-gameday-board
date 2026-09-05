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
| `scripts/check.py` | Offline smoke test: flag table, CT kickoff, cover/total math |
| `manifest.webmanifest`, `sw.js`, `icons/` | PWA: install metadata, UI-shell service worker, home-screen icons |
| `docs/DEPLOY.md`, `deploy/` | Hosting notes plus Caddyfile, nginx.conf, systemd unit drafts. Nothing deployed |

## Install on iPhone (PWA)

The board is a Progressive Web App: a manifest, home-screen icons, and a
service worker that caches only the UI shell. Live scores are never cached.

1. Serve it somewhere Safari on the phone can reach. On the same Wi-Fi that is
   `http://<your-mac-ip>:8765/` only if you change the bind address in
   `server.py`; off-LAN needs a tunnel (Cloudflare Tunnel or Tailscale Serve).
   The default `127.0.0.1` bind is deliberate, see Limitations.
2. Open the URL in Safari (not Chrome; iOS only installs PWAs from Safari).
3. Tap Share, then **Add to Home Screen**, then Add.
4. Launch it from the icon. It opens full-screen with the dark status bar,
   remembers stars, and shows the last snapshot if the server is unreachable
   (the header says so instead of LIVE).

The page shows a one-time Add-to-Home-Screen hint in Safari on iOS; dismiss
with the ×. Ship a new shell by bumping `VERSION` in `sw.js`.

Fastest way to get the phone on it from anywhere, on gameday only:

```
brew install cloudflared
scripts/tunnel.sh        # starts server.py if needed, prints the https URL, Ctrl+C ends both
```

Stable hostnames, Tailscale, and an always-on box are in `docs/DEPLOY.md`.

### iPhone QA checklist

Test portrait on a 390 to 430 wide phone (iPhone 13 through 16 Pro Max).

- No horizontal page scroll. Chip rows scroll; the page must not.
- Dynamic Island / notch does not cover the week label or the LIVE timestamp.
- Tapping the search field does not zoom the page (input is 16px).
- Chips, star, Copy, Maps, ESPN all hit on the first tap (44pt targets).
- Live cover line wraps; the white score never collides with the dim `proj`
  number.
- Add to Home Screen opens standalone with no Safari chrome and a dark
  status bar.
- Airplane mode: the shell and last snapshot load, the header shows a live
  error, no fake scores.

## Weekly refresh

Before each Saturday, rebuild the snapshot for the coming slate:

```
python3 scripts/refresh_week.py
```

With no arguments it targets Thursday through Monday of the current or next
slate (Tuesday and Wednesday roll forward). Pass `--start 20260911 --end
20260914` to pick dates. Rerun it Saturday morning to refresh the forecast to
same-day accuracy, then restart `server.py`.

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
- Localhost only. See `docs/DEPLOY.md` for tunnels and hosting.

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
