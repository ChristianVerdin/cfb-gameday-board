import SwiftUI

struct PlaysTab: View {
    let sheet: GameSheet
    @Binding var filter: PlayFilter

    var body: some View {
        let all = sheet.plays.filter { GameLogic.matches(filter, $0.play) }
        let list = sheet.phase == .live ? Array(all.reversed()) : all
        VStack(alignment: .leading, spacing: 10) {
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach(PlayFilter.allCases) { f in
                        Button(f.title) { filter = f }
                            .font(.footnote.weight(.semibold))
                            .padding(.horizontal, 12).padding(.vertical, 6)
                            .background(filter == f ? Color.accentColor : Color.white.opacity(0.12), in: Capsule())
                            .foregroundStyle(filter == f ? Color.black : Color.primary)
                            .buttonStyle(.plain)
                            .accessibilityAddTraits(filter == f ? .isSelected : [])
                    }
                }
            }
            .accessibilityElement(children: .contain)
            .accessibilityLabel("Play filters")
            if list.isEmpty {
                SheetEmpty(text: "No plays match.")
            } else {
                SheetCard {
                    LazyVStack(spacing: 0) {
                        ForEach(list) { item in
                            PlayRow(play: item.play, sheet: sheet, team: item.team)
                            if item.id != list.last?.id { Divider() }
                        }
                    }
                }
            }
        }
    }
}
