import SwiftUI
import WidgetKit

struct SlateEntry: TimelineEntry {
    let date: Date
    let scope: WidgetScope
    let slate: WidgetSlate?
    /// True when the slate is cached because the board could not be reached.
    let offline: Bool

    var games: [WidgetGame] { slate?.games(for: scope) ?? [] }
}

struct SlateProvider: AppIntentTimelineProvider {
    var loader = SlateLoader()

    func placeholder(in context: Context) -> SlateEntry {
        SlateEntry(date: Date(), scope: .all, slate: .sample, offline: false)
    }

    func snapshot(for configuration: ShowGamesIntent, in context: Context) async -> SlateEntry {
        if context.isPreview { return SlateEntry(date: Date(), scope: configuration.scope, slate: .sample, offline: false) }
        return await entry(for: configuration, now: Date())
    }

    func timeline(for configuration: ShowGamesIntent, in context: Context) async -> Timeline<SlateEntry> {
        let now = Date()
        let entry = await entry(for: configuration, now: now)
        let next = entry.slate?.nextRefresh(for: entry.scope, now: now) ?? now + WidgetSlate.fastRefresh * 3
        return Timeline(entries: [entry], policy: .after(next))
    }

    private func entry(for configuration: ShowGamesIntent, now: Date) async -> SlateEntry {
        let result = await loader.load(now: now)
        return SlateEntry(date: now, scope: configuration.scope, slate: result.slate, offline: result.offline)
    }
}

extension WidgetSlate {
    /// Placeholder content for the widget gallery.
    static let sample: WidgetSlate = {
        func team(_ abbr: String, _ name: String, _ score: Int?, _ color: String, _ alt: String) -> WidgetTeam {
            WidgetTeam(abbr: abbr, name: name, score: score, record: nil, color: color, alt: alt)
        }
        func game(_ id: String, _ state: String, _ away: WidgetTeam, _ home: WidgetTeam, _ status: String, _ tv: String) -> WidgetGame {
            var g = WidgetGame(away: away, home: home, id: id, state: state, status: status, tv: tv)
            g.situation = state == "in" ? "2nd & 6 at KC 31" : nil
            return g
        }
        let games = [
            game("1", "in", team("BUF", "Bills", 21, "00338d", "d50a0a"), team("KC", "Chiefs", 17, "e31837", "ffb81c"), "Q3 6:42", "CBS"),
            game("2", "pre", team("GB", "Packers", nil, "203731", "ffb612"), team("DET", "Lions", nil, "0076b6", "b0b7bc"), "Sun 7:20 PM CT", "NBC"),
            game("3", "post", team("SEA", "Seahawks", 24, "002244", "69be28"), team("SF", "49ers", 20, "aa0000", "b3995d"), "Final", "Fox"),
        ]
        return WidgetSlate(fetchedAt: Date(), weekLabel: "Week 10", games: games)
    }()
}

private extension WidgetGame {
    init(away: WidgetTeam, home: WidgetTeam, id: String, state: String, status: String, tv: String) {
        self.id = id; self.state = state; self.away = away; self.home = home; self.status = status; self.tv = tv
        situation = nil; possession = nil; redZone = false; date = nil; timeTBD = false; held = nil
    }
}
