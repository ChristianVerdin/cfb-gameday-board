import SwiftUI
import WidgetKit

/// site.css tokens, so the widget reads as the board.
enum SlateStyle {
    static let bg = Color(hex: "0b1220")
    static let text = Color(hex: "f4f7fb")
    static let muted = Color(hex: "9aa8bf")
    static let dim = Color(hex: "6e7c94")
    static let gold = Color(hex: "e8c36a")
    static let red = Color(hex: "ff7a7a")
}

extension Color {
    init(hex: String) {
        let (r, g, b) = Color.rgb(hex) ?? (0.6, 0.66, 0.75)
        self.init(red: r, green: g, blue: b)
    }

    static func rgb(_ hex: String) -> (Double, Double, Double)? {
        let s = hex.trimmingCharacters(in: CharacterSet(charactersIn: "#"))
        guard s.count == 6, let v = UInt32(s, radix: 16) else { return nil }
        return (Double(v >> 16 & 0xff) / 255, Double(v >> 8 & 0xff) / 255, Double(v & 0xff) / 255)
    }
}

extension SlateTeam {
    /// The team's color, or its alternate when the main one would vanish on the dark background.
    var dot: Color {
        for hex in [color, alt].compactMap({ $0 }) {
            if let c = Color.rgb(hex), 0.2126 * c.0 + 0.7152 * c.1 + 0.0722 * c.2 > 0.18 { return Color(hex: hex) }
        }
        return SlateStyle.muted
    }
}

/// Everything one widget entry shows, decided up front so tests can render it without a timeline.
struct SlateContent: Sendable {
    var day: SlateDay?
    var filter: SlateFilter
    var updated: Date?
    var offline: Bool

    init(day: SlateDay?, filter: SlateFilter, updated: Date?, offline: Bool) {
        self.day = day; self.filter = filter; self.updated = updated; self.offline = offline
    }

    init(_ loaded: SlateStore.Loaded, filter: SlateFilter, now: Date) {
        self.init(day: Slate.day(loaded.games, live: loaded.live, filter: filter, now: now),
                  filter: filter, updated: loaded.updated, offline: loaded.offline)
    }

    /// Tapping outside a game row.
    var url: URL {
        if filter == .rivalry { return URL(string: "cfbgameday://rivalry")! }
        if (day?.liveCount ?? 0) > 0 { return URL(string: "cfbgameday://live")! }
        return URL(string: "cfbgameday://board")!
    }

    var when: String {
        guard let day else { return "CFB GameDay" }
        return day.isToday ? "Today" : Slate.format(day.date, "EEE M/d")
    }

    var count: String {
        let n = day?.rows.count ?? 0
        switch filter {
        case .all: return n == 1 ? "1 game" : "\(n) games"
        case .ranked: return n == 1 ? "1 Top 25 game" : "\(n) Top 25 games"
        case .rivalry: return n == 1 ? "1 trophy game" : "\(n) trophy games"
        }
    }

    var empty: String {
        switch filter {
        case .all: "No games on the board yet"
        case .ranked: "No Top 25 games on this week's board"
        case .rivalry: "No trophy games on this week's board"
        }
    }

    var stamp: String? {
        guard let updated else { return nil }
        let t = Slate.format(updated, "h:mm a")
        return offline ? "Offline · \(t) CT" : "Updated \(t) CT"
    }

    static let placeholder: SlateContent = {
        let team = SlateTeam(abbr: "TEAM", color: "9aa8bf")
        let rows = (0..<10).map { i in
            SlateRow(id: "\(i)", away: team, home: team, neutral: false, phase: .upcoming, showScore: false,
                     status: "2:30 PM", kickoff: nil, network: "TV", rivalry: false, weather: nil)
        }
        return SlateContent(day: SlateDay(date: .now, isToday: true, rows: rows, liveCount: 0),
                            filter: .all, updated: nil, offline: false)
    }()
}

struct SlateView: View {
    let content: SlateContent
    let family: WidgetFamily

    var body: some View {
        switch family {
        case .accessoryInline: SlateInline(content: content)
        case .accessoryRectangular: SlateRectangular(content: content)
        case .systemSmall: SlateSmall(content: content)
        case .systemLarge, .systemExtraLarge: SlateList(content: content, rows: 12)
        default: SlateList(content: content, rows: 4)
        }
    }
}

private struct LiveDot: View {
    var body: some View { Circle().fill(SlateStyle.red).frame(width: 6, height: 6) }
}

private struct LiveCount: View {
    let count: Int
    var body: some View {
        if count > 0 {
            HStack(spacing: 4) {
                LiveDot()
                Text("\(count) LIVE").font(.system(size: 11, weight: .bold)).foregroundStyle(SlateStyle.red)
            }
        }
    }
}

private struct Team: View {
    let team: SlateTeam
    var lost = false
    var size: CGFloat = 13

    var body: some View {
        HStack(spacing: 3) {
            Circle().fill(team.dot).frame(width: 6, height: 6)
            if team.ranked, let rank = team.rank {
                Text("\(rank)").font(.system(size: size - 3, weight: .medium)).foregroundStyle(SlateStyle.dim)
            }
            Text(team.abbr ?? "TBD").font(.system(size: size, weight: .semibold))
                .foregroundStyle(lost ? SlateStyle.muted : SlateStyle.text)
        }
    }
}

private struct Score: View {
    let team: SlateTeam
    let row: SlateRow
    var lost = false
    var size: CGFloat = 13

    var body: some View {
        if row.showScore {
            Text("\(team.score ?? 0)").font(.system(size: size, weight: .bold).monospacedDigit())
                .foregroundStyle(lost ? SlateStyle.muted : SlateStyle.text)
        }
    }
}

private struct Status: View {
    let row: SlateRow

    var body: some View {
        Group {
            switch row.phase {
            case .live:
                HStack(spacing: 4) {
                    LiveDot()
                    Text(row.status).foregroundStyle(SlateStyle.red)
                }
            case .upcoming:
                HStack(spacing: 5) {
                    if let weather = row.weather { Text(weather).foregroundStyle(SlateStyle.muted) }
                    Text([row.status, row.network].compactMap { $0 }.joined(separator: " · "))
                        .foregroundStyle(SlateStyle.text)
                }
            case .unknown:
                Text(row.status).foregroundStyle(SlateStyle.dim)
            case .final:
                Text(row.status).foregroundStyle(SlateStyle.muted)
            }
        }
        .font(.system(size: 11, weight: .medium).monospacedDigit())
        .lineLimit(1)
        .minimumScaleFactor(0.8)
    }
}

private struct Trophy: View {
    let row: SlateRow
    var body: some View {
        if row.rivalry {
            Image(systemName: "trophy.fill").font(.system(size: 9)).foregroundStyle(SlateStyle.gold)
        }
    }
}

private struct RowLine: View {
    let row: SlateRow

    var body: some View {
        HStack(spacing: 5) {
            Trophy(row: row)
            Team(team: row.away, lost: row.awayLost)
            Score(team: row.away, row: row, lost: row.awayLost)
            Text(row.neutral ? "vs" : "@").font(.system(size: 11)).foregroundStyle(SlateStyle.dim)
            Team(team: row.home, lost: row.homeLost)
            Score(team: row.home, row: row, lost: row.homeLost)
            Spacer(minLength: 4)
            Status(row: row)
        }
        .lineLimit(1)
    }
}

private struct Footer: View {
    let content: SlateContent
    let more: Int

    var body: some View {
        HStack {
            if more > 0 { Text("+\(more) more") }
            Spacer(minLength: 4)
            if let stamp = content.stamp { Text(stamp) }
        }
        .font(.system(size: 10))
        .foregroundStyle(SlateStyle.dim)
        .lineLimit(1)
    }
}

private struct Empty: View {
    let content: SlateContent
    var body: some View {
        Text(content.empty).font(.system(size: 13, weight: .medium)).foregroundStyle(SlateStyle.muted)
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
    }
}

/// Medium (4 games) and large (12): one line per game.
struct SlateList: View {
    let content: SlateContent
    let rows: Int

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 6) {
                Text((content.day == nil ? content.when : "\(content.when) · \(content.count)").uppercased())
                    .font(.system(size: 11, weight: .bold)).foregroundStyle(SlateStyle.gold).lineLimit(1)
                Spacer(minLength: 4)
                LiveCount(count: content.day?.liveCount ?? 0)
            }
            if let day = content.day {
                let shown = Array(day.rows.prefix(rows))
                VStack(alignment: .leading, spacing: rows > 4 ? 8 : 7) {
                    ForEach(shown) { row in
                        if let link = row.link {
                            Link(destination: link) { RowLine(row: row) }
                        } else {
                            RowLine(row: row)
                        }
                    }
                }
                .padding(.top, 9)
                Spacer(minLength: 4)
                Footer(content: content, more: day.rows.count - shown.count)
            } else {
                Empty(content: content)
                Footer(content: content, more: 0)
            }
        }
        .widgetURL(content.url)   // game rows carry their own Link
    }
}

/// Small: the first game in full, the rest as a count.
struct SlateSmall: View {
    let content: SlateContent

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            HStack(spacing: 4) {
                Text(content.when.uppercased()).font(.system(size: 11, weight: .bold)).foregroundStyle(SlateStyle.gold)
                Spacer(minLength: 2)
                LiveCount(count: content.day?.liveCount ?? 0)
            }
            if let row = content.day?.rows.first {
                Spacer(minLength: 0)
                ForEach(Array([(row.away, row.awayLost), (row.home, row.homeLost)].enumerated()), id: \.offset) { _, side in
                    HStack(spacing: 4) {
                        Team(team: side.0, lost: side.1, size: 16)
                        Spacer(minLength: 2)
                        Score(team: side.0, row: row, lost: side.1, size: 17)
                    }
                }
                HStack(spacing: 4) {
                    Trophy(row: row)
                    Status(row: row)
                }
                Spacer(minLength: 0)
                Text(content.count).font(.system(size: 10)).foregroundStyle(SlateStyle.dim)
            } else {
                Empty(content: content)
            }
        }
        .widgetURL(content.day?.rows.first?.link ?? content.url)
    }
}

/// Lock Screen: tinted by the system, so no colors of its own.
struct SlateRectangular: View {
    let content: SlateContent

    var body: some View {
        if let day = content.day, let row = day.rows.first {
            VStack(alignment: .leading, spacing: 1) {
                Text(status(row, day)).font(.system(size: 12, weight: .semibold)).widgetAccentable()
                Text(SlateRectangular.matchup(row)).font(.system(size: 15, weight: .bold))
                Text(day.liveCount > 0 ? "\(day.liveCount) live · \(content.count)" : content.count)
                    .font(.system(size: 11)).foregroundStyle(.secondary)
            }
            .lineLimit(1)
            .minimumScaleFactor(0.8)
            .frame(maxWidth: .infinity, alignment: .leading)
            .widgetURL(row.link ?? content.url)
        } else {
            Text(content.empty).font(.system(size: 12)).lineLimit(2).widgetURL(content.url)
        }
    }

    private func status(_ row: SlateRow, _ day: SlateDay) -> String {
        switch row.phase {
        case .live: return "LIVE · \(row.status)"
        case .upcoming:
            let when = day.isToday ? row.status : "\(Slate.format(day.date, "EEE")) \(row.status)"
            return [when, row.network].compactMap { $0 }.joined(separator: " · ")
        case .unknown, .final: return row.status
        }
    }

    static func matchup(_ row: SlateRow) -> String {
        let away = row.away.abbr ?? "TBD", home = row.home.abbr ?? "TBD"
        guard row.showScore else { return "\(away) \(row.neutral ? "vs" : "@") \(home)" }
        return "\(away) \(row.away.score ?? 0)  \(home) \(row.home.score ?? 0)"
    }
}

/// The one line above the Lock Screen clock.
struct SlateInline: View {
    let content: SlateContent

    var body: some View {
        let row = content.day?.rows.first
        Text(row.map { "\(SlateRectangular.matchup($0))\($0.phase == .live ? " ·" : "") \($0.status)" } ?? "CFB GameDay")
            .widgetURL(row?.link ?? content.url)
    }
}
