# Guideline 2.1 reply — submission a0285351 (1.0.0 (1), rejected 2026-09-05 23:18)

Apple asked for six items because the account has no review history. Nothing in
the build needs to change. Do the three steps below, then click **Resubmit to
App Review** on the same build.

## Step 0: prerequisites (10 minutes, one time)

- iPhone 14 ("Christian's iPhone (2)") updated to the current iOS release
  (Settings, General, Software Update). Apple said "latest operating system".
- The phone signed in to the same Apple ID that is on the Hoyne Labs developer
  team, with the TestFlight app installed from the App Store.
- A voiceover is optional. Apple only needs a screen recording of the real app;
  a silent one is accepted. If you want narration, Step 1c covers it.

## Step 1a: put build 1.0.0 (1) on the phone (TestFlight)

1. App Store Connect, CFB GameDay Board, **TestFlight** tab.
2. Left sidebar, Internal Testing, **+** to create a group named `Hoyne`.
   Add yourself as a tester. Leave "Enable automatic distribution" on.
3. In the group, Builds, **+**, pick 1.0.0 (1). Internal groups need no beta
   review. If it asks about export compliance, answer No (HTTPS only).
4. On the phone, open TestFlight, accept the invite from the email or the
   in-app list, Install.

Fallback: plug the phone in, `cd ios && xcodegen generate && open CFBGameDay.xcodeproj`,
select the phone as the run destination, press Run. Trust the developer
under Settings, General, VPN and Device Management if iOS asks.

## Step 1b: record the walkthrough (physical iPhone)

Settings, Control Center, add **Screen Recording** if it is not there.
Turn on Do Not Disturb so no banner lands in the clip. Then:

1. On the home screen, open Control Center, tap the record button, wait for
   the 3-second countdown, and swipe back to the home screen before it starts.
2. Tap the **CFB GameDay Board** icon. The recording must begin with the launch.
3. Board tab loads the slate. Scroll slowly through four or five cards so
   venue, kickoff time, weather line, TV, and the posted line with the gold
   `proj` score are readable.
4. Tap a day pill, tap a conference filter, then clear both.
5. Tap the search field, type a team name, wait for the board to narrow, clear it.
6. Tap a venue name. Apple Maps opens. Swipe back to the app.
7. Pull down to refresh.
8. **Live** tab. On a non-game day it shows the latest finals with the cover
   and total resolved. That is fine; the reply text says so.
9. Star two games on the Board tab, then open the **Starred** tab.
10. **About** tab. Scroll to Links, tap Privacy policy, come back.
11. Open Control Center, turn on Airplane Mode, return to the app, pull to
    refresh, show the offline view. Turn Airplane Mode off, tap Retry.
12. Open Control Center, tap the red record button to stop.

Target 60 to 90 seconds. AirDrop the .mp4 from Photos to the Mac and save it
as `ios/review/walkthrough-raw.mp4` (the folder is gitignored).

## Step 1c: optional narration with ElevenLabs

Apple does not require audio. Only do this if you want the clip to explain
itself. Two rules: the narration describes what is on screen and never
promises picks, wagers, or "locks"; and the video track stays the untouched
phone recording, since Apple wants a real device capture.

Script, one line per beat, about 75 seconds read at a normal pace:

```
This is CFB GameDay Board, launched from the home screen on an iPhone.
The Board tab shows every FBS game this week. Each card has the venue, kickoff time in Central, the kickoff-hour weather at the stadium, the TV network, and the publicly posted line with the implied score.
Day and conference filters narrow the slate. Search finds a team, stadium, city, or network.
Tapping a venue opens Apple Maps outside the app.
Pull down to refresh.
The Live tab lists games in progress with score, clock, and whether the favorite is covering. Between game days it shows the latest finals.
Starring a game adds it to the Starred tab.
About lists the data sources, ESPN and Open-Meteo, with links to the privacy policy and support page.
With no connection, the app shows an offline view and a Retry button.
There are no accounts, no purchases, no ads, and no wagering. It is an information display.
```

Generate the audio in ElevenLabs (elevenlabs.io, Text to Speech, a neutral
voice, model Multilingual v2 or Flash, speed 1.0) and save it as
`ios/review/narration.mp3`. Or ask a Claude session in this repo to generate
it through the ElevenLabs connector and drop it in that path.

Mux without re-encoding the video. If the narration is shorter than the
recording, it simply ends early; if it is longer, the phone recording is not
trimmed, so re-record the narration shorter instead:

```
mkdir -p ios/review
ffmpeg -i ios/review/walkthrough-raw.mp4 -i ios/review/narration.mp3 \
  -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a 128k -shortest \
  ios/review/walkthrough.mp4
ffprobe ios/review/walkthrough.mp4 2>&1 | rg "Duration|Stream"
```

Watch it once end to end before attaching it. If timing is off, cut the
narration into lines and adjust with `-itsoffset`, or drop the audio and
attach `walkthrough-raw.mp4`; silent is fine.

## Step 2: reply text (paste into "Reply to App Review")

On the submission page (the one showing Rejected), click **Reply to App
Review**, paste the block below, attach `ios/review/walkthrough.mp4` with the
paperclip (under 500 MB), Send.

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

App Store Connect, Distribution tab, the 1.0.0 version page, scroll to **App
Review Information**. Replace the Notes with the block below and add the same
video under **Attachments**. Click Save at the top right.

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
