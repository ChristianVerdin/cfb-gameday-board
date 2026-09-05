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
        case .board: "all"
        case .live: "live"
        case .starred: "starred"
        case .about: nil
        }
    }
}
