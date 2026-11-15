import XCTest

final class DecodingTests: XCTestCase {
    func testLiveFixture() throws {
        let live: LivePayload = try Fixture.load("live")
        XCTAssertEqual(live.games.count, 14)
        XCTAssertEqual(live.season, SeasonInfo(year: 2026, type: 2))
        XCTAssertEqual(live.week.number, 10)
        XCTAssertEqual(live.teamsOnBye, ["CHI", "DEN", "PHI", "TB"])
        let final = try XCTUnwrap(live.games.first { $0.id == "401873052" })
        XCTAssertEqual(final.state, .post)
        XCTAssertEqual(final.result, .away)
        XCTAssertEqual(final.away?.abbr, "WSH")
        XCTAssertEqual(final.away?.record, TeamRecord(wins: 3, losses: 5, ties: 1))
        XCTAssertEqual(final.away?.linescores, [0, 10, 7, 7])
        XCTAssertEqual(final.date, date("2026-11-13T01:15Z"))
        let inGame = try XCTUnwrap(live.games.first { $0.id == "401873055" })
        XCTAssertEqual(inGame.state, .in)
        XCTAssertEqual(inGame.situation?.possession, .away)
        XCTAssertEqual(inGame.situation?.yl100, 36)
        XCTAssertEqual(inGame.wp?.home ?? 0, 0.218, accuracy: 0.0001)
        XCTAssertEqual(inGame.desk?.score, 55)
        XCTAssertEqual(inGame.broadcasts, ["Fox"])
        XCTAssertEqual(live.games.filter { $0.state == .pre }.count, 3)
    }

    func testLiveGameSheets() throws {
        let live: GameSheet = try Fixture.load("game_live")
        XCTAssertEqual(live.state, .in)
        XCTAssertEqual(live.periodLabel, "Q4")
        XCTAssertEqual(live.teams.away?.abbr, "CAR")
        XCTAssertEqual(live.teams.home?.score, 17)
        XCTAssertEqual(live.linescores.away.count, 4)
        XCTAssertFalse(live.drives.isEmpty)
        XCTAssertFalse(live.drives[0].playList.isEmpty)
        XCTAssertEqual(live.liveDrive?.id, live.currentDriveID)
        XCTAssertEqual(live.tracker?.team, "CAR")
        XCTAssertEqual(live.tracker?.currentYardLine, 36)
        XCTAssertGreaterThan(live.winProb.points.count, 50)
        XCTAssertEqual(live.winProb.quarters.map(\.label), ["Q1", "Q2", "Q3", "Q4"])
        XCTAssertEqual(live.box.first?.label, "1st downs")
        XCTAssertEqual(live.box.first?.away, "18")
        XCTAssertEqual(live.leaders.home.first?.key, "passingYards")
        XCTAssertEqual(live.scoring.first?.kind, "TD")
        XCTAssertEqual(live.warnings, ["duplicate_plays:5"])
    }

    func testFinalGameSheet() throws {
        let sheet: GameSheet = try Fixture.load("game_final")
        XCTAssertEqual(sheet.state, .post)
        XCTAssertEqual(sheet.result, .away)
        XCTAssertEqual(sheet.teams.away?.score, 24)
        XCTAssertEqual(sheet.teams.home?.score, 21)
        XCTAssertNil(sheet.tracker)
        XCTAssertNil(sheet.currentDriveID)
        XCTAssertEqual(sheet.overtimePeriods, 0)
        XCTAssertEqual(sheet.scoring.count, 7)
    }

    func testOvertimeSheet() throws {
        let sheet: GameSheet = try Fixture.load("game_ot")
        XCTAssertEqual(sheet.state, .post)
        XCTAssertEqual(sheet.overtimePeriods, 1)
        XCTAssertEqual(sheet.periodLabel, "OT")
        XCTAssertEqual(sheet.result, .home)
        XCTAssertEqual(sheet.linescores.home.count, 5)
        XCTAssertTrue(sheet.scoring.contains { $0.periodLabel == "OT" })
    }

    func testTieSheetAndBoardResult() throws {
        let sheet: GameSheet = try Fixture.load("game_tie")
        XCTAssertEqual(sheet.result, .tie)
        XCTAssertEqual(sheet.teams.away?.score, sheet.teams.home?.score)
        let game = try makeGame(state: "post", extra: ",\"completed\":true")
        XCTAssertEqual(game.result, .tie)
    }

    func testPlaceholderGamesHaveNoTeams() throws {
        let live: LivePayload = try Fixture.load("live_placeholder")
        XCTAssertEqual(live.games.count, 6)
        XCTAssertTrue(live.games.allSatisfy { $0.placeholder && $0.away == nil && $0.home == nil })
        let board = BoardGame.build(live: live, snapshot: nil)
        XCTAssertEqual(board.count, 6)
        XCTAssertTrue(board.allSatisfy { $0.placeholder })
        XCTAssertEqual(board[0].matchup, board[0].flexNote ?? "To be determined")
    }

    func testFlexWeekIsAllTBD() throws {
        let live: LivePayload = try Fixture.load("live_flex")
        let board = BoardGame.build(live: live, snapshot: nil)
        let tbd = board.filter(\.timeTBD)
        XCTAssertEqual(tbd.count, 4)
        XCTAssertTrue(tbd.allSatisfy { $0.window == .flex && $0.kickoffText == "TBD" })
    }

    func testSnapshotFixture() throws {
        let snap: Snapshot = try Fixture.load("games")
        XCTAssertEqual(snap.games.count, 14)
        XCTAssertEqual(snap.week.number, 10)
        XCTAssertEqual(snap.week.end, date("2026-11-18T07:59Z"))
        XCTAssertEqual(snap.teamsOnBye.map(\.abbr), ["CHI", "DEN", "PHI", "TB"])
        let no = try XCTUnwrap(snap.games.first { $0.id == "401873055" })
        XCTAssertEqual(no.venue?.roof, .dome)
        XCTAssertEqual(no.weatherStatus, "dome")
        XCTAssertNil(no.weather)
        XCTAssertEqual(no.home?.nv, "NO")
        let nyg = try XCTUnwrap(snap.games.first { $0.id == "401873052" })
        XCTAssertEqual(nyg.weather?.label, "Drizzle")
        XCTAssertEqual(nyg.weather?.temp ?? 0, 47.8, accuracy: 0.01)
        XCTAssertEqual(nyg.weather?.compass, "NNE")
        XCTAssertNil(nyg.home?.score, "snapshot scores arrive as empty strings")
        XCTAssertEqual(nyg.away?.nv, "WAS")
    }

    func testMetricsFixture() throws {
        let m: Metrics = try Fixture.load("metrics")
        XCTAssertEqual(m.teams.count, 32)
        XCTAssertEqual(m.throughWeek, 10)
        XCTAssertEqual(m.license, "CC-BY-4.0")
        XCTAssertEqual(m.leagueEPAPerPlay ?? 0, 0.003, accuracy: 0.0001)
        let buf = try XCTUnwrap(m.teams["BUF"])
        XCTAssertEqual(buf.offense?.epaRank, 3)
        XCTAssertEqual(buf.defense?.successRank, 25)
        XCTAssertNil(buf.defense?.proe)
        XCTAssertFalse(buf.smallSample)
    }

    func testMergedBoardUsesSnapshotForVenueAndColors() throws {
        let live: LivePayload = try Fixture.load("live")
        let snap: Snapshot = try Fixture.load("games")
        let board = BoardGame.build(live: live, snapshot: snap)
        XCTAssertEqual(board.count, 14)
        let no = try XCTUnwrap(board.first { $0.id == "401873055" })
        XCTAssertEqual(no.venue?.roof, .dome)
        XCTAssertEqual(no.home?.fullName, "New Orleans Saints")
        XCTAssertEqual(no.home?.score, 17)
        XCTAssertEqual(no.home?.metricsKey, "NO")
        XCTAssertEqual(no.window, .sundayEarly)
    }

    func testSnapshotFromAnotherWeekIsIgnored() throws {
        let live: LivePayload = try Fixture.load("live")
        var snap: Snapshot = try Fixture.load("games")
        snap.week.number = 9
        let board = BoardGame.build(live: live, snapshot: snap)
        XCTAssertNil(board.first?.venue?.roof)
        XCTAssertEqual(board.count, 14)
    }

    func testSnapshotAloneFillsTheBoard() throws {
        let snap: Snapshot = try Fixture.load("games")
        XCTAssertEqual(BoardGame.build(live: nil, snapshot: snap).count, 14)
    }

    func testBoardSortsLiveFirstThenUpcomingThenFinal() throws {
        let live: LivePayload = try Fixture.load("live")
        let sorted = BoardGame.sorted(BoardGame.build(live: live, snapshot: nil))
        let states = sorted.map(\.state)
        XCTAssertEqual(states, states.sorted { $0.rank < $1.rank })
        let liveScores = sorted.filter(\.isLive).map { $0.desk?.score ?? 0 }
        XCTAssertEqual(liveScores, liveScores.sorted(by: >))
    }
}

private extension GameState {
    var rank: Int { self == .in ? 0 : self == .pre ? 1 : 2 }
}
