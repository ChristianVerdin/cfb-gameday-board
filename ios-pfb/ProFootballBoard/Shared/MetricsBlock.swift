import SwiftUI

/// Season-to-date nflverse numbers for the two matchups: each offence against the other defence. Hidden when
/// either team has a small sample or the metrics belong to another season.
struct MetricsBlock: View {
    let game: BoardGame
    let metrics: Metrics?
    let seasonYear: Int?

    private struct Pair {
        var offense: Team
        var defense: Team
        var off: MetricSide
        var def: MetricSide
    }

    private var pairs: [Pair]? {
        guard let metrics, !game.placeholder, let away = game.away, let home = game.home else { return nil }
        if let y = seasonYear, let m = metrics.season, y != m { return nil }
        guard let a = usable(away, metrics), let h = usable(home, metrics),
              let aOff = a.offense, let aDef = a.defense, let hOff = h.offense, let hDef = h.defense else { return nil }
        return [Pair(offense: away, defense: home, off: aOff, def: hDef),
                Pair(offense: home, defense: away, off: hOff, def: aDef)]
    }

    private func usable(_ team: Team, _ metrics: Metrics) -> TeamMetrics? {
        guard let t = metrics.teams[team.metricsKey], !t.smallSample, t.offense != nil, t.defense != nil else { return nil }
        return t
    }

    var body: some View {
        if let pairs, let metrics {
            VStack(alignment: .leading, spacing: 10) {
                ForEach(pairs, id: \.offense.abbr) { block($0) }
                Text(footnote(metrics))
                    .font(.caption2).foregroundStyle(BoardTheme.muted)
            }
        }
    }

    private func block(_ p: Pair) -> some View {
        VStack(spacing: 4) {
            Text("\(p.offense.abbr) offense vs \(p.defense.abbr) defense")
                .font(.caption.weight(.semibold)).foregroundStyle(BoardTheme.gold)
                .frame(maxWidth: .infinity, alignment: .leading)
            row("EPA/play", signed(p.off.epa, 3) + rank(p.off.epaRank), signed(p.def.epa, 3) + rank(p.def.epaRank))
            row("Success rate", percent(p.off.successRate) + rank(p.off.successRank), percent(p.def.successRate) + rank(p.def.successRank))
            if let proe = p.off.proe { row("PROE", signed(proe, 1) + " pts" + rank(p.off.proeRank), nil) }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(spoken(p))
    }

    private func row(_ title: String, _ left: String, _ right: String?) -> some View {
        ViewThatFits(in: .horizontal) {
            HStack {
                Text(left).frame(maxWidth: .infinity, alignment: .leading)
                Text(title).foregroundStyle(BoardTheme.muted).font(.caption)
                Text(right ?? "").frame(maxWidth: .infinity, alignment: .trailing)
            }
            .lineLimit(1)
            VStack(alignment: .leading, spacing: 1) {
                Text(title).foregroundStyle(BoardTheme.muted).font(.caption)
                Text(left)
                if let right, !right.isEmpty { Text(right) }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .font(.footnote.monospacedDigit())
    }

    private func footnote(_ m: Metrics) -> String {
        "nflverse" + (m.throughWeek.map { ", through Week \($0)" } ?? "") + ", CC BY 4.0. " + (game.kind == .playoff ? "Regular season, per play." : "Season to date, per play.")
    }

    private func spoken(_ p: Pair) -> String {
        var s = "\(p.offense.abbr) offense versus \(p.defense.abbr) defense. EPA per play \(signed(p.off.epa, 3)) against \(signed(p.def.epa, 3))."
        s += " Success rate \(percent(p.off.successRate)) against \(percent(p.def.successRate))."
        if let proe = p.off.proe { s += " Pass rate over expected \(signed(proe, 1)) points." }
        return s
    }

    private func signed(_ v: Double?, _ digits: Int) -> String {
        guard let v else { return "" }
        return (v > 0 ? "+" : "") + v.formatted(.number.precision(.fractionLength(digits)))
    }

    private func percent(_ v: Double?) -> String {
        v.map { ($0 * 100).formatted(.number.precision(.fractionLength(1))) + "%" } ?? ""
    }

    private func rank(_ r: Int?) -> String { r.map { " #\($0)" } ?? "" }
}
