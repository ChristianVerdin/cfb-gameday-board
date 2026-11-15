import SwiftUI

struct DrivesTab: View {
    let sheet: GameSheet
    @Binding var expanded: [String: Bool]

    private var live: Bool { sheet.phase == .live }

    var body: some View {
        VStack(spacing: 10) {
            if let g = sheet.trackerGeometry { FieldTracker(sheet: sheet, geometry: g) }
            if sheet.drives.isEmpty {
                SheetEmpty(text: "No drives yet.")
            } else {
                ForEach(live ? Array(sheet.drives.reversed()) : sheet.drives) { drive in
                    DriveCard(sheet: sheet, drive: drive, live: live && drive.live, isOpen: isOpen(drive)) {
                        expanded[drive.id] = !isOpen(drive)
                    }
                }
            }
        }
    }

    private func isOpen(_ d: Drive) -> Bool { expanded[d.id] ?? (live && d.live) }
}

private struct DriveCard: View {
    let sheet: GameSheet
    let drive: Drive
    let live: Bool
    let isOpen: Bool
    let toggle: () -> Void

    @State private var adminOpen = false

    private var tone: DriveTone { GameLogic.tone(of: drive) }

    private var meta: String {
        let start = drive.start.map { s in [PeriodLabel.of(s.period), s.yardText.map { "from \($0)" } ?? ""].filter { !$0.isEmpty }.joined(separator: " ") }
        return [start, Plural.count(drive.plays, "play"), "\(drive.yards) yds", drive.time].compactMap { $0 }.filter { !$0.isEmpty }.joined(separator: " · ")
    }

    private var resultText: String { live ? "On the field" : drive.resultText ?? drive.result ?? "Drive" }

    var body: some View {
        let list = live ? Array(drive.playList.reversed()) : drive.playList
        let main = list.filter { !$0.isAdmin }, admin = list.filter(\.isAdmin)
        SheetCard {
            VStack(alignment: .leading, spacing: 6) {
                Button(action: toggle) {
                    VStack(alignment: .leading, spacing: 4) {
                    HStack(spacing: 8) {
                        SheetChip(abbr: drive.team, colors: sheet.chipColors(for: drive.team))
                        Text(resultText).font(.subheadline.weight(.bold)).foregroundStyle(toneColor)
                        Spacer(minLength: 4)
                        Image(systemName: "chevron.down").font(.footnote.weight(.semibold)).foregroundStyle(.secondary)
                            .rotationEffect(.degrees(isOpen ? 180 : 0))
                    }
                    Text(meta).font(.caption).foregroundStyle(.secondary).frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
                .buttonStyle(.plain)
                .accessibilityElement(children: .combine)
                .accessibilityHint(isOpen ? "Collapses the plays" : "Expands the plays")
                .accessibilityAddTraits(.isButton)
                if isOpen {
                    if main.isEmpty {
                        Text("No plays yet.").font(.footnote).foregroundStyle(.secondary)
                    } else {
                        ForEach(main) { PlayRow(play: $0, sheet: sheet) }
                    }
                    if !admin.isEmpty {
                        DisclosureGroup(isExpanded: $adminOpen) {
                            ForEach(admin) { PlayRow(play: $0, sheet: sheet) }
                        } label: {
                            Text("\(admin.count) admin \(admin.count == 1 ? "play" : "plays")").font(.footnote).foregroundStyle(.secondary)
                        }
                    }
                }
            }
        }
        .overlay(alignment: .leading) {
            if live { RoundedRectangle(cornerRadius: 2).fill(Color.green).frame(width: 3).padding(.vertical, 8) }
        }
    }

    private var toneColor: Color {
        switch tone {
        case .score: .green
        case .turnover: .red
        case .plain: .primary
        }
    }
}
