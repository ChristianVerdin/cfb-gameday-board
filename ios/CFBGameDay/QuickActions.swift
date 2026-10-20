import SwiftUI
import UIKit

/// Where a quick action or a deep link lands: a tab, and the app.js hash to show in it.
struct Route: Equatable {
    let tab: BoardTab
    let fragment: String
}

/// Home Screen quick actions: long-press the app icon. The items themselves are static
/// (`UIApplicationShortcutItems` in project.yml); this routes the chosen one to a tab.
enum QuickAction: String {
    case live, starred, tv, rivalry

    init?(_ item: UIApplicationShortcutItem) {
        // Types are "com.hoynelabs.cfbgameday.<case>".
        guard let last = item.type.split(separator: ".").last else { return nil }
        self.init(rawValue: String(last))
    }

    /// app.js hashes: #live, #starred, #tv (the by-network view), #rivalry (trophy games).
    var route: Route {
        switch self {
        case .live: Route(tab: .live, fragment: "live")
        case .starred: Route(tab: .starred, fragment: "starred")
        case .tv: Route(tab: .board, fragment: "tv")
        case .rivalry: Route(tab: .board, fragment: "rivalry")
        }
    }
}

extension Route {
    /// cfbgameday://<quick action>, cfbgameday://board, cfbgameday://game/<ESPN id>.
    /// App Store in-app events require a link that opens the app itself, not the website.
    init?(url: URL) {
        guard url.scheme?.lowercased() == "cfbgameday" else { return nil }
        let host = (url.host ?? "").lowercased()
        if let action = QuickAction(rawValue: host) {
            self = action.route
            return
        }
        switch host {
        case "", "board", "all":
            self = Route(tab: .board, fragment: "all")
        case "game":
            // Same shape app.js accepts for #game/<id>: 6 to 12 digits, nothing else reaches the page.
            let id = url.pathComponents.dropFirst().first ?? ""
            guard (6...12).contains(id.count), id.allSatisfy({ $0.isASCII && $0.isNumber }) else { return nil }
            self = Route(tab: .board, fragment: "game/\(id)")
        default:
            return nil
        }
    }
}

@MainActor
final class QuickActions: ObservableObject {
    static let shared = QuickActions()
    @Published var pending: Route?

    @discardableResult
    func handle(_ item: UIApplicationShortcutItem) -> Bool {
        guard let action = QuickAction(item) else { return false }
        pending = action.route
        return true
    }

    @discardableResult
    func handle(_ url: URL) -> Bool {
        guard let route = Route(url: url) else { return false }
        pending = route
        return true
    }
}

final class AppDelegate: NSObject, UIApplicationDelegate {
    func application(_ application: UIApplication, configurationForConnecting session: UISceneSession,
                     options: UIScene.ConnectionOptions) -> UISceneConfiguration {
        if let item = options.shortcutItem { QuickActions.shared.handle(item) }   // cold launch
        let config = UISceneConfiguration(name: nil, sessionRole: session.role)
        config.delegateClass = SceneDelegate.self
        return config
    }
}

final class SceneDelegate: NSObject, UIWindowSceneDelegate {
    // Already running: the scene gets the action instead of a new connection.
    func windowScene(_ windowScene: UIWindowScene, performActionFor shortcutItem: UIApplicationShortcutItem,
                     completionHandler: @escaping (Bool) -> Void) {
        completionHandler(QuickActions.shared.handle(shortcutItem))
    }
}
