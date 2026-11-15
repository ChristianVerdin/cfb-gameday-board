import Foundation

struct WidgetTeam: Codable, Equatable, Sendable {
    var abbr: String
    var name: String
    var score: Int?
    var record: String?
    var color: String?
    var alt: String?

    var chip: ChipColors { TeamColors.chip(color: color, alt: alt) }

    static let tbd = WidgetTeam(abbr: "TBD", name: "To be determined")

    init(abbr: String, name: String, score: Int? = nil, record: String? = nil, color: String? = nil, alt: String? = nil) {
        self.abbr = abbr; self.name = name; self.score = score; self.record = record; self.color = color; self.alt = alt
    }

    init(_ team: Team?) {
        guard let team else { self = .tbd; return }
        self.init(abbr: team.abbr, name: team.name, score: team.score, record: team.record?.text, color: team.color, alt: team.alt)
    }
}

/// The few fields a widget needs from a `BoardGame`; this is also what the on-disk cache holds.
struct WidgetGame: Codable, Equatable, Sendable, Identifiable {
    var id: String
    var state: String
    var away: WidgetTeam
    var home: WidgetTeam
    /// "Q4 0:02", "Final", "Final/OT" or the Central kickoff time.
    var status: String
    var tv: String
    var situation: String?
    var possession: String?
    var redZone: Bool
    var date: Date?
    var timeTBD: Bool

    var isLive: Bool { state == GameState.in.rawValue }
    var isUpcoming: Bool { state == GameState.pre.rawValue }
    var isFinal: Bool { state == GameState.post.rawValue }
    var started: Bool { !isUpcoming }
    var matchup: String { "\(away.abbr) @ \(home.abbr)" }

    func involves(_ abbr: String) -> Bool { away.abbr == abbr || home.abbr == abbr }

    init(_ g: BoardGame) {
        id = g.id
        state = g.state.rawValue
        away = WidgetTeam(g.away)
        home = WidgetTeam(g.home)
        tv = g.tv
        date = g.date
        timeTBD = g.timeTBD
        possession = g.isLive ? g.situation?.possession?.rawValue : nil
        redZone = g.isLive && (g.situation?.isRedZone ?? false)
        situation = g.isLive ? Self.situationText(g.situation) : nil
        switch g.state {
        case .in:
            let live = g.statusShort.isEmpty ? [g.periodLabel, g.clock].filter { !$0.isEmpty }.joined(separator: " ") : g.statusShort
            status = live.isEmpty ? "Live" : live
        case .post:
            status = g.statusShort.isEmpty ? (g.ot ? "Final/OT" : "Final") : g.statusShort
        case .pre:
            status = g.placeholder ? (g.flexNote ?? "TBD") : g.kickoffText
        }
    }

    private static func situationText(_ s: Situation?) -> String? {
        guard let s, !s.stoppage, let text = s.text, !text.isEmpty else { return nil }
        if let yard = s.yardText, !yard.isEmpty { return "\(text) at \(yard)" }
        return text
    }
}

enum WidgetScope: Equatable, Sendable {
    case all, live, team(String)
}

struct WidgetSlate: Codable, Equatable, Sendable {
    var fetchedAt: Date
    var weekLabel: String?
    /// Board order: live, then upcoming by kickoff, then finals.
    var games: [WidgetGame]

    init(fetchedAt: Date, weekLabel: String?, games: [WidgetGame]) {
        self.fetchedAt = fetchedAt; self.weekLabel = weekLabel; self.games = games
    }

    init(live: LivePayload?, snapshot: Snapshot?, fetchedAt: Date) {
        let games = BoardGame.sorted(BoardGame.build(live: live, snapshot: snapshot))
        self.init(fetchedAt: fetchedAt, weekLabel: live?.week.label ?? snapshot?.week.label, games: games.map(WidgetGame.init))
    }

    func games(for scope: WidgetScope) -> [WidgetGame] {
        switch scope {
        case .all: games
        case .live: games.filter(\.isLive)
        case .team(let abbr): games.filter { $0.involves(abbr) }
        }
    }

    var liveCount: Int { games.filter(\.isLive).count }

    /// The first game that has not kicked off yet, for the empty states.
    func nextUp(after now: Date) -> WidgetGame? {
        games.filter { $0.isUpcoming && !$0.timeTBD && ($0.date ?? .distantPast) > now }
            .min { ($0.date ?? .distantFuture) < ($1.date ?? .distantFuture) }
    }

    static let fastRefresh: TimeInterval = 300
    static let longestWait: TimeInterval = 7200
    static let kickoffLead: TimeInterval = 1800

    /// Every 5 minutes while a game is live or kicks within an hour; otherwise 30 minutes before the next kickoff, at most 2 hours out.
    func nextRefresh(for scope: WidgetScope, now: Date) -> Date {
        let relevant: [WidgetGame]
        if case .live = scope { relevant = games } else { relevant = games(for: scope) }
        if relevant.contains(where: \.isLive) { return now + Self.fastRefresh }
        let kickoffs = relevant.filter { $0.isUpcoming && !$0.timeTBD }.compactMap(\.date)
        if kickoffs.contains(where: { $0.timeIntervalSince(now) <= 3600 && $0.timeIntervalSince(now) >= -10800 }) {
            return now + Self.fastRefresh
        }
        guard let next = kickoffs.filter({ $0 > now }).min() else { return now + Self.longestWait }
        let wait = min(max(next.timeIntervalSince(now) - Self.kickoffLead, Self.fastRefresh), Self.longestWait)
        return now + wait
    }
}

/// The last good slate, kept in the widget's Caches directory.
struct SlateCache: Sendable {
    var url: URL

    init(url: URL = SlateCache.defaultURL) { self.url = url }

    static var defaultURL: URL {
        URL.cachesDirectory.appending(path: "pfb-widget-slate.json")
    }

    func load() -> WidgetSlate? {
        guard let data = try? Data(contentsOf: url) else { return nil }
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return try? decoder.decode(WidgetSlate.self, from: data)
    }

    func save(_ slate: WidgetSlate) {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        guard let data = try? encoder.encode(slate) else { return }
        try? FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        try? data.write(to: url, options: .atomic)
    }
}

struct SlateLoader: Sendable {
    var api: any BoardAPI = APIClient.shared
    var cache = SlateCache()

    /// A fresh slate, or the cached one flagged offline when the live scoreboard cannot be reached.
    func load(now: Date = Date()) async -> (slate: WidgetSlate?, offline: Bool) {
        async let snapshot = try? api.snapshot()
        async let live = try? api.live(season: nil, week: nil)
        let (snap, scoreboard) = await (snapshot, live)
        if let scoreboard {
            let slate = WidgetSlate(live: scoreboard, snapshot: snap, fetchedAt: now)
            cache.save(slate)
            return (slate, false)
        }
        if let cached = cache.load() { return (cached, true) }
        if let snap { return (WidgetSlate(live: nil, snapshot: snap, fetchedAt: now), true) }
        return (nil, true)
    }
}
