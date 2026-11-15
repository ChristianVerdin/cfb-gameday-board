import SwiftUI

struct GameHeader: View {
    let sheet: GameSheet

    private var possession: Possession? { sheet.phase == .live ? sheet.trackerGeometry?.side : nil }

    var body: some View {
        SheetCard {
            VStack(alignment: .leading, spacing: 12) {
                teamRow(sheet.teams.away, score: sheet.totals.away, side: .away)
                teamRow(sheet.teams.home, score: sheet.totals.home, side: .home)
                HStack(spacing: 8) {
                    StatusPill(phase: sheet.phase)
                    Text(sheet.statusText).font(.subheadline.weight(.semibold)).monospacedDigit()
                }
                .accessibilityElement(children: .combine)
                if sheet.phase != .pre { Linescore(sheet: sheet) }
            }
        }
    }

    private func teamRow(_ team: Team?, score: Int, side: Possession) -> some View {
        let abbr = team?.abbr ?? (side == .away ? "Away" : "Home")
        return HStack(spacing: 10) {
            SheetChip(abbr: abbr, colors: team?.chip ?? ChipColors(background: .neutralBG, foreground: .neutralFG))
            Text(team?.name.isEmpty == false ? team!.name : abbr).font(.headline)
            if possession == side {
                Image(systemName: "circle.fill").font(.system(size: 8)).foregroundStyle(.orange)
                    .accessibilityLabel("Has the ball")
            }
            Spacer()
            Text(sheet.phase == .pre ? "" : "\(score)").font(.title.weight(.bold)).monospacedDigit()
        }
        .accessibilityElement(children: .combine)
    }
}

private struct StatusPill: View {
    let phase: SheetPhase

    private var text: String {
        switch phase {
        case .final: "FINAL"
        case .live: "LIVE"
        case .hold: "PAUSED"
        case .pre: "PRE"
        }
    }

    var body: some View {
        Text(text)
            .font(.caption2.weight(.heavy))
            .padding(.horizontal, 7).padding(.vertical, 3)
            .foregroundStyle(phase == .live ? Color.black : Color.primary)
            .background(phase == .live ? Color.green : Color.white.opacity(0.14), in: Capsule())
            .accessibilityHidden(true)
    }
}

struct Linescore: View {
    let sheet: GameSheet

    var body: some View {
        let ls = sheet.linescores
        let n = max(ls.away.count, ls.home.count, 4)
        let labels = GameLogic.lineLabels(n)
        let totals = sheet.totals
        ScrollView(.horizontal, showsIndicators: false) {
            Grid(alignment: .trailing, horizontalSpacing: 14, verticalSpacing: 4) {
                GridRow {
                    Text("")
                    ForEach(labels, id: \.self) { Text($0).foregroundStyle(.secondary) }
                    Text("T").foregroundStyle(.secondary)
                }
                row(sheet.awayAbbr, ls.away, n: n, total: totals.away)
                row(sheet.homeAbbr, ls.home, n: n, total: totals.home)
            }
            .font(.footnote.monospacedDigit())
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(accessibilityText(labels: labels, totals: totals))
    }

    private func row(_ abbr: String, _ values: [Int?], n: Int, total: Int) -> some View {
        GridRow {
            Text(abbr).fontWeight(.semibold).gridColumnAlignment(.leading)
            ForEach(0..<n, id: \.self) { i in
                Text(i < values.count ? values[i].map(String.init) ?? "" : "")
            }
            Text("\(total)").fontWeight(.bold)
        }
    }

    private func accessibilityText(labels: [String], totals: (away: Int, home: Int)) -> String {
        func part(_ abbr: String, _ v: [Int?]) -> String {
            let periods = labels.enumerated().compactMap { i, l in i < v.count ? v[i].map { "\(l) \($0)" } : nil }
            return "\(abbr): " + periods.joined(separator: ", ")
        }
        return "Line score. " + part(sheet.awayAbbr, sheet.linescores.away) + ". " + part(sheet.homeAbbr, sheet.linescores.home) + "."
    }
}
