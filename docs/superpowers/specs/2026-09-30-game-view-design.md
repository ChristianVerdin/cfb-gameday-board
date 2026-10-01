# Game view — design (2026-09-30)

Approved by cv in session 2026-09-30.

## Goal
Tap a live or final game and see what happened in it, without leaving the board:
scoring plays, team box score, player leaders, drives, and ESPN's win-probability
line. Information display only; adds no line, odds, or cover content.

## Decisions
- Entry: a **Game** button on live and final cards opens a bottom sheet over the
  board. URL becomes `#game/<espn id>` (shareable; Back closes it). Pre-kick cards
  get no button; a shared link to a pre-kick game says the view opens at kickoff.
- Tabs: Scoring · Box · Leaders · Drives. Drives carries a small inline-SVG line
  of home win %, labelled "ESPN win probability", current value at the end.
- Live games refresh with the board's 30 s poll while the sheet is open.
- iOS needs no new build: native tabs set `#live` etc., which closes the sheet.

## Backend
- `server.game_payload(summary)` trims ESPN's ~450 KB summary to a few KB:
  `{id, state, linescores{away,home}, scoring[], box{rows[[label, away, home]]},
  leaders{away[], home[]}, drives[], current, winprob{points[], quarters[]}}`.
  Never copies `odds`, `pickcenter`, `againstTheSpread`, `predictor`.
- `server.pull_summary(id)` hits the summary endpoint (two hosts, same headers).
- `/api/game?id=` on `server.py` (per-id cache: 20 s live, frozen when final) and
  `api/game.py` on Vercel (`s-maxage` 20 s live, 3600 s final, 300 s pre).
- `id` must be 6–12 digits, else 400: the endpoint must not be a general fetcher.

## Client
- `app.js`: `esc()` for every ESPN string in the sheet, `openGame(id)`,
  `renderGame()`, `winprobSvg()`; `applyHash()` routes `#game/<id>`.
- `site.css`: `.gsheet` bottom sheet, tab pills reuse `.fbtn`.
- `sw.js` VERSION bump (shell changed). `/api/*` stays network-only.

## Errors
ESPN failure → sheet shows "Couldn't load game detail" plus Retry; the board is
unaffected. Missing sections (e.g. no drives yet) render "Nothing yet".

## Tests (`scripts/check.py`, offline)
- Fixture `scripts/fixtures/summary_final.json` (trimmed real summary) through
  `game_payload`: shape, counts, quarter marks, and no wagering keys or terms in
  the JSON.
- `api/game.py` exists and is in `vercel.json` functions; id validator rejects
  non-numeric ids.
- node: `gameHash()` parses `#game/123456` and rejects junk.
