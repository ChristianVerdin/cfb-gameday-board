import SwiftUI

struct ScoringTab: View {
    let sheet: GameSheet

    var body: some View {
        let list = sheet.phase == .live ? Array(sheet.scoring.reversed()) : sheet.scoring
        if list.isEmpty {
            SheetEmpty(text: "No scoring yet.")
        } else {
            SheetCard {
                LazyVStack(spacing: 0) {
                    ForEach(list) { s in
                        row(s)
                        if s.id != list.last?.id { Divider() }
                    }
                }
            }
        }
    }

    private func row(_ s: ScoringPlay) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 6) {
                Text([s.periodLabel, s.clock ?? ""].filter { !$0.isEmpty }.joined(separator: " "))
                    .font(.caption.weight(.semibold)).foregroundStyle(.secondary).monospacedDigit()
                SheetChip(abbr: s.team, colors: sheet.chipColors(for: s.team))
                if !s.kind.isEmpty { Tag(text: s.kind, color: .green) }
            }
            Text(s.text).font(.subheadline)
            if let a = s.away, let h = s.home {
                Text("\(sheet.awayAbbr) \(a) – \(sheet.homeAbbr) \(h)").font(.caption.weight(.semibold)).monospacedDigit()
            }
        }
        .padding(.vertical, 6)
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityElement(children: .combine)
    }
}
