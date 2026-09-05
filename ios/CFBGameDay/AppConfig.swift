import Foundation

enum AppConfig {
    /// Single origin the app is allowed to render. Everything else opens in Safari.
    static let boardURL: URL = {
        let s = Bundle.main.object(forInfoDictionaryKey: "BoardURL") as? String ?? "https://cfbgameday.app"
        return URL(string: s)!
    }()
    static var boardHost: String {
        Bundle.main.object(forInfoDictionaryKey: "BoardHost") as? String ?? boardURL.host ?? "cfbgameday.app"
    }
    static var version: String {
        let v = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "?"
        let b = Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "?"
        return "\(v) (\(b))"
    }
    static let privacyURL = boardURL.appending(path: "privacy")
    static let supportURL = boardURL.appending(path: "support")
    static let sourceURL = URL(string: "https://github.com/ChristianVerdin/cfb-gameday-board")!
}
