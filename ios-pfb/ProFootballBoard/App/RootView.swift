import SwiftUI

struct RootView: View {
    @Environment(BoardStore.self) private var board
    @Environment(Router.self) private var router
    @Environment(\.scenePhase) private var scenePhase

    private struct GameRef: Identifiable { let id: String }

    var body: some View {
        @Bindable var router = router
        TabView(selection: $router.tab) {
            BoardView(filter: .all)
                .tabItem { Label("Board", systemImage: "sportscourt") }
                .tag(AppTab.board)
            BoardView(filter: .live)
                .tabItem { Label("Live", systemImage: "dot.radiowaves.left.and.right") }
                .tag(AppTab.live)
            BoardView(filter: .following)
                .tabItem { Label("Following", systemImage: "star") }
                .tag(AppTab.following)
            AboutView()
                .tabItem { Label("About", systemImage: "info.circle") }
                .tag(AppTab.about)
        }
        .sheet(item: Binding(get: { router.gameID.map(GameRef.init) }, set: { router.gameID = $0?.id })) { ref in
            GameView(gameID: ref.id)
        }
        .onChange(of: scenePhase, initial: true) { _, phase in board.setActive(phase != .background) }
    }
}
