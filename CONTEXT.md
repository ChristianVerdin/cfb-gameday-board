# CONTEXT.md — CFB GameDay Board

> Single-page situational awareness. Read this first in a fresh session.
> `CLAUDE.md` is the rule book; this is the live state. Architecture:
> `docs/ARCHITECTURE.md`. Hosting: `docs/DEPLOY.md`. Store listing: `ios/APP_STORE.md`.

**Brand entity:** Hoyne Labs LLC · seller name on the App Store: Hoyne Labs · contact hoynelabs@gmail.com
**Live site:** https://cfbgameday.app (Vercel, deploys on push to `main`) · alias https://cfb-gameday-board.vercel.app
**Repo:** https://github.com/ChristianVerdin/cfb-gameday-board (public, MIT) · local `/Users/cv/projects/cfb-gameday`
**iOS:** bundle `com.hoynelabs.cfbgameday` · App Store Connect app id 6809035228 · Team ID 3V73W9NUZ6
**Domain:** cfbgameday.app, Vercel-registered, free first year, renews 2027-09-05 at $15
**State (2026-10-07):** site live with **Week 6** on the new **Tue–Mon window** (58 games Tue 10/6–Sat 10/10: 1 Tue final, 2 Wed, 4 Thu, 5 Fri, 46 Sat), rebuilt locally Wed 13:25 CT: 58/58 forecasts, 58/58 enriched, 0 warnings, every unplayed game lined; IOWA @ WASH (Fri) has no network on ESPN yet and renders TBD · Week 6 promo text re-applied 2026-10-07 (58 games, rain at ≥60%) · ASC key rotated 2026-10-07 (`FQRRWFFM28` revoked, now `WUSAQJV85V`) · `<title>`/meta description are now generated per week (SEO) · **iOS 1.0.1 (4) live; 1.0.2 (5) submitted 2026-10-07**, auto-release on approval · 1.0.2 listing copy staged in `ios/metadata/version/1.0.2/` (game sheet; no `promotionalText` on purpose, so a release keeps the live weekly line), ratings prompt committed, nothing uploaded · trimmed plan below (cv, 2026-10-07)

## Plan (trimmed by cv, 2026-10-07): only what's needed

| When | What | Who |
|---|---|---|
| Wed 10/7 6:25 PM CT | Live game-sheet check moved up to tonight's Wednesday games (background check of `/api/game` for JXST @ KENN and NMSU @ FIU, two pulls 45 s apart) | Claude |
| Sat 10/10 morning | Confirm a Saturday refresh ran (`gh run list --workflow=refresh.yml`, live `generated_at`) | Claude |
| ~~Sun 10/11~~ Wed 10/7 | **1.0.2 (5) submitted 2026-10-07 14:34 CT on cv's go** (submission `03db7f99-14dc-44b9-a001-1b971376fb4b`; releases itself on approval). Version `31e0114f-722b-4c5b-810f-f516603279e8` (PREPARE_FOR_SUBMISSION, release AFTER_APPROVAL), build `45cfcb22-cede-417d-a6a6-6da5c79cffbd` attached; game-sheet description + What's New + keywords applied; promo text on 1.0.2; 5 new 6.5" screenshots (Sat board/weather desk, game sheet scoring, box score, Lines sheet, By TV; `ios/screenshots/1.0.2/`, gitignored) replaced the Week 1 set; age rating override V2 `EIGHTEEN_PLUS` on 1.0.2's declaration `e9c6a4d4-...`; `asc review doctor` 0 errors/0 warnings/0 blocking. Submit: `asc review submit --app 6809035228 --version-id 31e0114f-722b-4c5b-810f-f516603279e8 --build-id 45cfcb22-cede-417d-a6a6-6da5c79cffbd --confirm` | done |
| Wed 10/14 | Week 7 build + `promo_text.py --apply` + `asc reviews list --app 6809035228` (weekly; replaces review notifications for cv) | Claude |
| ~~Before Nov 1~~ | **Done 2026-10-07:** board window Tue–Mon (Tue 7 AM CT cron, 7-date live cap, empty dates skipped), promo rain clause at ≥60% | Claude |
| On hold (cv) | ~~Mac listing~~ done 2026-10-07 · EU DSA checked 2026-10-07: account is declared **not a trader**, so EU listings show no contact info. cv is changing the LLC's business address (Illinois SOS first, then D-U-N-S, then Apple membership → Update your information); revisit trader status only after that, since a trader listing displays the D-U-N-S address | cv |

Done 2026-10-07: Week 6 live, Week 6 promo text, week-aware `<title>`/description, ESPN-text escaping fix,
ratings prompt (`ReviewPrompt.swift`), ASC key rotated (`WUSAQJV85V`), accessibility labels published (Dark Interface,
Differentiate Without Color), search-results/header image made, 1.0.2 copy staged.

**Parked** (revisit only if cv asks): the search-results/header image (cv: don't use it; source stays in `docs/creative-asset.html`), promo video + AI pictures (pipeline committed: `scripts/app_video.py`,
Eleven v4 wired, App Store 886x1920 cut tested offline), Xcode Cloud test-only workflow (needs a shared scheme in
`project.yml` + `ios/ci_scripts/ci_post_clone.sh`), custom product pages, A/B tests, web analytics, campaign links,
1.1 (universal links + widget), Xcode 27.1 / iPhone Duo (Duo screenshots required for submissions from April 2027),
Rivalry Week In-App Event + nominations (decide early November). Calendar: membership renews Feb 27, 2027; dev
cert expires Mar 2, 2027 (Xcode renews it).

**Before Saturday's screenshots:** the simulator must not hold eligible ratings-prompt state, or the 1.0.2
build shows the rating sheet mid-capture. Fresh install, or clear `review.*` with
`xcrun simctl spawn <udid> defaults delete "$(xcrun simctl get_app_container <udid> com.hoynelabs.cfbgameday data)/Library/Preferences/com.hoynelabs.cfbgameday" review.days`
(also `review.first`, `review.askedVersion`). Host-side `defaults` and `simctl spawn defaults <domain>` both miss the
app's container prefs.

### Findings behind it (2026-10-07 analytics pass)

- **Age rating is 4+ on the store, not the documented 17+.** `asc age-rating view` shows every answer NONE and both overrides NONE. Either it was never saved or Apple's 2025 age-rating migration (4+/9+/13+/16+/18+, V2 override) dropped it.
- **App Store funnel, Sep 10–Oct 5** (Analytics Reports, request 15cce5e9, `cfbgameday-reports`): 5 first-time downloads total, none since 9/21; 305 search impressions (~12/day, ~70% outside the US) → 21 product-page views → 4 Get taps. Impression→page view (~7%) is the leak. A search result shows only icon, name, subtitle, rating and the first screenshots, all of which need a new version; promo text appears on the product page, not in search. Sessions, crashes and deletions report nothing (below Apple's privacy thresholds). 1 rating (5.0), 0 written reviews.
- **No web usage data exists.** No analytics on the site by design. Vercel Pro keeps runtime logs 1 day, deeper metrics need Observability Plus. Google indexes only `/`. GitHub: 1 repo view in 14 days; topics widened 2026-10-07.
- **Mac listing** shows "Not verified for macOS".
- **Midweek games were off the board** (Thu–Mon window). Fixed 2026-10-07: the window is now Tue–Mon with a Tue 7 AM CT cron.
- **Analytics download gotcha:** `asc analytics download` re-lists reports per segment, so 65 back-to-back downloads hit Apple's hourly limit (429, retry-after ~37 min, then a rolling few minutes). Space them or download per processing date.


## ASC key rotation — resolved 2026-10-07

`FQRRWFFM28` (App Manager, "release-script") was printed into a 2026-09-25 session transcript and was
revoked by cv on 2026-10-07; Apple now rejects it. The replacement is **`WUSAQJV85V`** (App Manager),
installed at `~/.appstoreconnect/private_keys/AuthKey_WUSAQJV85V.p8` (600), set as the `cfbgameday`
profile and default key in `~/.asc/config.json`, and as `ASC_KEY_ID` in `~/.config/cfb-gameday.env`.
Verified with `asc apps list` / `asc review status`; the old `.p8` is deleted. `R79Z9DL337`
(`cfbgameday-reports`, Admin) was never exposed and is unchanged.

**Lesson for any session:** never select `downloads_url_chains.url` from a Chrome history DB: `data:`
downloads embed their entire payload in that column. Select `target_path` and `tab_url` instead.

---

## 2026-09-05 — Built, shipped to the web, submitted to App Review, all in one day

**State right now**
- iOS 1.0.0 was **rejected 2026-09-05 23:18 CT under Guideline 2.1, Information
  Needed** (new account, no review history; nothing wrong with the build).
  Submission id a0285351-31b8-4551-ac2c-4c8c214ecde7. Reply sent 2026-09-07
  12:44 CT with the six answers and a narrated physical-device recording
  (`ios/review/walkthrough.mp4`, built by `scripts/review_mux.py` from the
  ElevenLabs lines in `ios/review/lines/`). Same text goes in App Review
  Information, Notes. Kit: `ios/APP_REVIEW_REPLY.md`.
- 2026-09-07: cv found revisited tabs rendering blank (Board, Live, Board).
  Root cause: the shared WKWebView was re-parented in `updateUIView`, which
  SwiftUI skips when a tab's inputs are unchanged. Fixed in `WebScreen.swift`
  (`HostView.didMoveToWindow`), verified by `scripts/ios_tab_check.sh` (AXe +
  simulator screenshots). Also fixed: `.a2hs` CSS overrode the `hidden`
  attribute so the Add to Home Screen hint showed inside the app; `sw.js` v4.
  Build 1.0.0 (3) uploaded, attached, notes and the video attachment set,
  and the submission **resubmitted 2026-09-07 13:03 CT, Waiting for Review**,
  all through the `asc` CLI (`brew install asc`, key `cfbgameday` in
  `~/.asc/config.json`). The API refuses `submissions-submit` until the
  rejected item is marked resolved (`asc review items update --resolved true`);
  the web Resubmit button does that step for you. `asc validate` reports
  "app availability is missing" through the v2 API even though pricing is set
  (Free, USA base) and the submission went through; treat it as noise unless
  Apple raises it. Manual release selected: when Approved, click
  **Release This Version**.
- Also done 2026-09-07 with the `asc` CLI: the live listing pulled into
  `ios/metadata/` (asc round-trip, validated), a 1.0.1 metadata file with the
  keyword cleanup the audit asked for (locked until the next version), the
  release script now uploads, attaches, and optionally `--submit`s through
  `asc publish appstore`, and the `asc@rorkai` plugin plus the global
  `app-store-release` skill capture all of this for the next app on the
  account. A background loop in the session polls `asc review status` every
  10 min until the state changes. Reports: a second, Admin key (profile `cfbgameday-reports`) was added
  and the ongoing analytics report request created; the App Manager key
  stays the default. Details in `ios/APP_STORE.md`, Reports.
- Web is live at cfbgameday.app with HSTS, www redirects to apex, service worker
  caches the shell only, `/api/live` is a Vercel Python function CDN-cached 20 s.
- Snapshot refreshes itself: GitHub Action `refresh.yml` runs Thu 9 PM CT and
  Sat 9 AM CT, commits `games.json`/`games.js`, Vercel redeploys. First run
  today rebuilt Week 1 mid-slate and exposed a bug (ESPN nulls odds at kickoff);
  fixed by carrying the prior snapshot's line forward.
- Local mode still works unchanged: `python3 server.py` on 127.0.0.1:8765.

**What Review will see**
- Native tabs Board / Live / Starred / About driving the site through URL hashes,
  pull-to-refresh, offline view with Retry, external links leave the app.
- Copy is scores / venue / weather / posted lines. No book links, no accounts,
  age rating 17+, privacy label "no data collected", `/privacy` and `/support`
  pages on the domain.
- Likely outcomes and the prepared responses are in `ios/APP_STORE.md`.

**2026-09-10 — Approved.** 1.0.0 (3) passed App Review (submission
a0285351 COMPLETE, version a7fbb1ed-f98e-4636-8927-cd3058d491bc in
PENDING_DEVELOPER_RELEASE, release type MANUAL). Week 2 snapshot pushed
2026-09-10 15:45 CT so the first installs see the current slate. Release
with `asc versions release --version-id a7fbb1ed-f98e-4636-8927-cd3058d491bc --confirm`
or the web button, then run the After approval list below.

**Released 2026-09-10 ~15:44 CT.** `asc versions release` → READY_FOR_DISTRIBUTION;
App Store Connect showed "Removed from App Store" / "175 Processing" for ~2 min while
availability propagated (contentStatuses PROCESSING_TO_AVAILABLE), then 175 Available.
Store page live ~15:56 CT: https://apps.apple.com/us/app/cfb-gameday-board/id6809035228.
Release-day marketing pass (same afternoon): store badge + README link pushed, Smart App
Banner / Open Graph / Twitter card / JSON-LD / robots / sitemap on the site, share image
`icons/og.png`, `scripts/promo_text.py` with the Week 2 promotional text applied, Wall of
Apps PR #2481, GitHub profile README section, dailylocks.ai footer link. Details and the
manual follow-ups: `ios/APP_STORE.md` § Marketing surfaces.

## First CI run of the new pipeline (2026-09-17, run 35282517054)

Passed. Enrichment worked from GitHub's runners — `enriched=75`, no 403 — the
generated `index.html` block was written (`75 SportsEvent entries`), the step
summary rendered, and `gameday-bot` committed `games.json games.js index.html`,
which proves the widened `git add`. `sitemap.xml` was unchanged only because
`lastmod` was already today's date.

It also found a real defect on its first run: **8 of 75 kickoff forecasts were
lost to Open-Meteo TLS handshake timeouts on the runner.** That is not a visible
gap — `impact()` runs on `wx=None` and reports "Clean outdoor conditions", so the
live board showed UTEP @ MICH as clean while ESPN's own label said Rain, and
dropped the EXTREME HEAT flag from a 98°F LT @ BAY. The new `warnings`/`counts`
are what made it visible at all; `check.py` warned at 11% and correctly did not
fail the build. `forecast()` now retries once against a whole-run budget of 20
with a 10 s timeout, and the snapshot was rebuilt locally to 0 missing.

**Expect this again.** The runner's network is flakier than this Mac's. If a
gameday snapshot lands with `forecast_failed` in `counts`, rebuild locally and
push rather than leaving it — the weather is the point of the board.

## iOS 1.0.1 (2026-09-17)

**Approved 2026-09-18 13:17 CT** (review took ~19 h from the 18:27 CT submit) —
`AFTER_APPROVAL` released it with no click. Apple's email warns public availability
can lag up to 24 h: at 13:34 CT the iTunes lookup API still reported 1.0.0 while
ASC said `READY_FOR_SALE`. That lag is normal, not a failed release; version state `READY_FOR_DISTRIBUTION` / `READY_FOR_SALE`, submission
`COMPLETE`. The Week 3 promo text carried over as planned. The notes below are the
submission record.

**Submitted for review 2026-09-17 18:27 CT on cv's say-so** — submission
`b8867a34-41e7-449c-b0df-12b9fc7eb220`, state `WAITING_FOR_REVIEW`,
`asc review doctor` reported 0 blockers.

**Release type was switched to `AFTER_APPROVAL`** at cv's request, so it ships
itself the moment Apple approves — nothing to press. 1.0.0 stays `MANUAL`; the
release type is per version, so the next version defaults back to whatever the
script/metadata sets and has to be switched again if the same behaviour is wanted:
```
asc versions update --version-id <VERSION_ID> --release-type AFTER_APPROVAL
```

The Week 3 promotional text was pushed onto the 1.0.1 record before submitting.
Without that, releasing 1.0.1 would have swapped the weekly billboard back to the
evergreen line that `ios/metadata/version/1.0.1/en-US.json` carries as its
off-season default. **Any future version needs the same step**, or run
`promo_text.py --apply` again right after the release.

- Version `1.0.1` id `8e2d8924-410a-42c5-ad1b-abfe684435a0`, `READY_FOR_SALE`
  (was `WAITING_FOR_REVIEW`), release `AFTER_APPROVAL`.
- Build **4** id `62cd0f47-97ce-4725-a820-d9997922c6a0`, `VALID`, attached.
- Submission `b8867a34-41e7-449c-b0df-12b9fc7eb220`, submitted 2026-09-17 23:27 UTC.
- Metadata applied and verified live: the 98-char keyword set and a What's New
  describing the foreground refresh (the drafted "no functional changes" line was
  false once this build existed).
- Change: `WebContainer` observes `willEnterForeground` and reloads only when the
  page is actually holding a stale slate - see the decision table in the commit.
- Status any time: `asc review status --app 6809035228`.
- **On rejection:** playbook in `ios/APP_STORE.md` § likely rejections. The API
  refuses `submissions-submit` until the rejected item is marked resolved
  (`asc review items update --resolved true`); the web Resubmit button does that step.
- Screenshots are still the Week 1 set from 2026-09-05. Dated, not a rejection risk.

**Release-script gotcha found today:** `scripts/release_ios.sh` is not idempotent
after a partial run. Its upload can succeed while the run is cut off before attach,
which leaves an uploaded build plus a created App Store version record and no
build attached. Re-running then fails twice over: `publish appstore` reports
"bundle version must be higher than the previously uploaded version" and
`versions create` reports "cannot create a new version of the App in the current
state". Recovery is not another full run - it is:
```
asc builds list --app 6809035228 --limit 8          # find the uploaded build id
asc versions list --app 6809035228                  # find the existing version id
asc versions attach-build --version-id VID --build-id BID
asc metadata plan --app 6809035228 --dir metadata --version 1.0.1
```
Also note the build list lags several minutes behind a successful upload, so
"not in the list" does not mean "not uploaded".

**Open items**
- **Game sheet shipped 2026-09-30** (web, so the iOS app has it with no build):
  Game button on live/final cards → `#game/<id>` sheet with scoring, box, leaders,
  drives and ESPN win probability, from `/api/game`. Verified on Thu 10/1
  finals; still to watch it refresh mid-game on a live Saturday game. Next iOS version's description/What's New should mention it
  (`ios/metadata/`). Spec: `docs/superpowers/specs/2026-09-30-game-view-design.md`.
- Campaign links need the App Analytics provider token (`pt`); cv reads it from
  Analytics → Acquisition → Campaigns → Generate Campaign Link, then the links in
  `index.html`, `support.html`, `README.md`, the profile README, and the X bio get
  `?pt=…&ct=…&mt=8` (names listed in `ios/APP_STORE.md`).
- Pin `cfb-gameday-board` on the GitHub profile by hand (no API).
- Decide the Apple Silicon Mac checkbox (Pricing and Availability, defaults on).
- ~~Ship 1.0.1~~ — submitted 2026-09-17, live by 2026-09-18. The **native
  ratings prompt** that was bundled into this item was *not* built; it is still open
  for a later version.
- Featuring nominations / In-App Events for Rivalry Week, Championship Saturday, Playoff.
- If a second rejection cites 4.2, the next native lever is a Starred list
  backed by `games.json`.
- Optional, unbuilt: line-movement chip on cards (offered 2026-09-17, cv declined;
  the open/current data is already in the snapshot so it stays cheap), playing
  surface on the card (`enrich.surface` is stored and rendered nowhere, cv declined),
  Telegram ping from the refresh Action (needs a chat ID declared in `CLAUDE.md`),
  starred-game props hook into `sportsbettingml_full_package`.
- Refresh App Store screenshots — still the Week 1 set from 2026-09-05.
- The weekly `promo_text.py --apply` is the one genuinely manual step and is
  deliberately not in the Action, which would mean putting the `.p8` in repo
  secrets. It is cosmetic; skipping a week breaks nothing.

**Things learned the hard way today**
- `vercel link` refuses to run non-interactively here; `.vercel/project.json`
  was written by hand from `vercel project inspect`. The Vercel MCP token
  cannot create projects (403); `vercel project add` can.
- Preview deployments sit behind Vercel Authentication; test on the production alias.
- App Store Connect needs the org's Company Name set via the web form for the
  first app; Xcode cannot create the first record.
- Xcode's "Update to recommended settings" flipped the project to iPhone+iPad,
  which triggers upload error 90474 (iPad orientations). `ios/project.yml` now
  pins `TARGETED_DEVICE_FAMILY: "1"` everywhere and `UIRequiresFullScreen: true`.
- Organizer imports every archive opened with `open`; two archives with the same
  name are easy to confuse. Delete the stale one from
  `~/Library/Developer/Xcode/Archives/<date>/` before distributing.

## Weekly ops (in season)

The snapshot refresh is automatic; the App Store promotional text is **not**.

**Thursday (or whenever the week rolls):**
```
python3 scripts/promo_text.py --apply   # Week N billboard; Apple allows this without review
```
Re-run it after the Friday snapshot if convenient: its weather clause comes from the
forecast and can flip between runs (Week 3 went from rain at 11 kickoffs Thursday to
heat flags at 35 Friday). No Saturday-morning re-apply; cv decided 2026-09-18 that
a day-old weather clause is fine and not worth a local job or the `.p8` in CI.

**If the Action fails or ESPN changes shape:**
```
python3 scripts/refresh_week.py          # Tue..Mon of the slate in progress
python3 scripts/check.py
git add games.json games.js index.html sitemap.xml && git commit -m "Snapshot: ..." && git push
```
`index.html` and `sitemap.xml` are generated too (the SportsEvent block and the
kicker), so they must go in the same commit or the structured data freezes.
`--seo-only` rebuilds just those from the committed `games.json`, no network.
`--no-enrich` skips the per-game ESPN summary pass if you want a fast local run.

**On a gameday morning, do not assume the cron fired.** GitHub creates scheduled
runs late under load and can drop them: measured on this repo, the Thursday cron
due 2026-09-11 02:00 UTC was created 07:08 UTC (5h08m late) and the Saturday one
due 2026-09-12 14:00 UTC was created 16:52 UTC. That is why the schedule is five
crons, each hours ahead of when it is needed (Sat 8 AM backs up Sat 4 AM). Confirm with:
```
gh run list --workflow=refresh.yml --limit 5
curl -s https://cfbgameday.app/games.js | head -c 400 | grep -o '"generated_at":"[^"]*"'
```
`gh workflow run refresh.yml` forces one. It also builds the coming week early: Week 4 was
forced Wed 2026-09-23 09:12 CT, ahead of the 1 PM cron, and went live in about 3 minutes.

## Shipping the next iOS build

```
scripts/release_ios.sh --bump 1.0.1     # or no --bump to keep the version; build number auto-increments
git add ios/project.yml && git commit -m "iOS 1.0.1 (3)" && git push
```

The script regenerates the project, archives, exports an App Store IPA
(`ios/ExportOptions.plist`), validates, and uploads through the App Store
Connect API using `ASC_KEY_ID` / `ASC_ISSUER_ID` from `~/.config/cfb-gameday.env`
and the `.p8` in `~/.appstoreconnect/private_keys/`. Verified end to end on 2026-09-05:
export plus `altool --validate-app` passed with the API key (key id FQRRWFFM28, rotated 2026-10-07 to WUSAQJV85V,
App Manager role; the `.p8` is in `~/.appstoreconnect/private_keys/`, never in git).
`--no-upload` stops at the IPA, then `open ios/build/CFBGameDay.xcarchive` and
upload from Organizer as a fallback. After upload: App Store Connect, add a new
version, What's New, attach the build, submit.

## After approval

1. Click **Release This Version** in App Store Connect.
2. Un-hide the App Store links: remove `hidden` from `#store-link` in
   `support.html` and `#store-footer` in `index.html` (badge already in
   `icons/app-store-badge.svg`, URL `https://apps.apple.com/app/id6809035228`).
3. Add the App Store link to `README.md`.
4. Install the App Store Connect app on the phone for review/ratings pushes.
5. `asc apps wall submit --app 6809035228 --confirm` (free Wall of Apps listing, needs `gh` auth).
6. Ship 1.0.1 with `scripts/release_ios.sh --bump 1.0.1` so the audited keywords go live.
7. Watch `asc testflight crashes list` and `asc testflight feedback list --app 6809035228` the first week.
