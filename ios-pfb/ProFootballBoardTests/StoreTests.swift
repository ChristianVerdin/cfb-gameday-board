import XCTest

private struct StubAPI: BoardAPI {
    var livePayload: LivePayload?
    var snapshotPayload: Snapshot?
    var metricsPayload: Metrics?
    var sheet: GameSheet?

    func live(season: Int?, week: Int?) async throws -> LivePayload {
        guard let livePayload else { throw APIError.offline }
        return livePayload
    }
    func game(id: String) async throws -> GameSheet {
        guard let sheet else { throw APIError.badStatus(404) }
        return sheet
    }
    func snapshot() async throws -> Snapshot {
        guard let snapshotPayload else { throw APIError.offline }
        return snapshotPayload
    }
    func metrics() async throws -> Metrics {
        guard let metricsPayload else { throw APIError.offline }
        return metricsPayload
    }
}

@MainActor
final class StoreTests: XCTestCase {
    private func loadedStub() throws -> StubAPI {
        StubAPI(livePayload: try Fixture.load("live"), snapshotPayload: try Fixture.load("games"),
                metricsPayload: try Fixture.load("metrics"), sheet: try Fixture.load("game_live"))
    }

    func testRefreshMergesEverything() async throws {
        let now = date("2026-11-15T21:10Z")
        let store = BoardStore(api: try loadedStub(), clock: { now })
        await store.refresh()
        XCTAssertEqual(store.games.count, 14)
        XCTAssertEqual(store.lastUpdated, now)
        XCTAssertNil(store.error)
        XCTAssertEqual(store.byes, ["CHI", "DEN", "PHI", "TB"])
        XCTAssertEqual(store.weekLabel, "Week 10")
        XCTAssertEqual(store.metrics?.teams.count, 32)
        XCTAssertEqual(store.games.first?.state, .in)
        XCTAssertEqual(store.games.last?.state, .post)
        XCTAssertEqual(store.game(id: "401873055")?.venue?.name, "Caesars Superdome")
    }

    func testDeskIsTheTopThreeLiveGamesByScore() async throws {
        let store = BoardStore(api: try loadedStub(), clock: { date("2026-11-15T21:10Z") })
        await store.refresh()
        let live = store.games.filter(\.isLive).compactMap { $0.desk?.score }.sorted(by: >)
        XCTAssertEqual(store.desk.count, min(3, live.count))
        XCTAssertEqual(store.desk.compactMap { $0.desk?.score }, Array(live.prefix(3)))
        XCTAssertTrue(store.desk.allSatisfy(\.isLive))
    }

    func testFailedPollKeepsLastGoodData() async throws {
        let store = BoardStore(api: try loadedStub(), clock: { date("2026-11-15T21:10Z") })
        await store.refresh()
        let before = store.games
        let broken = BoardStoreFailureProbe(base: try loadedStub())
        let store2 = BoardStore(api: broken, clock: { date("2026-11-15T21:10Z") })
        await store2.refresh()
        XCTAssertEqual(store2.games.count, 14)
        await broken.failLive()
        await store2.refresh()
        XCTAssertEqual(store2.error, .offline)
        XCTAssertEqual(store2.games, before)
        XCTAssertEqual(store2.lastUpdated, date("2026-11-15T21:10Z"))
    }

    func testOfflineFromTheStartShowsErrorAndSnapshotOnly() async throws {
        var stub = try loadedStub()
        stub.livePayload = nil
        let store = BoardStore(api: stub)
        await store.refresh()
        XCTAssertEqual(store.error, .offline)
        XCTAssertNil(store.lastUpdated)
        XCTAssertEqual(store.games.count, 14, "the snapshot still fills the board")
    }

    func testFollowingFilter() async throws {
        let defaults = UserDefaults(suiteName: "pfb.tests.\(UUID().uuidString)")!
        let follow = FollowStore(defaults: defaults)
        follow.toggle("CAR")
        let store = BoardStore(api: try loadedStub())
        await store.refresh()
        let mine = store.games(for: .following, following: follow)
        XCTAssertEqual(mine.map(\.id), ["401873055"])
        XCTAssertEqual(FollowStore(defaults: defaults).teams, ["CAR"], "persists across launches")
        follow.toggle("CAR")
        XCTAssertTrue(store.games(for: .following, following: follow).isEmpty)
        XCTAssertEqual(store.games(for: .live, following: follow).count, store.liveCount)
    }

    func testGameStoreLoadsSheet() async throws {
        let game = GameStore(gameID: "401873055", api: try loadedStub(), clock: { date("2026-11-15T21:10Z") })
        await game.refresh()
        XCTAssertEqual(game.sheet?.id, "401873055")
        XCTAssertEqual(game.lastUpdated, date("2026-11-15T21:10Z"))
        let missing = GameStore(gameID: "1", api: StubAPI())
        await missing.refresh()
        XCTAssertEqual(missing.error, .badStatus(404))
        XCTAssertNil(missing.sheet)
    }

    func testRouterOpensTabsAndGames() {
        let router = Router()
        router.open(.game("401873055"))
        XCTAssertEqual(router.gameID, "401873055")
        XCTAssertTrue(router.open(url: URL(string: "pfb://live")!))
        XCTAssertEqual(router.tab, .live)
        XCTAssertNil(router.gameID)
        XCTAssertFalse(router.open(url: URL(string: "pfb://bogus")!))
    }
}

private actor BoardStoreFailureProbe: BoardAPI {
    let base: StubAPI
    private var failing = false
    init(base: StubAPI) { self.base = base }
    func failLive() { failing = true }
    func live(season: Int?, week: Int?) async throws -> LivePayload {
        if failing { throw APIError.offline }
        return try await base.live(season: season, week: week)
    }
    func game(id: String) async throws -> GameSheet { try await base.game(id: id) }
    func snapshot() async throws -> Snapshot { try await base.snapshot() }
    func metrics() async throws -> Metrics { try await base.metrics() }
}
