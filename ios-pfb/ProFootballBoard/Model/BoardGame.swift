import Foundation

/// One game with the live scoreboard merged over the weekly snapshot. Live values win; the snapshot supplies
/// venue, roof, weather, round and team colours.
struct BoardGame: Identifiable, Equatable, Sendable {
    var id: String
    var state: GameState
    var status: String
    var statusShort: String
    var period: Int
    var periodLabel: String
    var clock: String
    var clockSeconds: Int
    var completed: Bool
    var ot: Bool
    var result: GameResult?
    var date: Date?
    var timeTBD: Bool
    var flexNote: String?
    var neutral: Bool
    var kind: GameKind
    var round: String?
    var broadcasts: [String]
    var venue: Venue?
    var weather: Weather?
    var weatherStatus: String?
    var situation: Situation?
    var wp: WinProbability?
    var desk: Desk?
    var away: Team?
    var home: Team?
    var placeholder: Bool

    var isLive: Bool { state == .in }
    var tv: String { broadcasts.joined(separator: " / ") }

    var abroad: Bool {
        if let country = venue?.country, !country.isEmpty { return country != "US" }
        return neutral
    }

    var window: GameWindow {
        GameWindow.classify(date: date, timeTBD: timeTBD, kind: kind, round: round, abroad: abroad)
    }

    var kickoffText: String { Chicago.kickoff(date, tbd: timeTBD) }

    var kickoffSortKey: TimeInterval {
        timeTBD ? .infinity : (date?.timeIntervalSince1970 ?? .infinity)
    }

    func involves(_ abbr: String) -> Bool { away?.abbr == abbr || home?.abbr == abbr }

    /// "WSH @ NYG", or a placeholder label while the matchup is open.
    var matchup: String {
        guard let away, let home else { return flexNote ?? "To be determined" }
        return "\(away.abbr) @ \(home.abbr)"
    }

    static func merged(snapshot s: SnapshotGame?, live l: LiveGame?, seasonType: Int?, weekLabel: String?) -> BoardGame? {
        guard s != nil || l != nil else { return nil }
        let away = l?.away.map { $0.merged(over: s?.away) } ?? s?.away
        let home = l?.home.map { $0.merged(over: s?.home) } ?? s?.home
        let allStar = ["AFC", "NFC"].contains(away?.abbr ?? "") && ["AFC", "NFC"].contains(home?.abbr ?? "")
        let kind = s?.kind ?? (allStar ? .allStar : seasonType == 3 ? .playoff : .regular)
        let state = l?.state ?? s?.state ?? .pre
        var game = BoardGame(
            id: l?.id ?? s?.id ?? "", state: state,
            status: l?.status ?? "", statusShort: l?.statusShort ?? s?.statusShort ?? "",
            period: l?.period ?? 0, periodLabel: l?.periodLabel ?? "", clock: l?.clock ?? "", clockSeconds: l?.clockSeconds ?? 0,
            completed: l?.completed ?? (state == .post), ot: l?.ot ?? false, result: l?.result,
            date: l?.date ?? s?.date, timeTBD: l?.timeTBD ?? s?.timeTBD ?? false,
            flexNote: l?.flexNote ?? s?.flexNote, neutral: l?.neutral ?? s?.neutral ?? false,
            kind: kind, round: s?.round ?? (kind == .playoff ? (s?.weekLabel ?? weekLabel ?? "Playoffs") : nil),
            broadcasts: (l?.broadcasts.isEmpty == false ? l?.broadcasts : s?.broadcasts) ?? [],
            venue: s?.venue ?? l?.venueName.map { Venue(name: $0) }, weather: s?.weather, weatherStatus: s?.weatherStatus,
            situation: l?.situation, wp: l?.wp, desk: l?.desk,
            away: away, home: home, placeholder: (l?.placeholder ?? s?.placeholder ?? false) || away == nil || home == nil)
        if game.state == .post, game.result == nil, let a = away?.score, let h = home?.score {
            game.result = a == h ? .tie : a > h ? .away : .home
        }
        return game
    }

    /// Joins the snapshot onto the live scoreboard by game id. The snapshot is ignored when it describes another
    /// week; with no live games the snapshot alone fills the board.
    static func build(live: LivePayload?, snapshot: Snapshot?) -> [BoardGame] {
        let usable: Bool = {
            guard let snapshot else { return false }
            guard let live else { return true }
            return snapshot.week.number == live.week.number && snapshot.season.type == live.season.type
        }()
        let snapGames = usable ? snapshot?.games ?? [] : []
        let bySnap = Dictionary(snapGames.map { ($0.id, $0) }, uniquingKeysWith: { a, _ in a })
        let type = live?.season.type ?? snapshot?.season.type
        let label = live?.week.label ?? snapshot?.week.label
        if let live, !live.games.isEmpty {
            return live.games.compactMap { merged(snapshot: bySnap[$0.id], live: $0, seasonType: type, weekLabel: label) }
        }
        return snapGames.compactMap { merged(snapshot: $0, live: nil, seasonType: type, weekLabel: label) }
    }

    /// Live games first (highest desk score first), then upcoming by kickoff, then finals by kickoff.
    static func sorted(_ games: [BoardGame]) -> [BoardGame] {
        func rank(_ g: BoardGame) -> Int { g.state == .in ? 0 : g.state == .pre ? 1 : 2 }
        return games.sorted { a, b in
            if rank(a) != rank(b) { return rank(a) < rank(b) }
            if a.isLive, a.desk?.score != b.desk?.score { return (a.desk?.score ?? 0) > (b.desk?.score ?? 0) }
            if a.kickoffSortKey != b.kickoffSortKey { return a.kickoffSortKey < b.kickoffSortKey }
            return a.id < b.id
        }
    }
}
