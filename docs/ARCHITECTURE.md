# Architecture

One folder, no build. Three moving parts:

1. A **snapshot** (`games.json` / `games.js`) built once per week by
   `scripts/refresh_week.py`.
2. A **live proxy** (`server.py`, `GET /api/live`) that polls ESPN while games
   are on.
3. A **client** (`index.html` + `app.js`) that renders the snapshot and merges
   live data onto it in place.

## Snapshot vs live

The snapshot is the source of truth for everything that does not change during
a game: venue, city, geo, kickoff-hour weather, flags and impact notes, TV,
gamecast link, tickets, conference grouping, and the opening view of the line.
It is committed to git so the board still renders with no network.

Live data is layered on top by `applyLive()` in `app.js`. Per game it
overwrites: `gameState`, `status`, `statusDetail`, `statusShort`, `period`,
`clock`, `completed`, `situation`, both scores, records (only if the live
record is better than what we have), and `odds`. When odds change, implied
scores, `spread_abs`, and `blowout` are recomputed client-side.

Live never touches weather. If a live weather refresh is ever added it must
call Open-Meteo at the venue lat/lon for the kickoff hour and stamp
`fetched_at`. No fake live weather.

### Cover / total math (`liveMath()`)

```
combined = away + home
margin   = home - away
coverBy  = margin + homeSpread     HOME COVER if > 0, PUSH if 0, AWAY COVER if < 0
overNeed = total - combined        OVER if combined > total
```

`homeSpread` is `odds.spread` as ESPN reports it: negative when the home team is
favored (`EMU -2.5` -> `-2.5`), positive when the home team is the dog
(`OKST +19.5` -> `19.5`). Implied score follows from the same convention:

```
implied.home = (total - homeSpread) / 2
implied.away = (total + homeSpread) / 2
```

Both numbers are the DraftKings line ESPN publishes, re-read on every live
poll. Label it as the ESPN/DK snapshot; it is not a live steam feed.

## ESPN endpoints

All ESPN access goes through `server.py`. The browser never calls ESPN.

Scoreboard, one call per date, tried in order until one returns events:

```
https://site.web.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard?dates=YYYYMMDD&limit=300&groups=80
https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard?dates=YYYYMMDD&limit=300&groups=80
https://cdn.espn.com/core/college-football/scoreboard?xhr=1&render=true&device=desktop&country=us&lang=en&region=us&site=espn&dates=YYYYMMDD&limit=300&groups=80
https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard?dates=YYYYMMDD&limit=300
```

Notes on that feed:

- `groups=80` is FBS. FCS opponents still appear as competitors in FBS games.
- `dates=` is an Eastern-time calendar date. A 7:30 PM CT Saturday kick is a
  Saturday ESPN date; a 10:30 PM PT kick is still that same ESPN date.
- `site.api.espn.com` returns 403 to some clients. The browser-like headers in
  `server.py` get `site.web.api` and `cdn.espn.com` through. If every host
  fails for a date the proxy reports it in `warnings` and keeps going.
- The `cdn.espn.com` route nests events under `content.sbData.events`;
  `events_from()` handles both shapes.
- Records live in `competitors[].records[]`; the overall one has
  `type: "total"` (name `overall`). Early in the season ESPN sometimes serves
  `0-0` there even after games are played, which is why the client refuses to
  overwrite a real record with `0-0`.
- Conference names are not in the scoreboard payload, only `team.conferenceId`.
  `scripts/refresh_week.py` resolves ids through
  `.../college-football/scoreboard/conferences` (FBS groups under parent `80`).
  Anything not in that list is treated as FCS.
- Odds: `competitions[].odds[0]` with `provider`, `details`, `spread`,
  `overUnder`, and nested `pointSpread` / `total` / `moneyline` blocks that
  each carry `close` and `open`. `parse_odds()` in `server.py` flattens that;
  the refresh script reuses the same function so snapshot and live odds have
  the same shape.

### `/api/live` response

```
{ ok, count, fetched_at, warnings[], dates[], games[] }
games[]: { id, state, status, statusDetail, statusShort, period, clock,
           completed, home{id,abbr,score,record,winner}, away{...},
           odds{...}, situation{text,lastPlay,possession,isRedZone} | null }
```

### Closing line capture

ESPN removes `odds` from an event once it is final. `server.py` keeps a
`LineBook`: the last non-null odds seen per game id, seeded from the snapshot
and persisted to `lines.json` (gitignored) whenever it changes. Once a game is
`post` the stored line is frozen and served in its place, so cover math on a
final uses the closing line even after a page reload or server restart. A
server that only started after a game ended serves the snapshot line for it.

### Polling and caching

- The client polls `/api/live` every 30 s (and on the Refresh button).
- `server.py` keeps a per-date cache. A date is re-fetched from ESPN only when
  its cache is older than 20 s. Concurrent requests share one fetch.
- Dates whose games are all `post` are frozen: served from cache, never
  re-fetched for the life of the process.
- Dates with no game in progress and no kickoff within 90 minutes use a 5 min
  TTL instead of 20 s.
- Which dates to poll comes from the snapshot: `games.json` carries a `dates`
  list written by the refresh script. If that is missing the server derives
  Eastern dates from each game's `date`. The old hard-coded Week 1 list is the
  final fallback.

## Open-Meteo snapshot process

Done once per week by `scripts/refresh_week.py`, never live.

1. **Geocode** the venue city:
   `https://geocoding-api.open-meteo.com/v1/search?name=<city>&count=10&language=en&format=json`.
   Results are filtered to `country_code == "US"` and, when ESPN gives a state,
   to the matching `admin1`. First match wins. The result supplies `lat`,
   `lon`, `elev` (meters), `geo_name`, `admin1`, and the venue's IANA timezone.
   `elev_ft = round(elev * 3.28084)`. Cities are deduplicated per run, and any
   venue already present in the existing `games.json` reuses its stored `geo`
   instead of hitting the geocoder again.
2. **Forecast** at the kickoff hour:
   `https://api.open-meteo.com/v1/forecast?latitude=..&longitude=..&hourly=temperature_2m,relative_humidity_2m,precipitation_probability,precipitation,weather_code,wind_speed_10m,wind_gusts_10m,wind_direction_10m,cloud_cover&temperature_unit=fahrenheit&wind_speed_unit=mph&precipitation_unit=inch&timezone=auto&start_date=..&end_date=..`.
   The kickoff UTC instant is shifted by the response's `utc_offset_seconds` to
   get `kick_local`, and the hourly row whose time equals that hour (minutes
   dropped) becomes `wx`. Open-Meteo forecasts 16 days out; beyond that `wx`
   is null and the ESPN text forecast (`espn_weather`) is used for the label.
3. **Derive** the display fields:
   - `wx_label` / `wx_emoji` from the WMO `weather_code` (0 Clear, 1 Mostly
     clear, 2 Partly cloudy, 3 Overcast, 45/48 Fog, 51-57 Drizzle, 61-67 Rain,
     71-77 Snow, 80-82 Showers, 95-99 Thunderstorm). Indoor venues get
     `Indoor climate` / stadium emoji regardless of code.
   - `wind_dir` is the 16-point compass label of `winddir`.
   - `flags[]` and `impact_score`:

     | Condition | Flag | Score |
     | --- | --- | --- |
     | venue `indoor` | `INDOOR` (only flag; level `NONE`) | 0 |
     | temp >= 95 | `EXTREME HEAT` | 0 |
     | 90 <= temp < 95 | `HOT` | 0 |
     | temp <= 32 | `FREEZING` | 1 |
     | 32 < temp <= 40 | `COLD` | 0 |
     | wind >= 20 | `HIGH WIND` | 2 |
     | 15 <= wind < 20 | `WIND` | 1 |
     | pop >= 60 | `RAIN RISK` | 2 |
     | 40 <= pop < 60 | `SHOWERS` | 1 |
     | elev_ft >= 4000 | `ALTITUDE` | 0 |

   - `impact_level`: `NONE` indoor, else `CLEAR` (0), `WATCH` (1), `UNDER` (2+).
   - `impact_notes[]`: heat note when rounded temp >= 93 (`"96° and sunny —
     hydration / rotation game"`, or `"98° heat — early-season pace can stay
     fast; monitor late-game fade"` at 98+), wind note (`"Wind 18 mph — check
     total"`), rain note (`"75% rain — lean under if it arrives"`), cold note,
     elevation note (`"Elevation 6,030 ft — kicking / conditioning note"`).
     If nothing scored and no heat note, `"Clean outdoor conditions"` is added
     first. Indoor: `"Indoor — weather off the board"`.
   - `kick_ct` is the kickoff in America/Chicago, e.g. `Sat 2:30 PM CT`.
   - `group`: `P4/P5` if either team is ACC / Big 12 / Big Ten / SEC / Pac-12,
     else `FCS mix` if either team is FCS, else `G5`.
   - `implied`, `spread_abs`, `blowout` (spread_abs >= 28) from the odds.

## Rebuilding `games.json` for a new week

```
python3 scripts/refresh_week.py                      # Thu..Mon of the current/next slate
python3 scripts/refresh_week.py --start 20260911 --end 20260914
```

- `--start` / `--end` are inclusive ESPN (Eastern) dates, `YYYYMMDD`. With no
  arguments: the Thursday on or before today (Thu-Mon) or the coming Thursday
  (Tue-Wed), through the following Monday. `--start` alone means that one day.
- `--out DIR` writes elsewhere (default: repo root). Useful to diff before
  overwriting.
- Output: `games.json` and `games.js` with the payload
  `{ generated_at, source, week_label, dates[], count, games[] }`, and a
  printed game count.
- Stdlib only (`urllib`, `json`, `zoneinfo`). No third-party packages.
- Rate limits: Open-Meteo is free without a key at about 10k calls/day; a
  full week is roughly 80 forecast calls plus one geocode per distinct city,
  with a short sleep between calls. ESPN is one call per date.
- After running: restart `server.py` (it reads `dates` from `games.json` at
  startup), hard-refresh the page, commit the new snapshot.

The refresh script imports `fetch_json`, `endpoints`, `events_from`, and
`parse_odds` from `server.py` so there is one copy of the ESPN logic.

## Client notes

- Day pills, default day, and time-window buckets are computed from the game
  dates in America/Chicago, so the client has no per-week constants. The
  header kicker reads `week_label` from the payload.
- Stars persist in `localStorage` under `cfb_gameday_stars_v1`.
- The gold implied score is only rendered on pre-game cards, labelled `proj`.
  Once a game is live or final the real score column replaces it.
- `python3 scripts/check.py` runs the offline smoke test; run it after touching
  `impact()`, `kick_ct()`, or `liveMath()`.

## PWA

`manifest.webmanifest` + `icons/` (SVG source, PNGs rendered with `qlmanage`
and `sips`) + `sw.js`. The service worker precaches the shell (`/`,
`index.html`, `app.js`, `games.js`, manifest, icons) and answers every
same-origin GET network-first with cache fallback, so a fresh deploy is picked
up on the next online load and the last snapshot still renders offline. It
never intercepts `/api/*`: live data is network-only and the header shows the
`LIVE ERR` state when the server is unreachable. Bump `VERSION` in `sw.js`
to drop old caches. `app.js` registers the worker on any non-`file:` origin
(localhost counts as secure) and shows a one-time Add-to-Home-Screen hint in
iOS Safari when not already running standalone.

## Hosting (not done)

The proxy binds `127.0.0.1` on purpose: it is an unauthenticated ESPN
fetch-amplifier and must not sit on `0.0.0.0` without auth. Off-LAN options in
cost order: PWA shell (UI only, live data still needs the server), Cloudflare
Tunnel or Tailscale Serve from this Mac on gameday, then a small VPS with nginx
or Caddy in front of the same `server.py` under systemd. Deploy files are not
in the repo yet.
