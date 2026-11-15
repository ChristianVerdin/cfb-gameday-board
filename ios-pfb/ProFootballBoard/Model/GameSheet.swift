import Foundation

struct DrivePoint: Equatable, Sendable, Decodable {
    var period: Int?
    var clock: String?
    var yardText: String?
    var yl100: Int?

    private enum CodingKeys: String, CodingKey { case period, clock, yl100, yardText = "yard_text" }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        period = c.int(.period); clock = c.str(.clock); yardText = c.str(.yardText); yl100 = c.int(.yl100)
    }
}

struct Play: Equatable, Sendable, Decodable, Identifiable {
    var id: String
    var seq: Int?
    var period: Int
    var periodLabel: String
    var clock: String?
    var down: Int?
    var distance: Int?
    var yardText: String?
    var text: String
    var type: String
    /// "play" or "admin" (kickoffs, timeouts, period ends).
    var kind: String
    var away: Int?
    var home: Int?
    /// Home win probability after the play, 0...1.
    var winProbability: Double?
    var yards: Int
    var scoring: Bool
    var scoreValue: Int
    var penalty: Bool
    var turnover: Bool

    private enum CodingKeys: String, CodingKey {
        case id, seq, period, periodLabel, clock, down, distance, text, type, kind, away, home, yards, scoring, penalty, turnover
        case yardText = "yard_text", winProbability = "wp", scoreValue = "score_value"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        guard let id = c.str(.id) else { throw DecodingError.dataCorruptedError(forKey: .id, in: c, debugDescription: "play id") }
        self.id = id
        seq = c.int(.seq)
        period = c.int(.period) ?? 0
        periodLabel = c.str(.periodLabel) ?? PeriodLabel.of(period)
        clock = c.str(.clock); down = c.int(.down); distance = c.int(.distance); yardText = c.str(.yardText)
        text = c.str(.text) ?? ""; type = c.str(.type) ?? ""; kind = c.str(.kind) ?? "play"
        away = c.int(.away); home = c.int(.home); winProbability = c.dbl(.winProbability)
        yards = c.int(.yards) ?? 0
        scoring = c.flag(.scoring) ?? false; scoreValue = c.int(.scoreValue) ?? 0
        penalty = c.flag(.penalty) ?? false; turnover = c.flag(.turnover) ?? false
    }

    var isAdmin: Bool { kind == "admin" }
}

struct Drive: Equatable, Sendable, Decodable, Identifiable {
    var id: String
    var team: String
    var desc: String
    var result: String?
    var resultText: String?
    var live: Bool
    var start: DrivePoint?
    var end: DrivePoint?
    var plays: Int
    var yards: Int
    var time: String?
    var scoring: Bool
    var playList: [Play]

    private enum CodingKeys: String, CodingKey {
        case id, team, desc, result, live, start, end, plays, yards, time, scoring
        case resultText = "result_text", playList = "plays_list"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        guard let id = c.str(.id) else { throw DecodingError.dataCorruptedError(forKey: .id, in: c, debugDescription: "drive id") }
        self.id = id
        team = c.str(.team) ?? ""; desc = c.str(.desc) ?? ""; result = c.str(.result); resultText = c.str(.resultText)
        live = c.flag(.live) ?? false; start = c.obj(.start); end = c.obj(.end)
        playList = c.list(.playList)
        plays = c.int(.plays) ?? playList.count
        yards = c.int(.yards) ?? 0; time = c.str(.time); scoring = c.flag(.scoring) ?? false
    }
}

struct ScoringPlay: Equatable, Sendable, Decodable, Identifiable {
    var id: String
    var driveID: String?
    var period: Int
    var periodLabel: String
    var clock: String?
    var team: String
    /// TD, FG, SF and so on, as ESPN abbreviates the scoring type.
    var kind: String
    var text: String
    var away: Int?
    var home: Int?

    private enum CodingKeys: String, CodingKey {
        case id, period, periodLabel, clock, team, kind, text, away, home
        case driveID = "drive_id"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        guard let id = c.str(.id) else { throw DecodingError.dataCorruptedError(forKey: .id, in: c, debugDescription: "scoring id") }
        self.id = id
        driveID = c.str(.driveID)
        period = c.int(.period) ?? 0
        periodLabel = c.str(.periodLabel) ?? PeriodLabel.of(period)
        clock = c.str(.clock); team = c.str(.team) ?? ""; kind = c.str(.kind) ?? ""; text = c.str(.text) ?? ""
        away = c.int(.away); home = c.int(.home)
    }
}

struct DriveTracker: Equatable, Sendable, Decodable {
    var driveID: String
    var team: String
    /// ESPN yard line numbers measured from the home goal line, as in the sheet payload.
    var startYardLine: Int?
    var currentYardLine: Int?
    var plays: Int
    var yards: Int
    var elapsed: String?

    private enum CodingKeys: String, CodingKey {
        case team, plays, yards, elapsed
        case driveID = "drive_id", startYardLine = "start_yl", currentYardLine = "cur_yl"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        guard let id = c.str(.driveID) else { throw DecodingError.dataCorruptedError(forKey: .driveID, in: c, debugDescription: "tracker") }
        driveID = id; team = c.str(.team) ?? ""
        startYardLine = c.int(.startYardLine); currentYardLine = c.int(.currentYardLine)
        plays = c.int(.plays) ?? 0; yards = c.int(.yards) ?? 0; elapsed = c.str(.elapsed)
    }
}

struct WinProbPoint: Equatable, Sendable, Decodable {
    /// Home win probability, 0...1.
    var home: Double
    var playID: String?
    /// Seconds of game time elapsed.
    var elapsed: Int?

    private enum CodingKeys: String, CodingKey { case p, pid, t }

    init(home: Double, playID: String? = nil, elapsed: Int? = nil) { self.home = home; self.playID = playID; self.elapsed = elapsed }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        guard let p = c.dbl(.p), (0...1).contains(p) else { throw DecodingError.dataCorruptedError(forKey: .p, in: c, debugDescription: "wp point") }
        home = p; playID = c.str(.pid); elapsed = c.int(.t)
    }
}

struct QuarterMark: Equatable, Sendable, Decodable {
    var label: String
    /// Index into the points array where the period starts.
    var index: Int

    init(from decoder: Decoder) throws {
        var u = try decoder.unkeyedContainer()
        label = try u.decode(String.self)
        index = (try? u.decode(Int.self)) ?? 0
    }
}

struct WinProbSeries: Equatable, Sendable, Decodable {
    var points: [WinProbPoint]
    var quarters: [QuarterMark]
    var overtimeStart: Int?

    private enum CodingKeys: String, CodingKey { case points, quarters, otAt = "ot_at" }

    init(points: [WinProbPoint] = [], quarters: [QuarterMark] = [], overtimeStart: Int? = nil) {
        self.points = points; self.quarters = quarters; self.overtimeStart = overtimeStart
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        points = c.list(.points); quarters = c.list(.quarters); overtimeStart = c.int(.otAt)
    }
}

/// One team-stat row: label, away value, home value.
struct BoxRow: Equatable, Sendable, Decodable, Identifiable {
    var label: String
    var away: String
    var home: String
    var id: String { label }

    init(label: String, away: String, home: String) { self.label = label; self.away = away; self.home = home }

    init(from decoder: Decoder) throws {
        var u = try decoder.unkeyedContainer()
        label = try u.decode(String.self)
        away = (try? u.decode(String.self)) ?? ""
        home = (try? u.decode(String.self)) ?? ""
    }
}

struct Leader: Equatable, Sendable, Decodable, Identifiable {
    var key: String
    var label: String
    var name: String
    var position: String?
    var value: Double?
    var line: String?
    var id: String { key + name }

    private enum CodingKeys: String, CodingKey { case key, label, name, pos, value, line }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        guard let name = c.str(.name) else { throw DecodingError.dataCorruptedError(forKey: .name, in: c, debugDescription: "leader") }
        self.name = name
        key = c.str(.key) ?? ""; label = c.str(.label) ?? ""; position = c.str(.pos); value = c.dbl(.value); line = c.str(.line)
    }
}

struct SheetTeams: Equatable, Sendable, Decodable {
    var away: Team?
    var home: Team?

    private enum CodingKeys: String, CodingKey { case away, home }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        away = c.obj(.away); home = c.obj(.home)
    }
}

struct SheetLines: Equatable, Sendable, Decodable {
    var away: [Int?]
    var home: [Int?]

    private enum CodingKeys: String, CodingKey { case away, home }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        away = ((try? c.decodeIfPresent([Int?].self, forKey: .away)) ?? nil) ?? []
        home = ((try? c.decodeIfPresent([Int?].self, forKey: .home)) ?? nil) ?? []
    }
}

struct SheetLeaders: Equatable, Sendable, Decodable {
    var away: [Leader]
    var home: [Leader]

    private enum CodingKeys: String, CodingKey { case away, home }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        away = c.list(.away); home = c.list(.home)
    }
}

/// /api/nfl/game?id=: drives, plays, win probability, scoring, team stats and leaders for one game.
struct GameSheet: Equatable, Sendable, Decodable {
    var id: String
    var fetchedAt: Date?
    var stale: Bool
    var state: GameState
    var status: String?
    var period: Int
    var periodLabel: String
    var clock: String?
    var lastPlayWallclock: Date?
    var teams: SheetTeams
    var linescores: SheetLines
    var overtimePeriods: Int
    var result: GameResult?
    var scoring: [ScoringPlay]
    var drives: [Drive]
    var currentDriveID: String?
    var tracker: DriveTracker?
    var winProb: WinProbSeries
    var box: [BoxRow]
    var leaders: SheetLeaders
    var warnings: [String]

    private enum CodingKeys: String, CodingKey {
        case ok, id, stale, state, status, period, periodLabel, clock, teams, linescores, result, scoring, drives, tracker
        case winprob, box, leaders, warnings
        case fetchedAt = "fetched_at", lastPlayWallclock = "last_play_wallclock", overtimePeriods = "ot_periods"
        case currentDriveID = "current_drive_id"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        guard c.flag(.ok) ?? true else { throw DecodingError.dataCorruptedError(forKey: .id, in: c, debugDescription: "ok is false") }
        guard let id = c.str(.id), !id.isEmpty else { throw DecodingError.dataCorruptedError(forKey: .id, in: c, debugDescription: "game id") }
        self.id = id
        fetchedAt = ISODate.parse(c.str(.fetchedAt))
        stale = c.flag(.stale) ?? false
        state = GameState(c.str(.state))
        status = c.str(.status)
        period = c.int(.period) ?? 0
        periodLabel = c.str(.periodLabel) ?? PeriodLabel.of(period)
        clock = c.str(.clock)
        lastPlayWallclock = ISODate.parse(c.str(.lastPlayWallclock))
        teams = c.obj(.teams) ?? SheetTeams.empty
        linescores = c.obj(.linescores) ?? SheetLines.empty
        overtimePeriods = c.int(.overtimePeriods) ?? 0
        result = c.str(.result).flatMap(GameResult.init(rawValue:))
        scoring = c.list(.scoring); drives = c.list(.drives)
        currentDriveID = c.str(.currentDriveID); tracker = c.obj(.tracker)
        winProb = c.obj(.winprob) ?? WinProbSeries()
        box = c.list(.box); leaders = c.obj(.leaders) ?? SheetLeaders.empty
        warnings = c.strings(.warnings)
    }

    var liveDrive: Drive? { drives.first { $0.live } }
}

private extension Decodable {
    static var empty: Self { try! JSONDecoder().decode(Self.self, from: Data("{}".utf8)) }
}
