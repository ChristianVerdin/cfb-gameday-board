import XCTest

final class PeriodLabelTests: XCTestCase {
    func testLabels() {
        XCTAssertEqual(PeriodLabel.of(0), "")
        XCTAssertEqual(PeriodLabel.of(nil), "")
        XCTAssertEqual(PeriodLabel.of(-1), "")
        XCTAssertEqual((1...4).map(PeriodLabel.of), ["Q1", "Q2", "Q3", "Q4"])
        XCTAssertEqual(PeriodLabel.of(5), "OT")
        XCTAssertEqual(PeriodLabel.of(6), "2OT")
        XCTAssertEqual(PeriodLabel.of(7), "3OT")
    }

    func testLiveGameDerivesLabelFromPeriod() throws {
        let g: LiveGame = try Fixture.decode("{\"id\":\"1\",\"period\":6}")
        XCTAssertEqual(g.periodLabel, "2OT")
        XCTAssertTrue(g.ot)
    }
}

final class FieldGeometryTests: XCTestCase {
    func testAwayPossessionAttacksTowardTheHomeGoal() throws {
        let f = try XCTUnwrap(FieldPosition(Situation(distance: 10, possession: .away, yl100: 36)))
        XCTAssertEqual(f.ball, 64)
        XCTAssertEqual(f.attackingGoal, 100)
        XCTAssertEqual(f.direction, 1)
        XCTAssertEqual(f.firstDownLine, 74)
        XCTAssertEqual(f.yardsToGoal, 36)
    }

    func testHomePossessionAttacksTowardTheAwayGoal() throws {
        let f = try XCTUnwrap(FieldPosition(Situation(distance: 10, possession: .home, yl100: 25)))
        XCTAssertEqual(f.ball, 25)
        XCTAssertEqual(f.attackingGoal, 0)
        XCTAssertEqual(f.direction, -1)
        XCTAssertEqual(f.firstDownLine, 15)
    }

    func testGoalToGoClampsTheFirstDownLine() throws {
        let f = try XCTUnwrap(FieldPosition(Situation(distance: 8, possession: .home, yl100: 4)))
        XCTAssertEqual(f.firstDownLine, 0)
        let a = try XCTUnwrap(FieldPosition(Situation(distance: 8, possession: .away, yl100: 4)))
        XCTAssertEqual(a.ball, 96)
        XCTAssertEqual(a.firstDownLine, 100)
    }

    func testNoPositionWithoutPossessionOrDuringStoppage() {
        XCTAssertNil(FieldPosition(nil))
        XCTAssertNil(FieldPosition(Situation(possession: nil, yl100: 40)))
        XCTAssertNil(FieldPosition(Situation(possession: .home, yl100: nil)))
        XCTAssertNil(FieldPosition(Situation(stoppage: true, possession: .home, yl100: 40)))
    }

    func testFixtureSituationDecodesToFieldPosition() throws {
        let live: LivePayload = try Fixture.load("live")
        let s = try XCTUnwrap(live.games.first { $0.id == "401873055" }?.situation)
        XCTAssertEqual(FieldPosition(s)?.ball, 64)
    }
}

final class WindowTests: XCTestCase {
    private func window(_ iso: String, tbd: Bool = false, kind: GameKind = .regular, round: String? = nil, abroad: Bool = false) -> GameWindow {
        GameWindow.classify(date: date(iso), timeTBD: tbd, kind: kind, round: round, abroad: abroad)
    }

    func testPrimeTimeAndSundayWindows() {
        XCTAssertEqual(window("2026-11-13T01:15Z"), .thursdayNight)        // Thu 7:15 PM CT
        XCTAssertEqual(window("2026-11-15T18:00Z"), .sundayEarly)          // Sun 12:00 PM CT
        XCTAssertEqual(window("2026-11-15T18:29Z"), .sundayEarly)
        XCTAssertEqual(window("2026-11-15T18:30Z"), .sundayLate)           // 12:30 PM CT
        XCTAssertEqual(window("2026-11-15T21:25Z"), .sundayLate)
        XCTAssertEqual(window("2026-11-15T23:59Z"), .sundayLate)           // 5:59 PM CT
        XCTAssertEqual(window("2026-11-16T00:00Z"), .sundayNight)          // 6:00 PM CT
        XCTAssertEqual(window("2026-11-16T01:20Z"), .sundayNight)
        XCTAssertEqual(window("2026-11-17T01:15Z"), .mondayNight)
    }

    func testInternationalMorningOnlyWhenAbroad() {
        XCTAssertEqual(window("2026-11-15T14:30Z", abroad: true), .international)
        XCTAssertEqual(window("2026-11-15T14:30Z", abroad: false), .sundayEarly)
        XCTAssertEqual(window("2026-11-15T17:00Z", abroad: true), .sundayEarly, "11:00 AM CT is not a morning slot")
    }

    func testHolidaysAndOddDays() {
        XCTAssertEqual(window("2026-11-26T22:30Z"), .thanksgiving)         // Thu Nov 26, 4:30 PM CT
        XCTAssertEqual(window("2026-11-27T01:20Z"), .thanksgiving)         // Thu Nov 26, 7:20 PM CT
        XCTAssertEqual(window("2026-11-26T01:00Z"), .wednesday)
        XCTAssertEqual(window("2026-11-27T20:00Z"), .blackFriday)
        XCTAssertEqual(window("2026-12-25T18:00Z"), .christmas)
        XCTAssertEqual(window("2026-12-24T18:00Z"), .christmas)
        XCTAssertEqual(window("2026-12-26T18:00Z"), .saturday)
        XCTAssertEqual(window("2026-12-18T01:15Z"), .thursdayNight)
        XCTAssertEqual(window("2026-09-12T01:00Z"), .friday)
    }

    func testChicagoDayNotUTCDay() {
        XCTAssertEqual(window("2026-11-16T04:00Z"), .sundayNight, "10 PM Sunday CT is already Monday UTC")
    }

    func testFlexAndPostseason() {
        XCTAssertEqual(window("2026-11-15T18:00Z", tbd: true), .flex)
        XCTAssertEqual(GameWindow.classify(date: nil, timeTBD: false, kind: .regular, round: nil, abroad: false), .flex)
        XCTAssertEqual(window("2027-01-10T18:00Z", kind: .playoff, round: "Wild Card"), .postseason("Wild Card"))
        XCTAssertEqual(GameWindow.classify(date: nil, timeTBD: true, kind: .playoff, round: nil, abroad: false), .postseason("Playoffs"))
        XCTAssertEqual(window("2027-02-04T01:00Z", kind: .allStar), .proBowl)
    }

    func testLabels() {
        XCTAssertEqual(GameWindow.thursdayNight.label, "TNF")
        XCTAssertEqual(GameWindow.international.label, "Int'l AM")
        XCTAssertEqual(GameWindow.flex.label, "Flex TBD")
        XCTAssertEqual(GameWindow.postseason("Divisional").label, "Divisional")
    }

    func testOrderingFollowsFirstKickoff() throws {
        let games = [
            try makeGame(id: "a", date: "2026-11-16T01:20Z"),
            try makeGame(id: "b", date: "2026-11-13T01:15Z"),
            try makeGame(id: "c", date: "2026-11-15T18:00Z"),
            try makeGame(id: "d", tbd: true),
        ]
        XCTAssertEqual(GameWindow.ordered(games), [.thursdayNight, .sundayEarly, .sundayNight, .flex])
    }
}

final class DeskTests: XCTestCase {
    private func item(_ id: String, _ eff: Double, progress: Int = 0, kick: TimeInterval = 0) -> DeskRanking.Item {
        .init(id: id, effective: eff, progress: progress, kickoff: kick)
    }

    func testOrdersByScoreThenProgressThenKickoff() {
        let order = DeskRanking.order([item("a", 40), item("b", 70), item("c", 70, progress: 3000), item("d", 70, progress: 3000, kick: -5)], previousTop: nil)
        XCTAssertEqual(order, ["d", "c", "b", "a"])
    }

    func testPreviousLeaderKeepsFirstWithinFivePoints() {
        let items = [item("a", 60), item("b", 64.9)]
        XCTAssertEqual(DeskRanking.order(items, previousTop: "a"), ["a", "b"])
        XCTAssertEqual(DeskRanking.order(items, previousTop: nil), ["b", "a"])
        XCTAssertEqual(DeskRanking.order(items, previousTop: "zzz"), ["b", "a"])
    }

    func testNewLeaderTakesOverAtFivePoints() {
        XCTAssertEqual(DeskRanking.order([item("a", 60), item("b", 65)], previousTop: "a"), ["b", "a"])
    }

    func testHysteresisOnlyProtectsFirstPlace() {
        XCTAssertEqual(DeskRanking.order([item("a", 50), item("b", 80), item("c", 79)], previousTop: "c"), ["c", "b", "a"])
    }

    func testSwingCountsThreeMinutes() {
        let now = date("2026-11-15T18:10Z")
        let samples = [
            DeskRanking.Sample(time: now.addingTimeInterval(-300), homeWP: 0.9),
            DeskRanking.Sample(time: now.addingTimeInterval(-120), homeWP: 0.50),
            DeskRanking.Sample(time: now, homeWP: 0.62),
        ]
        let s = DeskRanking.swing(samples, now: now)
        XCTAssertEqual(s.points, 12, accuracy: 0.001)
        XCTAssertEqual(s.toward, .home)
        XCTAssertEqual(DeskRanking.swing([samples[2]], now: now).points, 0)
        XCTAssertEqual(DeskRanking.swing(samples.reversed().map { $0 }.dropLast().map { $0 }, now: now).toward, .away)
    }

    func testEffectiveScoreCapsTheSwingBonus() {
        XCTAssertEqual(DeskRanking.effectiveScore(50, swingPoints: 3.6), 54)
        XCTAssertEqual(DeskRanking.effectiveScore(50, swingPoints: 40), 65)
    }
}

final class PollCadenceTests: XCTestCase {
    private let now = date("2026-11-15T17:00Z")

    func testTwentySecondsWhileAnyGameIsLive() throws {
        let games = [try makeGame(id: "1", state: "post"), try makeGame(id: "2", state: "in", date: "2026-11-15T16:00Z")]
        XCTAssertEqual(PollCadence.interval(for: games, now: now), 20)
    }

    func testSixtySecondsWithinAnHourOfKickoff() throws {
        XCTAssertEqual(PollCadence.interval(for: [try makeGame(date: "2026-11-15T17:59Z")], now: now), 60)
        XCTAssertEqual(PollCadence.interval(for: [try makeGame(date: "2026-11-15T17:00Z")], now: now), 60)
        XCTAssertEqual(PollCadence.interval(for: [try makeGame(date: "2026-11-15T15:00Z")], now: now), 60, "kicked off, not live yet")
    }

    func testIdleOtherwise() throws {
        XCTAssertEqual(PollCadence.interval(for: [try makeGame(date: "2026-11-15T18:30Z")], now: now), 120)
        XCTAssertEqual(PollCadence.interval(for: [try makeGame(date: "2026-11-15T10:00Z")], now: now), 120)
        XCTAssertEqual(PollCadence.interval(for: [try makeGame(tbd: true)], now: now), 120)
        XCTAssertEqual(PollCadence.interval(for: [try makeGame(state: "post", date: "2026-11-15T17:30Z")], now: now), 120)
        XCTAssertEqual(PollCadence.interval(for: [], now: now), 120)
    }

    func testGameSheetCadence() {
        XCTAssertEqual(GameStore.interval(for: .in), 20)
        XCTAssertEqual(GameStore.interval(for: .pre), 60)
        XCTAssertNil(GameStore.interval(for: .post))
    }
}

final class FormatTests: XCTestCase {
    func testChicagoKickoffText() {
        XCTAssertEqual(Chicago.kickoff(date("2026-11-15T18:00Z")), "Sun 12:00 PM CT")
        XCTAssertEqual(Chicago.kickoff(date("2026-11-13T01:15Z")), "Thu 7:15 PM CT")
        XCTAssertEqual(Chicago.kickoff(date("2026-09-13T17:00Z")), "Sun 12:00 PM CT")
        XCTAssertEqual(Chicago.kickoff(nil), "TBD")
        XCTAssertEqual(Chicago.kickoff(date("2026-11-15T18:00Z"), tbd: true), "TBD")
        XCTAssertEqual(Chicago.dayKey(date("2026-11-16T04:00Z")), "2026-11-15")
    }

    func testChipColors() {
        let navy = TeamColors.chip(color: "003c7f", alt: "c9243f")
        XCTAssertEqual(navy.background, RGB(hex: "003c7f"))
        XCTAssertEqual(navy.foreground, .white)
        let gold = TeamColors.chip(color: "d3bc8d", alt: "000000")
        XCTAssertEqual(gold.foreground, .ink)
        let invisible = TeamColors.chip(color: "162036", alt: "ffb612")
        XCTAssertEqual(invisible.background, RGB(hex: "ffb612"), "falls back to the alternate when the colour vanishes into the card")
        XCTAssertEqual(TeamColors.chip(color: nil, alt: "zz").background, .neutralBG)
        XCTAssertEqual(TeamColors.chip(color: "#003c7f", alt: nil).background, RGB(hex: "003c7f"))
        XCTAssertNil(RGB(hex: "12345"))
    }

    func testRoutes() {
        XCTAssertEqual(Route(url: URL(string: "pfb://game/401873055")!), .game("401873055"))
        XCTAssertEqual(Route(url: URL(string: "pfb://live")!), .tab(.live))
        XCTAssertEqual(Route(url: URL(string: "pfb://board")!), .tab(.board))
        XCTAssertEqual(Route(url: URL(string: "pfb://following")!), .tab(.following))
        XCTAssertNil(Route(url: URL(string: "pfb://game/")!))
        XCTAssertNil(Route(url: URL(string: "pfb://game/abc")!))
        XCTAssertNil(Route(url: URL(string: "pfb://nowhere")!))
        XCTAssertNil(Route(url: URL(string: "https://cfbgameday.app/nfl")!))
    }

    func testLiveURLCarriesSeasonAndWeekOnly() {
        XCTAssertEqual(APIClient.liveURL(season: nil, week: nil).absoluteString, "https://cfbgameday.app/api/nfl/live")
        XCTAssertEqual(APIClient.liveURL(season: 2, week: 10).absoluteString, "https://cfbgameday.app/api/nfl/live?st=2&week=10")
    }

    func testCompass() {
        XCTAssertEqual(Weather.compass(0), "N")
        XCTAssertEqual(Weather.compass(359), "N")
        XCTAssertEqual(Weather.compass(90), "E")
        XCTAssertEqual(Weather.compass(-90), "W")
        XCTAssertNil(Weather.compass(nil))
    }
}
