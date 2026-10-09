import StoreKit
import SwiftUI

struct RootView: View {
    @StateObject private var container = WebContainer()
    @State private var tab: BoardTab = BoardTab(rawValue: UserDefaults.standard.string(forKey: "tab") ?? "") ?? .board
    @Environment(\.scenePhase) private var phase
    @Environment(\.requestReview) private var requestReview

    var body: some View {
        TabView(selection: $tab) {
            ForEach(BoardTab.allCases) { t in
                Group {
                    if let fragment = t.fragment {
                        WebScreen(container: container, fragment: fragment)
                    } else {
                        AboutView(container: container)
                    }
                }
                .tabItem { Label(t.title, systemImage: t.symbol) }
                .tag(t)
            }
        }
        .tint(.yellow)
        .focusedSceneValue(\.boardActions, BoardActions(
            select: { tab = $0 },
            reload: { container.reload() },
            find: {
                if tab.fragment == nil { tab = .board }
                container.focusSearch()
            }
        ))
        .onAppear { WindowSizing.apply() }
        .onChange(of: tab) { _, new in
            if let fragment = new.fragment { container.show(fragment: fragment) }
        }
        .onChange(of: phase, initial: true) { _, new in
            guard new == .active, ReviewPrompt.shouldAsk() else { return }
            ReviewPrompt.markAsked()                        // before the delay: launch can flip phase twice
            Task {
                try? await Task.sleep(for: .seconds(5))     // let the board load first
                guard container.failure == nil else { return }
                requestReview()
            }
        }
    }
}
