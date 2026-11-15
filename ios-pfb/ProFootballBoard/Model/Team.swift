import Foundation

struct TeamRecord: Equatable, Sendable, Decodable {
    var wins: Int
    var losses: Int
    var ties: Int
    var text: String

    init(wins: Int, losses: Int, ties: Int = 0) {
        self.wins = wins; self.losses = losses; self.ties = ties
        text = Self.format(wins, losses, ties)
    }

    private enum CodingKeys: String, CodingKey { case w, l, t, text }

    init(from decoder: Decoder) throws {
        if let single = try? decoder.singleValueContainer(), let s = try? single.decode(String.self) {
            let p = s.split(separator: "-").compactMap { Int($0) }
            guard p.count >= 2 else { throw DecodingError.dataCorruptedError(in: single, debugDescription: "record") }
            wins = p[0]; losses = p[1]; ties = p.count > 2 ? p[2] : 0
            text = Self.format(wins, losses, ties)
            return
        }
        let c = try decoder.container(keyedBy: CodingKeys.self)
        guard let w = c.int(.w), let l = c.int(.l) else {
            throw DecodingError.dataCorruptedError(forKey: .w, in: c, debugDescription: "record")
        }
        wins = w; losses = l; ties = c.int(.t) ?? 0
        text = c.str(.text) ?? Self.format(w, l, ties)
    }

    private static func format(_ w: Int, _ l: Int, _ t: Int) -> String { "\(w)-\(l)" + (t > 0 ? "-\(t)" : "") }
}

/// A team as it appears in /api/nfl/live, /api/nfl/game and the snapshot; every field is optional on the wire.
struct Team: Equatable, Sendable, Decodable {
    var id: String
    var abbr: String
    var name: String
    var fullName: String?
    /// nflverse abbreviation (keys /nfl/metrics.json); differs from `abbr` for a few clubs.
    var nv: String?
    var color: String?
    var alt: String?
    var score: Int?
    var record: TeamRecord?
    var timeouts: Int?
    var linescores: [Int?]

    init(id: String = "", abbr: String, name: String = "", fullName: String? = nil, nv: String? = nil, color: String? = nil,
         alt: String? = nil, score: Int? = nil, record: TeamRecord? = nil, timeouts: Int? = nil, linescores: [Int?] = []) {
        self.id = id; self.abbr = abbr; self.name = name; self.fullName = fullName; self.nv = nv; self.color = color
        self.alt = alt; self.score = score; self.record = record; self.timeouts = timeouts; self.linescores = linescores
    }

    private enum CodingKeys: String, CodingKey { case id, abbr, nv, name, full, color, alt, score, record, timeouts, linescores }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        guard let abbr = c.str(.abbr), !abbr.isEmpty else {
            throw DecodingError.dataCorruptedError(forKey: .abbr, in: c, debugDescription: "team without an abbreviation")
        }
        self.abbr = abbr
        id = c.str(.id) ?? ""
        name = c.str(.name) ?? ""
        fullName = c.str(.full)
        nv = c.str(.nv)
        color = c.str(.color)
        alt = c.str(.alt)
        score = c.int(.score)          // "" in the snapshot, a number in /api/nfl/live
        record = c.obj(.record)
        timeouts = c.int(.timeouts)
        linescores = ((try? c.decodeIfPresent([Int?].self, forKey: .linescores)) ?? nil) ?? []
    }

    var displayName: String { fullName ?? name }
    var metricsKey: String { nv ?? abbr }
    var chip: ChipColors { TeamColors.chip(color: color, alt: alt) }

    /// Live values win over the snapshot's; names, colours and the full name fall back to the snapshot.
    func merged(over snap: Team?) -> Team {
        guard let snap else { return self }
        var out = self
        if out.name.isEmpty { out.name = snap.name }
        out.fullName = snap.fullName ?? fullName
        out.nv = snap.nv ?? nv
        out.color = snap.color ?? color
        out.alt = snap.alt ?? alt
        if let live = record, live.text != "0-0" || snap.record == nil { out.record = live } else { out.record = snap.record }
        if out.id.isEmpty { out.id = snap.id }
        return out
    }
}
