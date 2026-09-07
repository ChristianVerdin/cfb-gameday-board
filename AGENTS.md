# AGENTS.md — CFB GameDay Board automation map

Every process that runs without a human, with file paths, schedule, cost, and
what it must never do. There are **no LLM agents** in this project; nothing here
calls Claude, Grok, or any model. Rules: `CLAUDE.md`. Live state: `CONTEXT.md`.

---

## 1. Snapshot refresh bot (GitHub Actions)

**File:** `.github/workflows/refresh.yml` → `scripts/refresh_week.py` → `scripts/check.py`
**Schedule:** `0 2 * * 5` (Thu 9 PM CT) and `0 14 * * 6` (Sat 9 AM CT), plus `workflow_dispatch` with optional `start`/`end` (YYYYMMDD).
**Does:** pulls ESPN scoreboard for Thu..Mon, geocodes venues and pulls kickoff-hour weather from Open-Meteo, derives flags/impact/implied/group/kick_ct, writes `games.json` + `games.js`, commits as `gameday-bot` when changed. Vercel deploys the push.
**Cost:** $0 (public Actions minutes on a public repo; ESPN and Open-Meteo are keyless).
**Guardrails:** carries the prior snapshot's line forward when ESPN has none (never strips lines mid-slate); exits clean with no commit in the offseason; `check.py` must pass before the commit.
**Manual trigger:** `gh workflow run refresh.yml`.

## 2. Live proxy, hosted (Vercel function)

**File:** `api/live.py` (imports `pull_date`, `live_payload`, `parse_dates` from `server.py`)
**Trigger:** browser polls `GET /api/live?dates=…` every 30 s while any game on those dates is not final.
**Cache:** `Cache-Control: public, max-age=0, s-maxage=20, stale-while-revalidate=40` → Vercel CDN serves all viewers from one ESPN pull per 20 s per URL.
**Cost:** Vercel Pro plan already paid; function invocations are a rounding error at this traffic.
**Guardrails:** max 5 dates per request, `YYYYMMDD` validated; 502 with `no-store` on ESPN failure; no state, no line book (closing lines live in the browser's localStorage via `chooseOdds()` in `app.js`).

## 3. Live proxy, local (`server.py`)

**Run:** `python3 server.py` → 127.0.0.1:8765. `PORT` env overrides the port; `BIND` stays loopback.
**Does:** static files + `/api/live` with a per-date in-process cache (20 s, 5 min when idle, frozen once all games on a date are final) and a `LineBook` persisted to `lines.json`.
**Guardrails:** never bind 0.0.0.0 on a public network; it is an unauthenticated ESPN fetch-amplifier.

## 4. Vercel Git integration

**Trigger:** every push to `main` on `ChristianVerdin/cfb-gameday-board`.
**Does:** production deploy to cfbgameday.app. Preview deploys for other branches sit behind Vercel Authentication.
**Config:** `vercel.json` (function, headers, www→apex redirect, cleanUrls), `.vercelignore`.

## 5. Service worker (`sw.js`)

**Runs in:** every visitor's browser after first load.
**Does:** precaches the UI shell (`/`, `index.html`, `site.css`, `app.js`, `games.js`, manifest, icons, privacy, support); network-first with cache fallback for same-origin GETs.
**Guardrails:** never intercepts `/api/*`. Bump `VERSION` when the shell changes.

## 6. Gameday tunnel helper (manual, fallback only)

**File:** `scripts/tunnel.sh` → `cloudflared tunnel --url http://127.0.0.1:8765`
**When:** only if the hosted site is down. Random URL, Mac must stay awake, Ctrl+C ends it.

## 7. iOS release script (manual, one command)

**File:** `scripts/release_ios.sh` + `ios/ExportOptions.plist`
**Does:** bumps the build number in `ios/project.yml`, `xcodegen generate`, Release archive, App Store IPA export, `altool --validate-app`, then `asc publish appstore` (upload, wait for processing, find or create the App Store version, apply `ios/metadata/version/<version>/en-US.json` if present, attach the build). `--submit` adds `--submit --confirm` and sends the version to review. Without `asc` on PATH it falls back to `altool --upload-app` and the build is attached by hand.
**Auth:** `asc` profile `cfbgameday` in `~/.asc/config.json` (key FQRRWFFM28, App Manager); altool fallback reads `ASC_KEY_ID` / `ASC_ISSUER_ID` from `~/.config/cfb-gameday.env`; `.p8` in `~/.appstoreconnect/private_keys/`.
**Cost:** $0. **Guardrails:** never commits the key; `*.p8` is gitignored; `--no-upload` stops at the IPA; `--submit` is the only path that submits, and it is never the default.

## 8. iOS tab smoke test (manual, simulator)

**File:** `scripts/ios_tab_check.sh` (needs AXe: `brew install cameroncooke/axe/axe`, a booted simulator, and a Debug simulator build in `ios/build/DerivedData`).
**Does:** installs and launches the app, taps Board, Live, Board, Starred, Live, About, Board, Starred, screenshots each, and fails if a web tab's header band has no bright pixels (the blank-revisit bug of 2026-09-07). Run it before every iOS upload.

## 9. App Review status watch (session-scoped, optional)

**Command:** a shell loop around `asc review status --app 6809035228` every 10 min that exits when the version state changes; started from a Claude Code session as a background task when a submission is pending. Nothing is scheduled on the machine; nothing notifies (no Telegram chat ID). `asc status --app 6809035228 --watch` is the equivalent one-liner.

## Not automated, on purpose

- Release after approval, pricing, age rating, screenshots, and replying to App Review messages (cv, in App Store Connect). Submitting is scripted (`release_ios.sh --submit`, or `asc review submissions-submit`) but only run on cv's say-so.
- Telegram alerts: no chat ID is declared for this project; do not send.
- Player-prop posting: lives in `~/projects/sportsbettingml_full_package`, never here.
