import SwiftUI
import WidgetKit

enum SlateStyle {
    static let background = RGB(hex: "0b1220")!.color
    static let muted = Color(red: 0.62, green: 0.69, blue: 0.80)
    static let live = Color(red: 0.96, green: 0.36, blue: 0.36)
    static let boardURL = URL(string: "pfb://board")!

    static func gameURL(_ id: String) -> URL { URL(string: "pfb://game/\(id)") ?? boardURL }
}

struct SlateEntryView: View {
    let entry: SlateEntry
    @Environment(\.widgetFamily) private var family

    var body: some View {
        SlateContent(entry: entry, family: family)
            .containerBackground(for: .widget) { SlateStyle.background }
    }
}

struct SlateContent: View {
    let entry: SlateEntry
    let family: WidgetFamily

    private var limit: Int {
        switch family {
        case .systemMedium: 3
        case .systemLarge: 7
        case .accessoryRectangular: 2
        default: 1
        }
    }

    var body: some View {
        let games = Array(entry.games.prefix(limit))
        switch family {
        case .accessoryInline: InlineView(games: games, entry: entry)
        case .accessoryRectangular: RectangularView(games: games, entry: entry)
        case .systemSmall: SmallView(games: games, entry: entry)
        default: ListView(games: games, entry: entry)
        }
    }
}

// MARK: - Pieces

struct TeamChip: View {
    let team: WidgetTeam
    var width: CGFloat = 42

    var body: some View {
        let chip = team.chip
        Text(team.abbr)
            .font(.system(size: 13, weight: .heavy, design: .rounded))
            .lineLimit(1)
            .minimumScaleFactor(0.7)
            .foregroundStyle(chip.foreground.color)
            .frame(width: width, height: 22)
            .background(chip.background.color, in: RoundedRectangle(cornerRadius: 6))
    }
}

private struct Header: View {
    let entry: SlateEntry

    private var title: String {
        let week = entry.slate?.weekLabel ?? "Pro Football"
        switch entry.scope {
        case .all: return week
        case .live: return "Live now"
        case .team(let abbr): return "\(abbr) · \(week)"
        }
    }

    var body: some View {
        HStack(spacing: 4) {
            Text(title.uppercased()).lineLimit(1)
            Spacer(minLength: 2)
            if entry.offline, let fetched = entry.slate?.fetchedAt {
                Text("Cached \(Chicago.time(fetched))").lineLimit(1).minimumScaleFactor(0.7)
            } else if let live = entry.slate?.liveCount, live > 0 {
                HStack(spacing: 3) {
                    Circle().frame(width: 5, height: 5)
                    Text("\(live) live")
                }
                .foregroundStyle(SlateStyle.live)
            }
        }
        .font(.system(size: 10, weight: .bold))
        .foregroundStyle(SlateStyle.muted)
    }
}

private struct EmptyState: View {
    let entry: SlateEntry

    private var message: String {
        guard entry.slate != nil else { return "Can't reach the board" }
        switch entry.scope {
        case .all: return "No games this week"
        case .live: return "No live games"
        case .team(let abbr): return "\(abbr) has no game this week"
        }
    }

    private var detail: String? {
        guard let slate = entry.slate else { return "Will retry shortly" }
        if case .team = entry.scope { return slate.weekLabel.map { "\($0) · bye or not scheduled" } }
        guard let next = slate.nextUp(after: entry.date) else { return nil }
        return "Next: \(next.matchup), \(next.status)"
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Spacer(minLength: 0)
            Text(message).font(.system(size: 15, weight: .semibold)).foregroundStyle(.white)
            if let detail { Text(detail).font(.system(size: 11)).foregroundStyle(SlateStyle.muted) }
            Spacer(minLength: 0)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

private func scoreText(_ team: WidgetTeam, game: WidgetGame) -> String {
    game.started ? (team.score.map(String.init) ?? "–") : ""
}

private func sub(_ game: WidgetGame) -> String? {
    if game.isLive, let s = game.situation { return s }
    return game.tv.isEmpty ? nil : game.tv
}

private func dimmed(_ team: WidgetTeam, in game: WidgetGame) -> Bool {
    guard game.isFinal, let a = game.away.score, let h = game.home.score, a != h else { return false }
    return team.abbr == (a > h ? game.home.abbr : game.away.abbr)
}

// MARK: - Small

private struct SmallView: View {
    let games: [WidgetGame]
    let entry: SlateEntry

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Header(entry: entry)
            if let game = games.first {
                VStack(spacing: 5) {
                    line(game.away, game, side: "away")
                    line(game.home, game, side: "home")
                }
                Spacer(minLength: 0)
                VStack(alignment: .leading, spacing: 1) {
                    Text(game.status)
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundStyle(game.isLive ? SlateStyle.live : .white)
                    if let s = sub(game) {
                        Text(s).font(.system(size: 10)).foregroundStyle(SlateStyle.muted)
                    }
                }
                .lineLimit(1)
                .minimumScaleFactor(0.8)
            } else {
                EmptyState(entry: entry)
            }
        }
        .widgetURL(games.first.map { SlateStyle.gameURL($0.id) } ?? SlateStyle.boardURL)
    }

    private func line(_ team: WidgetTeam, _ game: WidgetGame, side: String) -> some View {
        HStack(spacing: 6) {
            TeamChip(team: team)
            if game.possession == side {
                Circle().fill(SlateStyle.live).frame(width: 5, height: 5)
            }
            Spacer(minLength: 2)
            if game.started {
                Text(scoreText(team, game: game))
                    .font(.system(size: 24, weight: .bold, design: .rounded).monospacedDigit())
                    .foregroundStyle(dimmed(team, in: game) ? SlateStyle.muted : .white)
            } else if let record = team.record {
                Text(record).font(.system(size: 11)).foregroundStyle(SlateStyle.muted)
            }
        }
    }
}

// MARK: - Medium and large

private struct ListView: View {
    let games: [WidgetGame]
    let entry: SlateEntry

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Header(entry: entry).padding(.bottom, 6)
            if games.isEmpty {
                EmptyState(entry: entry)
            } else {
                ForEach(Array(games.enumerated()), id: \.element.id) { index, game in
                    if index > 0 { Divider().overlay(Color.white.opacity(0.08)) }
                    Link(destination: SlateStyle.gameURL(game.id)) { Row(game: game) }
                        .frame(maxHeight: .infinity)
                }
            }
        }
        .widgetURL(SlateStyle.boardURL)
    }
}

private struct Row: View {
    let game: WidgetGame

    var body: some View {
        HStack(spacing: 6) {
            TeamChip(team: game.away)
            Text(scoreText(game.away, game: game))
                .frame(width: 28, alignment: .trailing)
                .foregroundStyle(dimmed(game.away, in: game) ? SlateStyle.muted : .white)
            Text(game.started ? "–" : "@").foregroundStyle(SlateStyle.muted).frame(width: 12)
            Text(scoreText(game.home, game: game))
                .frame(width: 28, alignment: .leading)
                .foregroundStyle(dimmed(game.home, in: game) ? SlateStyle.muted : .white)
            TeamChip(team: game.home)
            Spacer(minLength: 4)
            VStack(alignment: .trailing, spacing: 1) {
                Text(game.status)
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(game.isLive ? SlateStyle.live : .white)
                if let s = sub(game) {
                    Text(s).font(.system(size: 10)).foregroundStyle(SlateStyle.muted)
                }
            }
            .lineLimit(1)
            .minimumScaleFactor(0.75)
        }
        .font(.system(size: 17, weight: .bold, design: .rounded).monospacedDigit())
        .frame(maxHeight: .infinity)
        .contentShape(Rectangle())
    }
}

// MARK: - Lock Screen

private struct RectangularView: View {
    let games: [WidgetGame]
    let entry: SlateEntry

    var body: some View {
        VStack(alignment: .leading, spacing: 1) {
            if games.isEmpty {
                Text(entry.slate == nil ? "Board unavailable" : entry.scope == .live ? "No live games" : "No games").font(.headline)
            } else {
                ForEach(games) { game in
                    Text(headline(game)).font(.system(size: 14, weight: .bold).monospacedDigit()).widgetAccentable()
                    Text([game.status, game.tv].filter { !$0.isEmpty }.joined(separator: " · ")).font(.system(size: 11))
                }
            }
        }
        .lineLimit(1)
        .minimumScaleFactor(0.8)
        .frame(maxWidth: .infinity, alignment: .leading)
        .widgetURL(games.first.map { SlateStyle.gameURL($0.id) } ?? SlateStyle.boardURL)
    }

    private func headline(_ g: WidgetGame) -> String {
        g.started ? "\(g.away.abbr) \(g.away.score ?? 0) – \(g.home.score ?? 0) \(g.home.abbr)" : g.matchup
    }
}

private struct InlineView: View {
    let games: [WidgetGame]
    let entry: SlateEntry

    var body: some View {
        Group {
            if let g = games.first {
                Text(g.started
                     ? "\(g.away.abbr) \(g.away.score ?? 0)-\(g.home.score ?? 0) \(g.home.abbr) · \(g.status)"
                     : "\(g.matchup) · \(g.status)")
            } else {
                Text(entry.slate == nil ? "Board unavailable" : "No games")
            }
        }
        .widgetURL(games.first.map { SlateStyle.gameURL($0.id) } ?? SlateStyle.boardURL)
    }
}
