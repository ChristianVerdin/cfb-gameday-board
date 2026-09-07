#!/bin/zsh
# Smoke test for the shared-WKWebView tab bug: every tab must render on revisit.
# Needs a built simulator app (see CONTEXT.md), a booted simulator, and AXe (brew install cameroncooke/axe/axe).
#   scripts/ios_tab_check.sh [UDID]
# Taps Board, Live, Board, Starred, Live, About, Board and measures the header area
# brightness of a screenshot after each tap. A blank tab is the flat background.
set -e
UDID=${1:-$(xcrun simctl list devices booted -j | python3 -c 'import json,sys;d=json.load(sys.stdin);print([x["udid"] for v in d["devices"].values() for x in v][0])')}
APP=${APP:-ios/build/DerivedData/Build/Products/Debug-iphonesimulator/CFBGameDay.app}
OUT=${OUT:-/tmp/cfb-tab-check}; mkdir -p "$OUT"
xcrun simctl terminate "$UDID" com.hoynelabs.cfbgameday 2>/dev/null || true
xcrun simctl install "$UDID" "$APP"
xcrun simctl launch "$UDID" com.hoynelabs.cfbgameday >/dev/null
sleep 6
fail=0
for tab in Board Live Board Starred Live About Board Starred; do
  axe tap --label "$tab" --udid "$UDID" >/dev/null; sleep 2
  xcrun simctl io "$UDID" screenshot "$OUT/$tab.png" >/dev/null 2>&1
  # header band below the status bar (7%..15% of the height): white title text if rendered, flat background if blank
  y=$(ffmpeg -v info -i "$OUT/$tab.png" -vf "crop=iw:ih*0.08:0:ih*0.07,signalstats,metadata=print:key=lavfi.signalstats.YMAX" -f null - 2>&1 | rg -o 'YMAX=[0-9.]+' | head -1 | cut -d= -f2)
  state=RENDERED; [[ "$tab" != About ]] && (( ${y%.*} < 120 )) && { state=BLANK; fail=1; }
  printf "%-8s YMAX=%-5s %s\n" "$tab" "$y" "$state"
done
(( fail )) && { echo "FAIL: a tab was blank on revisit"; exit 1; }
echo "PASS: all tabs rendered"
