# App Store listing and submission notes

Status: 1.0.0 (1) submitted 2026-09-05, manual release. 2026-09-05 23:18 Apple asked
for more information (Guideline 2.1, six items). The reply and the screen-recording
steps are in `REVIEW_REPLY.md`.
Live state and what to do on approval or rejection: `../CONTEXT.md`.
The copy below is also laid out field-by-field in `PASTE_ME.md`.

Everything below is copy-paste ready for App Store Connect. Nothing in it
promises wagering, picks, or "locks". Keep it that way through Review.

## Prerequisites (must be true before you upload)

- https://cfbgameday.app serves the board, `/privacy`, and `/support`.
  `BoardURL` / `BoardHost` in `ios/project.yml` point at that domain.
- `ios/project.yml` carries `DEVELOPMENT_TEAM: 3V73W9NUZ6` (Hoyne Labs LLC), so
  automatic signing survives `xcodegen generate`.
- The app has been run on a physical iPhone (Review checks this, 2.1).
- Vercel project stays deployed during Review. A dead backend is a 2.1 rejection.

## Build and upload

```
scripts/release_ios.sh --bump 1.0.1   # from the repo root; see CONTEXT.md for the API key setup
```

Fallback by hand: `scripts/release_ios.sh --no-upload`, then
`open ios/build/CFBGameDay.xcarchive`, Distribute App, App Store Connect, Upload.

## App Store Connect: app record

| Field | Value |
| --- | --- |
| Name | CFB GameDay Board |
| Subtitle | Scores, weather, TV, lines |
| Bundle ID | com.hoynelabs.cfbgameday |
| SKU | cfbgameday-ios |
| Primary language | English (U.S.) |
| Primary category | Sports |
| Secondary category | Reference |
| Price | Free |
| In-App Purchases | None |
| Age rating | 17+ (see answers below) |
| Copyright | 2026 Hoyne Labs LLC |
| Privacy Policy URL | https://cfbgameday.app/privacy |
| Support URL | https://cfbgameday.app/support |
| Marketing URL | https://cfbgameday.app |

### Age rating questionnaire

Answer "None" to everything except:

- Gambling and Contests: **Simulated Gambling: No. Gambling: No.** Then, under
  "Unrestricted Web Access": No. Pick **17+** manually if the wizard lands on
  lower, because the app displays publicly posted betting lines. Being honest
  here avoids a metadata rejection later.

### App Privacy (nutrition label)

- Data collection: **No, we do not collect data from this app.**
- Tracking: No.

This is accurate: no analytics, no accounts, no identifiers. The only network
calls are to cfbgameday.app, which proxies ESPN and serves static files.

## Version information

**Promotional text** (170 chars, editable without a new build)

> College football Saturdays on one screen: venue, kickoff weather, TV, posted lines, and live cover and total state for every FBS game.

**Description**

> CFB GameDay Board puts the whole college football slate on one screen.
>
> BEFORE KICKOFF
> - Every FBS game with kickoff time in US Central
> - Venue, city, elevation, and a one-tap map
> - Kickoff-hour weather at the stadium: temperature, wind, rain chance, humidity, with flags for heat, wind, rain, and altitude
> - TV network and streaming service
> - Publicly posted point spread, total, and moneyline with the implied final score
>
> DURING THE GAMES
> - Live scores, clock, down and distance, last play, red-zone marker
> - Whether the favorite is covering and what the total needs, updated every 30 seconds
> - A live desk that lists only the games in progress
>
> FILTERS
> - Day, time window, conference, ranked only, weather-impact only, starred only
> - Lines sheet, by-network board, and a landslide board for the biggest spreads
> - Search by team, stadium, city, TV, or conference
>
> DATA
> Scores, schedules, and posted lines come from ESPN's public scoreboard. Weather comes from Open-Meteo. No account, no sign-in, no ads.
>
> CFB GameDay Board is an information display. It is not a sportsbook, it does not accept wagers or payments, and it is not betting advice.

**Keywords** (100 chars)

> college football,cfb,scores,ncaa football,gameday,weather,spread,odds,live scores,schedule

**What's New** (1.0.0)

> First release. Week-by-week slate with venue, weather, TV, posted lines, and live cover and total state.

## Screenshots

Required sizes: 6.9" (iPhone 17 Pro Max / 16 Pro Max, 1320×2868) and 6.5"
(1284×2778 or 1242×2688). Take them from the simulator with the live site on a
Saturday so the Live tab has content:

```
xcrun simctl boot "iPhone 17 Pro Max"
xcrun simctl install booted ios/build/DerivedData/Build/Products/Debug-iphonesimulator/CFBGameDay.app
xcrun simctl launch booted com.hoynelabs.cfbgameday
xcrun simctl io booted screenshot shot-1-board.png
```

Plan (5 shots): Board with day pills and stats, a live card with cover/total,
Lines sheet view, Weather desk with heat/wind flags, About tab. No device
frames needed. Screenshots must show this app, not a mock.

## Review notes (App Review Information)

Rewritten 2026-09-06 to answer Apple's 2.1 information request up front. Same text
as `REVIEW_REPLY.md`, minus the screen-recording item.

> CFB GameDay Board is an informational sports display: NCAA football scores, venues, kickoff weather, TV listings, and the publicly posted point spread and total for context. No accounts, no sign-in, no purchases, no deposits, no way to place a wager, no sportsbook links. Content comes from our always-on backend at https://cfbgameday.app. No demo account is needed.
>
> PURPOSE AND AUDIENCE
> An information display for adult NCAA college football fans in the United States who follow the full Saturday slate. One screen per game: kickoff time in US Central, stadium and city with elevation, kickoff-hour weather at the stadium, TV network or streaming service, the publicly posted spread and total as context, and once games start the live score, clock, down and distance, and whether the game is tracking above or below the posted numbers. Rated 17+ because it displays posted betting lines. Not a sportsbook, no wagers, no payments, no sportsbook links, no betting advice.
>
> SETUP AND ACCESS
> No setup, login, credentials, or sample files. Launch and the Board tab loads the current week. Tabs: Board (full slate with day, time, conference, ranked, weather-impact, and starred filters, plus search), Live (games in progress), Starred (games the user starred; stored on the device), About (data sources, privacy, support, source, reload). Pull down to refresh. Venue taps open Apple Maps; ESPN links open Safari. Offline shows a Retry screen. Live scores appear during games (in season Thursday to Saturday plus holiday Sundays and Mondays); otherwise the board shows the upcoming slate and the Live tab shows an empty state.
>
> EXTERNAL SERVICES
> ESPN public scoreboard feed (site.api.espn.com) for schedules, scores, game state, TV, and the posted lines ESPN publishes; team logos from ESPN's public image CDN (a.espncdn.com). Open-Meteo (open-meteo.com) for venue geocoding and the kickoff-hour forecast, open data, no key. Our backend at https://cfbgameday.app on Vercel serves the content and proxies ESPN; the app never calls ESPN directly. Apple Maps links for directions. GitHub for the public source and issue tracker. No authentication, payment, analytics, advertising, AI, or push services. No data collected: https://cfbgameday.app/privacy.
>
> REGIONAL DIFFERENCES
> None. Identical in every region; NCAA football only, times in US Central, same data for every user.
>
> REGULATED INDUSTRY / THIRD-PARTY MATERIAL
> Not a regulated industry: no gambling offered, accepted, facilitated, or linked, so no gaming license applies. No licensed media (no video, audio, or broadcast content). Displays publicly available factual sports data with attribution to ESPN and Open-Meteo in the app and on the support page; team logos as shown on ESPN's public scoreboard, for identification only. Free, no purchases, source public under MIT at https://github.com/ChristianVerdin/cfb-gameday-board.

Contact: your name, phone, and email as registered with the developer account.

## Export compliance

`ITSAppUsesNonExemptEncryption` is `false` in Info.plist (HTTPS only). No ERN needed.

## Likely Review outcomes and the response

| Result | Why | Response |
| --- | --- | --- |
| Approved | Sports scores + weather + TV, native tabs/about/offline/refresh, backend up, honest metadata | Ship |
| 4.2 Minimum functionality | Reviewer sees only a web page | Point to native tabs, pull-to-refresh, offline state, About; if they insist, add a native Starred list backed by `games.json` in 1.1 |
| 2.1 Performance | Backend unreachable during review | Check Vercel status; never submit while the domain is mid-migration |
| 2.1 Information Needed | New developer account, Apple wants a device recording and six written answers | Received 2026-09-05. Reply text and recording steps: `REVIEW_REPLY.md` |
| 5.3 Gaming | Copy reads as a wagering aid | Reply that no bets are placed, no books are linked, and lines are ESPN's public data; do not add disclaimers that sound like a sportsbook |
| Metadata rejected | Screenshots do not match the app | Re-take from the simulator with the current build |

Do not argue "it is a PWA". Fix and resubmit.
