#!/bin/sh
# Pro Football Board: regenerate project, archive, export an App Store IPA, upload to TestFlight.
# Never submits for App Review.
#
#   scripts/release_ios_pfb.sh                  # bump build, archive, export, upload, add to the internal group
#   scripts/release_ios_pfb.sh --bump 1.0.1     # set MARKETING_VERSION first
#   scripts/release_ios_pfb.sh --no-upload      # stop after the IPA is exported
#
# App id: PFB_APP_ID env var, else ios-pfb/.asc-app-id (gitignored, one line).
# Internal TestFlight group: PFB_TESTFLIGHT_GROUP (name or id, default "Internal").
# Upload: ASC_KEY_ID and ASC_ISSUER_ID for asc/altool; the .p8 stays in ~/.appstoreconnect/private_keys/.
# Cloud signing with no Xcode account: ASC_SIGNING_KEY_ID (plus ASC_ISSUER_ID), as in release_ios.sh.
set -eu
cd "$(dirname "$0")/../ios-pfb"
ENV_FILE="$HOME/.config/cfb-gameday.env"; [ -f "$ENV_FILE" ] && . "$ENV_FILE"

BUMP=""; UPLOAD=1
while [ $# -gt 0 ]; do
  case "$1" in
    --bump) BUMP="${2:?--bump needs a version}"; shift 2 ;;
    --no-upload) UPLOAD=0; shift ;;
    *) echo "unknown arg $1"; exit 2 ;;
  esac
done

APP_ID="${PFB_APP_ID:-}"
[ -z "$APP_ID" ] && [ -f .asc-app-id ] && APP_ID=$(tr -d ' \n' < .asc-app-id)
if [ "$UPLOAD" -eq 1 ] && [ -z "$APP_ID" ]; then
  echo "==> no app id: set PFB_APP_ID or put it in ios-pfb/.asc-app-id"; exit 1
fi
GROUP="${PFB_TESTFLIGHT_GROUP:-Internal}"

cur_build=$(sed -n 's/^ *CURRENT_PROJECT_VERSION: "\([0-9]*\)".*/\1/p' project.yml | head -1)
[ -n "$cur_build" ] || { echo "==> CURRENT_PROJECT_VERSION not found in project.yml"; exit 1; }
next_build=$((cur_build + 1))
sed -i '' "s/^\( *CURRENT_PROJECT_VERSION: \)\"[0-9]*\"/\1\"$next_build\"/" project.yml
if [ -n "$BUMP" ]; then
  sed -i '' "s/^\( *MARKETING_VERSION: \)\"[^\"]*\"/\1\"$BUMP\"/" project.yml
fi
version=$(sed -n 's/^ *MARKETING_VERSION: "\([^"]*\)".*/\1/p' project.yml | head -1)
echo "==> ProFootballBoard $version ($next_build)"

AUTH=""
if [ -n "${ASC_SIGNING_KEY_ID:-}" ]; then
  : "${ASC_ISSUER_ID:?set ASC_ISSUER_ID to sign with ASC_SIGNING_KEY_ID}"
  AUTH="-authenticationKeyPath $HOME/.appstoreconnect/private_keys/AuthKey_$ASC_SIGNING_KEY_ID.p8 -authenticationKeyID $ASC_SIGNING_KEY_ID -authenticationKeyIssuerID $ASC_ISSUER_ID"
fi

xcodegen generate >/dev/null
rm -rf build/ProFootballBoard.xcarchive build/export
# shellcheck disable=SC2086
xcodebuild -project ProFootballBoard.xcodeproj -scheme ProFootballBoard -configuration Release \
  -destination 'generic/platform=iOS' -archivePath build/ProFootballBoard.xcarchive \
  -allowProvisioningUpdates $AUTH archive 2>&1 | grep -E "error:|ARCHIVE (SUCCEEDED|FAILED)" || true
[ -d build/ProFootballBoard.xcarchive ] || { echo "==> archive failed"; exit 1; }
# shellcheck disable=SC2086
xcodebuild -exportArchive -archivePath build/ProFootballBoard.xcarchive \
  -exportOptionsPlist ExportOptions.plist -exportPath build/export \
  -allowProvisioningUpdates $AUTH 2>&1 | grep -E "error:|EXPORT (SUCCEEDED|FAILED)" || true
IPA=$(ls build/export/*.ipa 2>/dev/null | head -1)
[ -n "$IPA" ] || { echo "==> export failed, no IPA. 'No Accounts': sign in to Xcode or set ASC_SIGNING_KEY_ID."; exit 1; }
echo "==> IPA: $IPA ($(du -h "$IPA" | cut -f1))"

if [ "$UPLOAD" -eq 0 ]; then
  echo "==> --no-upload: stop here."
  exit 0
fi
command -v asc >/dev/null 2>&1 || { echo "==> asc not installed; upload the IPA by hand"; exit 1; }
: "${ASC_KEY_ID:?set ASC_KEY_ID (App Store Connect API key id)}"
: "${ASC_ISSUER_ID:?set ASC_ISSUER_ID (App Store Connect issuer id)}"
export ASC_TELEMETRY_DISABLED=1
echo "==> TestFlight upload to group '$GROUP'"
asc publish testflight --app "$APP_ID" --ipa "$IPA" --version "$version" --build-number "$next_build" \
  --group "$GROUP" --wait --timeout 30m --test-notes "Pro Football Board $version ($next_build)" --locale en-US --output json
echo "==> done. Commit ios-pfb/project.yml. This script never submits for App Review."
