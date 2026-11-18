# Deploy

Live: https://cfbgameday.app (www redirects to the apex). Vercel project
`cfb-gameday-board` on team `christian-verdins-projects`, GitHub-connected:
every push to `main` deploys. `cfb-gameday-board.vercel.app` stays as the
generated alias. The tunnel and self-host sections below remain as fallbacks.

## Vercel (live)

- `vercel.json`: four Python functions: `api/live.py` and `api/game.py` (the
  college board, 15 s max) and `api/nfl/live.py` and `api/nfl/game.py` (the pro
  football board, 30 s max). Each carries an `excludeFiles` list that keeps the
  bundle small; the college functions also drop `nfl/**`, `nflcore/**` and
  `api/nfl/**`, the NFL ones keep `nflcore/`. Also HSTS and nosniff headers,
  `noindex` on `/api/nfl/*`, no-cache on both service workers, and `cleanUrls`
  so `/privacy` and `/support` resolve.
- `.well-known/apple-app-site-association` (universal links, from iOS 1.1) is
  served with `Content-Type: application/json` by a `vercel.json` header rule;
  Apple fetches it through its own CDN, so check
  `https://app-site-association.cdn-apple.com/a/v1/cfbgameday.app` after a change.
- `.vercelignore` (read it for the full list) keeps `ios/`, `ios-pfb/`,
  `docs/`, `deploy/`, `scripts/`, `.github/`, `lines.json`, env files and keys,
  the local notes (`CLAUDE.md`, `AGENTS.md`, `CONTEXT*.md`), `.claude/`,
  `.worktrees/` and `captures/` out of the upload. The Vercel CLI uses it in
  place of `.gitignore`, so a hand deploy relies on it; `scripts/check.py`
  fails if a local-notes entry in `.gitignore` is missing from it. Run
  `vercel build` only in a throwaway export (`git archive HEAD | tar -x -C <dir>`):
  it leaves `uv.lock`, `pyproject.toml` and `.python-version` behind.
- Local CLI link lives in `.vercel/project.json` (gitignored). Recreate with
  `vercel project inspect cfb-gameday-board --scope christian-verdins-projects`
  and write `{orgId, projectId, projectName}` by hand; `vercel link` refuses to
  run non-interactively in this shell.
- Manual deploys: `vercel deploy --yes` (preview, behind Vercel Authentication)
  or `vercel deploy --prod --yes`.
- Checks: `curl -sI "https://cfb-gameday-board.vercel.app/api/live?dates=YYYYMMDD"`
  twice; `x-vercel-cache` goes `MISS` then `HIT`.

### Domain: cfbgameday.app (done 2026-09-05)

Claimed free-with-Pro (renews $15/yr on 2027-09-05, registrar Vercel), attached
with `vercel domains add cfbgameday.app cfb-gameday-board` plus the `www`
host. Vercel runs the nameservers, so DNS and the certificate are automatic.
Check with `vercel domains inspect cfbgameday.app --scope christian-verdins-projects`
and `curl -sI https://cfbgameday.app/`. If the domain ever moves, update
`BoardURL` / `BoardHost` in `ios/project.yml`, `README.md`, `privacy.html`,
`support.html`, and this file.

### Weekly data

`.github/workflows/refresh.yml` runs seven times a week (Tue 4 AM and a 10 AM
backup, Wed 1 PM, Thu 7 AM, Fri 7 AM, Sat 4 AM and an 8 AM backup, all CDT; cron
in UTC, so an hour earlier in CST from November to mid-March, and scheduled hours
early because GitHub starts scheduled runs late),
rebuilds the snapshot, heals a run that lost kickoff forecasts, runs
`scripts/check.py`, and commits `games.json`, `games.js`, `index.html` and
`sitemap.xml` when they changed. Details: `AGENTS.md` § 1. Vercel deploys the commit. Trigger
by hand with `gh workflow run refresh.yml` (optional `start` / `end` inputs).

### Pro football board (`/nfl`)

Stats only. `.github/workflows/nfl-refresh.yml` rebuilds `nfl/games.json` on 15
UTC crons (Tue 12:00 to Mon 12:00, including Thu and Fri 06:00 runs for
daytime holiday games; the file has the exact list) and `nfl-metrics.yml` builds `nfl/metrics.json` on Tue
and Wed 14:00 UTC. Both commit with a rebase-and-retry push and Vercel deploys
the commit. Both crons are gated by the repo variable `NFL_REFRESH_ENABLED`
(set it to `false` to stop them); manual `gh workflow run` always goes.
`pr-check.yml` runs `scripts/check.py` and `scripts/check_nfl.py` on pull
requests. A dispatch that sits queued with no jobs for several minutes is a
GitHub ghost: dispatch again.

## Self-hosting (fallback only)

Vercel is the production host. Everything below is the fallback if it ever
has to move: a tunnel for a single gameday, or an always-on box.

## Rule that does not change

`server.py` binds `127.0.0.1:8765`. `/api/live` is an unauthenticated ESPN
proxy; exposed on `0.0.0.0` on a public IP it is an open fetch-amplifier and
will get the IP 403'd. Only a TLS reverse proxy (Caddy or nginx) or a tunnel
faces the internet. Do not port-forward 8765.

## 0. Same Wi-Fi phone test (minutes, dies when you leave)

```
ipconfig getifaddr en0          # e.g. 192.168.1.42
```

Edit `BIND` in `server.py` to `"0.0.0.0"`, run it, open
`http://192.168.1.42:8765/` in iPhone Safari, then change `BIND` back. macOS
may prompt for the firewall. Not a substitute for HTTPS: Safari will not
install a PWA from an http LAN address as a full standalone app on every iOS
version, and the service worker needs a secure context.

## 1. Cloudflare quick tunnel from the Mac (gameday only, $0)

```
brew install cloudflared
python3 server.py                                   # terminal 1
cloudflared tunnel --url http://127.0.0.1:8765      # terminal 2
```

`scripts/tunnel.sh` does both and prints the URL. Use the printed
`https://<random>.trycloudflare.com` on the phone. HTTPS, so
Add to Home Screen and the service worker both work. The URL changes on every
restart and the Mac must stay awake. Ctrl+C both when the slate ends.

Named tunnel for a stable hostname on a domain you control:

```
cloudflared tunnel login
cloudflared tunnel create cfb-gameday
cloudflared tunnel route dns cfb-gameday gameday.example.com
cloudflared tunnel run --url http://127.0.0.1:8765 cfb-gameday
```

The tunnel credentials JSON lands in `~/.cloudflared/`. Never copy it into
this repo (`.gitignore` blocks `.cloudflared/`).

Tailscale equivalent, phone on the tailnet only, no public exposure:

```
tailscale serve --bg 8765
```

## 2. Always-on box (Fly/Render/VPS/EC2, roughly $0-12/mo)

Only if the Saturday tunnel gets old. Layout on the box:

```
Internet -> Caddy :443 (TLS)  ->  127.0.0.1:8765 server.py
                                    /           static files
                                    /api/live   ESPN proxy, 20 s cache
```

Steps:

1. `git clone` to `/opt/cfb-gameday`, `chown -R www-data`. Python 3.11+ only,
   no venv needed (stdlib).
2. `cp deploy/cfb-gameday.service /etc/systemd/system/` then
   `systemctl enable --now cfb-gameday`. The unit is read-only except the
   repo dir, which `lines.json` needs.
3. Caddy: `cp deploy/Caddyfile /etc/caddy/Caddyfile`, set the host,
   `systemctl reload caddy`. Caddy obtains the certificate. nginx users take
   `deploy/nginx.conf` and `certbot --nginx` instead.
4. DNS: `A gameday <server IP>` (or `CNAME` to the platform hostname). Wait
   for TLS before pointing anything at it. Never submit an App Store build
   against a `trycloudflare.com` URL.
5. Private desk instead of a public page: uncomment `basicauth` in the
   Caddyfile (`caddy hash-password`) or `auth_basic` in nginx.

Production settings already true in `server.py`: loopback bind, 20 s per-date
cache, dates with all games final are frozen, `lines.json` written on every
odds change, `Cache-Control: no-store`, ESPN 403s logged and not retried in a
loop, no keys anywhere.

AWS note for this account: a `t3.micro` fits the Free Tier credits, but do
not provision it without an explicit "deploy to EC2" plus a host. No NAT
Gateway, no load balancer; Caddy on the instance is enough.

## Weekly ops on the box

```
cd /opt/cfb-gameday
git pull
python3 scripts/refresh_week.py      # Tue..Mon of the slate in progress
python3 scripts/check.py
sudo systemctl restart cfb-gameday   # server reads dates from games.json at start
```

Run the refresh again Saturday morning for same-day weather.

## Done means

- `https://gameday.…/` loads the board and `/api/live` returns `{ "ok": true, … }`.
- iPhone Safari: Share, Add to Home Screen, opens standalone.
- No mixed content, HSTS on, port 8765 closed from outside.
