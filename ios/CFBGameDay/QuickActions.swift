import SwiftUI
import UIKit

/// Home Screen quick actions: long-press the app icon. The items themselves are static
/// (`UIApplicationShortcutItems` in project.yml); this routes the chosen one to a tab.
enum QuickAction: String {
    case live, starred, tv

    init?(_ item: UIApplicationShortcutItem) {
        // Types are "com.hoynelabs.cfbgameday.<case>".
        guard let last = item.type.split(separator: ".").last else { return nil }
        self.init(rawValue: String(last))
    }

    var tab: BoardTab {
        switch self {
        case .live: .live
        case .starred: .starred
        case .tv: .board
        }
    }
    /// app.js hash: #live, #starred, #tv (the by-network view).
    var fragment: String { rawValue }
}

@MainActor
final class QuickActions: ObservableObject {
    static let shared = QuickActions()
    @Published var pending: QuickAction?

    @discardableResult
    func handle(_ item: UIApplicationShortcutItem) -> Bool {
        guard let action = QuickAction(item) else { return false }
        pending = action
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
