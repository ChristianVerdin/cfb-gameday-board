# App Store listing and release notes

Live listing: https://apps.apple.com/us/app/cfb-gameday-board/id6809035228 (short form
`https://apps.apple.com/app/id6809035228`), published by Hoyne Labs LLC (seller name "Hoyne Labs"),
175 territories. Live state, ids of whatever is in flight, and what to do next: `../CONTEXT.md`.

Where the listing lives:
- Version copy (description, keywords, What's New, URLs): `metadata/version/<version>/en-US.json`,
  applied by `scripts/release_ios.sh`. App-level copy (name, subtitle, privacy URL): `metadata/app-info/en-US.json`.
- Promotional text: generated weekly by `scripts/promo_text.py` (see Listing copy), never stored per version.
- `PASTE_ME.md` is the 1.0.0 first-submission sheet and `APP_REVIEW_REPLY.md` the 2.1 "Information Needed"
  kit; both are kept for reference and are not current copy.

Nothing in the listing promises wagering, picks, or "locks". Keep it that way through Review.

## Versions

| Version (build) | Submitted | Live | What it added |
| --- | --- | --- | --- |
| 1.0.0 (3) | 09-05; 2.1 Information Needed, resubmitted 09-07 | 09-10, manual release | First release |
| 1.0.1 (4) | 09-17 | 09-18 | Reload when resumed on a stale slate; keyword cleanup |
| 1.0.2 (5) | 10-07 | 10-08 | Game-sheet listing copy, ratings prompt, new screenshots, 18+ override |
| 1.0.3 (6) | 10-09 | 10-10 | iPad, resizable Mac window, Board menu, captioned screenshots, weather-led subtitle |
| 1.0.4 (7) | 10-14 | 10-15 | Home Screen quick actions |
| 1.0.5 (8) | 10-20, with six in-app events | 10-20 | Rivalry Games quick action, `cfbgameday://` deep links |
| 1.1.0 (9) | 10-21 | 10-22 | Today's Games widget, universal links, sixth screenshot |

All dates 2026, Central. From 1.0.1 every version has used release type `AFTER_APPROVAL`, so approval
is the release; Apple's lookup API and store page can lag ASC's `READY_FOR_SALE` by up to a day.

## Release checklist

Every version so far, in order. Submitting, and anything else Apple sees, happens only on cv's go.

1. **Test.** `python3 scripts/check.py`; the unit tests
   (`cd ios && xcodebuild -project CFBGameDay.xcodeproj -scheme CFBGameDay -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -derivedDataPath build/DerivedData test`);
   `scripts/ios_tab_check.sh` (every tab renders on revisit). Exercise the new feature on the simulator.
2. **Copy.** Copy the previous `metadata/version/<v>/en-US.json` to the new version and edit description,
   What's New and keywords. Leave `promotionalText` out (a release would otherwise revert the weekly line).
   `asc metadata validate --dir ios/metadata` (it catches keywords over 100 characters).
3. **Build.** `ASC_SIGNING_KEY_ID=R79Z9DL337 scripts/release_ios.sh --bump X.Y.Z` from the repo root.
   The prefix is needed while Xcode is signed out ("No Accounts"): only the Admin key may cloud-sign. The
   script bumps the build number, archives, exports, validates, uploads, waits for processing, creates the
   version, applies its metadata and attaches the build. It is not idempotent after a partial run; recovery
   is in `../CONTEXT.md` (attach to the existing ids, don't rerun). Commit `ios/project.yml` afterwards.
4. **Fill the version record.** It inherits screenshots, keywords, release type and (so far) the age-rating
   override, but not the promotional text.
   - `python3 scripts/promo_text.py --apply --version X.Y.Z`
   - `asc versions list --app 6809035228`: release type `AFTER_APPROVAL`
   - `asc age-rating view --version-id <VERSION_ID>`: `ageRatingOverrideV2` is `EIGHTEEN_PLUS`
   - Review notes: append a `NEW IN X.Y.Z` paragraph (see Review notes); 4,000 characters at most
   - Screenshots, if the version changes what the app looks like (see Screenshots)
5. **Check.** `asc review doctor --app 6809035228` should report 0 errors, 0 warnings, 0 blocking. Its one
   info line (Regulations and Permits declarations are website-only) has never blocked a submission.
6. **Submit, on cv's go.** `asc review submit --app 6809035228 --version-id <VERSION_ID> --build-id <BUILD_ID> --confirm`.
   If it answers "Version is not ready to be submitted yet, please try again later" while doctor is clean,
   it has still left a draft submission holding the version; `asc review submissions-submit --id <DRAFT> --confirm`
   a minute later went through for 1.1.0. After a rejection, mark the item resolved first
   (`asc review items update --id <ITEM> --resolved true`), or the same misleading message comes back.
7. **After approval.** iTunes lookup (`curl -s "https://itunes.apple.com/lookup?id=6809035228&country=us"`) shows the
   version; the promo text carried; README, `support.html`, `CLAUDE.md` and `../CONTEXT.md` describe the new
   feature as live.

## Prerequisites (must be true before you upload)

- https://cfbgameday.app serves the board, `/privacy`, `/support` and `/.well-known/apple-app-site-association`.
  `BoardURL` / `BoardHost` in `ios/project.yml` point at that domain.
- `ios/project.yml` carries `DEVELOPMENT_TEAM: 3V73W9NUZ6` (Hoyne Labs LLC), so automatic signing survives
  `xcodegen generate`. Cloud signing registered the widget's bundle id and the Associated Domains capability
  by itself (1.1.0); no developer-portal step was needed.
- The app has been run on a physical iPhone (Review checks this, 2.1).
- The Vercel project stays deployed during Review. A dead backend is a 2.1 rejection.

## App Store Connect: app record

| Field | Value |
| --- | --- |
| Name | CFB GameDay Board |
| Subtitle | Scores, kickoff weather & TV (from 1.0.3) |
| Bundle ID | com.hoynelabs.cfbgameday (widget: com.hoynelabs.cfbgameday.widget) |
| Apple ID | 6809035228 |
| SKU | cfbgameday-ios |
| Primary language | English (U.S.) |
| Primary category | Sports |
| Secondary category | Reference |
| Price | Free, USA base; no In-App Purchases |
| Age rating | 18+ (the legacy rating field reads 17+) |
| Copyright | 2026 Hoyne Labs LLC |
| Privacy Policy URL | https://cfbgameday.app/privacy |
| Support URL | https://cfbgameday.app/support |
| Marketing URL | https://cfbgameday.app |

### Age rating

Every questionnaire answer is None or No, Gambling and Simulated Gambling included: the app takes no
wagers. The rating comes from the override, `ageRatingOverrideV2: EIGHTEEN_PLUS` (legacy
`ageRatingOverride: SEVENTEEN_PLUS`), because the board shows publicly posted betting lines. The declaration
is per version. On 2026-10-07 the store showed 4+ because no override had been saved, so check it on every
new version and set it if missing:
`asc age-rating edit --id <DECLARATION_ID> --age-rating-override-v2 EIGHTEEN_PLUS`.

### App Privacy (nutrition label)

- Data collection: **No, we do not collect data from this app.** Tracking: No.

Accurate because there are no analytics, accounts or identifiers. Network calls go only to cfbgameday.app,
which proxies ESPN and serves static files; the widget (1.1) fetches the same public slate and scores and
caches its last copy on the device. `privacy.html` says so.

## Listing copy

**Keywords** (100 characters; locked while a version is in review, so they change only with a new version).
Live from 1.1.0, 97 characters:

> college,ncaa,football,ncaaf,live,schedule,spread,odds,lines,forecast,rankings,rivalry,bowl,widget

Rules learned so far: never repeat a word from the name or subtitle (cfb, gameday, board, scores, kickoff,
weather, tv), because Apple already indexes them and `asc metadata keywords audit` only catches phrase-level
overlap, not single words; no sportsbook or network names, wagering verbs, or trademarks (CFP, trophy-game
names). History: 1.0.0 shipped `college football,cfb,scores,ncaa football,gameday,weather,spread,odds,live scores,schedule`,
which spent bytes on name and subtitle words and a second `football`. 1.0.1 moved to single tokens and bought
`channel`, `rankings` and `fbs`. 1.0.3 moved `kickoff` into the subtitle and the keyword became `lines`.
1.1.0 traded `totals`, `channel` and `fbs` for `rivalry`, `bowl` and `widget` ahead of Rivalry Week and bowl
season.

**Promotional text** (170 characters) is the weekly billboard, and the only listing field Apple lets you
change without review. `python3 scripts/promo_text.py` previews it from `games.json` (game count, Saturday
count, the Saturday marquee with trophy games first, the board's own weather flags, finals skipped); `--apply`
pushes it to the newest editable version, `--version X.Y.Z` to a specific one. Run it on the weekly pass
after the Tuesday build (`git pull` first), and again Thursday or Friday if you like, because the weather
clause comes from a multi-day forecast. cv ruled out a Saturday re-apply, a scheduled job, and putting the `.p8`
in CI (2026-09-18). The evergreen off-season line is in `metadata/version/1.0.0/en-US.json`.

**Description and What's New**: the version's JSON file is the copy. 1.1.0 runs Before kickoff, During the
games, Rivalry games, Game sheet, Filters, Widgets, Quick actions and links, On iPad and Mac, Data, and the
not-a-sportsbook line.

## Screenshots

Sets on 1.1.0: 6.9" iPhone (1320x2868, `APP_IPHONE_67`) and 6.5" iPhone (1284x2778, `APP_IPHONE_65`) with six
shots each (board, weather, game, lines, tv from 1.0.3, plus widget from 1.1.0), and 13" iPad (2064x2752,
`APP_IPAD_PRO_3GEN_129`) with the first five. Only the first three show in search results, which is where the
listing loses most people (search impression to page view), so put the strongest shots first.

Capture raw shots from the simulator as `<device>-<n>-<slug>.png` (`iphone` on the iOS 27 iPhone 17 Pro Max,
`ipad` on the iOS 27 iPad Pro 13-inch (M5)), with a slug that has a caption in `CAPTIONS` in
`scripts/store_shots.py` (board, weather, game, lines, tv, widget), then:

```
xcrun simctl status_bar <udid> override --time 9:41 --batteryState charged --batteryLevel 100 --wifiBars 3
python3 scripts/store_shots.py ios/screenshots/<version>/raw ios/screenshots/<version>
```

That writes the 6.9" (`iphone-*`), 6.5" (`iphone65-*`) and 13" (`ipad-*`) sets, RGB, at Apple's exact sizes.
If a time shows in the shot (the widget's "Updated 5:03 PM CT"), set the status-bar clock to match. The
board's pills are web content AXe cannot see, so drive the page with `axe tap -x -y` (points);
`-fragment game/<id>` at launch opens the game sheet on a final. The Home Screen widget gallery can be
driven with AXe too: long-press an empty spot, Edit, Add Widget, search, swipe between sizes. Captions follow
Guideline 2.3.3 (the app stays the subject): no prices, URLs or betting language. `ios/screenshots/` is
gitignored.

Upload with the version localization id (`asc localizations list --version <VERSION_ID>`). Device type
`IPHONE_69` lands in the 6.9" set (`APP_IPHONE_67`). Without `--replace` a file is appended to the set; with
`--replace --confirm` the set is swapped. `--path` takes a directory, so give each size its own:

```
asc screenshots upload --version-localization <LOC_ID> --path <dir-with-6.9-files> --device-type IPHONE_69
asc screenshots upload --version-localization <LOC_ID> --path <dir-with-6.5-files> --device-type IPHONE_65
```

## iPad and Mac (from 1.0.3)

Apple: "iPhone apps always run in a fixed-size window" on Mac; an iPad app that supports multitasking gets a
resizable one (developer.apple.com/documentation/apple-silicon/running-your-ios-apps-in-macos). So
`project.yml` targets iPhone + iPad, iPad declares all four orientations, and there is no `UIRequiresFullScreen`
(deprecated in iPadOS 26; from iOS 27 it no longer blocks resizing, TN3192). `WindowSizing` sets a 390x600 pt
minimum through `UIWindowScene.sizeRestrictions` (the Mac shows iPad apps at 77%, so that reads as about
301x494 there). The Board menu (`BoardCommands.swift`) gives Command-1 to 4 for tabs, Command-F for search,
Command-R for reload on the Mac menu bar, the iPadOS menu bar and hardware keyboards. The Mac listing was
verified compatible on 2026-10-07.

Run it on this Mac as "Designed for iPad": the Mac is registered on the team (asc device `BY6D69H6KW`,
2026-10-09), then

```
cd ios && xcodebuild -scheme CFBGameDay -destination 'platform=macOS,variant=Designed for iPad' \
  -derivedDataPath build/DerivedDataMac -allowProvisioningUpdates build
W=build/MacRun/CFBGameDay.app; rm -rf build/MacRun; mkdir -p $W/Wrapper
cp -R build/DerivedDataMac/Build/Products/Debug-iphoneos/CFBGameDay.app $W/Wrapper/
ln -s Wrapper/CFBGameDay.app $W/WrappedBundle; open $W
```

(`open` on the bare `.app` fails with "incorrect executable format"; the Wrapper/WrappedBundle layout is what
the App Store installs in /Applications.)

## Home Screen quick actions and deep links (from 1.0.4)

Long-press the icon: **Live Games**, **Starred**, **By TV**, and from 1.0.5 **Rivalry Games**. The items are
static `UIApplicationShortcutItems` in `project.yml`, so they show before the first launch; `QuickActions.swift`
routes them (scene connection options on a cold launch, the scene delegate's `performActionFor` when running).
By TV opens the Board tab on `#tv` and Rivalry Games on `#rivalry`; leaving the tab resets it, and a repeat
action re-dispatches `hashchange` because the in-page view pills don't touch the hash. Not on Mac (no Home
Screen there); About shows the Board menu keys instead. Test on a simulator with AXe:
`axe touch -x X -y Y --down --up --delay 1.5` on the icon, then tap the item; `describe-ui` lists icons on other
Home Screen pages with an off-screen x, so swipe first.

`cfbgameday://` deep links (1.0.5) use the same routing (`Route` in `QuickActions.swift`, `onOpenURL` in
`RootView`): `rivalry`, `live`, `starred`, `tv`, `board` and `game/<ESPN id>`, plus `lines` and `blowouts` from 1.1. A game link
from Live or Starred first resets the shared page to `#all`, so closing the sheet lands on all games. Test with
`xcrun simctl openurl <udid> cfbgameday://rivalry` (the simulator asks "Open in CFB GameDay?" first; event links
do not).

## Widgets and universal links (1.1)

**Widget** (`CFBGameDayWidget/`, bundle `com.hoynelabs.cfbgameday.widget`): one widget, "Today's Games", in
small, medium (4 games), large (12), Lock Screen rectangular and inline. Edit Widget offers Show: All games /
Top 25 / Rivalry games (`SlateIntent`). It reads `games.json` and, once a game on the shown day may have kicked
off, `/api/live?dates=` for that day (plus anything that kicked off in the last 6 hours), and keeps the last good
copy in its Caches dir ("Offline · 2:31 PM CT" when a refresh fails). Day shown: one with a live game, else
today, else the next day with games, else the last (Sunday shows Saturday's finals). Refresh hint: 10 min while
games are on, just after the next kickoff otherwise, and at Central midnight. No odds, no implied score, no
weather flags beyond the snapshot's kickoff forecast on upcoming outdoor games; finals dim the trailing side by
score. Live and final rows link to `cfbgameday://game/<id>`; the rest of the widget opens Live (games on),
Rivalry (that setting), or the board.

**Universal links**: `applinks:cfbgameday.app`, and `.well-known/apple-app-site-association` on the site claims
`/` and `/index.html` (any fragment) for `3V73W9NUZ6.com.hoynelabs.cfbgameday`; `/privacy`, `/support` and
`/api/*` stay on the web. `Route(url:)` maps `#rivalry`, `#live`, `#starred`, `#tv`, `#lines`, `#blowouts`,
`#game/<id>` the same way as `cfbgameday://`. Apple's CDN served the file within minutes of the 10-21 deploy
(`curl https://app-site-association.cdn-apple.com/a/v1/cfbgameday.app`); `check.py` guards the file.

Tested 2026-10-21 on the iOS 27 simulator: 12 unit tests (routing, day choice, filters, live dates, refresh
timing) plus rendered previews of every size (`TEST_RUNNER_SNAPSHOT_DIR=<dir>` on the test command); widget
added from the gallery with live data, Edit Widget -> Rivalry games, tap opened the board on the Rivalry
filter; `simctl openurl https://cfbgameday.app/#live` opened the Live tab, `#game/<id>` the game sheet,
`/privacy` Safari; tab check passed. The Lock Screen sizes were checked as renders only. If a test run fails
with "Application failed preflight checks" (Busy), `xcrun simctl uninstall <udid> com.hoynelabs.cfbgameday` and
run again.

## In-app events and nominations (2026 season)

Apple requires every in-app event to deep-link into the app itself, which is why 1.0.5 exists. Six events,
all approved 2026-10-20 with 1.0.5 (Rivalry Saturdays published 10-21; each other one publishes on its date),
USA only, purpose all users, text kept generic (no "College Football Playoff" or trophy-game marks in event
text; those names appear only as board data):

| Event (display name) | id | Badge | Publish | Runs (CT) | Deep link |
|---|---|---|---|---|---|
| Rivalry Saturdays | 6825048877 | Special Event | Oct 21 | Oct 24 - Nov 22 | `cfbgameday://rivalry` |
| Rivalry Week | 6825049405 | Live Event, high | Nov 10 | Nov 24 - Nov 29 | `cfbgameday://rivalry` |
| Championship Week | 6825049467 | Live Event | Nov 17 | Dec 1 - Dec 6 | `cfbgameday://board` |
| Bowl Season | 6825049670 | Special Event | Nov 28 | Dec 12 - Jan 11 | `cfbgameday://board` |
| Playoff Season | 6825049981 | Live Event | Dec 4 | Dec 18 - Jan 16 | `cfbgameday://board` |
| National Championship | 6825049993 | Live Event, high | Jan 4 | Jan 18 - Jan 26 | `cfbgameday://board` |

A schedule scan on 10-21 found 2 to 6 tagged trophy games every Saturday of the Rivalry Saturdays window and
20 in Rivalry Week, so the event never opens on an empty Rivalry view. Rules (Apple): 15 min to 31 days, publish
at most 14 days before start, 10 published / 15 approved at once, reviewed independently of a version (or in
the same submission), name 30 / short 50 / long 120 characters, media opaque JPG/PNG, card 16:9 (1920x1080 to
3840x2160), details 9:16. A territory is required (`--territories USA`; without it asc's create fails and
deletes the event).

Media: `ios/screenshots/events/` (gitignored). `compose.html?layout=card|details&back=..&front=..` frames board
screenshots (390 pt @3x, captured with the sticky header accounted for) on a dark field, no added text and no
posted lines; render at 1920x1080 / 1080x1920 in headless Chrome, then `ffmpeg -i raw.png -pix_fmt rgb24 out.png`
to drop alpha. The Rivalry Week shots come from a `--start 20261124 --end 20261130 --out <scratch>` preview
served by a copy of `server.py`.

Nominations (NEW_CONTENT, USA; **submitted 2026-10-21** with the events linked): "Rivalry Week 2026"
(`d88131cc-2e00-4597-b8d0-f5b455f59db9`, Nov 24-29) and "Postseason 2026-27" (`29768088-c2c0-4a7c-86c7-03fe2eb922b2`,
Dec 1 - Jan 26). The API rejects draft event ids in `--in-app-events`; link them once the events are approved
(`asc nominations update --id .. --in-app-events .. --has-in-app-events=true --submitted=false`), then submit with
`--submitted=true`. Apple asks for about three weeks of lead time. The submit can answer HTTP 500 and still go
through (Postseason did on 10-21, and a view right after still read DRAFT): re-check with
`asc nominations list --app 6809035228 --status SUBMITTED` before retrying.

How 1.0.5 and the events went in as one review submission, so Review tested the links on the new build:
```
asc review submissions-create --app 6809035228 --platform IOS
asc review items-add --submission SUB --item-type appStoreVersions --item-id 2064e46f-b3c0-4966-b352-5303d7fc6da8
asc review items-add --submission SUB --item-type appEvents --item-id 6825048877   # and each other event id
asc review submissions-submit --id SUB --confirm
```

## Review notes (App Review Information)

The notes live on each version's review detail and carry over to the next version. Their shape: what the app
is and is not (an information display, not a sportsbook, why it is 18+); SETUP (none, no login); EXTERNAL
SERVICES (our backend on Vercel, ESPN's public scoreboard, Open-Meteo, Apple Maps; no auth, payment,
analytics, ad or AI services); REGIONS; REGULATED / PROTECTED MATERIAL; then one paragraph per feature version
(IPAD AND MAC, NEW IN 1.0.4, NEW IN 1.0.5, NEW IN 1.1), each saying what changed, how to see it, and "No new data,
accounts, or services". At 1.1.0 they run 3,483 of Apple's 4,000 characters, so the next version has room for
about one more paragraph; fold the oldest NEW IN paragraphs into one line before going over.

```
asc review details-for-version --version-id <VERSION_ID>          # detail id and current notes
asc review details-update --id <DETAIL_ID> --notes "$(cat notes.txt)"
```

Contact fields are the account holder's and are not repeated here (this repo is public).

## Reports

Analytics needs an Admin API key. Two keys are registered with `asc`:

| Profile | Key | Role | Use |
| --- | --- | --- | --- |
| `cfbgameday` (default) | WUSAQJV85V (rotated 2026-10-07; FQRRWFFM28 revoked) | App Manager | uploads, metadata, review, TestFlight |
| `cfbgameday-reports` | R79Z9DL337 | Admin | reports, and cloud signing while Xcode is signed out |

Ongoing analytics report request `15cce5e9-253a-459b-b969-a07eed348d67` created 2026-09-07; Apple produces daily
instances from there.

```
asc --profile cfbgameday-reports analytics view --request-id 15cce5e9-253a-459b-b969-a07eed348d67
asc --profile cfbgameday-reports analytics download --request-id 15cce5e9-253a-459b-b969-a07eed348d67 --instance-id <INSTANCE_ID>
asc --profile cfbgameday-reports analytics sales --vendor <VENDOR> --type SALES --subtype SUMMARY --frequency DAILY --date YYYY-MM-DD
```

`analytics download` re-lists reports per segment, so dozens back to back hit Apple's hourly limit (429,
retry-after about 37 minutes); space them or download per processing date. Both `.p8` files live in
`~/.appstoreconnect/private_keys/`, never in the repo. Download and traffic numbers go in
`../CONTEXT.private.md`, not here.

## Marketing surfaces

- **Site:** Smart App Banner (`apple-itunes-app` meta) on `/`, `/support`, `/privacy`; Open Graph + Twitter
  card (`icons/og.png`, 1200x630, source `docs/og-card.html`, re-render with headless Chrome at 1200x630 if the
  copy changes); JSON-LD SoftwareApplication; `robots.txt` + `sitemap.xml`; App Store badge on `/support` and in
  the board footer. From 1.1, links to the board open the app for people who have it (universal links).
- **Cross-links:** this repo's README, the GitHub profile README (project row, use case, featured section with
  three iPhone screenshots), the publisher's site hoynelabs.com, and the Wall of Apps listing
  (https://github.com/rorkai/App-Store-Connect-CLI/pull/2481).
- **In-app events and featuring nominations** are filed through `asc app-events` and `asc nominations` (see
  above). File nominations about three weeks ahead.
- **Campaign links (attribution in App Analytics).** Format:
  `https://apps.apple.com/app/apple-store/id6809035228?pt=PROVIDER_TOKEN&ct=CAMPAIGN&mt=8`. The provider token
  is shown once in App Store Connect -> Analytics -> Acquisition -> Campaigns -> Generate Campaign Link; the API
  does not expose it. Parked (see `../CONTEXT.md`) until cv wants attribution. Campaign names to use: `site-footer`, `site-support`,
  `github-readme`, `github-profile`, `x-bio`, `x-post`.
- **By hand only:** pinning `cfb-gameday-board` on the GitHub profile (no API for profile pins).
- **Apple marketing rules that apply:** official badge only, unaltered, min 40 px tall with clear space; say
  "on the App Store"; screenshots in Apple's product bezels only; never imply Apple endorsement.
  https://developer.apple.com/app-store/marketing/guidelines/

## Export compliance

`ITSAppUsesNonExemptEncryption` is `false` in the app's Info.plist (HTTPS only), so every build arrives with
`usesNonExemptEncryption: false` and no question to answer. No ERN needed. The widget needs no key of its own.

## Likely Review outcomes and the response

| Result | Why | Response |
| --- | --- | --- |
| Approved | Sports scores + weather + TV, native tabs/About/offline/refresh, quick actions, widget, backend up, honest metadata | Ship |
| 4.2 Minimum functionality | Reviewer sees only a web page | Point to the native tabs, pull-to-refresh, offline state, About, quick actions, `cfbgameday://` routing and, from 1.1, the native widget; if they insist, add a native Starred list backed by `games.json` |
| 2.1 Performance | Backend unreachable during review | Check Vercel status; never submit while the domain is mid-migration |
| 2.1 Information Needed (happened 2026-09-05) | New developer account, no review history | Screen recording from a physical iPhone plus six written answers; `APP_REVIEW_REPLY.md` has the text. Same build, resubmit |
| 5.3 Gaming | Copy reads as a wagering aid | Reply that no bets are placed, no books are linked, and lines are ESPN's public data; do not add disclaimers that sound like a sportsbook |
| Metadata rejected | Screenshots do not match the app | Re-take from the simulator with the current build |

Do not argue "it is a PWA". Fix and resubmit.
