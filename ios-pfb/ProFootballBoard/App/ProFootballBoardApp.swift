import SwiftUI

@main
struct ProFootballBoardApp: App {
    @State private var board = BoardStore()
    @State private var following = FollowStore()
    @State private var router = Router()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(board)
                .environment(following)
                .environment(router)
                .onOpenURL { router.open(url: $0) }
        }
    }
}
