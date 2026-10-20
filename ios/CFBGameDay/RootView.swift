import StoreKit
import SwiftUI

struct RootView: View {
    @StateObject private var container = WebContainer()
    @ObservedObject private var quick = QuickActions.shared
    @State private var tab: BoardTab = BoardTab(rawValue: UserDefaults.standard.string(forKey: "tab") ?? "") ?? .board
    /// The Board tab's view. A quick action or deep link can open it on another view (By TV, Rivalry); leaving the tab resets it.
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
        .onChange(of: quick.pending, initial: true) { _, route in
            guard let route else { return }
            quick.pending = nil
            open(route)
        }
        .onOpenURL { quick.handle($0) }   // cfbgameday:// deep links, cold or warm launch
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

    private func open(_ route: Route) {
        // The page is shared across tabs. A game link from Live or Starred clears that tab's
        // filter first, so closing the game sheet steps back to all games, not "No games live".
        if route.fragment.hasPrefix("game/") && tab != route.tab { container.show(fragment: "all") }
        if route.tab == .board { boardFragment = route.fragment }
        if tab == route.tab {
            container.show(fragment: route.fragment, reapply: true)   // same tab: onChange won't fire
        } else {
            tab = route.tab
        }
    }
}
