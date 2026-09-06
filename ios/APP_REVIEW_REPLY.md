# Guideline 2.1 reply — submission a0285351 (1.0.0 (1), rejected 2026-09-05 23:18)

Apple asked for six items because the account has no review history. Nothing in
the build needs to change. Do the three steps below, then click **Resubmit to
App Review** on the same build.

## Step 1: screen recording (physical iPhone, latest iOS)

Install the submitted build on the phone through TestFlight (App Store Connect,
TestFlight tab, add yourself as an internal tester for build 1.0.0 (1)) or run
it from Xcode with the phone plugged in. Then Control Center, Screen Record,
and walk this in order. Target 60 to 90 seconds. No narration needed.

1. Home screen. Tap the CFB GameDay Board icon so the recording starts with launch.
2. Board tab loads the slate. Scroll a few cards: venue, kickoff time, weather line, TV, posted line and gold `proj` score.
3. Tap a day pill and a conference filter, then clear them. Type a team name in search, clear it.
4. Tap a venue to open Maps (shows external links leave the app), come back.
5. Pull down to refresh.
6. Live tab. On a Sunday it shows final cards with the cover and total state resolved; that is fine, say so in the reply.
7. Star two games, open the Starred tab.
8. About tab: data sources, Privacy policy, Support links (tap Privacy, come back).
9. Airplane mode on, pull to refresh, show the offline view and Retry. Airplane mode off, Retry.
10. Stop recording.

AirDrop the .mp4 to the Mac. Attach it in the App Store Connect reply box
(paperclip icon) and also under App Review Information, Attachments, on the
version page. Keep it under 500 MB; Settings, Screen Recording quality does
not matter.

## Step 2: reply text (paste into "Reply to App Review")

```
Thank you for the review. The requested screen recording is attached; it was captured on a physical iPhone running the current iOS release and begins with launching the app. The same information has been added to the App Review Information notes.

1. Screen recording
Attached. It shows launch, the Board tab with the week's slate (venue, kickoff time, kickoff-hour weather, TV, posted line), day and conference filters, search, the venue map link opening in Apple Maps, pull-to-refresh, the Live tab (on a non-game day it shows the most recent finals with the cover and total state resolved), starring games and the Starred tab, the About tab with privacy and support links, and the offline state with Retry. The app has no account registration, login, or deletion flows, no user-generated content, and no paid content or features.

2. Purpose and audience
CFB GameDay Board is a one-screen information display for NCAA FBS college football Saturdays. It is for fans who want to know, for every game on the slate, where it is played, when it kicks off, what the weather will be at the stadium at kickoff, which network carries it, and what the publicly posted point spread and total are, followed by live scores and whether the favorite is covering as the games play. The problem it solves is that this information is normally spread across several sites and apps; the board puts the whole slate on one screen with filters. It is free, has no ads, no accounts, and collects no data. It is not a sportsbook, does not accept wagers or payments, does not link to any sportsbook, and is not betting advice. It is rated 17+ because it displays publicly posted betting lines for context.

3. Setup and access
No setup, login, credentials, or sample files are required. Launch the app and the Board tab loads the current week's slate. Board, Live, and Starred are native tabs over the same board; About is native. Pull down on any tab to refresh. Tap a star on a card to add a game to Starred. Live scores appear during game windows (Thursday through Saturday in season); outside those windows the board shows the upcoming slate with lines and weather, and the Live tab shows the most recent finals.

4. External services
- Our own backend at https://cfbgameday.app (hosted on Vercel), which serves the board and a small proxy for live scores.
- ESPN's public college football scoreboard feed, for schedules, scores, team logos, and the posted point spread, total, and moneyline. Read-only.
- Open-Meteo (open-meteo.com), for kickoff-hour weather at each stadium's coordinates. Read-only, no key.
- Apple Maps, opened outside the app when the user taps a venue.
No authentication services, payment processors, analytics SDKs, advertising SDKs, or AI services are used.

5. Regional differences
None. The app functions identically in every region. All content is US college football and all times are shown in US Central time regardless of the user's locale.

6. Regulated industry or protected material
The app does not operate in a regulated industry. It does not offer, facilitate, or link to gambling; it only displays odds that ESPN publishes publicly, attributed to ESPN. Scores and schedules are public ESPN data, weather is from Open-Meteo's open API, and team logos are ESPN's public assets. There is no other third-party material.
```

## Step 3: App Review Information, Notes field

Replace the current note with the block below (the reply text from Step 2
minus the opening paragraph and item 1, with the recording attached beside it).

```
CFB GameDay Board is a one-screen information display for NCAA FBS college football Saturdays: venue, kickoff time, kickoff-hour stadium weather, TV network, the publicly posted point spread and total, then live scores and cover/total state during games. Free, no ads, no accounts, no data collected. Not a sportsbook: no wagers, no payments, no sportsbook links, not betting advice. Rated 17+ because it shows publicly posted lines.

SETUP: none. No login, credentials, or sample files. Launch and the Board tab loads the week's slate. Board, Live, Starred are native tabs over the same board; About is native. Pull down to refresh. Live scores appear Thursday to Saturday in season; otherwise the board shows the upcoming slate and the Live tab shows the latest finals.

EXTERNAL SERVICES: our backend at https://cfbgameday.app (Vercel); ESPN's public college football scoreboard feed (schedules, scores, logos, posted lines; read-only); Open-Meteo (kickoff-hour weather at stadium coordinates; read-only, no key); Apple Maps opens outside the app for venues. No auth, payment, analytics, ad, or AI services.

REGIONS: identical in every region. US college football content, all times in US Central.

REGULATED / PROTECTED MATERIAL: none. Odds shown are ESPN's public data with attribution; scores, schedules, and logos are ESPN's public data; weather is Open-Meteo's open API.

A screen recording from a physical iPhone is attached under Attachments.
```

Contact fields stay as registered (Christian Verdin, phone, hoynelabs@gmail.com).

## Step 4: resubmit

Version page, Save. Back on the submission page, **Resubmit to App Review**.
Same build 1.0.0 (1); do not upload a new one. Then update `CONTEXT.md` with
the resubmission time.
