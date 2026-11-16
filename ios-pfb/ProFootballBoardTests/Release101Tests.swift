import XCTest

/// Records the parameters of every live call and answers from closures.
private actor RecordingAPI: BoardAPI {
    struct Call: Equatable { var season: Int?; var week: Int? }

    var livePayload: LivePayload?
    var snapshotPayload: Snapshot?
    var gameError: APIError?
    var rejectExplicit = false
    private(set) var calls: [Call] = []

    init(live: LivePayload?, snapshot: Snapshot?, gameError: APIError? = nil, rejectExplicit: Bool = false) {
        livePayload = live; snapshotPayload = snapshot; self.gameError = gameError; self.rejectExplicit = rejectExplicit
    }

    func live(season: Int?, week: Int?) async throws -> LivePayload {
        calls.append(Call(season: season, week: week))
        if rejectExplicit, season != nil || week != nil { throw APIError.badStatus(400) }
        guard let livePayload else { throw APIError.offline }
        return livePayload
    }
    func game(id: String) async throws -> GameSheet {
        if let gameError { throw gameError }
        throw APIError.offline
    }
    func snapshot() async throws -> Snapshot {
        guard let snapshotPayload else { throw APIError.offline }
        return snapshotPayload
    }
    func metrics() async throws -> Metrics { throw APIError.offline }
}

private let noSlateJSON = """
{"ok":true,"v":1,"count":0,"fetched_at":"2027-03-01T18:00:00Z","stale":false,"season":null,"week":null,
 "teams_on_bye":[],"games":[],"warnings":["no_slate"]}
"""

private let sunday = date("2026-11-15T21:10Z")

@MainActor
final class Release101Tests: XCTestCase {

    // MARK: Explicit week parameters

    func testBadRequestOnExplicitWeekRetriesWithoutParameters() async throws {
        let api = RecordingAPI(live: try Fixture.load("live"), snapshot: try Fixture.load("games"), rejectExplicit: true)
        let store = BoardStore(api: api, clock: { sunday })
        await store.refresh()
        let calls = await api.calls
        XCTAssertEqual(calls, [.init(season: 2, week: 10), .init(season: nil, week: nil)])
        XCTAssertNil(store.error)
        XCTAssertEqual(store.games.count, 14)
    }

    func testPreseasonOrOutOfRangeSnapshotSendsNoParameters() async throws {
        var snap: Snapshot = try Fixture.load("games")
        snap.season.type = 1
        let api = RecordingAPI(live: try Fixture.load("live"), snapshot: snap)
        await BoardStore(api: api, clock: { sunday }).refresh()
        var calls = await api.calls
        XCTAssertEqual(calls, [.init(season: nil, week: nil)])

        snap.season.type = 2
        snap.week.number = 19
        let api2 = RecordingAPI(live: try Fixture.load("live"), snapshot: snap)
        await BoardStore(api: api2, clock: { sunday }).refresh()
        calls = await api2.calls
        XCTAssertEqual(calls, [.init(season: nil, week: nil)])
    }

    func testRegularWeekStillSendsExplicitParameters() async throws {
        let api = RecordingAPI(live: try Fixture.load("live"), snapshot: try Fixture.load("games"))
        await BoardStore(api: api, clock: { sunday }).refresh()
        let calls = await api.calls
        XCTAssertEqual(calls, [.init(season: 2, week: 10)])
    }

    // MARK: Game sheet errors

    func testClientErrorsAreNotRetriedOnATimer() {
        XCTAssertTrue(APIError.badStatus(400).isPermanent)
        XCTAssertTrue(APIError.badStatus(404).isPermanent)
        XCTAssertFalse(APIError.badStatus(429).isPermanent)
        XCTAssertFalse(APIError.badStatus(408).isPermanent)
        XCTAssertFalse(APIError.badStatus(502).isPermanent)
        XCTAssertFalse(APIError.offline.isPermanent)
        XCTAssertFalse(APIError.timeout.isPermanent)
    }

    func testBadGameIdSurfacesAsPermanentError() async {
        let store = GameStore(gameID: "123456", api: RecordingAPI(live: nil, snapshot: nil, gameError: .badStatus(400)))
        await store.refresh()
        XCTAssertEqual(store.error, .badStatus(400))
        XCTAssertEqual(store.error?.isPermanent, true)
        XCTAssertNil(store.sheet)
    }

    func testErrorTextHasNoHttpCode() {
        XCTAssertFalse(APIError.badStatus(502).message.contains("502"))
    }

    // MARK: Suspended, delayed and postponed

    func testSuspendedAndDelayedAreHeldInAnyState() throws {
        for state in ["in", "post"] {
            for status in ["STATUS_SUSPENDED", "STATUS_DELAYED", "STATUS_RAIN_DELAY"] {
                let g = try makeGame(state: state, period: 3, extra: ",\"status\":\"\(status)\",\"clock\":\"4:12\"")
                XCTAssertTrue(g.isHeld, "\(state) \(status)")
            }
        }
        XCTAssertFalse(try makeGame(state: "pre", extra: ",\"status\":\"STATUS_DELAYED\"").isHeld)
        XCTAssertFalse(try makeGame(state: "post", extra: ",\"status\":\"STATUS_FINAL\"").isHeld)
        XCTAssertFalse(try makeGame(state: "in", extra: ",\"status\":\"STATUS_HALFTIME\"").isHeld)
    }

    func testSuspendedGameReportedAsPostIsNotFinalInTheWidget() throws {
        let held = try makeGame(state: "post", period: 3, extra: ",\"status\":\"STATUS_SUSPENDED\",\"clock\":\"4:12\"")
        let widget = WidgetGame(held)
        XCTAssertFalse(widget.isFinal)
        XCTAssertTrue(widget.status.hasPrefix("Suspended"), widget.status)
        let delayed = WidgetGame(try makeGame(state: "in", period: 2, extra: ",\"status\":\"STATUS_RAIN_DELAY\""))
        XCTAssertTrue(delayed.status.hasPrefix("Delayed"), delayed.status)
        let final = WidgetGame(try makeGame(state: "post", period: 4, extra: ",\"status\":\"STATUS_FINAL\""))
        XCTAssertTrue(final.isFinal)
    }

    func testSuspendedSheetIsHeldEvenWhenPost() throws {
        var json = try XCTUnwrap(JSONSerialization.jsonObject(with: Fixture.data("game_final")) as? [String: Any])
        json["status"] = "STATUS_SUSPENDED"
        let sheet = try JSONDecoder().decode(GameSheet.self, from: JSONSerialization.data(withJSONObject: json))
        XCTAssertEqual(sheet.state, .post)
        XCTAssertTrue(sheet.isHeld)
        json["status"] = "STATUS_RAIN_DELAY"
        let delayed = try JSONDecoder().decode(GameSheet.self, from: JSONSerialization.data(withJSONObject: json))
        XCTAssertTrue(delayed.isHeld)
        json["status"] = "STATUS_FINAL"
        XCTAssertFalse(try JSONDecoder().decode(GameSheet.self, from: JSONSerialization.data(withJSONObject: json)).isHeld)
    }

    // MARK: Offseason

    func testNoSlatePayloadDecodesAndShowsNoWeek() async throws {
        let live: LivePayload = try Fixture.decode(noSlateJSON)
        XCTAssertTrue(live.games.isEmpty)
        XCTAssertEqual(live.warnings, ["no_slate"])
        XCTAssertNil(live.week.number)

        var snap: Snapshot = try Fixture.load("games")
        snap.week.end = date("2026-11-18T07:59Z")
        let api = RecordingAPI(live: live, snapshot: snap)
        let store = BoardStore(api: api, clock: { date("2027-03-01T18:00Z") })
        await store.refresh()
        let calls = await api.calls
        XCTAssertEqual(calls, [.init(season: nil, week: nil)], "a past snapshot sends no parameters")
        XCTAssertTrue(store.noSlate)
        XCTAssertNil(store.weekLabel, "the old week's title is dropped")
        XCTAssertTrue(store.games.isEmpty)
        XCTAssertGreaterThan(PollCadence.offseason, PollCadence.idle)
    }

    func testOtherWarningsAreNotNoSlate() async throws {
        let store = BoardStore(api: RecordingAPI(live: try Fixture.load("live"), snapshot: try Fixture.load("games")),
                               clock: { sunday })
        await store.refresh()
        XCTAssertFalse(store.noSlate)
        XCTAssertEqual(store.weekLabel, "Week 10")
    }

    func testWidgetSlateRemembersOffseason() throws {
        let live: LivePayload = try Fixture.decode(noSlateJSON)
        let slate = WidgetSlate(live: live, snapshot: try Fixture.load("games"), fetchedAt: sunday)
        XCTAssertEqual(slate.offseason, true)
        XCTAssertNil(slate.weekLabel)
        XCTAssertTrue(slate.games.isEmpty)
        let regular = WidgetSlate(live: try Fixture.load("live"), snapshot: nil, fetchedAt: sunday)
        XCTAssertNil(regular.offseason)
    }

    // MARK: Widget cache

    private func tempCache() -> SlateCache {
        SlateCache(url: FileManager.default.temporaryDirectory.appending(path: "pfb-\(UUID().uuidString)/slate.json"))
    }

    func testSnapshotOnlyFallbackIsDatedByTheSnapshot() async throws {
        let snap: Snapshot = try Fixture.load("games")
        let api = RecordingAPI(live: nil, snapshot: snap)
        let result = await SlateLoader(api: api, cache: tempCache()).load(now: date("2026-11-16T20:00Z"))
        XCTAssertTrue(result.offline)
        XCTAssertEqual(result.slate?.fetchedAt, snap.generatedAt)
        XCTAssertNotEqual(result.slate?.fetchedAt, date("2026-11-16T20:00Z"))
    }

    func testOldCacheIsReplacedBySnapshotButFreshCacheIsKept() async throws {
        let cache = tempCache()
        let good = RecordingAPI(live: try Fixture.load("live"), snapshot: try Fixture.load("games"))
        _ = await SlateLoader(api: good, cache: cache).load(now: sunday)
        let down = RecordingAPI(live: nil, snapshot: try Fixture.load("games"))

        let soon = await SlateLoader(api: down, cache: cache).load(now: sunday + 3600)
        XCTAssertEqual(soon.slate?.fetchedAt, sunday)
        XCTAssertGreaterThan(soon.slate?.liveCount ?? 0, 0)

        let days = await SlateLoader(api: down, cache: cache).load(now: sunday + 3 * 86400)
        XCTAssertNotEqual(days.slate?.fetchedAt, sunday, "the three-day-old cache is not shown as the latest")
        XCTAssertEqual(days.slate?.fetchedAt, try Fixture.load("games", as: Snapshot.self).generatedAt)
        XCTAssertTrue(days.offline)

        let noSnapshot = await SlateLoader(api: RecordingAPI(live: nil, snapshot: nil), cache: cache).load(now: sunday + 3 * 86400)
        XCTAssertEqual(noSnapshot.slate?.fetchedAt, sunday, "an old cache still beats nothing")
    }

    // MARK: Rating prompt

    private func prompt(_ version: String = "1.0.1") -> ReviewPrompt {
        ReviewPrompt(defaults: UserDefaults(suiteName: "pfb.review.\(UUID().uuidString)")!, version: version)
    }

    func testPromptWaitsForThreeDaysAndAWeek() {
        let p = prompt()
        let start = date("2026-11-16T15:00Z")
        XCTAssertFalse(p.shouldAsk(now: start))
        XCTAssertFalse(p.shouldAsk(now: start + 86400))
        XCTAssertFalse(p.shouldAsk(now: start + 2 * 86400), "three days, but not yet a week")
        XCTAssertFalse(p.shouldAsk(now: start + 60), "same day again adds nothing")
        XCTAssertTrue(p.shouldAsk(now: start + 8 * 86400))
    }

    func testPromptAsksOncePerVersion() {
        let defaults = UserDefaults(suiteName: "pfb.review.\(UUID().uuidString)")!
        let start = date("2026-11-16T15:00Z")
        let v1 = ReviewPrompt(defaults: defaults, version: "1.0.1")
        _ = v1.shouldAsk(now: start)
        _ = v1.shouldAsk(now: start + 86400)
        XCTAssertTrue(v1.shouldAsk(now: start + 8 * 86400))
        v1.markAsked()
        XCTAssertFalse(v1.shouldAsk(now: start + 9 * 86400))
        XCTAssertFalse(ReviewPrompt(defaults: defaults, version: "1.0.1").shouldAsk(now: start + 20 * 86400))
        XCTAssertTrue(ReviewPrompt(defaults: defaults, version: "1.0.2").shouldAsk(now: start + 20 * 86400))
    }
}
