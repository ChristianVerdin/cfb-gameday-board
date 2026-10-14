import StoreKit
import SwiftUI

struct RootView: View {
    @StateObject private var container = WebContainer()
    @ObservedObject private var quick = QuickActions.shared
    @State private var tab: BoardTab = BoardTab(rawValue: UserDefaults.standard.string(forKey: "tab") ?? "") ?? .board
    /// The Board tab's view. A quick action can open it on another view (By TV); leaving the tab resets it.
    @State private var boardFragment = BoardTab.board.fragment ?? "all"
    @Environment(\.scenePhase) private var phase
    @Environment(\.requestReview) private var requestReview

    var body: some View {
        TabView(selection: $tab) {
            ForEach(BoardTab.allCases) { t in
                Group {
                    if let fragment = fragment(for: t) {
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
        .onChange(of: tab) { old, new in
            if old == .board { boardFragment = BoardTab.board.fragment ?? "all" }
            if let fragment = fragment(for: new) { container.show(fragment: fragment) }
        }
        .onChange(of: quick.pending, initial: true) { _, action in
            guard let action else { return }
            quick.pending = nil
            open(action)
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

    private func fragment(for t: BoardTab) -> String? {
        t == .board ? boardFragment : t.fragment
    }

    private func open(_ action: QuickAction) {
        if action.tab == .board { boardFragment = action.fragment }
        if tab == action.tab {
            container.show(fragment: action.fragment, reapply: true)   // same tab: onChange won't fire
        } else {
            tab = action.tab
        }
    }
}
