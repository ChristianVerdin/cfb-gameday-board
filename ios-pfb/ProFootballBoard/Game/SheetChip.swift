import SwiftUI

/// Team abbreviation in team colours; text only, never a logo.
struct SheetChip: View {
    let abbr: String
    let colors: ChipColors

    var body: some View {
        Text(abbr)
            .font(.caption.weight(.heavy))
            .padding(.horizontal, 7)
            .padding(.vertical, 2)
            .foregroundStyle(colors.foreground.color)
            .background(colors.background.color, in: RoundedRectangle(cornerRadius: 5, style: .continuous))
            .accessibilityLabel(abbr)
    }
}

struct SheetCard<Content: View>: View {
    @ViewBuilder var content: Content

    var body: some View {
        content
            .padding(12)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(RGB.card.color, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
    }
}

struct SheetEmpty: View {
    let text: String
    var systemImage = "sportscourt"

    var body: some View {
        VStack(spacing: 8) {
            Image(systemName: systemImage).font(.title2).foregroundStyle(.secondary).accessibilityHidden(true)
            Text(text).font(.subheadline).foregroundStyle(.secondary).multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 28)
        .accessibilityElement(children: .combine)
    }
}
