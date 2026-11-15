import Foundation

enum AppTab: String, CaseIterable, Hashable, Sendable {
    case board, live, following, about
}

enum Route: Equatable, Sendable {
    case tab(AppTab)
    case game(String)

    /// pfb://game/<id>, pfb://live, pfb://board, pfb://following, pfb://about
    init?(url: URL) {
        guard url.scheme?.lowercased() == "pfb", let host = url.host?.lowercased() else { return nil }
        if host == "game" {
            let id = url.pathComponents.dropFirst().first ?? ""
            guard (6...14).contains(id.count), id.allSatisfy(\.isASCII), id.allSatisfy(\.isNumber) else { return nil }
            self = .game(id)
        } else if let tab = AppTab(rawValue: host) {
            self = .tab(tab)
        } else {
            return nil
        }
    }
}
