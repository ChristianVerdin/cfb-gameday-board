import Foundation

enum GameTab: String, CaseIterable, Identifiable, Sendable {
    case drives, plays, winProb, scoring, box, leaders
    var id: String { rawValue }

    var title: String {
        switch self {
        case .drives: "Drives"
        case .plays: "Plays"
        case .winProb: "Win prob"
        case .scoring: "Scoring"
        case .box: "Box"
        case .leaders: "Leaders"
        }
    }
}

enum PlayFilter: String, CaseIterable, Identifiable, Sendable {
    case all, scoring, big, turnover, penalty
    var id: String { rawValue }

    var title: String {
        switch self {
        case .all: "All"
        case .scoring: "Scoring"
        case .big: "Big plays"
        case .turnover: "Turnovers"
        case .penalty: "Penalties"
        }
    }
}

enum SheetPhase: Equatable, Sendable {
    case pre, live, final, hold
}

enum DriveTone: Equatable, Sendable {
    case plain, score, turnover
}

struct SheetPlay: Identifiable, Equatable, Sendable {
    var play: Play
    var team: String
    var id: String { play.id }
}

enum GameLogic {
    static let bigYards = 20
    static let allStarTeamIDs: Set<String> = ["31", "32"]
    private static let nonScrimmage = ["kickoff", "punt", "field goal", "extra point", "two-point", "timeout", "end period", "end of", "coin toss"]
    private static let turnoverResults = ["interception", "fumble", "downs", "turnover", "safety"]

    static func isBigPlay(_ p: Play) -> Bool {
        guard !p.isAdmin, !p.penalty else { return false }
        let type = p.type.lowercased()
        if nonScrimmage.contains(where: type.contains) { return false }
        return p.yards >= bigYards
    }

    static func matches(_ filter: PlayFilter, _ p: Play) -> Bool {
        if p.isAdmin { return false }
        switch filter {
        case .all: return true
        case .scoring: return p.scoring
        case .big: return isBigPlay(p)
        case .turnover: return p.turnover
        case .penalty: return p.penalty
        }
    }

    /// Every play of every drive in game order; plays without a sequence keep their drive order.
    static func allPlays(_ sheet: GameSheet) -> [SheetPlay] {
        var out: [(SheetPlay, Int)] = []
        for drive in sheet.drives {
            for p in drive.playList { out.append((SheetPlay(play: p, team: drive.team), out.count)) }
        }
        return out.sorted {
            let a = $0.0.play.seq ?? 0, b = $1.0.play.seq ?? 0
            return a != b ? a < b : $0.1 < $1.1
        }.map(\.0)
    }

    static func downText(_ p: Play) -> String {
        guard let down = p.down, (1...4).contains(down) else { return "" }
        let ord = ["1st", "2nd", "3rd", "4th"][down - 1]
        guard let d = p.distance else { return ord }
        return "\(ord) & \(d)"
    }

    static func tone(of drive: Drive) -> DriveTone {
        if drive.scoring { return .score }
        let r = (drive.result ?? "").lowercased()
        return turnoverResults.contains(where: r.contains) ? .turnover : .plain
    }

    static func lineLabels(_ n: Int) -> [String] {
        (0..<max(0, n)).map { $0 < 4 ? "Q\($0 + 1)" : (n > 5 ? "\($0 - 3)OT" : "OT") }
    }

    static func winProbLabel(_ home: Double, away: String, homeAbbr: String) -> String {
        let h = Int((home * 100).rounded())
        if h == 50 { return "even" }
        return h > 50 ? "\(homeAbbr) \(h)%" : "\(away) \(100 - h)%"
    }
}

struct TrackerGeometry: Equatable, Sendable {
    /// The field is 120 units wide: the away end zone is 0...10, the home end zone 110...120.
    static let width = 120.0
    static let endZone = 10.0

    var side: Possession
    var direction: Double
    var startX: Double
    var currentX: Double
    var redZone: Bool
    var redZoneX: Double

    /// `start` and `current` are the payload's distances from the home goal line.
    init?(start: Int?, current: Int?, side: Possession?) {
        guard let start, let current, let side else { return nil }
        func clamp(_ v: Int) -> Double { Double(max(0, min(100, v))) }
        self.side = side
        direction = side == .away ? 1 : -1
        startX = Self.endZone + 100 - clamp(start)
        currentX = Self.endZone + 100 - clamp(current)
        redZone = side == .away ? clamp(current) <= 20 : clamp(current) >= 80
        redZoneX = side == .away ? 90 : 10
    }

    var arrowTip: Double { currentX + direction * 7 }
}

extension GameSheet {
    var isOffGame: Bool {
        guard let status else { return false }
        return ["STATUS_POSTPONED", "STATUS_CANCELED", "STATUS_CANCELLED"].contains(status)
    }

    var phase: SheetPhase {
        if isOffGame || isHeld { return .hold }
        switch state {
        case .in: return .live
        case .post: return .final
        case .pre: return drives.isEmpty && scoring.isEmpty ? .pre : .hold
        }
    }

    var isProBowl: Bool {
        [teams.away?.id, teams.home?.id].contains { $0.map(GameLogic.allStarTeamIDs.contains) ?? false }
    }

    var awayAbbr: String { teams.away?.abbr ?? "Away" }
    var homeAbbr: String { teams.home?.abbr ?? "Home" }

    var totals: (away: Int, home: Int) {
        if !linescores.away.isEmpty || !linescores.home.isEmpty {
            return (linescores.away.reduce(0) { $0 + ($1 ?? 0) }, linescores.home.reduce(0) { $0 + ($1 ?? 0) })
        }
        if let last = scoring.last { return (last.away ?? 0, last.home ?? 0) }
        return (teams.away?.score ?? 0, teams.home?.score ?? 0)
    }

    var statusText: String {
        switch phase {
        case .final:
            let ot = overtimePeriods
            let t = totals
            return "Final" + (ot > 1 ? "/\(ot)OT" : ot == 1 ? "/OT" : "") + (result == .tie || t.away == t.home ? " · Tie" : "")
        case .pre:
            return "Game detail opens at kickoff"
        case .hold, .live:
            if isOffGame { return status == "STATUS_POSTPONED" ? "Postponed" : "Canceled" }
            if isHeld { return HeldStatus.pill(status) }
            if status == "STATUS_HALFTIME" { return "Halftime" }
            if status == "STATUS_END_PERIOD" { return "End of \(periodLabel)" }
            if phase == .live { return [periodLabel, clock ?? ""].filter { !$0.isEmpty }.joined(separator: " ") }
            return "Paused"
        }
    }

    var defaultTab: GameTab { phase == .final ? .scoring : .drives }

    func team(_ abbr: String) -> Team? {
        [teams.away, teams.home].compactMap { $0 }.first { $0.abbr == abbr || $0.id == abbr }
    }

    func chipColors(for abbr: String) -> ChipColors {
        team(abbr)?.chip ?? ChipColors(background: .neutralBG, foreground: .neutralFG)
    }

    func side(ofTeam key: String?) -> Possession? {
        guard let key, !key.isEmpty else { return nil }
        if let a = teams.away, key == a.abbr || key == a.id { return .away }
        if let h = teams.home, key == h.abbr || key == h.id { return .home }
        return nil
    }

    var trackerGeometry: TrackerGeometry? {
        guard phase == .live, let t = tracker else { return nil }
        let drive = drives.first { $0.id == t.driveID }
        let side = side(ofTeam: t.team) ?? side(ofTeam: drive?.team)
        return TrackerGeometry(start: t.startYardLine, current: t.currentYardLine, side: side)
    }

    var plays: [SheetPlay] { GameLogic.allPlays(self) }
}
