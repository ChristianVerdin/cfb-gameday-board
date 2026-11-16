import Foundation

/// Where the ball sits on a 0...100 field drawn left to right: 0 is the away team's goal line, 100 the home team's.
/// The away team attacks toward 100, the home team toward 0.
struct FieldPosition: Equatable, Sendable {
    var ball: Double
    var firstDownLine: Double?
    var attackingGoal: Double
    /// +1 when the offence moves toward the right edge, -1 toward the left.
    var direction: Int
    var possession: Possession

    /// nil unless the situation names a possession and a yards-to-goal value.
    init?(_ situation: Situation?) {
        guard let s = situation, !s.stoppage, let side = s.possession, let yl = s.yl100 else { return nil }
        let toGoal = Double(max(0, min(100, yl)))
        possession = side
        direction = side == .away ? 1 : -1
        attackingGoal = side == .away ? 100 : 0
        ball = side == .away ? 100 - toGoal : toGoal
        if let d = s.distance, d > 0 {
            firstDownLine = max(0, min(100, ball + Double(direction * d)))
        } else {
            firstDownLine = nil
        }
    }

    var yardsToGoal: Double { abs(attackingGoal - ball) }
}

enum DeskRanking {
    static let hysteresis = 5.0
    static let swingWindow: TimeInterval = 180
    static let swingCap = 15

    struct Sample: Equatable, Sendable {
        var time: Date
        var homeWP: Double
    }

    struct Item: Equatable, Sendable {
        var id: String
        var effective: Double
        var progress: Int
        var kickoff: TimeInterval
    }

    /// Win-probability movement across the last three minutes, in points.
    static func swing(_ samples: [Sample], now: Date) -> (points: Double, toward: Possession?) {
        let recent = samples.filter { now.timeIntervalSince($0.time) <= swingWindow }
        guard let first = recent.first, let last = recent.last, recent.count >= 2 else { return (0, nil) }
        let d = last.homeWP - first.homeWP
        return (abs(d) * 100, d > 0 ? .home : d < 0 ? .away : nil)
    }

    static func effectiveScore(_ score: Int, swingPoints: Double) -> Double {
        Double(score + min(swingCap, Int(swingPoints.rounded())))
    }

    /// Orders by effective score, then game progress, then kickoff. The previous leader keeps #1 unless the new
    /// leader is ahead by at least `hysteresis` points.
    static func order(_ items: [Item], previousTop: String?) -> [String] {
        var out = items.sorted {
            if $0.effective != $1.effective { return $0.effective > $1.effective }
            if $0.progress != $1.progress { return $0.progress > $1.progress }
            return $0.kickoff < $1.kickoff
        }
        if let prevID = previousTop, let prev = out.first(where: { $0.id == prevID }), out[0].id != prevID,
           out[0].effective < prev.effective + hysteresis {
            out.removeAll { $0.id == prevID }
            out.insert(prev, at: 0)
        }
        return out.map(\.id)
    }
}

enum PollCadence {
    static let live: TimeInterval = 20
    static let nearKickoff: TimeInterval = 60
    static let idle: TimeInterval = 120
    /// The API says there is no slate; nothing changes until the next season.
    static let offseason: TimeInterval = 1800

    /// 20 s while any game is live; 60 s when an upcoming game kicks within an hour (or kicked off in the last
    /// three hours without going live); 120 s otherwise.
    static func interval(for games: [BoardGame], now: Date) -> TimeInterval {
        if games.contains(where: \.isLive) { return live }
        let soon = games.contains { g in
            guard g.state == .pre, !g.timeTBD, let d = g.date else { return false }
            let t = d.timeIntervalSince(now)
            return t <= 3600 && t >= -10800
        }
        return soon ? nearKickoff : idle
    }
}
