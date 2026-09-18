# CONTEXT.md — CFB GameDay Board

> Single-page situational awareness. Read this first in a fresh session.
> `CLAUDE.md` is the rule book; this is the live state. Architecture:
> `docs/ARCHITECTURE.md`. Hosting: `docs/DEPLOY.md`. Store listing: `ios/APP_STORE.md`.

**Brand entity:** Hoyne Labs LLC · seller name on the App Store: Hoyne Labs · contact hoynelabs@gmail.com
**Live site:** https://cfbgameday.app (Vercel, deploys on push to `main`) · alias https://cfb-gameday-board.vercel.app
**Repo:** https://github.com/ChristianVerdin/cfb-gameday-board (public, MIT) · local `/Users/cv/projects/cfb-gameday`
**iOS:** bundle `com.hoynelabs.cfbgameday` · App Store Connect app id 6809035228 · Team ID 3V73W9NUZ6
**Domain:** cfbgameday.app, Vercel-registered, free first year, renews 2027-09-05 at $15
**State (2026-09-18):** site live with Week 3 · **iOS 1.0.1 (4) live on the App Store** (approved and auto-released by 2026-09-18, `READY_FOR_SALE`) · nothing waiting on Apple

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

**If the Action fails or ESPN changes shape:**
```
python3 scripts/refresh_week.py          # Thu..Mon of the current/next slate
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
due 2026-09-12 14:00 UTC was created 16:52 UTC. That is why the schedule is four
crons each sitting hours ahead of when it is needed. Confirm with:
```
gh run list --workflow=refresh.yml --limit 5
curl -s https://cfbgameday.app/games.js | head -c 400 | grep -o '"generated_at":"[^"]*"'
```
`gh workflow run refresh.yml` forces one.

## Shipping the next iOS build

```
scripts/release_ios.sh --bump 1.0.1     # or no --bump to keep the version; build number auto-increments
git add ios/project.yml && git commit -m "iOS 1.0.1 (3)" && git push
```

The script regenerates the project, archives, exports an App Store IPA
(`ios/ExportOptions.plist`), validates, and uploads through the App Store
Connect API using `ASC_KEY_ID` / `ASC_ISSUER_ID` from `~/.config/cfb-gameday.env`
and the `.p8` in `~/.appstoreconnect/private_keys/`. Verified end to end on 2026-09-05:
export plus `altool --validate-app` passed with the API key (key id FQRRWFFM28,
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
