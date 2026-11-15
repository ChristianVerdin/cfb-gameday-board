import Charts
import SwiftUI

struct WinProbTab: View {
    let sheet: GameSheet

    private struct Marker: Identifiable {
        let id: Int
        let label: String
    }

    private var points: [WinProbPoint] { sheet.winProb.points }

    private var markers: [Marker] {
        let n = points.count
        var out = sheet.winProb.quarters.filter { $0.index >= 0 && $0.index < n && !$0.label.isEmpty }
            .map { Marker(id: $0.index, label: String($0.label.prefix(4))) }
        if let ot = sheet.winProb.overtimeStart, ot >= 0, ot < n, !out.contains(where: { $0.label.contains("OT") }) {
            out.append(Marker(id: ot, label: "OT"))
        }
        return out
    }

    private var latest: String? {
        guard sheet.phase == .live, let last = points.last else { return nil }
        return GameLogic.winProbLabel(last.home, away: sheet.awayAbbr, homeAbbr: sheet.homeAbbr)
    }

    var body: some View {
        if points.count < 2 {
            SheetEmpty(text: "No win probability for this game yet.", systemImage: "chart.xyaxis.line")
        } else {
            SheetCard {
                VStack(alignment: .leading, spacing: 10) {
                    HStack {
                        Text("ESPN win probability").font(.subheadline.weight(.bold))
                        Spacer()
                        if let latest { Text("Latest: \(latest)").font(.caption).foregroundStyle(.secondary) }
                    }
                    chart
                    HStack {
                        Text("\(sheet.homeAbbr) ↑")
                        Spacer()
                        Text("\(sheet.awayAbbr) ↓")
                    }
                    .font(.caption.weight(.semibold)).foregroundStyle(.secondary)
                    Text("ESPN's model estimate of the home team's chance at each play. It is not a result.")
                        .font(.caption).foregroundStyle(.secondary)
                }
            }
        }
    }

    private var chart: some View {
        Chart {
            RuleMark(y: .value("Even", 50))
                .foregroundStyle(.secondary.opacity(0.6))
                .lineStyle(StrokeStyle(lineWidth: 1, dash: [4, 3]))
            ForEach(markers) { m in
                RuleMark(x: .value("Play", m.id))
                    .foregroundStyle(.secondary.opacity(0.35))
                    .annotation(position: .top, alignment: .leading, spacing: 2, overflowResolution: .init(x: .fit(to: .chart), y: .disabled)) {
                        Text(m.label).font(.caption2.weight(.semibold)).foregroundStyle(.secondary).padding(.leading, 3)
                    }
            }
            ForEach(Array(points.enumerated()), id: \.offset) { i, p in
                LineMark(x: .value("Play", i), y: .value("Home win probability", p.home * 100))
                    .interpolationMethod(.monotone)
                    .foregroundStyle(Color.accentColor)
                    .lineStyle(StrokeStyle(lineWidth: 2.5, lineJoin: .round))
            }
        }
        .chartXScale(domain: 0...(points.count - 1))
        .chartYScale(domain: 0...100)
        .chartXAxis(.hidden)
        .chartYAxis {
            AxisMarks(values: [0, 50, 100]) { v in
                AxisGridLine().foregroundStyle(.secondary.opacity(0.2))
                AxisValueLabel { Text("\(v.as(Int.self) ?? 0)%").font(.caption2) }
            }
        }
        .frame(height: 220)
        .padding(.top, 14)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(summary)
    }

    private var summary: String {
        let first = Int(((points.first?.home ?? 0.5) * 100).rounded()), last = Int(((points.last?.home ?? 0.5) * 100).rounded())
        return "ESPN win probability chart for \(sheet.homeAbbr). Starts at \(first) percent, latest \(last) percent. An estimate, not a result."
    }
}
