import Foundation
import Observation

/// Which tab is selected and which game sheet is open. Deep links, shortcuts and intents all go through `open`.
@Observable @MainActor
final class Router {
    var tab: AppTab = .board
    var gameID: String?

    func open(_ route: Route) {
        switch route {
        case .tab(let t):
            gameID = nil
            tab = t
        case .game(let id):
            gameID = id
        }
    }

    @discardableResult
    func open(url: URL) -> Bool {
        guard let route = Route(url: url) else { return false }
        open(route)
        return true
    }
}
