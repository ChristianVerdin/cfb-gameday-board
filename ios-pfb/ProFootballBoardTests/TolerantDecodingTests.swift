import XCTest

final class TolerantDecodingTests: XCTestCase {
    func testNumbersMayArriveAsStrings() throws {
        let game: LiveGame = try Fixture.decode("""
        {"id":401873055,"state":"in","period":"4","clock_s":"2","away":{"id":29,"abbr":"CAR","score":"17","timeouts":"2"},
         "home":{"id":"18","abbr":"NO","score":17.0},"situation":{"down":"2","distance":"10","yl100":"36","possession":"away"}}
        """)
        XCTAssertEqual(game.id, "401873055")
        XCTAssertEqual(game.period, 4)
        XCTAssertEqual(game.clockSeconds, 2)
        XCTAssertEqual(game.away?.score, 17)
        XCTAssertEqual(game.away?.timeouts, 2)
        XCTAssertEqual(game.home?.score, 17)
        XCTAssertEqual(game.situation?.down, 2)
        XCTAssertEqual(game.situation?.yl100, 36)
    }

    func testNullsAndUnknownKeysAreIgnored() throws {
        let game: LiveGame = try Fixture.decode("""
        {"id":"7","state":null,"status":null,"period":null,"clock":null,"away":null,"home":null,"situation":null,"wp":null,
         "desk":null,"broadcasts":null,"mystery":{"a":[1,2,3]},"result":"sideways"}
        """)
        XCTAssertEqual(game.state, .pre)
        XCTAssertEqual(game.period, 0)
        XCTAssertNil(game.away)
        XCTAssertNil(game.result)
        XCTAssertEqual(game.broadcasts, [])
    }

    func testBadItemsDropOnlyThemselves() throws {
        let payload: LivePayload = try Fixture.decode("""
        {"ok":true,"games":[{"id":"1","state":"pre"},{"state":"in"},"junk",null,{"id":"2","state":"post","away":{"abbr":"X"},"home":{"id":3}}]}
        """)
        XCTAssertEqual(payload.games.map(\.id), ["1", "2"])
        XCTAssertNotNil(payload.games[1].away)
        XCTAssertNil(payload.games[1].home, "a team without an abbreviation is dropped, not fatal")
    }

    func testPayloadWithoutGamesFails() {
        XCTAssertThrowsError(try Fixture.decode("{\"ok\":true}", as: LivePayload.self))
        XCTAssertThrowsError(try Fixture.decode("{\"ok\":false,\"games\":[]}", as: LivePayload.self))
        XCTAssertThrowsError(try Fixture.decode("{\"games\":{}}", as: Snapshot.self))
    }

    func testSheetSurvivesBrokenSections() throws {
        let sheet: GameSheet = try Fixture.decode("""
        {"id":"9","state":"in","period":2,"drives":[{"id":"d1","plays_list":[{"id":"p1","text":"x"},{"text":"no id"}]},{"oops":1}],
         "scoring":"none","winprob":{"points":[{"p":0.5},{"p":7},{"p":"0.6"}],"quarters":[["Q1",0],["bad"]]},
         "box":[["1st downs","3","4"],["Lonely"],5],"leaders":null,"teams":{"away":{"abbr":"A"}}}
        """)
        XCTAssertEqual(sheet.drives.count, 1)
        XCTAssertEqual(sheet.drives[0].playList.map(\.id), ["p1"])
        XCTAssertEqual(sheet.scoring, [])
        XCTAssertEqual(sheet.winProb.points.map(\.home), [0.5, 0.6])
        XCTAssertEqual(sheet.winProb.quarters.count, 2)
        XCTAssertEqual(sheet.box.count, 2)
        XCTAssertEqual(sheet.box[1], BoxRow(label: "Lonely", away: "", home: ""))
        XCTAssertEqual(sheet.leaders.home, [])
        XCTAssertEqual(sheet.teams.away?.abbr, "A")
        XCTAssertNil(sheet.teams.home)
    }

    func testRecordForms() throws {
        let t: Team = try Fixture.decode("{\"abbr\":\"A\",\"record\":\"2-1-1\"}")
        XCTAssertEqual(t.record, TeamRecord(wins: 2, losses: 1, ties: 1))
        let u: Team = try Fixture.decode("{\"abbr\":\"A\",\"record\":{\"w\":\"3\",\"l\":5,\"t\":null}}")
        XCTAssertEqual(u.record?.text, "3-5")
        let v: Team = try Fixture.decode("{\"abbr\":\"A\",\"record\":\"bye\"}")
        XCTAssertNil(v.record)
    }

    func testDateFormats() throws {
        let z = try XCTUnwrap(ISODate.parse("2026-11-15T18:00Z"))
        XCTAssertEqual(ISODate.parse("2026-11-15T18:00:00Z"), z)
        XCTAssertEqual(ISODate.parse("2026-11-15T12:00:00-06:00"), z)
        XCTAssertEqual(ISODate.parse("2026-11-15T18:00:00.000Z"), z)
        XCTAssertEqual(ISODate.parse("2026-11-15T19:30+01:30"), z)
        XCTAssertEqual(ISODate.parse("2026-11-15T18:00:30Z"), z.addingTimeInterval(30))
        XCTAssertNil(ISODate.parse(""))
        XCTAssertNil(ISODate.parse("TBD"))
        XCTAssertNil(ISODate.parse("garbage-in-here!!"))
    }
}
