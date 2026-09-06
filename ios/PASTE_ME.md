# App Store Connect: copy/paste sheet

Work top to bottom on the "iOS App Version 1.0" page, then the three sidebar pages. Click Save after each page.

## Version page

### Screenshots
Drag the five files ending in `-6.5.png` from `ios/screenshots/` into the 6.5" box. Then "View All Sizes in Media Manager" and drag the five `-6.9.png` files into the 6.9" slot.

### Promotional Text
```
College football Saturdays on one screen: venue, kickoff weather, TV, posted lines, and live cover and total state for every FBS game.
```

### Description
```
CFB GameDay Board puts the whole college football slate on one screen.

BEFORE KICKOFF
- Every FBS game with kickoff time in US Central
- Venue, city, elevation, and a one-tap map
- Kickoff-hour weather at the stadium: temperature, wind, rain chance, humidity, with flags for heat, wind, rain, and altitude
- TV network and streaming service
- Publicly posted point spread, total, and moneyline with the implied final score

DURING THE GAMES
- Live scores, clock, down and distance, last play, red-zone marker
- Whether the favorite is covering and what the total needs, updated every 30 seconds
- A live desk that lists only the games in progress

FILTERS
- Day, time window, conference, ranked only, weather-impact only, starred only
- Lines sheet, by-network board, and a landslide board for the biggest spreads
- Search by team, stadium, city, TV, or conference

DATA
Scores, schedules, and posted lines come from ESPN's public scoreboard. Weather comes from Open-Meteo. No account, no sign-in, no ads.

CFB GameDay Board is an information display. It is not a sportsbook, it does not accept wagers or payments, and it is not betting advice.
```

### Keywords
```
college football,cfb,scores,ncaa football,gameday,weather,spread,odds,live scores,schedule
```

### Support URL
```
https://cfbgameday.app/support
```

### Marketing URL
```
https://cfbgameday.app
```

### Version
Leave `1.0`.

### Copyright
```
2026 Hoyne Labs LLC
```

### Build
Leave empty until Apple emails "has completed processing". Then click the plus, pick 1.0.0 (1), answer export compliance: **No** (HTTPS only).

### App Review Information
- Sign-in required: unchecked
- Contact: your first name, last name, phone, email
- Notes:
```
CFB GameDay Board is an informational sports display: NCAA football scores, venues, kickoff weather, TV listings, and the publicly posted point spread and total for context. No accounts, no sign-in, no purchases, no deposits, no way to place a wager, no sportsbook links. Content comes from our always-on backend at https://cfbgameday.app. No demo account is needed.

PURPOSE AND AUDIENCE
An information display for adult NCAA college football fans in the United States who follow the full Saturday slate. One screen per game: kickoff time in US Central, stadium and city with elevation, kickoff-hour weather at the stadium, TV network or streaming service, the publicly posted spread and total as context, and once games start the live score, clock, down and distance, and whether the game is tracking above or below the posted numbers. Rated 17+ because it displays posted betting lines. Not a sportsbook, no wagers, no payments, no sportsbook links, no betting advice.

SETUP AND ACCESS
No setup, login, credentials, or sample files. Launch and the Board tab loads the current week. Tabs: Board (full slate with day, time, conference, ranked, weather-impact, and starred filters, plus search), Live (games in progress), Starred (games the user starred; stored on the device), About (data sources, privacy, support, source, reload). Pull down to refresh. Venue taps open Apple Maps; ESPN links open Safari. Offline shows a Retry screen. Live scores appear during games (in season Thursday to Saturday plus holiday Sundays and Mondays); otherwise the board shows the upcoming slate and the Live tab shows an empty state.

EXTERNAL SERVICES
ESPN public scoreboard feed (site.api.espn.com) for schedules, scores, game state, TV, and the posted lines ESPN publishes; team logos from ESPN's public image CDN (a.espncdn.com). Open-Meteo (open-meteo.com) for venue geocoding and the kickoff-hour forecast, open data, no key. Our backend at https://cfbgameday.app on Vercel serves the content and proxies ESPN; the app never calls ESPN directly. Apple Maps links for directions. GitHub for the public source and issue tracker. No authentication, payment, analytics, advertising, AI, or push services. No data collected: https://cfbgameday.app/privacy.

REGIONAL DIFFERENCES
None. Identical in every region; NCAA football only, times in US Central, same data for every user.

REGULATED INDUSTRY / THIRD-PARTY MATERIAL
Not a regulated industry: no gambling offered, accepted, facilitated, or linked, so no gaming license applies. No licensed media (no video, audio, or broadcast content). Displays publicly available factual sports data with attribution to ESPN and Open-Meteo in the app and on the support page; team logos as shown on ESPN's public scoreboard, for identification only. Free, no purchases, source public under MIT at https://github.com/ChristianVerdin/cfb-gameday-board.
```

### Version Release
Manually release this version.

Click **Save**.

## Sidebar: App Information

### Subtitle
```
Scores, weather, TV, lines
```

### Category
- Primary: Sports
- Secondary: Reference

### Content Rights
Does not contain, show, or access third-party content. (Public data feeds, no licensed content.)

### Age Rating
Click Edit. Answer **None** / **No** to every question. Where it asks about gambling: Simulated Gambling: None. Real gambling: No. Unrestricted web access: No.
If the computed rating is below 17+, use the age rating override and set **17+** (the app displays posted betting lines). Done, then Save.

## Sidebar: App Privacy

### Privacy Policy URL
```
https://cfbgameday.app/privacy
```

Click Get Started. Choose **No, we do not collect data from this app**. Publish.

## Sidebar: Pricing and Availability

- Price: Free (USD 0)
- Availability: all countries or regions
- Save

## Submit

After the build is attached on the version page: **Add for Review**, then **Submit to App Review**.
