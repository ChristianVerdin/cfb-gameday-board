import Foundation
import Observation

/// Teams the user stars, kept on device in UserDefaults.
@Observable @MainActor
final class FollowStore {
    static let key = "pfb.following.v1"

    private(set) var teams: Set<String>
    @ObservationIgnored private let defaults: UserDefaults

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        teams = Set(defaults.stringArray(forKey: Self.key) ?? [])
    }

    func isFollowing(_ abbr: String) -> Bool { teams.contains(abbr) }

    func toggle(_ abbr: String) {
        if teams.contains(abbr) { teams.remove(abbr) } else { teams.insert(abbr) }
        defaults.set(teams.sorted(), forKey: Self.key)
    }

    func follows(_ game: BoardGame) -> Bool {
        teams.contains { game.involves($0) }
    }
}
