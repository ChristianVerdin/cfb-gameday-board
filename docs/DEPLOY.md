# Deploy

Nothing here is deployed yet. These are the files and the order for when a
public HTTPS URL is wanted. Cheapest first.

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
python3 scripts/refresh_week.py      # Thu..Mon of the coming slate
python3 scripts/check.py
sudo systemctl restart cfb-gameday   # server reads dates from games.json at start
```

Run the refresh again Saturday morning for same-day weather.

## Done means

- `https://gameday.…/` loads the board and `/api/live` returns `{ "ok": true, … }`.
- iPhone Safari: Share, Add to Home Screen, opens standalone.
- No mixed content, HSTS on, port 8765 closed from outside.
