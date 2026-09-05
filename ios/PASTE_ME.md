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
CFB GameDay Board is an informational sports display: NCAA football scores, venues, kickoff weather, TV listings, and the publicly posted point spread and total for context. There are no accounts, no sign-in, no purchases, no deposits, and no way to place a wager. The app does not link to any sportsbook.

The content is served from our own backend at https://cfbgameday.app, which is always on. The Board, Live, and Starred tabs show the same live board filtered natively; pull down to refresh. The About tab, offline handling, and external-link routing (maps, ESPN game pages) are native.

No demo account is needed. Live scores appear on game days (Thursday to Saturday during the season); outside game windows the board shows the upcoming slate with lines and weather.
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
