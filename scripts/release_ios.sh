#!/bin/sh
# One-command iOS release: regenerate project, archive, export an App Store IPA,
# validate, and upload through the App Store Connect API. No Xcode clicks.
#
#   scripts/release_ios.sh                 # archive + export + upload
#   scripts/release_ios.sh --bump 1.0.1    # set MARKETING_VERSION first (build number auto-increments)
#   scripts/release_ios.sh --no-upload     # stop after the IPA is exported
#
# Upload needs an App Store Connect API key (Users and Access > Integrations > App Store Connect API):
#   ~/.appstoreconnect/private_keys/AuthKey_<KEY_ID>.p8      (altool finds it there by itself)
#   export ASC_KEY_ID=<KEY_ID> ASC_ISSUER_ID=<ISSUER_ID>       (put both in ~/.zshrc or ~/.config/cfb-gameday.env)
# The .p8 never goes in the repo. .gitignore blocks *.p8.
set -eu
cd "$(dirname "$0")/../ios"
ENV_FILE="$HOME/.config/cfb-gameday.env"; [ -f "$ENV_FILE" ] && . "$ENV_FILE"

BUMP=""; UPLOAD=1
while [ $# -gt 0 ]; do
  case "$1" in
    --bump) BUMP="$2"; shift 2 ;;
    --no-upload) UPLOAD=0; shift ;;
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

xcodegen generate >/dev/null
rm -rf build/CFBGameDay.xcarchive build/export
xcodebuild -project CFBGameDay.xcodeproj -scheme CFBGameDay -configuration Release \
  -destination 'generic/platform=iOS' -archivePath build/CFBGameDay.xcarchive \
  -allowProvisioningUpdates archive 2>&1 | grep -E "error:|ARCHIVE (SUCCEEDED|FAILED)"
xcodebuild -exportArchive -archivePath build/CFBGameDay.xcarchive \
  -exportOptionsPlist ExportOptions.plist -exportPath build/export \
  -allowProvisioningUpdates 2>&1 | grep -E "error:|EXPORT (SUCCEEDED|FAILED)"
IPA=$(ls build/export/*.ipa | head -1)
echo "==> IPA: $IPA ($(du -h "$IPA" | cut -f1))"

if [ "$UPLOAD" -eq 0 ]; then
  echo "==> --no-upload: stop here. Open build/CFBGameDay.xcarchive in Organizer to upload by hand."
  exit 0
fi
: "${ASC_KEY_ID:?set ASC_KEY_ID (App Store Connect API key id)}"
: "${ASC_ISSUER_ID:?set ASC_ISSUER_ID (App Store Connect issuer id)}"
echo "==> validate"
xcrun altool --validate-app -f "$IPA" -t ios --apiKey "$ASC_KEY_ID" --apiIssuer "$ASC_ISSUER_ID" 2>&1 | tail -3
echo "==> upload"
xcrun altool --upload-app -f "$IPA" -t ios --apiKey "$ASC_KEY_ID" --apiIssuer "$ASC_ISSUER_ID" 2>&1 | tail -3
echo "==> uploaded $version ($next_build). Commit ios/project.yml, then attach the build in App Store Connect."
