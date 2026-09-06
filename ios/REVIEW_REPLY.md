# Reply to App Review: Guideline 2.1, Information Needed (2026-09-05)

Submission a0285351-31b8-4551-ac2c-4c8c214ecde7, iOS 1.0.0 (1). Apple asked for
six items because the developer account has little review history. Nothing is
rejected; the submission stays open until we reply.

Two things to do, in order:

1. Record the screen recording on a physical iPhone (steps below). Only cv can
   do this; it cannot come from the simulator.
2. In App Store Connect, open the message thread on the version page, click
   **Reply**, paste the text in "Reply text" below, attach the recording, send.
   Then paste the same six answers into **App Review Information > Notes** and
   Save, so future submissions carry them.

## 1. Screen recording (physical device)

- iPhone on the current iOS release. Settings > Control Center, add Screen
  Recording. Install the exact build under review from TestFlight (1.0.0, build 1),
  or the App Store Connect build via Xcode Organizer; do not record a Debug build.
- Airplane mode off, Wi-Fi or cellular on. Cold start: kill the app first.
- Start recording, then:
  1. Tap the app icon from the Home Screen. Launch screen, then the Board tab loads.
  2. Scroll the Board. Tap a day pill, then a time window, then the conference filter.
     Toggle "ranked only" and "weather impact".
  3. Tap a game card so venue, weather, TV, posted line, and proj score are on screen.
     Tap the venue name: Apple Maps opens outside the app. Swipe back into the app.
  4. Pull down to refresh.
  5. Tap the Live tab. On a game day this shows in-progress games with cover and
     total state. Off game day it shows the empty state; that is fine, say so in the reply.
  6. Star two games on Board, then tap the Starred tab.
  7. Tap the About tab. Scroll through Data, Links, and the "Not a sportsbook" footer.
     Tap Privacy policy: Safari opens. Swipe back. Tap Reload board.
  8. Optional, 10 seconds: turn on Airplane mode, pull to refresh, show the offline
     screen and its Retry button, turn Airplane mode off, tap Retry.
- Stop recording. Keep it under 3 minutes. Trim the Control Center frames off
  the start in Photos. AirDrop the .mp4 to the Mac and attach it in the reply.
  If App Store Connect rejects the file size, compress with
  `ffmpeg -i in.mp4 -vf scale=-2:1280 -crf 28 out.mp4` or attach it in the
  Notes field via the attachment button instead.

## Reply text

Paste the whole block. Item 1 assumes the recording is attached to the same reply.

```
Thank you for the review. Answers to each item follow. The same text has been added to the App Review Information notes for this app.

1. SCREEN RECORDING
Attached. It was captured on a physical iPhone running the current iOS release, starting from the Home Screen launch. It shows the Board tab with filters, a game card with venue, weather, TV and the posted line, the venue link opening Apple Maps, pull-to-refresh, the Live tab, starring games and the Starred tab, and the About tab with the privacy and support links. There is no account registration, login, or account deletion, because the app has no accounts. There is no user-generated content. There is no paid content: no in-app purchases, subscriptions, or payments of any kind.

2. PURPOSE AND AUDIENCE
CFB GameDay Board is an information display for NCAA college football fans in the United States. On a college football Saturday a fan following the full slate has to check a scores site, a weather site, a TV listings site, and a schedule to know when each game kicks off, on what channel, in what conditions, and how it is going. This app puts that on one screen per game: kickoff time in US Central, stadium and city with elevation, the kickoff-hour weather forecast at the stadium, the TV network or streaming service, the publicly posted point spread and total as context for how lopsided the matchup is expected to be, and once games start, the live score, clock, down and distance, and whether the game is tracking above or below those posted numbers. The audience is adult fans who watch several games at once. The app is rated 17+ because it displays publicly posted betting lines. It is not a sportsbook, it does not accept wagers or payments, it does not link to any sportsbook, and it gives no betting advice.

3. SETUP AND ACCESS
No setup, login, credentials, or sample files are needed. Launch the app and the Board tab loads the current week's games. Tabs: Board (the full slate, with day, time window, conference, ranked, weather-impact, and starred filters, plus search by team, stadium, city, TV network, or conference), Live (only games in progress), Starred (games the user tapped the star on; stored on the device), and About (data sources, privacy policy, support, source code, reload). Pull down on any board to refresh. Tapping a venue opens Apple Maps; tapping a game's ESPN link opens Safari. If the device is offline the app shows an offline screen with a Retry button. Live scores appear during games, which in season run Thursday through Saturday plus some holiday Sundays and Mondays; outside those windows the board shows the upcoming slate with venue, weather, TV, and posted lines, and the Live tab shows an empty state.

4. EXTERNAL SERVICES
- ESPN public scoreboard feed (site.api.espn.com): schedules, scores, game state, TV listings, and the posted point spread, total, and moneyline that ESPN publishes with each game. Team logo images are loaded from ESPN's public image CDN (a.espncdn.com), the same images shown on ESPN's scoreboard.
- Open-Meteo (open-meteo.com): venue geocoding and the hourly weather forecast at the stadium for the kickoff hour. Open data, no API key.
- Our own backend at https://cfbgameday.app, hosted on Vercel: serves the app content and proxies the ESPN scoreboard for live updates. The app never talks to ESPN directly; every request goes to cfbgameday.app.
- Apple Maps (maps.apple.com links) for venue directions, opened outside the app.
- GitHub (github.com) hosts the public source code and the issue tracker linked from the About tab and the support page.
No authentication service, no payment processor, no analytics or advertising SDK, no AI service, no push notifications. The app collects no data; see https://cfbgameday.app/privacy.

5. REGIONAL DIFFERENCES
None. The app functions identically in every region. Content is NCAA college football only, all times are shown in US Central, and the same data is served to every user regardless of location. No feature is enabled, disabled, or changed by region.

6. REGULATED INDUSTRY / THIRD-PARTY MATERIAL
The app does not operate in a regulated industry. It does not offer, accept, or facilitate gambling, and it does not link to any gambling operator, so no gaming license applies. It contains no licensed or protected third-party media: no game video, audio, or broadcast content. It displays publicly available factual sports data (schedules, scores, weather, TV listings, and the betting lines ESPN publishes on its public scoreboard) with attribution to ESPN and Open-Meteo in the app and on the support page. Team logos are displayed as they appear on ESPN's public scoreboard, for team identification only. The app is free, has no purchases, and the full source code is public at https://github.com/ChristianVerdin/cfb-gameday-board under the MIT license.

Contact for any follow-up: Christian Verdin, Hoyne Labs LLC, hoynelabs@gmail.com, and the phone number on file in App Review Information.
```

## Notes field (App Review Information)

The Notes field gets a condensed version of items 2 through 6 with a one-line lead.
The exact text is the `Notes:` block in `PASTE_ME.md` (also quoted under
"Review notes" in `APP_STORE.md`). Paste it over the current Notes and Save.

## After sending

- Update `CONTEXT.md`: date replied, and that the status should move back to
  In Review. Apple usually responds within 24 to 48 hours of a reply.
- If they come back with 4.2 or 5.3 instead, the prepared responses are in
  the outcomes table in `APP_STORE.md`.
