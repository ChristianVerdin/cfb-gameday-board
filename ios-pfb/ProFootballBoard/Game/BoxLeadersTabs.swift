import SwiftUI

struct BoxTab: View {
    let sheet: GameSheet

    var body: some View {
        if sheet.box.isEmpty {
            SheetEmpty(text: "Box score not available yet.", systemImage: "tablecells")
        } else {
            SheetCard {
                Grid(horizontalSpacing: 12, verticalSpacing: 0) {
                    GridRow {
                        Text(sheet.awayAbbr).gridColumnAlignment(.trailing)
                        Text("")
                        Text(sheet.homeAbbr).gridColumnAlignment(.leading)
                    }
                    .font(.caption.weight(.heavy)).foregroundStyle(.secondary)
                    ForEach(sheet.box) { r in
                        Divider().gridCellUnsizedAxes(.horizontal)
                        GridRow {
                            Text(r.away).fontWeight(.semibold)
                            Text(r.label).font(.footnote).foregroundStyle(.secondary).frame(maxWidth: .infinity)
                            Text(r.home).fontWeight(.semibold)
                        }
                        .font(.subheadline.monospacedDigit())
                        .padding(.vertical, 7)
                        .accessibilityElement(children: .ignore)
                        .accessibilityLabel("\(r.label): \(sheet.awayAbbr) \(r.away), \(sheet.homeAbbr) \(r.home)")
                    }
                }
            }
        }
    }
}

struct LeadersTab: View {
    let sheet: GameSheet

    var body: some View {
        VStack(spacing: 10) {
            column(sheet.awayAbbr, sheet.leaders.away)
            column(sheet.homeAbbr, sheet.leaders.home)
        }
    }

    private func column(_ abbr: String, _ list: [Leader]) -> some View {
        SheetCard {
            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 8) {
                    SheetChip(abbr: abbr, colors: sheet.chipColors(for: abbr))
                    Text(sheet.team(abbr)?.name ?? abbr).font(.headline)
                }
                if list.isEmpty {
                    Text("None yet.").font(.footnote).foregroundStyle(.secondary)
                }
                ForEach(list) { l in
                    VStack(alignment: .leading, spacing: 1) {
                        Text(l.label).font(.caption).foregroundStyle(.secondary)
                        Text([l.name, l.position].compactMap { $0 }.joined(separator: " · ")).font(.subheadline.weight(.semibold))
                        if let line = l.line { Text(line).font(.footnote).foregroundStyle(.secondary) }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .accessibilityElement(children: .combine)
                }
            }
        }
    }
}
