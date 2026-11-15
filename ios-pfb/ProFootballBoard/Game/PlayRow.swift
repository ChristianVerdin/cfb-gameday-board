import SwiftUI

struct PlayRow: View {
    let play: Play
    let sheet: GameSheet
    var team: String?

    private var when: String { [play.periodLabel, play.clock ?? ""].filter { !$0.isEmpty }.joined(separator: " ") }

    private var situation: String {
        let dn = GameLogic.downText(play)
        guard let yard = play.yardText else { return dn }
        return dn.isEmpty ? yard : "\(dn) at \(yard)"
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 6) {
                Text(when).font(.caption.weight(.semibold)).foregroundStyle(.secondary).monospacedDigit()
                if let team, !team.isEmpty { SheetChip(abbr: team, colors: sheet.chipColors(for: team)) }
                Spacer(minLength: 0)
                tags
            }
            if !situation.isEmpty { Text(situation).font(.caption).foregroundStyle(.secondary) }
            Text(play.text).font(.subheadline).foregroundStyle(play.isAdmin ? .secondary : .primary)
            if play.scoring, let a = play.away, let h = play.home {
                Text("\(sheet.awayAbbr) \(a) – \(sheet.homeAbbr) \(h)").font(.caption.weight(.semibold)).monospacedDigit()
            }
        }
        .padding(.vertical, 6)
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityElement(children: .combine)
    }

    @ViewBuilder private var tags: some View {
        if play.scoring { Tag(text: play.scoreValue > 0 ? "+\(play.scoreValue)" : "Score", color: .green) }
        if play.turnover { Tag(text: "Turnover", color: .red) }
        if play.penalty { Tag(text: "Penalty", color: .yellow) }
        if GameLogic.isBigPlay(play) { Tag(text: "\(play.yards) yds", color: .blue) }
    }
}

struct Tag: View {
    let text: String
    let color: Color

    var body: some View {
        Text(text)
            .font(.caption2.weight(.bold))
            .padding(.horizontal, 6).padding(.vertical, 2)
            .foregroundStyle(color)
            .background(color.opacity(0.18), in: Capsule())
    }
}
