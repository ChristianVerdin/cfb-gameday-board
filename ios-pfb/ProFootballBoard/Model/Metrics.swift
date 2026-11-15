import Foundation

/// One side of a team's nflverse season line. `proe` exists on offence only.
struct MetricSide: Equatable, Sendable, Decodable {
    var epa: Double?
    var epaRank: Int?
    var successRate: Double?
    var successRank: Int?
    var proe: Double?
    var proeRank: Int?
    var plays: Int?

    private enum CodingKeys: String, CodingKey {
        case epa, sr, proe, plays
        case epaRank = "epa_rank", successRank = "sr_rank", proeRank = "proe_rank"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        epa = c.dbl(.epa); epaRank = c.int(.epaRank); successRate = c.dbl(.sr); successRank = c.int(.successRank)
        proe = c.dbl(.proe); proeRank = c.int(.proeRank); plays = c.int(.plays)
    }
}

struct TeamMetrics: Equatable, Sendable, Decodable {
    var offense: MetricSide?
    var defense: MetricSide?
    var games: Int?
    var smallSample: Bool

    private enum CodingKeys: String, CodingKey {
        case off, def, games
        case smallSample = "small_sample"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        offense = c.obj(.off); defense = c.obj(.def); games = c.int(.games)
        smallSample = c.flag(.smallSample) ?? false
    }
}

struct Metrics: Equatable, Sendable, Decodable {
    var generatedAt: Date?
    var season: Int?
    var throughWeek: Int?
    var leagueEPAPerPlay: Double?
    var leagueSuccessRate: Double?
    var license: String?
    var teams: [String: TeamMetrics]

    private enum CodingKeys: String, CodingKey {
        case season, source, league, teams
        case generatedAt = "generated_at", throughWeek = "through_week"
    }

    private struct Source: Decodable {
        var license: String?
        private enum K: String, CodingKey { case license }
        init(from decoder: Decoder) throws { license = try decoder.container(keyedBy: K.self).str(.license) }
    }

    private struct League: Decodable {
        var epa: Double?
        var sr: Double?
        private enum K: String, CodingKey { case epa = "epa_play", sr }
        init(from decoder: Decoder) throws {
            let c = try decoder.container(keyedBy: K.self)
            epa = c.dbl(.epa); sr = c.dbl(.sr)
        }
    }

    private struct AnyKey: CodingKey {
        var stringValue: String
        var intValue: Int? { nil }
        init?(stringValue: String) { self.stringValue = stringValue }
        init?(intValue: Int) { nil }
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        generatedAt = ISODate.parse(c.str(.generatedAt))
        season = c.int(.season); throughWeek = c.int(.throughWeek)
        let league: League? = c.obj(.league)
        leagueEPAPerPlay = league?.epa; leagueSuccessRate = league?.sr
        license = c.obj(.source, as: Source.self)?.license
        var out: [String: TeamMetrics] = [:]
        if let nested = try? c.nestedContainer(keyedBy: AnyKey.self, forKey: .teams) {
            for key in nested.allKeys {
                if let m = try? nested.decode(TeamMetrics.self, forKey: key) { out[key.stringValue] = m }
            }
        }
        teams = out
    }
}
