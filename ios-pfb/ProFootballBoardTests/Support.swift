import Foundation
import XCTest

private final class BundleToken {}

enum Fixture {
    static func data(_ name: String) throws -> Data {
        let url = try XCTUnwrap(Bundle(for: BundleToken.self).url(forResource: name, withExtension: "json"), "missing fixture \(name)")
        return try Data(contentsOf: url)
    }

    static func load<T: Decodable>(_ name: String, as type: T.Type = T.self) throws -> T {
        try JSONDecoder().decode(T.self, from: data(name))
    }

    static func decode<T: Decodable>(_ json: String, as type: T.Type = T.self) throws -> T {
        try JSONDecoder().decode(T.self, from: Data(json.utf8))
    }
}

func date(_ iso: String) -> Date { ISODate.parse(iso)! }

/// A BoardGame built from a minimal live payload.
func makeGame(id: String = "1", state: String = "pre", date iso: String? = nil, tbd: Bool = false, period: Int = 0,
              clockSeconds: Int = 0, desk: Int? = nil, away: String = "AAA", home: String = "BBB", extra: String = "") throws -> BoardGame {
    let when = iso.map { "\"date\":\"\($0)\"," } ?? ""
    let deskJSON = desk.map { "\"desk\":{\"score\":\($0),\"why\":[]}," } ?? ""
    let json = """
    {"id":"\(id)","state":"\(state)",\(when)\(deskJSON)"time_tbd":\(tbd),"period":\(period),"clock_s":\(clockSeconds)\(extra),
     "away":{"id":"1","abbr":"\(away)","score":0},"home":{"id":"2","abbr":"\(home)","score":0}}
    """
    let live: LiveGame = try Fixture.decode(json)
    return try XCTUnwrap(BoardGame.merged(snapshot: nil, live: live, seasonType: 2, weekLabel: nil))
}
