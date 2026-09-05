#!/bin/sh
# Gameday tunnel: start server.py if it is not up, open a Cloudflare quick tunnel,
# print the https URL. Ctrl+C stops the tunnel (and the server if we started it).
# The URL is random and changes every run; the Mac must stay awake.
set -e
cd "$(dirname "$0")/.."
PORT="${PORT:-8765}"
LOG="${TMPDIR:-/tmp}/cfb-gameday-tunnel.log"
command -v cloudflared >/dev/null || { echo "brew install cloudflared"; exit 1; }

STARTED=""
if ! lsof -nP -tiTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  PORT="$PORT" python3 server.py > "${TMPDIR:-/tmp}/cfb-gameday-server.log" 2>&1 &
  STARTED=$!
  sleep 1
  echo "server.py started (pid $STARTED)"
else
  echo "server.py already on $PORT"
fi

cloudflared tunnel --url "http://127.0.0.1:$PORT" > "$LOG" 2>&1 &
TUN=$!
trap 'kill $TUN 2>/dev/null; [ -n "$STARTED" ] && kill $STARTED 2>/dev/null; echo; echo stopped' INT TERM EXIT

i=0
while [ $i -lt 30 ]; do
  URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$LOG" | head -1)
  [ -n "$URL" ] && break
  sleep 1; i=$((i+1))
done
[ -z "$URL" ] && { echo "no tunnel URL after 30s; see $LOG"; exit 1; }
echo
echo "  $URL"
echo
echo "iPhone Safari: open it, Share, Add to Home Screen. Ctrl+C here when the slate ends."
wait $TUN
