# CLAUDE.md — cfb-gameday

Local CFB slate board for Saturdays: venue, kickoff-hour weather, DK lines via
ESPN, implied scores, TV, then live cover/total state. Owner: cv
(@SportsBettingML). Public repo: https://github.com/ChristianVerdin/cfb-gameday-board

## Session start
1. Read this file, then `README.md`. `docs/ARCHITECTURE.md` when touching
   data flow, ESPN, or weather.
2. `git status` and `git log --oneline | head -5`.
3. Check whether `server.py` is already running on 8765 (`lsof -nP -iTCP:8765`).
   On a game day, do not kill it. Test changes on another port: `PORT=8766 python3 server.py`.

## Run
```
python3 server.py                 # http://127.0.0.1:8765/  (live mode needs this)
python3 scripts/refresh_week.py   # rebuild games.json/games.js for the next Thu..Mon
python3 scripts/check.py          # offline smoke test, run after touching rules or liveMath
scripts/tunnel.sh                 # gameday Cloudflare quick tunnel, prints the https URL
```
Restart `server.py` after a refresh; it reads `dates` from `games.json` at startup.

## Hosted
- Vercel project `cfb-gameday-board` (team christian-verdins-projects), deploys on push to `main`.
  Production: https://cfbgameday.app (alias cfb-gameday-board.vercel.app). `docs/DEPLOY.md`.
- Snapshot refresh is a GitHub Action (Thu 9 PM CT, Sat 9 AM CT). Manual: `gh workflow run refresh.yml`.
- `api/live.py` is the hosted proxy; keep its payload identical to `server.py`'s. Both share `live_payload()`.

## Files
- `index.html` UI + CSS. `app.js` all client logic. Dark ESPN-style cards; keep it.
- `games.js` / `games.json` snapshot payload (`window.CFB_DATA`). Committed per week.
- `server.py` static server + `/api/live` ESPN proxy, per-date cache, closing-line book (`lines.json`, gitignored).
- `scripts/refresh_week.py` weekly snapshot builder. `scripts/check.py` smoke test.
- `manifest.webmanifest`, `sw.js`, `icons/` PWA. Shell-only cache; `/api/*` never cached. Bump `VERSION` in `sw.js` when the shell changes.
- `ios/`: edit `project.yml` and the Swift sources, then `cd ios && xcodegen generate`. The `.xcodeproj` is generated and gitignored. Listing copy: `ios/APP_STORE.md`. Bundle `com.hoynelabs.cfbgameday`, Hoyne Labs LLC.
- `privacy.html`, `support.html`, `site.css`: public pages App Review links to; keep them accurate when data sources change.

## Product rules
- Times in America/Chicago everywhere.
- Cover math: `coverBy = (home - away) + homeSpread`, HOME COVER if > 0. Label
  lines as the ESPN/DK snapshot, never as live steam.
- Implied score is gold and labelled `proj`; never show it on a live or final card.
- No fake live weather. A weather refresh must hit Open-Meteo at venue lat/lon
  for the kick hour and stamp `fetched_at`.
- Do not scrape DraftKings/FanDuel HTML. Odds come only from ESPN's feed.
- No player-prop posting here. That lives in `~/projects/sportsbettingml_full_package`
  (`check_prop` gate, `post_hit.py`). Do not copy it in.
- Stdlib only. Ask before adding any dependency.

## Working conventions
- If a "known issues" list is given with a task, fix those before new work.
- Commit after each completed step. Run `scripts/check.py` before committing rule changes.
- Public repo: never commit `.env`, keys, cookies, tokens, Apple `.p8` / provisioning profiles, Vercel tokens, `.vercel/`. Scan the tree before `git add`.
- Never rebuild the snapshot in a way that drops lines: `refresh_week.py` carries the prior line forward when ESPN has none. Keep that.
- Hosting is Vercel; `deploy/` holds self-host drafts only. Never deploy to EC2
  without "deploy to EC2" and a host. App Store upload, signing, and submission
  are cv's steps in Xcode; do not attempt them from the CLI.
- No sportsbook deep links, affiliate params, accounts, or push. Keep copy as
  scores / venue / weather / posted lines, never a wagering tool.
  The live proxy stays on 127.0.0.1 or behind auth; it is an ESPN fetch-amplifier.
- Telegram: this project has no chat ID declared. Ask before sending anything.
