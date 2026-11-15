import SwiftUI

/// The whip-around: the three live games most worth a look, then games kicking off within 30 minutes.
struct DeskSection: View {
    let desk: [BoardGame]
    let upcoming: [BoardGame]
    @Environment(BoardStore.self) private var board
    @Environment(Router.self) private var router

    var body: some View {
        TimelineView(.periodic(from: .now, by: 30)) { context in
            let soon = upcoming.filter { g in
                let t = g.kickoffSortKey - context.date.timeIntervalSince1970
                return g.state == .pre && !g.placeholder && t <= 1800 && t >= -60
            }.prefix(4)
            if !desk.isEmpty || !soon.isEmpty {
                VStack(alignment: .leading, spacing: 10) {
                    if !desk.isEmpty {
                        header("Whip-around \u{00B7} all live games")
                        ForEach(Array(desk.enumerated()), id: \.element.id) { i, g in deskCard(g, rank: i + 1) }
                    }
                    if !soon.isEmpty {
                        header("Next up")
                        ForEach(Array(soon)) { g in nextRow(g, now: context.date) }
                    }
                }
            }
        }
    }

    private func header(_ title: String) -> some View {
        Text(title).font(.headline).foregroundStyle(BoardTheme.gold).accessibilityAddTraits(.isHeader)
    }

    private func deskCard(_ g: BoardGame, rank: Int) -> some View {
        let swing = board.deskSwing(for: g.id)
        let info = StateInfo(g)
        return Button { router.open(.game(g.id)) } label: {
            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Text("#\(rank)").font(.subheadline.weight(.heavy)).foregroundStyle(BoardTheme.gold)
                    Text("\(g.away?.abbr ?? "") \(g.away?.score ?? 0) - \(g.home?.score ?? 0) \(g.home?.abbr ?? "")")
                        .font(.headline.monospacedDigit())
                    Spacer()
                }
                let line = [info?.text, g.situation?.text].compactMap { $0 }.filter { !$0.isEmpty }.joined(separator: " \u{00B7} ")
                if !line.isEmpty { Text(line).font(.subheadline).foregroundStyle(BoardTheme.muted) }
                let why = g.desk?.why ?? []
                let moved = swing.points >= 4 ? swing.toward : nil
                if !why.isEmpty || moved != nil {
                    HStack(spacing: 6) {
                        ForEach(why, id: \.self) { BoardTag(text: $0, tint: BoardTheme.gold) }
                        if let side = moved, let team = side == .home ? g.home : g.away {
                            BoardTag(text: "WP swing \(team.abbr) +\(Int(swing.points.rounded()))", tint: BoardTheme.blue)
                        }
                    }
                }
                if rank == 1, let play = g.situation?.lastPlay?.text, !play.isEmpty {
                    Text(play).font(.footnote).foregroundStyle(BoardTheme.muted).lineLimit(4)
                }
            }
            .padding(12)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(rank == 1 ? BoardTheme.card2 : BoardTheme.card, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous)
                .stroke(rank == 1 ? BoardTheme.gold.opacity(0.6) : BoardTheme.line.opacity(0.7), lineWidth: 1))
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .combine)
        .accessibilityHint("Opens the game sheet")
    }

    private func nextRow(_ g: BoardGame, now: Date) -> some View {
        let mins = max(0, Int(((g.kickoffSortKey - now.timeIntervalSince1970) / 60).rounded()))
        return Button { router.open(.game(g.id)) } label: {
            HStack {
                Text(g.matchup).font(.subheadline.weight(.semibold))
                Spacer()
                Text(mins == 0 ? "now" : "in \(mins) min").font(.subheadline).foregroundStyle(BoardTheme.muted)
            }
            .padding(12)
            .background(BoardTheme.card, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
        }
        .buttonStyle(.plain)
    }
}
