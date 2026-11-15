import Foundation

enum GameState: String, Equatable, Sendable {
    case pre, `in`, post
    init(_ raw: String?) { self = GameState(rawValue: raw ?? "") ?? .pre }
}

enum GameResult: String, Equatable, Sendable {
    case home, away, tie
}

enum Possession: String, Equatable, Sendable {
    case home, away
}

struct LastPlay: Equatable, Sendable, Decodable {
    var id: String
    var text: String
    var type: String?

    private enum CodingKeys: String, CodingKey { case id, text, type }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        guard let id = c.str(.id) else { throw DecodingError.dataCorruptedError(forKey: .id, in: c, debugDescription: "play id") }
        self.id = id; text = c.str(.text) ?? ""; type = c.str(.type)
    }
}

struct Situation: Equatable, Sendable, Decodable {
    var text: String?
    var down: Int?
    var distance: Int?
    var stoppage: Bool
    var possession: Possession?
    var possessionAbbr: String?
    var yardText: String?
    /// Yards to the goal line the offence is attacking.
    var yl100: Int?
    var isRedZone: Bool
    var goalToGo: Bool
    var lastPlay: LastPlay?

    init(text: String? = nil, down: Int? = nil, distance: Int? = nil, stoppage: Bool = false, possession: Possession? = nil,
         possessionAbbr: String? = nil, yardText: String? = nil, yl100: Int? = nil, isRedZone: Bool = false,
         goalToGo: Bool = false, lastPlay: LastPlay? = nil) {
        self.text = text; self.down = down; self.distance = distance; self.stoppage = stoppage; self.possession = possession
        self.possessionAbbr = possessionAbbr; self.yardText = yardText; self.yl100 = yl100; self.isRedZone = isRedZone
        self.goalToGo = goalToGo; self.lastPlay = lastPlay
    }

    private enum CodingKeys: String, CodingKey {
        case text, down, distance, stoppage, possession
        case possessionAbbr = "possession_abbr", yardText = "yard_text", yl100
        case isRedZone = "is_red_zone", goalToGo = "goal_to_go", lastPlay = "last_play"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        text = c.str(.text)
        down = c.int(.down)
        distance = c.int(.distance)
        stoppage = c.flag(.stoppage) ?? false
        possession = c.str(.possession).flatMap(Possession.init(rawValue:))
        possessionAbbr = c.str(.possessionAbbr)
        yardText = c.str(.yardText)
        yl100 = c.int(.yl100)
        isRedZone = c.flag(.isRedZone) ?? false
        goalToGo = c.flag(.goalToGo) ?? false
        lastPlay = c.obj(.lastPlay)
    }
}

struct WinProbability: Equatable, Sendable, Decodable {
    /// Home win probability, 0...1.
    var home: Double

    private enum CodingKeys: String, CodingKey { case home }

    init(home: Double) { self.home = home }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        guard let h = c.dbl(.home), (0...1).contains(h) else {
            throw DecodingError.dataCorruptedError(forKey: .home, in: c, debugDescription: "wp")
        }
        home = h
    }
}

struct Desk: Equatable, Sendable, Decodable {
    var score: Int
    var why: [String]

    private enum CodingKeys: String, CodingKey { case score, why }

    init(score: Int, why: [String] = []) { self.score = score; self.why = why }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        guard let s = c.int(.score) else { throw DecodingError.dataCorruptedError(forKey: .score, in: c, debugDescription: "desk") }
        score = s; why = c.strings(.why)
    }
}

struct LiveGame: Equatable, Sendable, Decodable {
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
    var timeTBD: Bool?
    var flexNote: String?
    var neutral: Bool?
    var placeholder: Bool
    var venueName: String?
    var broadcasts: [String]
    var away: Team?
    var home: Team?
    var situation: Situation?
    var wp: WinProbability?
    var desk: Desk?

    private enum CodingKeys: String, CodingKey {
        case id, state, status, statusShort, period, periodLabel, clock, completed, ot, result, date, neutral, placeholder
        case broadcasts, away, home, situation, wp, desk
        case clockSeconds = "clock_s", timeTBD = "time_tbd", flexNote = "flex_note", venueName = "venue_name"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        guard let id = c.str(.id) else { throw DecodingError.dataCorruptedError(forKey: .id, in: c, debugDescription: "game id") }
        self.id = id
        state = GameState(c.str(.state))
        status = c.str(.status) ?? ""
        statusShort = c.str(.statusShort) ?? ""
        period = c.int(.period) ?? 0
        periodLabel = c.str(.periodLabel) ?? PeriodLabel.of(c.int(.period))
        clock = c.str(.clock) ?? ""
        clockSeconds = c.int(.clockSeconds) ?? 0
        completed = c.flag(.completed) ?? (state == .post)
        ot = c.flag(.ot) ?? (period > 4)
        result = c.str(.result).flatMap(GameResult.init(rawValue:))
        date = ISODate.parse(c.str(.date))
        timeTBD = c.flag(.timeTBD)
        flexNote = c.str(.flexNote)
        neutral = c.flag(.neutral)
        placeholder = c.flag(.placeholder) ?? false
        venueName = c.str(.venueName)
        broadcasts = c.strings(.broadcasts)
        away = c.obj(.away)
        home = c.obj(.home)
        situation = c.obj(.situation)
        wp = c.obj(.wp)
        desk = c.obj(.desk)
    }
}

struct SeasonInfo: Equatable, Sendable, Decodable {
    var year: Int?
    /// 1 preseason, 2 regular season, 3 postseason.
    var type: Int?

    private enum CodingKeys: String, CodingKey { case year, type }

    init(year: Int? = nil, type: Int? = nil) { self.year = year; self.type = type }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        year = c.int(.year); type = c.int(.type)
    }
}

struct WeekInfo: Equatable, Sendable, Decodable {
    var number: Int?
    var label: String?
    var start: Date?
    var end: Date?

    private enum CodingKeys: String, CodingKey { case number, label, start, end }

    init(number: Int? = nil, label: String? = nil, start: Date? = nil, end: Date? = nil) {
        self.number = number; self.label = label; self.start = start; self.end = end
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        number = c.int(.number); label = c.str(.label)
        start = ISODate.parse(c.str(.start)); end = ISODate.parse(c.str(.end))
    }
}

struct LivePayload: Equatable, Sendable, Decodable {
    var ok: Bool
    var stale: Bool
    var fetchedAt: Date?
    var season: SeasonInfo
    var week: WeekInfo
    var teamsOnBye: [String]
    var warnings: [String]
    var games: [LiveGame]

    private enum CodingKeys: String, CodingKey {
        case ok, stale, season, week, warnings, games
        case fetchedAt = "fetched_at", teamsOnBye = "teams_on_bye"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        ok = c.flag(.ok) ?? true
        guard ok else { throw DecodingError.dataCorruptedError(forKey: .ok, in: c, debugDescription: "ok is false") }
        stale = c.flag(.stale) ?? false
        fetchedAt = ISODate.parse(c.str(.fetchedAt))
        season = c.obj(.season) ?? SeasonInfo()
        week = c.obj(.week) ?? WeekInfo()
        teamsOnBye = c.strings(.teamsOnBye)
        warnings = c.strings(.warnings)
        guard (try? c.decode([Lossy<LiveGame>].self, forKey: .games)) != nil else {
            throw DecodingError.dataCorruptedError(forKey: .games, in: c, debugDescription: "games is not an array")
        }
        games = c.list(.games)
    }
}
