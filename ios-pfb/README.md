# Pro Football Board (iOS)

A native SwiftUI companion to the web board at https://cfbgameday.app/nfl: the week's NFL slate with live scores,
field position, win probability, drive and play detail, kickoff weather and season advanced metrics. Stats only.
No accounts, push, analytics or ads. Times are shown in America/Chicago.

Independent and unofficial. Not affiliated with, endorsed or sponsored by the National Football League or any team.
Scores and play data via ESPN. Season metrics from nflverse (CC BY 4.0). Weather by Open-Meteo.com (CC BY 4.0).

## Layout

| Path | What |
| --- | --- |
| `project.yml` | XcodeGen spec; the `.xcodeproj` is generated and gitignored |
| `ProFootballBoard/Model/` | Tolerant Codable models, game merge, window classifier, field geometry, desk ranking |
| `ProFootballBoard/Data/` | `APIClient`, `BoardStore`, `GameStore`, `FollowStore`, `Router` |
| `ProFootballBoard/App/` | App entry point and the tab shell |
| `ProFootballBoard/Board`, `Game`, `Shared`, `Intents` | Feature views |
| `ProFootballBoardWidget/` | WidgetKit extension; compiles `Model/` and `Data/` too |
| `ProFootballBoardTests/` | Unit tests and captured fixtures |

Deep links: `pfb://board`, `pfb://live`, `pfb://following`, `pfb://about`, `pfb://game/<espn id>`.

## Build and test

Requires Xcode 26 and [XcodeGen](https://github.com/yonaskolb/XcodeGen).

```
cd ios-pfb
xcodegen generate
xcodebuild -project ProFootballBoard.xcodeproj -scheme ProFootballBoard \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro,OS=26.5' \
  -derivedDataPath build/DD CODE_SIGNING_ALLOWED=NO test
```

Pick any installed simulator runtime for `OS=`. Use a separate `-derivedDataPath` per concurrent build.

## Data

All reads are plain GETs of the board's public endpoints (no key, no cache-busting query):

| Endpoint | Content |
| --- | --- |
| `/api/nfl/live` (`?st=<season type>&week=<n>`) | Scoreboard: scores, status, situation, win probability, watch score |
| `/api/nfl/game?id=<espn id>` | One game: drives, plays, scoring, win probability series, team stats, leaders |
| `/nfl/games.json` | Weekly snapshot: venue, roof, kickoff weather, round |
| `/nfl/metrics.json` | nflverse EPA, success rate and pass rate over expected, per team |

Decoding ignores unknown keys, accepts numbers sent as strings and nulls, and drops a malformed list item
without failing the payload. Polling: 20 s while any game is live, 60 s within an hour of a kickoff, 120 s
otherwise, and paused while the app is not active. An open game sheet polls every 20 s while the game is live.

`ProFootballBoardTests/Fixtures/` holds real payloads captured from those endpoints plus overtime, tie,
flex and placeholder cases built with the board's own normalizer from committed ESPN fixtures.
