import Foundation

enum Roof: String, Equatable, Sendable {
    case open, dome, retractable, canopy
}

struct Venue: Equatable, Sendable, Decodable {
    var id: String?
    var name: String
    var city: String?
    var region: String?
    var country: String?
    var roof: Roof?
    var latitude: Double?
    var longitude: Double?
    var timeZone: String?

    private enum CodingKeys: String, CodingKey { case id, name, city, region, country, roof, lat, lon, tz }

    init(id: String? = nil, name: String, city: String? = nil, region: String? = nil, country: String? = nil, roof: Roof? = nil) {
        self.id = id; self.name = name; self.city = city; self.region = region; self.country = country; self.roof = roof
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        guard let name = c.str(.name) else { throw DecodingError.dataCorruptedError(forKey: .name, in: c, debugDescription: "venue name") }
        self.name = name
        id = c.str(.id); city = c.str(.city); region = c.str(.region); country = c.str(.country)
        roof = c.str(.roof).flatMap { Roof(rawValue: $0.lowercased()) }
        latitude = c.dbl(.lat); longitude = c.dbl(.lon); timeZone = c.str(.tz)
    }

    var place: String { [city, region].compactMap { $0 }.joined(separator: ", ") }
}

struct WeatherWindow: Equatable, Sendable, Decodable {
    var hours: Int?
    var maxGust: Double?
    var minTemp: Double?
    var maxPop: Double?
    var precipSum: Double?

    private enum CodingKeys: String, CodingKey {
        case hours
        case maxGust = "max_gust", minTemp = "min_temp", maxPop = "max_pop", precipSum = "precip_sum"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        hours = c.int(.hours); maxGust = c.dbl(.maxGust); minTemp = c.dbl(.minTemp)
        maxPop = c.dbl(.maxPop); precipSum = c.dbl(.precipSum)
    }
}

/// Kickoff-hour forecast from Open-Meteo. Temperatures in Fahrenheit, wind in mph, precipitation in inches.
struct Weather: Equatable, Sendable, Decodable {
    var fetchedAt: Date?
    var kickLocal: String?
    var temp: Double?
    var apparent: Double?
    var wind: Double?
    var gusts: Double?
    var windDirection: Double?
    var precipChance: Double?
    var precip: Double?
    var code: Int?
    var cloud: Double?
    var label: String?
    var roofNote: String?
    var flags: [String]
    var level: String?
    var notes: [String]
    var window: WeatherWindow?

    private enum CodingKeys: String, CodingKey {
        case temp, apparent, wind, gusts, winddir, pop, precip, code, cloud, label, flags, level, notes, window
        case fetchedAt = "fetched_at", kickLocal = "kick_local", roofNote = "roof_note"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        fetchedAt = ISODate.parse(c.str(.fetchedAt)); kickLocal = c.str(.kickLocal)
        temp = c.dbl(.temp); apparent = c.dbl(.apparent); wind = c.dbl(.wind); gusts = c.dbl(.gusts)
        windDirection = c.dbl(.winddir); precipChance = c.dbl(.pop); precip = c.dbl(.precip)
        code = c.int(.code); cloud = c.dbl(.cloud); label = c.str(.label); roofNote = c.str(.roofNote)
        flags = c.strings(.flags); level = c.str(.level); notes = c.strings(.notes); window = c.obj(.window)
    }

    var compass: String? { Weather.compass(windDirection) }

    static func compass(_ degrees: Double?) -> String? {
        guard let degrees, degrees.isFinite else { return nil }
        let points = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
        let d = degrees.truncatingRemainder(dividingBy: 360)
        return points[Int(((d + 360).truncatingRemainder(dividingBy: 360) / 22.5).rounded()) % 16]
    }
}

enum GameKind: String, Equatable, Sendable {
    case regular, playoff, allStar = "all_star"
}

struct SnapshotGame: Equatable, Sendable, Decodable {
    var id: String
    var name: String?
    var shortName: String?
    var date: Date?
    var timeTBD: Bool
    var flexNote: String?
    var kind: GameKind?
    var round: String?
    var weekLabel: String?
    var placeholder: Bool
    var neutral: Bool
    var broadcasts: [String]
    var streams: [String]
    var state: GameState?
    var statusShort: String?
    var venue: Venue?
    var away: Team?
    var home: Team?
    var weatherStatus: String?
    var weather: Weather?

    private enum CodingKeys: String, CodingKey {
        case id, name, date, kind, round, placeholder, neutral, broadcasts, streams, state, venue, away, home, wx
        case shortName, statusShort
        case timeTBD = "time_tbd", flexNote = "flex_note", weekLabel = "week_label", weatherStatus = "wx_status"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        guard let id = c.str(.id) else { throw DecodingError.dataCorruptedError(forKey: .id, in: c, debugDescription: "game id") }
        self.id = id
        name = c.str(.name); shortName = c.str(.shortName)
        date = ISODate.parse(c.str(.date))
        timeTBD = c.flag(.timeTBD) ?? false
        flexNote = c.str(.flexNote)
        kind = c.str(.kind).flatMap(GameKind.init(rawValue:))
        round = c.str(.round); weekLabel = c.str(.weekLabel)
        placeholder = c.flag(.placeholder) ?? false
        neutral = c.flag(.neutral) ?? false
        broadcasts = c.strings(.broadcasts); streams = c.strings(.streams)
        state = c.str(.state).map { GameState($0) }
        statusShort = c.str(.statusShort)
        venue = c.obj(.venue); away = c.obj(.away); home = c.obj(.home)
        weatherStatus = c.str(.weatherStatus); weather = c.obj(.wx)
    }
}

struct ByeTeam: Equatable, Sendable, Decodable {
    var id: String?
    var abbr: String
    var name: String?

    private enum CodingKeys: String, CodingKey { case id, abbr, name }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        guard let abbr = c.str(.abbr) else { throw DecodingError.dataCorruptedError(forKey: .abbr, in: c, debugDescription: "bye abbr") }
        self.abbr = abbr; id = c.str(.id); name = c.str(.name)
    }
}

/// The weekly snapshot (/nfl/games.json): venue, roof and kickoff weather for the week's games.
struct Snapshot: Equatable, Sendable, Decodable {
    var generatedAt: Date?
    var season: SeasonInfo
    var week: WeekInfo
    var teamsOnBye: [ByeTeam]
    var warnings: [String]
    var games: [SnapshotGame]

    private enum CodingKeys: String, CodingKey {
        case season, week, warnings, games
        case generatedAt = "generated_at", teamsOnBye = "teams_on_bye"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        guard (try? c.decode([Lossy<SnapshotGame>].self, forKey: .games)) != nil else {
            throw DecodingError.dataCorruptedError(forKey: .games, in: c, debugDescription: "games is not an array")
        }
        generatedAt = ISODate.parse(c.str(.generatedAt))
        season = c.obj(.season) ?? SeasonInfo()
        week = c.obj(.week) ?? WeekInfo()
        teamsOnBye = c.list(.teamsOnBye)
        warnings = c.strings(.warnings)
        games = c.list(.games)
    }

    var isPast: Bool { isPast(now: Date()) }

    func isPast(now: Date) -> Bool {
        guard let end = week.end else { return false }
        return now >= end
    }
}
