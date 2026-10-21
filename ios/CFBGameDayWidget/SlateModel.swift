import Foundation

// What the widget knows about the board: the week's snapshot (games.json) for the slate and
// /api/live for scores, the same two feeds the page reads. By rule it never carries odds or the
// implied score: a widget row is teams, score or kickoff, TV, and the snapshot's kickoff forecast.

enum SlateFilter: String, CaseIterable, Sendable {
    case all, ranked, rivalry
}

struct SlateTeam: Decodable, Hashable, Sendable {
    var id: String?
    var abbr: String?
    var rank: Int?
    var color: String?
    var alt: String?
    var score: Int?
    var winner: Bool?

    init(id: String? = nil, abbr: String?, rank: Int? = nil, color: String? = nil, alt: String? = nil,
         score: Int? = nil, winner: Bool? = nil) {
        self.id = id; self.abbr = abbr; self.rank = rank; self.color = color; self.alt = alt
        self.score = score; self.winner = winner
    }

    private enum CodingKeys: String, CodingKey { case id, abbr, rank, color, alt, score, winner }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = c.flexString(.id)
        abbr = try? c.decodeIfPresent(String.self, forKey: .abbr)
        rank = c.flexInt(.rank)
        color = try? c.decodeIfPresent(String.self, forKey: .color)
        alt = try? c.decodeIfPresent(String.self, forKey: .alt)
        score = c.flexInt(.score)                  // a string in games.json, a number in /api/live
        winner = try? c.decodeIfPresent(Bool.self, forKey: .winner)
    }

    /// ESPN ranks unranked teams 99.
    var ranked: Bool { (1...25).contains(rank ?? 99) }
}

struct SlateGame: Decodable, Sendable {
    var id: String
    var date: Date?
    var neutral = false
    var tbd = false
    var indoor = false
    var networks: [String] = []
    var gameState: String?       // pre / in / post when the snapshot was built
    var statusShort: String?
    var rivalry: String?
    var temp: Double?
    var wxEmoji: String?
    var home: SlateTeam
    var away: SlateTeam

    private enum CodingKeys: String, CodingKey {
        case id, date, neutral, indoor, networks, broadcasts, gameState, statusShort, rivalry, temp, home, away
        case tbd = "time_tbd", wxEmoji = "wx_emoji"
    }

    init(id: String, date: Date?, home: SlateTeam, away: SlateTeam) {
        self.id = id; self.date = date; self.home = home; self.away = away
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        guard let id = c.flexString(.id) else {
            throw DecodingError.dataCorruptedError(forKey: .id, in: c, debugDescription: "game without an id")
        }
        self.id = id
        date = (try? c.decodeIfPresent(String.self, forKey: .date)).flatMap(Slate.parseDate)
        neutral = (try? c.decodeIfPresent(Bool.self, forKey: .neutral)) ?? false
        tbd = (try? c.decodeIfPresent(Bool.self, forKey: .tbd)) ?? false
        indoor = (try? c.decodeIfPresent(Bool.self, forKey: .indoor)) ?? false
        networks = (try? c.decodeIfPresent([String].self, forKey: .networks))
            ?? (try? c.decodeIfPresent([String].self, forKey: .broadcasts)) ?? []
        gameState = try? c.decodeIfPresent(String.self, forKey: .gameState)
        statusShort = try? c.decodeIfPresent(String.self, forKey: .statusShort)
        rivalry = try? c.decodeIfPresent(String.self, forKey: .rivalry)
        temp = try? c.decodeIfPresent(Double.self, forKey: .temp)
        wxEmoji = try? c.decodeIfPresent(String.self, forKey: .wxEmoji)
        home = (try? c.decode(SlateTeam.self, forKey: .home)) ?? SlateTeam(abbr: nil)
        away = (try? c.decode(SlateTeam.self, forKey: .away)) ?? SlateTeam(abbr: nil)
    }
}

/// One game from /api/live (server.py `live_payload`).
struct LiveGame: Decodable, Sendable {
    var id: String
    var state: String?           // pre / in / post
    var statusShort: String?
    var completed: Bool?
    var home: SlateTeam?
    var away: SlateTeam?

    init(id: String, state: String?, statusShort: String?, completed: Bool?, home: SlateTeam?, away: SlateTeam?) {
        self.id = id; self.state = state; self.statusShort = statusShort; self.completed = completed
        self.home = home; self.away = away
    }
}

struct Snapshot: Decodable, Sendable {
    var games: [SlateGame]

    private enum CodingKeys: String, CodingKey { case games }

    init(games: [SlateGame]) { self.games = games }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        games = try c.decode([Lossy<SlateGame>].self, forKey: .games).compactMap(\.value)   // one bad game costs one row
    }
}

struct LiveFeed: Decodable, Sendable {
    var games: [LiveGame]

    private enum CodingKeys: String, CodingKey { case games }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        games = try c.decode([Lossy<LiveGame>].self, forKey: .games).compactMap(\.value)
    }
}

private struct Lossy<T: Decodable>: Decodable {
    let value: T?
    init(from decoder: Decoder) throws { value = try? T(from: decoder) }
}

private extension KeyedDecodingContainer {
    func flexInt(_ key: Key) -> Int? {
        if let i = try? decodeIfPresent(Int.self, forKey: key) { return i }
        if let s = try? decodeIfPresent(String.self, forKey: key) { return Int(s) }
        if let d = try? decodeIfPresent(Double.self, forKey: key) { return Int(d) }
        return nil
    }

    func flexString(_ key: Key) -> String? {
        if let s = try? decodeIfPresent(String.self, forKey: key) { return s }
        if let i = try? decodeIfPresent(Int.self, forKey: key) { return String(i) }
        return nil
    }
}

struct SlateRow: Identifiable, Hashable, Sendable {
    enum Phase: Int, Sendable {
        case live, upcoming, unknown, final   // sort order; unknown = kicked off but no live data yet
    }
    var id: String
    var away: SlateTeam
    var home: SlateTeam
    var neutral: Bool
    var phase: Phase
    var showScore: Bool
    var status: String           // "8:12 - 2nd", "Final/OT", "7:30 PM", "TBA", "Postponed"
    var kickoff: Date?
    var network: String?
    var rivalry: Bool
    var weather: String?         // "☀️ 52°", upcoming outdoor games only: the snapshot's kickoff-hour forecast

    var ranked: Bool { home.ranked || away.ranked }
    /// The trailing side of a final, dimmed on the widget. From the score: the snapshot has no winner flag.
    var awayLost: Bool { trails(away, home) }
    var homeLost: Bool { trails(home, away) }
    private func trails(_ a: SlateTeam, _ b: SlateTeam) -> Bool {
        phase == .final && showScore && (a.score ?? 0) < (b.score ?? 0)
    }
    var link: URL? {
        showScore ? URL(string: "cfbgameday://game/\(id)") : nil   // the game sheet needs a started game
    }
}

struct SlateDay: Sendable {
    var date: Date               // start of the Central day
    var isToday: Bool
    var rows: [SlateRow]         // live, upcoming, unknown, final
    var liveCount: Int
}

enum Slate {
    static let chicago = TimeZone(identifier: "America/Chicago")!
    static let eastern = TimeZone(identifier: "America/New_York")!

    static func calendar(_ tz: TimeZone) -> Calendar {
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = tz
        return cal
    }

    /// ESPN writes "2026-10-24T01:00Z" (no seconds), which ISO8601DateFormatter rejects.
    static func parseDate(_ s: String) -> Date? {
        for format in ["yyyy-MM-dd'T'HH:mmXXXXX", "yyyy-MM-dd'T'HH:mm:ssXXXXX", "yyyy-MM-dd'T'HH:mm:ss.SSSXXXXX"] {
            let f = DateFormatter()
            f.locale = Locale(identifier: "en_US_POSIX")
            f.dateFormat = format
            if let d = f.date(from: s) { return d }
        }
        return nil
    }

    static func format(_ date: Date, _ pattern: String, _ tz: TimeZone = chicago) -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = tz
        f.dateFormat = pattern
        return f.string(from: date)
    }

    static func keep(_ g: SlateGame, _ filter: SlateFilter) -> Bool {
        switch filter {
        case .all: true
        case .ranked: g.home.ranked || g.away.ranked
        case .rivalry: g.rivalry != nil
        }
    }

    static func row(_ g: SlateGame, live: LiveGame?, now: Date) -> SlateRow {
        var home = g.home, away = g.away
        let kick = g.tbd ? "TBA" : g.date.map { format($0, "h:mm a") } ?? "TBA"
        var phase = SlateRow.Phase.unknown
        var showScore = false
        var status = kick
        if let live {
            if let h = live.home { home.score = h.score; home.winner = h.winner }
            if let a = live.away { away.score = a.score; away.winner = a.winner }
            switch live.state {
            case "in":
                phase = .live; showScore = true; status = live.statusShort ?? "Live"
            case "post":
                // Postponed and canceled games are "post" too, with no score worth showing.
                phase = .final; showScore = live.completed ?? false; status = live.statusShort ?? "Final"
            default:
                phase = .upcoming
            }
        } else if g.gameState == "post" {
            phase = .final; status = g.statusShort ?? "Final"
            showScore = status.lowercased().hasPrefix("final")
        } else if g.tbd || (g.date ?? .distantFuture) > now {
            phase = .upcoming
        }
        let weather: String? = {
            guard phase == .upcoming, !g.indoor, let t = g.temp else { return nil }
            return [g.wxEmoji, "\(Int(t.rounded()))°"].compactMap { $0 }.joined(separator: " ")
        }()
        return SlateRow(id: g.id, away: away, home: home, neutral: g.neutral, phase: phase, showScore: showScore,
                        status: status, kickoff: g.date, network: g.networks.first, rivalry: g.rivalry != nil,
                        weather: weather)
    }

    /// The day the widget shows: the one with a game in progress, else today, else the next day
    /// with games, else the last one (Sunday shows Saturday's finals until the new week lands).
    static func day(_ games: [SlateGame], live: [String: LiveGame], filter: SlateFilter, now: Date) -> SlateDay? {
        let cal = calendar(chicago)
        let rows = games.filter { keep($0, filter) }.compactMap { g -> (day: Date, row: SlateRow)? in
            guard let kick = g.date else { return nil }
            return (cal.startOfDay(for: kick), row(g, live: live[g.id], now: now))
        }
        guard !rows.isEmpty else { return nil }
        let byDay = Dictionary(grouping: rows, by: \.day)
        let today = cal.startOfDay(for: now)
        let key = rows.filter { $0.row.phase == .live }.map(\.day).min()
            ?? (byDay[today] != nil ? today : nil)
            ?? byDay.keys.filter { $0 > today }.min()
            ?? byDay.keys.max()!
        let dayRows = byDay[key, default: []].map(\.row).sorted(by: order)
        return SlateDay(date: key, isToday: key == today, rows: dayRows,
                        liveCount: dayRows.filter { $0.phase == .live }.count)
    }

    static func order(_ a: SlateRow, _ b: SlateRow) -> Bool {
        if a.phase != b.phase { return a.phase.rawValue < b.phase.rawValue }
        let ka = a.kickoff ?? .distantFuture, kb = b.kickoff ?? .distantFuture
        if ka != kb { return a.phase == .final ? ka > kb : ka < kb }   // finals: latest first
        if a.ranked != b.ranked { return a.ranked }
        return a.id < b.id
    }

    /// ESPN (Eastern) dates /api/live needs: games that may have kicked off on the day the widget
    /// would show, plus any that kicked off in the last 6 hours (a late game still on past midnight).
    /// Nothing to ask for before the first kickoff, and never the rest of the week's finals.
    static func liveDates(_ games: [SlateGame], now: Date) -> [String] {
        let cal = calendar(chicago)
        let shown = day(games, live: [:], filter: .all, now: now)?.date
        let keys = games.compactMap { g -> String? in
            guard let kick = g.date, g.gameState != "post", kick <= now.addingTimeInterval(15 * 60),
                  cal.startOfDay(for: kick) == shown || kick > now.addingTimeInterval(-6 * 3600) else { return nil }
            return format(kick, "yyyyMMdd", eastern)
        }
        return Set(keys).sorted()
    }

    /// When WidgetKit should ask again: every 10 minutes while games are on, just after the next
    /// kickoff otherwise, and at the next Central midnight so the day rolls over.
    static func nextRefresh(_ day: SlateDay?, games: [SlateGame], filter: SlateFilter, now: Date) -> Date {
        if let day, day.rows.contains(where: { $0.phase == .live || $0.phase == .unknown }) {
            return now.addingTimeInterval(10 * 60)
        }
        var next = now.addingTimeInterval(3 * 3600)
        if let kick = games.filter({ keep($0, filter) && !$0.tbd }).compactMap(\.date).filter({ $0 > now }).min() {
            next = min(next, max(kick.addingTimeInterval(2 * 60), now.addingTimeInterval(5 * 60)))
        }
        let cal = calendar(chicago)
        if let midnight = cal.date(byAdding: .day, value: 1, to: cal.startOfDay(for: now)) {
            next = min(next, midnight.addingTimeInterval(60))
        }
        return next
    }
}

/// Network and cache. The widget's last good copy lives in its own Caches directory, so a
/// failed refresh shows the previous board marked offline instead of an empty widget.
enum SlateStore {
    static let board = URL(string: "https://cfbgameday.app")!

    struct Loaded: Sendable {
        var games: [SlateGame]
        var live: [String: LiveGame]
        var updated: Date?
        var offline: Bool
    }

    static func load(now: Date = .now, cachedOnly: Bool = false) async -> Loaded {
        var offline = false
        var updated: Date? = now
        guard let snapshot = await fetch(board.appending(path: "games.json"), cache: "games.json", as: Snapshot.self,
                                         cachedOnly: cachedOnly, offline: &offline, updated: &updated) else {
            return Loaded(games: [], live: [:], updated: nil, offline: true)
        }
        var live: [String: LiveGame] = [:]
        let dates = Slate.liveDates(snapshot.games, now: now)
        if !dates.isEmpty {
            var url = URLComponents(url: board.appending(path: "api/live"), resolvingAgainstBaseURL: false)!
            url.queryItems = [URLQueryItem(name: "dates", value: dates.joined(separator: ","))]
            if let feed = await fetch(url.url!, cache: "live.json", as: LiveFeed.self,
                                      cachedOnly: cachedOnly, offline: &offline, updated: &updated) {
                live = Dictionary(feed.games.map { ($0.id, $0) }, uniquingKeysWith: { a, _ in a })
            }
        }
        return Loaded(games: snapshot.games, live: live, updated: updated, offline: offline)
    }

    private static func fetch<T: Decodable>(_ url: URL, cache name: String, as type: T.Type, cachedOnly: Bool,
                                            offline: inout Bool, updated: inout Date?) async -> T? {
        let file = cacheDir?.appending(path: name)
        if !cachedOnly {
            var request = URLRequest(url: url, timeoutInterval: 10)
            request.setValue("CFBGameDayWidget", forHTTPHeaderField: "User-Agent")
            if let reply = try? await URLSession.shared.data(for: request),
               (reply.1 as? HTTPURLResponse)?.statusCode == 200,
               let value = try? JSONDecoder().decode(T.self, from: reply.0) {
                if let file { try? reply.0.write(to: file, options: .atomic) }
                return value
            }
        }
        guard let file, let data = try? Data(contentsOf: file),
              let value = try? JSONDecoder().decode(T.self, from: data) else { return nil }
        if !cachedOnly { offline = true }
        let saved = (try? file.resourceValues(forKeys: [.contentModificationDateKey]))?.contentModificationDate
        if let saved { updated = min(updated ?? saved, saved) }
        return value
    }

    private static var cacheDir: URL? {
        FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask).first
    }
}
