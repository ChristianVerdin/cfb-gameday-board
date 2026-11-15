# Pro Football Board: App Store notes

Bundle `com.hoynelabs.profootballboard` (widget `.widget`, tests `.tests`), team 3V73W9NUZ6, Hoyne Labs LLC.
Version 1.0.0, iOS 17.0+, iPhone and iPad. Stats only: no wagering content or vocabulary anywhere, including metadata and screenshots
(`scripts/check_nfl.py` scans this folder for it).

## Listing copy

- App info: `metadata/app-info/en-US.json` (name, subtitle, privacy URL). Category: Sports (`metadata/categories.json`).
- Version copy: `metadata/version/1.0.0/en-US.json` (description, keywords, promotional text, What's New, URLs).
- Support https://cfbgameday.app/nfl/support, privacy https://cfbgameday.app/nfl/privacy, marketing https://cfbgameday.app/nfl.
  The pages are `nfl/support.html` and `nfl/privacy.html` in this repo and must be live before submission.
- Name, subtitle, icon and keywords carry no NFL marks, team names or logos. "NFL" appears once in the description,
  nominatively ("fans of NFL games"). The independence disclaimer closes the description and sits in About.
- Required footer text (About, web footer): "Independent and unofficial. Not affiliated with, endorsed or sponsored by the
  National Football League or any team. Scores and play data via ESPN. Season metrics from nflverse (CC BY 4.0).
  Weather by Open-Meteo.com (CC BY 4.0)."
- Icon: `icon/make_icon.swift` draws it (`swift icon/make_icon.swift <out.png>`), output is the single 1024 PNG in
  `AppIcon.appiconset`. Navy field, gold yard lines, gold football, no text or marks.
- Screenshots: capture from the simulator (iPhone 6.9" and iPad 13"), `screenshots/` is gitignored. Use only the
  board, game sheet, drives, win probability chart and widgets. No team logos exist in the app.

## Age rating answers

Every content question is None, so the expected rating is 4+.

| Question | Answer |
| --- | --- |
| Cartoon or fantasy violence | None |
| Realistic violence | None |
| Prolonged graphic or sadistic realistic violence | None |
| Profanity or crude humor | None |
| Mature or suggestive themes | None |
| Horror or fear themes | None |
| Sexual content or nudity (graphic or not) | None |
| Alcohol, tobacco or drug use or references | None |
| Medical or treatment information | None |
| Health or wellness topics | No |
| Gambling (real) | No |
| Simulated gambling | None |
| Contests | None |
| Loot boxes | No |
| Unrestricted web access | No (links open in Safari only, no in-app web views) |
| User-generated content | No |
| Messaging and chat | No |
| Advertising | No |
| Parental controls, age assurance | No |

The app shows scores and statistics. It has no wagering content of any kind.

## Privacy label

Data Not Collected. No accounts, no analytics, no ads, no third-party SDKs, no tracking.
Followed teams and cached scores stay on the device. Requests go to cfbgameday.app, which sends no identifiers. The host keeps standard access logs (IP address, user agent, URL) for security and operations only; they are not linked to a person, so the answer stays Data Not Collected, the same as the CFB app.

Privacy manifests (`PrivacyInfo.xcprivacy`) ship in the app and the widget: no tracking, no collected data, UserDefaults reason CA92.1.

Before submitting, verify on a device or simulator every feature the description names: Following tab with a followed team, the widget families, and the Shortcuts phrases.
No App Tracking Transparency prompt. `ITSAppUsesNonExemptEncryption` is false.

## Review notes (paste into App Review Information)

Pro Football Board is an independent native SwiftUI app by Hoyne Labs LLC. It needs no sign-in, so there are no
demo credentials. It is a separate product from our other app, CFB GameDay Board, and is not a web wrapper or a
re-skin of it.

How it differs from CFB GameDay Board:
- Different sport and data model: pro football only, with its own schedule logic (byes, flex weeks, playoff rounds)
  and its own season metrics from nflverse.
- Native game sheet: scoring summary, team stats, leaders and a drive tracker with a field-position graphic, all
  rendered with SwiftUI. Nothing is a web view.
- Win probability chart built with Swift Charts.
- Widgets with team configuration, and App Intents for Shortcuts and Siri.
- A Following tab for chosen teams, a live desk that ranks games in progress, iPad layouts.
- Statistics only: no wagering content of any kind.

Content and rights: team names appear as plain-text abbreviation chips in team colors. There are no team
logos, league marks or player photos. The footer states that the app is independent and unofficial. Scores and
play data come from ESPN's public feed, season metrics from nflverse (CC BY 4.0), weather from Open-Meteo.com
(CC BY 4.0), all fetched through our server at cfbgameday.app.

To see live state in review: the board loads the current week. Outside game windows games show as scheduled or
final, and the game sheet opens for any final game. Support: hoynelabs@gmail.com.

## TestFlight plan

1. Create the app record (name Pro Football Board, bundle `com.hoynelabs.profootballboard`, SKU `profootballboard`,
   primary language English (U.S.)). Put its numeric id in `ios-pfb/.asc-app-id` (gitignored) or `PFB_APP_ID`.
2. Create an internal group named `Internal` (or set `PFB_TESTFLIGHT_GROUP`) and add the account holder's Apple ID.
3. Run `scripts/release_ios_pfb.sh`. It bumps the build in `project.yml`, archives, exports, and runs
   `asc publish testflight` into the internal group. It never submits for App Review.
   With Xcode signed out, prefix `ASC_SIGNING_KEY_ID=R79Z9DL337` and set `ASC_ISSUER_ID`.
4. Test on a real iPhone and iPad through a game window: live polling, drive tracker, win probability chart,
   widgets for a followed team, App Intents, offline launch, Dark appearance.
5. Before submission: privacy and support pages live, screenshots uploaded, age rating and privacy label entered,
   metadata applied with `asc metadata apply`. Submitting for review happens only when the account holder says so.
