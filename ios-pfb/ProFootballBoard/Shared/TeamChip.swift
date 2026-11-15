import SwiftUI

/// A text abbreviation in the team's colours. No logos.
struct TeamChip: View {
    let team: Team

    var body: some View {
        let colors = team.chip
        Text(team.abbr)
            .font(.subheadline.weight(.heavy).monospaced())
            .foregroundStyle(colors.foreground.color)
            .lineLimit(1)
            .minimumScaleFactor(0.7)
            .frame(minWidth: 52)
            .padding(.vertical, 5)
            .padding(.horizontal, 6)
            .background(colors.background.color, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
            .accessibilityHidden(true)
    }
}
