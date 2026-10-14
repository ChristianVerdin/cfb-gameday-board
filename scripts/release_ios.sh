#!/bin/sh
# One-command iOS release: regenerate project, archive, export an App Store IPA,
# validate, and upload through the App Store Connect API. No Xcode clicks.
#
#   scripts/release_ios.sh                 # archive + export + upload + attach to the App Store version
#   scripts/release_ios.sh --bump 1.0.1    # set MARKETING_VERSION first (build number auto-increments)
#   scripts/release_ios.sh --submit        # ...and submit the version for review (asks nothing else)
#   scripts/release_ios.sh --no-upload     # stop after the IPA is exported
#
# Upload needs an App Store Connect API key (Users and Access > Integrations > App Store Connect API):
#   ~/.appstoreconnect/private_keys/AuthKey_<KEY_ID>.p8      (altool finds it there by itself)
#   export ASC_KEY_ID=<KEY_ID> ASC_ISSUER_ID=<ISSUER_ID>       (put both in ~/.zshrc or ~/.config/cfb-gameday.env)
#   export ASC_SIGNING_KEY_ID=<KEY_ID>                         (optional: export-signing key when Xcode has no account)
# The .p8 never goes in the repo. .gitignore blocks *.p8.
#
# With the `asc` CLI installed and logged in (brew install asc; asc auth login ...), upload goes
# through `asc publish appstore`: upload, wait for processing, find or create the App Store
# version, apply ios/metadata/version/<version>/*.json if present, attach the build. Without
# asc it falls back to altool upload and you attach the build in App Store Connect by hand.
set -eu
cd "$(dirname "$0")/../ios"
ENV_FILE="$HOME/.config/cfb-gameday.env"; [ -f "$ENV_FILE" ] && . "$ENV_FILE"

BUMP=""; UPLOAD=1; SUBMIT=0
APP_ID=6809035228
while [ $# -gt 0 ]; do
  case "$1" in
    --bump) BUMP="$2"; shift 2 ;;
    --no-upload) UPLOAD=0; shift ;;
    --submit) SUBMIT=1; shift ;;
    *) echo "unknown arg $1"; exit 2 ;;
  esac
done

# version bookkeeping lives in project.yml so xcodegen never loses it
cur_build=$(sed -n 's/^ *CURRENT_PROJECT_VERSION: "\([0-9]*\)".*/\1/p' project.yml | head -1)
next_build=$((cur_build + 1))
sed -i '' "s/^\( *CURRENT_PROJECT_VERSION: \)\"[0-9]*\"/\1\"$next_build\"/" project.yml
if [ -n "$BUMP" ]; then
  sed -i '' "s/^\( *MARKETING_VERSION: \)\"[^\"]*\"/\1\"$BUMP\"/" project.yml
fi
version=$(sed -n 's/^ *MARKETING_VERSION: "\([^"]*\)".*/\1/p' project.yml | head -1)
echo "==> CFBGameDay $version ($next_build)"

# Export signs with the cloud-managed distribution certificate. Xcode does that through its signed-in
# account; with no account (Xcode > Settings > Accounts empty: "No Accounts") set ASC_SIGNING_KEY_ID to an
# API key allowed to cloud-sign. The App Manager key gets "Cloud signing permission error"; the Admin key
# (R79Z9DL337) works. Its .p8 must be in ~/.appstoreconnect/private_keys/.
AUTH=""
if [ -n "${ASC_SIGNING_KEY_ID:-}" ]; then
  : "${ASC_ISSUER_ID:?set ASC_ISSUER_ID to sign with ASC_SIGNING_KEY_ID}"
  AUTH="-authenticationKeyPath $HOME/.appstoreconnect/private_keys/AuthKey_$ASC_SIGNING_KEY_ID.p8 -authenticationKeyID $ASC_SIGNING_KEY_ID -authenticationKeyIssuerID $ASC_ISSUER_ID"
fi

xcodegen generate >/dev/null
rm -rf build/CFBGameDay.xcarchive build/export
# shellcheck disable=SC2086
xcodebuild -project CFBGameDay.xcodeproj -scheme CFBGameDay -configuration Release \
  -destination 'generic/platform=iOS' -archivePath build/CFBGameDay.xcarchive \
  -allowProvisioningUpdates $AUTH archive 2>&1 | grep -E "error:|ARCHIVE (SUCCEEDED|FAILED)"
[ -d build/CFBGameDay.xcarchive ] || { echo "==> archive failed"; exit 1; }
# shellcheck disable=SC2086
xcodebuild -exportArchive -archivePath build/CFBGameDay.xcarchive \
  -exportOptionsPlist ExportOptions.plist -exportPath build/export \
  -allowProvisioningUpdates $AUTH 2>&1 | grep -E "error:|EXPORT (SUCCEEDED|FAILED)"
# The greps above swallow xcodebuild's status, so check for the IPA itself.
IPA=$(ls build/export/*.ipa 2>/dev/null | head -1)
[ -n "$IPA" ] || { echo "==> export failed, no IPA. 'No Accounts': sign in to Xcode or set ASC_SIGNING_KEY_ID (see above)."; exit 1; }
echo "==> IPA: $IPA ($(du -h "$IPA" | cut -f1))"

if [ "$UPLOAD" -eq 0 ]; then
  echo "==> --no-upload: stop here. Open build/CFBGameDay.xcarchive in Organizer to upload by hand."
  exit 0
fi
: "${ASC_KEY_ID:?set ASC_KEY_ID (App Store Connect API key id)}"
: "${ASC_ISSUER_ID:?set ASC_ISSUER_ID (App Store Connect issuer id)}"
echo "==> validate"
xcrun altool --validate-app -f "$IPA" -t ios --apiKey "$ASC_KEY_ID" --apiIssuer "$ASC_ISSUER_ID" 2>&1 | tail -3
if command -v asc >/dev/null 2>&1; then
  export ASC_TELEMETRY_DISABLED=1
  META=""; [ -f "metadata/version/$version/en-US.json" ] && META="--metadata-dir metadata"
  SUB=""; [ "$SUBMIT" -eq 1 ] && SUB="--submit --confirm"
  echo "==> asc publish appstore $version ($next_build) ${META:+with metadata} ${SUB:+and submit}"
  # shellcheck disable=SC2086
  asc publish appstore --app "$APP_ID" --ipa "$IPA" --version "$version" --build-number "$next_build" \
    --wait --timeout 30m $META $SUB --output json
  echo "==> done. Commit ios/project.yml. Status: asc review status --app $APP_ID"
else
  echo "==> upload (altool; install asc for attach and submit)"
  xcrun altool --upload-app -f "$IPA" -t ios --apiKey "$ASC_KEY_ID" --apiIssuer "$ASC_ISSUER_ID" 2>&1 | tail -3
  echo "==> uploaded $version ($next_build). Commit ios/project.yml, then attach the build in App Store Connect."
fi
