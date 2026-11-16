import SwiftUI

/// The game sheet. Owns its NavigationStack and its GameStore; polls while visible and in the foreground.
struct GameView: View {
    let gameID: String
    @State private var store: GameStore
    @State private var picked: GameTab?
    @State private var filter: PlayFilter = .all
    @State private var expanded: [String: Bool] = [:]
    @Environment(\.dismiss) private var dismiss
    @Environment(\.scenePhase) private var scenePhase

    init(gameID: String) {
        self.gameID = gameID
        _store = State(initialValue: GameStore(gameID: gameID))
    }

    var body: some View {
        NavigationStack {
            content
                .background(Color(.systemBackground))
                .toolbarBackground(Color(.systemBackground), for: .navigationBar)
                .toolbar(.visible, for: .navigationBar)
                .navigationTitle(title)
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } }
                }
        }
        .onAppear { if scenePhase != .background { store.start() } }
        .onDisappear { store.stop() }
        .onChange(of: scenePhase) { _, phase in
            if phase == .background { store.stop() } else { store.start() }
        }
    }

    private var title: String {
        guard let s = store.sheet else { return "Game" }
        return "\(s.awayAbbr) at \(s.homeAbbr)"
    }

    @ViewBuilder private var content: some View {
        if let sheet = store.sheet {
            loaded(sheet)
        } else if store.error != nil {
            ContentUnavailableView {
                Label("Couldn't load the game", systemImage: "wifi.exclamationmark")
            } description: {
                Text(store.error?.isPermanent == true ? "The board has no game with that id." : "Check your connection and try again.")
            } actions: {
                Button("Retry") { Task { await store.refresh() } }.buttonStyle(.borderedProminent)
            }
        } else {
            ProgressView("Loading game").frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }

    private func loaded(_ sheet: GameSheet) -> some View {
        let tab = picked ?? sheet.defaultTab
        return ScrollView {
            VStack(spacing: 12) {
                GameHeader(sheet: sheet)
                notices(sheet)
                if sheet.phase == .pre {
                    SheetEmpty(text: sheet.isProBowl
                        ? "The Pro Bowl has no drive or win probability detail here. Play-by-play opens at kickoff."
                        : "Play-by-play opens at kickoff.")
                } else {
                    tabBody(tab, sheet)
                }
                footer
            }
            .padding(.horizontal, 12)
            .padding(.bottom, 24)
        }
        .safeAreaInset(edge: .top, spacing: 0) {
            if sheet.phase != .pre {
                TabBar(selection: Binding(get: { tab }, set: { picked = $0 }))
                    .padding(.horizontal, 12)
                    .background(Color(.systemBackground))
            }
        }
        .refreshable { await store.refresh() }
        .scrollBounceBehavior(.basedOnSize, axes: .horizontal)
    }

    @ViewBuilder private func notices(_ sheet: GameSheet) -> some View {
        if sheet.stale { Notice(text: "Showing saved data.") }
        if store.error != nil { Notice(text: "Update failed, retrying.") }
    }

    @ViewBuilder private func tabBody(_ tab: GameTab, _ sheet: GameSheet) -> some View {
        let empty = sheet.drives.isEmpty && sheet.scoring.isEmpty && sheet.winProb.points.isEmpty && sheet.box.isEmpty
        if sheet.isOffGame || (empty && sheet.isProBowl) {
            SheetEmpty(text: sheet.isOffGame ? "This game is \(sheet.statusText.lowercased())." : "No play-by-play detail for the Pro Bowl.")
        } else {
            switch tab {
            case .drives: DrivesTab(sheet: sheet, expanded: $expanded)
            case .plays: PlaysTab(sheet: sheet, filter: $filter)
            case .winProb: WinProbTab(sheet: sheet)
            case .scoring: ScoringTab(sheet: sheet)
            case .box: BoxTab(sheet: sheet)
            case .leaders: LeadersTab(sheet: sheet)
            }
        }
    }

    private var footer: some View {
        VStack(spacing: 2) {
            Text("Scores and play data via ESPN.")
            if let t = store.lastUpdated { Text("Updated \(Chicago.time(t))") }
        }
        .font(.caption2).foregroundStyle(.secondary)
        .padding(.top, 8)
    }
}

private struct TabBar: View {
    @Binding var selection: GameTab

    var body: some View {
        ScrollViewReader { proxy in
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 4) {
                    ForEach(GameTab.allCases) { tab in
                        Button { selection = tab } label: {
                            Text(tab.title)
                                .font(.subheadline.weight(.semibold))
                                .padding(.horizontal, 14).padding(.vertical, 8)
                                .background(selection == tab ? Color.accentColor : Color.clear, in: Capsule())
                                .foregroundStyle(selection == tab ? Color.black : Color.primary)
                        }
                        .buttonStyle(.plain)
                        .id(tab)
                        .accessibilityAddTraits(selection == tab ? .isSelected : [])
                    }
                }
                .padding(4)
            }
            .background(RGB.card.color, in: Capsule())
            .padding(.vertical, 4)
            .onChange(of: selection) { _, new in withAnimation { proxy.scrollTo(new, anchor: .center) } }
        }
        .accessibilityElement(children: .contain)
        .accessibilityLabel("Game detail")
    }
}

private struct Notice: View {
    let text: String

    var body: some View {
        Text(text).font(.footnote).foregroundStyle(.secondary)
            .frame(maxWidth: .infinity, alignment: .leading)
            .accessibilityAddTraits(.isStaticText)
    }
}
