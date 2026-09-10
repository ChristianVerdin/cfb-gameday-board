# CONTEXT.md — CFB GameDay Board

> Single-page situational awareness. Read this first in a fresh session.
> `CLAUDE.md` is the rule book; this is the live state. Architecture:
> `docs/ARCHITECTURE.md`. Hosting: `docs/DEPLOY.md`. Store listing: `ios/APP_STORE.md`.

**Brand entity:** Hoyne Labs LLC · seller name on the App Store: Hoyne Labs · contact hoynelabs@gmail.com
**Live site:** https://cfbgameday.app (Vercel, deploys on push to `main`) · alias https://cfb-gameday-board.vercel.app
**Repo:** https://github.com/ChristianVerdin/cfb-gameday-board (public, MIT) · local `/Users/cv/projects/cfb-gameday`
**iOS:** bundle `com.hoynelabs.cfbgameday` · App Store Connect app id 6809035228 · Team ID 3V73W9NUZ6
**Domain:** cfbgameday.app, Vercel-registered, free first year, renews 2027-09-05 at $15

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

**Open items**
- Release 1.0.0, then confirm https://apps.apple.com/app/id6809035228 renders (up to 24 h).
- If a second rejection cites 4.2, the next native lever is a Starred list
  backed by `games.json`.
- Optional, unbuilt: line-movement chip on cards, Telegram ping from the refresh
  Action (needs a chat ID declared in `CLAUDE.md`), starred-game props hook into
  `sportsbettingml_full_package`.

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

Nothing manual. If the Action fails or ESPN changes shape:

```
python3 scripts/refresh_week.py      # Thu..Mon of the current/next slate
python3 scripts/check.py
git add games.json games.js && git commit -m "Snapshot: ..." && git push
```

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
