import SwiftUI

enum BoardTab: String, CaseIterable, Identifiable {
    case board, live, starred, about
    var id: String { rawValue }

    var title: String {
        switch self {
        case .board: "Board"
        case .live: "Live"
        case .starred: "Starred"
        case .about: "About"
        }
    }
    var symbol: String {
        switch self {
        case .board: "sportscourt"
        case .live: "dot.radiowaves.left.and.right"
        case .starred: "star"
        case .about: "info.circle"
        }
    }
    /// URL fragment app.js reads to set its filters.
    var fragment: String? {
        switch self {
        // `-fragment lines` at launch (screenshots, debugging) opens the board on that view.
        case .board: UserDefaults.standard.string(forKey: "fragment") ?? "all"
        case .live: "live"
        case .starred: "starred"
        case .about: nil
        }
    }
}
