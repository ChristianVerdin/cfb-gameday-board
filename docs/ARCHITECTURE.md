# Architecture

One folder, no build. Three moving parts, plus a hosted copy on Vercel that
runs the same files with `api/live.py` in place of `server.py`:

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

### Hosted variant (Vercel)

`api/live.py` is a stateless Python function that imports `pull_date`,
`live_payload`, and `parse_dates` from `server.py`. It sets
`Cache-Control: public, max-age=0, s-maxage=20, stale-while-revalidate=40`, so
Vercel's CDN answers every viewer from one ESPN pull per 20 s per URL. There is
no in-process cache and no line book on the function.

The client sends `?dates=` built by `liveDatesFor()`: the snapshot's ESPN
dates minus any date whose games are all final. That replaces the local
server's frozen-date logic and keeps the CDN key stable.

Closing lines on the hosted site live in the browser: `chooseOdds()` in
`app.js` keeps the last non-null odds per game in `localStorage`
(`cfb_gameday_lines_v1`) and uses them when ESPN nulls the odds on a final.
`scripts/refresh_week.py` applies the same rule at build time, carrying the
prior snapshot's line forward when ESPN has none, so a mid-slate rebuild never
strips lines.

`#live`, `#starred`, `#all` in the URL set the filters (`hashFilters()`); the
iOS app's tabs use that.

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
  Eastern dates from each game's `date`. `fallback_dates()` is the final
  fallback: it computes Thu..Mon of the current or next slate rather than a
  frozen list, which had silently stayed on Week 1's dates. It deliberately
  duplicates `refresh_week.default_dates` instead of importing it — `vercel.json`
  excludes `scripts/**` from the `api/live.py` bundle, so that import would 502
  on every cold start.
- The `LineBook` is built lazily via `line_book()`. It used to be constructed at
  module import, which meant every Vercel cold start read a `lines.json` the
  bundle excludes and reparsed `games.json` to seed a book the function never
  uses or flushes.

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
   The call has a 10 s timeout and **one retry**, drawn from a whole-run budget
   of 20 so a bad Open-Meteo day cannot blow the Action's 20-minute cap. The
   retry exists because a dropped forecast is not a visible gap: `impact()` then
   runs on `wx=None` and reports "Clean outdoor conditions", so a 98° game
   silently loses its heat flag. A 2026-09-17 CI run lost 8 of 75 forecasts to
   TLS handshake timeouts exactly this way.
3. **Derive** the display fields:
   - `wx_label` / `wx_emoji` from the WMO `weather_code` (0 Clear, 1 Mostly
     clear, 2 Partly cloudy, 3 Overcast, 45/48 Fog, 51-57 Drizzle, 61-67 Rain,
     71-77 Snow, 80-82 Showers, 95-99 Thunderstorm). Indoor venues get
     `Indoor climate` / stadium emoji regardless of code.
   - `wind_dir` is the 16-point compass label of `winddir`.
   - `flags[]`, `impact_score` and `under_score`. Two scores, because one number
     was doing two jobs: `impact_score` is how much weather is in the game, and
     `under_score` is only the part that historically suppresses scoring. Heat
     counts toward the first and not the second, so a calm 102° game can never
     render as `UNDER` — which would contradict the board's own heat note that
     early-season pace stays fast.

     | Condition | Flag | `impact_score` | `under_score` |
     | --- | --- | --- | --- |
     | venue `indoor` | `INDOOR` (only flag; level `NONE`) | 0 | 0 |
     | temp >= 95 | `EXTREME HEAT` | 2 | 0 |
     | 90 <= temp < 95 | `HOT` | 1 | 0 |
     | temp <= 32 | `FREEZING` | 2 | 2 |
     | 32 < temp <= 40 | `COLD` | 1 | 1 |
     | wind >= 20 | `HIGH WIND` | 2 | 2 |
     | 15 <= wind < 20 | `WIND` | 1 | 1 |
     | pop >= 60 | `RAIN RISK` | 2 | 2 |
     | 40 <= pop < 60 | `SHOWERS` | 1 | 1 |
     | elev_ft >= 4000 | `ALTITUDE` | 0 | 0 |

   - `impact_level`: `NONE` indoor, else `UNDER` when `under_score >= 2`,
     `WATCH` when either score is non-zero, else `CLEAR`. A heat-only game is
     therefore `WATCH`: never `CLEAR`, never `UNDER`. The weather desk in
     `app.js` filters its directional list on `under_score > 0`, so hot games
     appear only in its dedicated heat section.
   - `impact_notes[]`: three heat bands, all nested under the `temp >= 90` flag
     branch so a note can never fire without its flag (the notes key off rounded
     temp while the flags key off raw temp, so 89.6° was otherwise one rounding
     away from a note with no flag) — `"101° heat — early-season pace can stay
     fast; monitor late-game fade"` at 98+, `"96° and sunny — hydration /
     rotation game"` at 93-97, `"90° at kick — heat, hydration and rotation, not
     a total read"` at 90-92. Then wind (`"Wind 18 mph — check total"`), rain
     (`"75% rain — lean under if it arrives"`), cold, and elevation
     (`"Elevation 6,030 ft — kicking / conditioning note"`). If nothing scored
     and there are no notes, `"Clean outdoor conditions"` is added first.
     Indoor: `"Indoor — weather off the board"`.
   - `kick_ct` is the kickoff in America/Chicago, e.g. `Sat 2:30 PM CT`.
   - `group`: `P4/P5` if either team is ACC / Big 12 / Big Ten / SEC / Pac-12,
     else `FCS mix` if either team is FCS, else `G5`.
   - `conf_game` / `conf_label`: ESPN states this directly as
     `competitions[0].conferenceCompetition`, already in the scoreboard payload,
     so it costs no extra call. It also gets the hard cases right — Notre Dame is
     Independent (id 18) but plays ACC opponents, and ESPN correctly says it is
     not a conference game. The derived rule (same real `conferenceId`, excluding
     18-vs-18 and any FCS side) is only a fallback for the cdn payload shape,
     which can omit the key. `conf_label` is the conference name, else null.
   - `implied`, `spread_abs`, `blowout` (spread_abs >= 28) from the odds.

4. **Enrich** each game from ESPN's per-game summary, as a separate pass after
   the build loop — never inside `build_game()`, where an exception drops the
   game entirely and a detail lookup must never cost a fixture.
   `https://site.web.api.espn.com/apis/site/v2/sports/football/college-football/summary?event=<id>`
   (the `site.api.espn.com` host 403s on this path; `site.web.api` does not).
   8 s timeout, and a circuit breaker abandons the pass after 5 consecutive
   failures — 75 hanging calls at the default 20 s would exceed the Action's
   20-minute cap. Writes one `enrich` block per game:

   | Key | Source | Note |
   | --- | --- | --- |
   | `at` | — | UTC stamp of the lookup |
   | `surface` | `gameInfo.venue.grass` | `"grass"` / `"turf"` |
   | `capacity` | `gameInfo.venue.capacity` | null in practice so far |
   | `attendance` | `gameInfo.attendance` | post-game only |
   | `predictor` | `predictor.{home,away}Team.gameProjection` | **stored, never rendered** |
   | `ats` | `againstTheSpread[].records` | empty until mid-season |
   | `conf_record` | `standings` entry stat `vsconf` | |

   A fresh null never overwrites a stored value, because ESPN drops `attendance`
   and ATS records intermittently. `--no-enrich` skips the pass; it defaults on.
   `predictor` is a win probability: rendering it beside the gold implied score
   would drift toward a wagering read, so it stays stored only. `lastFiveGames`
   is deliberately not extracted — its entries are contaminated with prior-season
   games, so a "form" string built from it in September is silently wrong.

5. **Write the generated HTML.** `write_seo()` replaces the content between
   `<!-- games:start -->` and `<!-- games:end -->` in `index.html` with a
   schema.org `@graph` of one `SportsEvent` per unplayed game, and rewrites the
   kicker div with `week_label` (or a neutral string, since `week_label()` can
   return None). `startDate` is venue-local with a real offset derived from
   `wx.utc_offset_seconds`, never the raw UTC. TV uses
   `publication` → `BroadcastEvent` → `publishedOn`. `sitemap.xml` gets
   `<lastmod>` from `generated_at`. Runs only when `--out` is the repo root;
   `--seo-only` rebuilds just this from the committed `games.json`, no network.
   **No odds, spread, total, implied, offers or potentialAction, ever** — this
   must never read as a sportsbook, and `check.py`'s `test_jsonld` enforces it
   with a forbidden-substring scan.

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
- `--no-enrich` skips the per-game ESPN summary pass; `--seo-only` rebuilds only
  the generated block in `index.html` and `sitemap.xml` from the committed
  `games.json`, with no network at all.
- Output: `games.json` and `games.js` with the payload
  `{ generated_at, source, week_label, dates[], warnings[], counts{}, count,
  games[] }`, and a printed game count. It also rewrites `index.html` and
  `sitemap.xml` when writing to the repo root, so all four files belong in the
  same commit — the refresh Action adds and diffs all four.
- `warnings[]` used to hold only whole-date scoreboard failures, so an empty list
  was not evidence of a clean build: a geocode failure produced no forecast, and
  `impact()` then reported "Clean outdoor conditions" for a game it knew nothing
  about. It now records geocode, forecast, per-game skip and enrichment failures
  too (capped at 50), and `counts{}` carries `geocode_failed`, `forecast_failed`,
  `forecast_missing`, `games_skipped`, `lines_carried`, `dates_failed`,
  `fallback_url_used`, `no_groups_fallback`, `enriched`, `enrich_failed`, plus
  `games` and `events`.
- The fourth scoreboard URL above has no `groups=80`, so a date served by it
  would carry the whole D1 slate. `pull()` reports which URL answered, and a
  groups-less result is refiltered to FBS rather than rejected — rejecting would
  lose a whole slate day on a bad ESPN afternoon.
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
- The header kicker also exists as static text in `index.html`, rewritten by the
  refresh script, so a crawler and the pre-hydration paint see the real week.
- Stars persist in `localStorage` under `cfb_gameday_stars_v1`. The closing-line
  book under `cfb_gameday_lines_v1` is pruned on load to ids in the current
  snapshot — its only reader is `chooseOdds(lineBook[g.id], …)`, so anything else
  is dead weight that would accumulate across a season. Stars are deliberately
  never pruned: those are user intent.
- The gold implied score is only rendered on pre-game cards, labelled `proj`.
  Once a game is live or final it is suppressed entirely, not dimmed, on all five
  surfaces that read it — card, lines sheet, blowout board, Copy-post text and
  CSV — via `started()`. The card keeps an empty placeholder div because `.trow`
  is a four-column grid. The CSV keeps all 16 headers and emits empty cells, never
  an em dash, which would break numeric parsing downstream.
- Filters include `Conf game`, an independent toggle rather than a value in the
  conference selector, so "SEC conference games" and "P4 non-conference" stay
  expressible. `isConfGame()` falls back to deriving from `conferenceId` when the
  snapshot predates `conf_game`.
- `python3 scripts/check.py` runs the offline smoke test; run it after touching
  `impact()`, `kick_ct()`, or `liveMath()`. It checks the impact table, the time
  helpers, `fallback_dates()`, five `app.js` functions extracted as source text
  and run under node, the shape of **every** game in the snapshot (it used to
  sample the first five, which is how a half-broken build could pass), the
  structured-data block, and run health. The health gate is deliberately lenient
  because it runs before the Action's commit and that commit also carries the odds
  refresh: it fails only above 25% missing forecasts, warns above 10%, and only
  inside Open-Meteo's ~16-day horizon. An enrichment failure never fails it.

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
fetch-amplifier and must not sit on `0.0.0.0` without auth. Options, cost
order, with the draft config files, are in `docs/DEPLOY.md` and `deploy/`.
