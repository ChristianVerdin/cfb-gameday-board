import SwiftUI
import WidgetKit
import XCTest

private struct FakeAPI: BoardAPI {
    var livePayload: LivePayload?
    var snapshotPayload: Snapshot?

    func live(season: Int?, week: Int?) async throws -> LivePayload {
        guard let livePayload else { throw APIError.offline }
        return livePayload
    }
    func game(id: String) async throws -> GameSheet { throw APIError.offline }
    func snapshot() async throws -> Snapshot {
        guard let snapshotPayload else { throw APIError.offline }
        return snapshotPayload
    }
    func metrics() async throws -> Metrics { throw APIError.offline }
}

final class WidgetTests: XCTestCase {
    private let now = date("2026-11-15T21:10Z")

    private func slate(_ live: String = "live", snapshot: String? = "games", at: Date? = nil) throws -> WidgetSlate {
        WidgetSlate(live: try Fixture.load(live, as: LivePayload.self),
                    snapshot: try snapshot.map { try Fixture.load($0, as: Snapshot.self) },
                    fetchedAt: at ?? now)
    }

    private func tempCache() -> SlateCache {
        SlateCache(url: FileManager.default.temporaryDirectory.appending(path: "pfb-\(UUID().uuidString)/slate.json"))
    }

    // MARK: Selection

    func testScopesFilterTheBoard() throws {
        let s = try slate()
        XCTAssertEqual(s.games.count, 14)
        XCTAssertEqual(s.games(for: .all).count, 14)
        let live = s.games(for: .live)
        XCTAssertEqual(live.count, 7)
        XCTAssertTrue(live.allSatisfy(\.isLive))
        let car = s.games(for: .team("CAR"))
        XCTAssertEqual(car.count, 1)
        XCTAssertEqual(car.first?.matchup, "CAR @ NO")
        XCTAssertTrue(s.games(for: .team("ARI")).isEmpty || s.games(for: .team("ARI")).count == 1)
        XCTAssertEqual(s.liveCount, 7)
    }

    func testBoardOrderIsLiveThenUpcomingThenFinal() throws {
        let states = try slate().games.map(\.state)
        XCTAssertEqual(states, states.sorted { rank($0) < rank($1) })
        XCTAssertEqual(states.first, "in")
        XCTAssertEqual(states.last, "post")
    }

    private func rank(_ s: String) -> Int { s == "in" ? 0 : s == "pre" ? 1 : 2 }

    func testStatusText() throws {
        let games = try slate().games
        XCTAssertEqual(games.first { $0.isLive }?.status.hasPrefix("Q"), true)
        XCTAssertTrue(games.filter(\.isFinal).allSatisfy { $0.status.hasPrefix("Final") })
        let upcoming = try XCTUnwrap(games.first { $0.isUpcoming })
        XCTAssertTrue(upcoming.status.hasSuffix(" CT"), upcoming.status)
    }

    func testPlaceholderAndFlexGamesDecodeWithoutTeams() throws {
        let s = try slate("live_placeholder", snapshot: nil)
        XCTAssertFalse(s.games.isEmpty)
        XCTAssertTrue(s.games.allSatisfy { $0.away == .tbd && $0.home == .tbd })
        XCTAssertTrue(s.games.allSatisfy { !$0.status.isEmpty })
        let flex = try slate("live_flex", snapshot: nil)
        XCTAssertTrue(flex.games.contains { $0.timeTBD })
    }

    func testNextUp() throws {
        let s = try slate()
        XCTAssertEqual(s.nextUp(after: now)?.isUpcoming, true)
        XCTAssertNil(try slate("live_placeholder", snapshot: nil).nextUp(after: now))
    }

    // MARK: Refresh policy

    func testRefreshIsFiveMinutesWhileALiveGameExists() throws {
        XCTAssertEqual(try slate().nextRefresh(for: .all, now: now), now + 300)
        XCTAssertEqual(try slate().nextRefresh(for: .live, now: now), now + 300)
    }

    func testRefreshFollowsKickoffs() throws {
        let s = try slate("live_flex", snapshot: nil)
        func kick(_ minutes: Double) -> WidgetSlate {
            var one = s.games[0]
            one.date = now + minutes * 60
            return WidgetSlate(fetchedAt: now, weekLabel: nil, games: [one])
        }
        XCTAssertEqual(kick(50).nextRefresh(for: .all, now: now), now + 300, "kicks within the hour")
        XCTAssertEqual(kick(90).nextRefresh(for: .all, now: now), now + 3600, "next kickoff minus 30 minutes")
        XCTAssertEqual(kick(31).nextRefresh(for: .all, now: now), now + 300, "kicks within the hour")
        XCTAssertEqual(kick(60 * 30).nextRefresh(for: .all, now: now), now + 7200, "capped at two hours")
        let empty = WidgetSlate(fetchedAt: now, weekLabel: nil, games: [])
        XCTAssertEqual(empty.nextRefresh(for: .all, now: now), now + 7200)
    }

    func testTeamScopeIgnoresOtherLiveGames() throws {
        let s = try slate()
        let other = try XCTUnwrap(s.games.last { $0.isUpcoming })
        let team = other.away.abbr
        XCTAssertGreaterThan(s.nextRefresh(for: .team(team), now: now), now + 300)
    }

    // MARK: Cache and loader

    func testCacheRoundTrips() throws {
        let cache = tempCache()
        XCTAssertNil(cache.load())
        let s = try slate()
        cache.save(s)
        XCTAssertEqual(cache.load(), s)
    }

    func testLoaderCachesGoodPayloadAndFallsBackOffline() async throws {
        let cache = tempCache()
        let good = FakeAPI(livePayload: try Fixture.load("live"), snapshotPayload: try Fixture.load("games"))
        let fresh = await SlateLoader(api: good, cache: cache).load(now: now)
        XCTAssertFalse(fresh.offline)
        XCTAssertEqual(fresh.slate?.games.count, 14)

        let later = now + 900
        let down = await SlateLoader(api: FakeAPI(), cache: cache).load(now: later)
        XCTAssertTrue(down.offline)
        XCTAssertEqual(down.slate?.fetchedAt, now)
        XCTAssertEqual(down.slate?.games.count, 14)

        let nothing = await SlateLoader(api: FakeAPI(), cache: tempCache()).load(now: later)
        XCTAssertTrue(nothing.offline)
        XCTAssertNil(nothing.slate)
    }

    func testLoaderUsesSnapshotWhenNoLiveAndNoCache() async throws {
        let api = FakeAPI(livePayload: nil, snapshotPayload: try Fixture.load("games"))
        let result = await SlateLoader(api: api, cache: tempCache()).load(now: now)
        XCTAssertTrue(result.offline)
        XCTAssertEqual(result.slate?.games.count, 14)
    }

    // MARK: Configuration

    func testTeamOptionsCoverTheLeague() throws {
        XCTAssertEqual(TeamOption.allCases.count, 32)
        XCTAssertEqual(Set(TeamOption.allCases.map(\.abbr)).count, 32)
        XCTAssertEqual(TeamOption.caseDisplayRepresentations.count, 32)
        let seen = try slate().games.flatMap { [$0.away.abbr, $0.home.abbr] }
        for abbr in seen { XCTAssertNotNil(TeamOption(rawValue: abbr), abbr) }
    }

    func testIntentScopes() {
        func intent(_ mode: ShowMode, _ team: TeamOption) -> ShowGamesIntent {
            let i = ShowGamesIntent()
            i.mode = mode
            i.team = team
            return i
        }
        XCTAssertEqual(ShowGamesIntent().scope, .all)
        XCTAssertEqual(intent(.live, .KC).scope, .live)
        XCTAssertEqual(intent(.team, .WSH).scope, .team("WSH"))
    }

    // MARK: Renders

    private static let outputDir: URL = {
        if let dir = ProcessInfo.processInfo.environment["SNAPSHOT_DIR"], !dir.isEmpty { return URL(fileURLWithPath: dir) }
        return URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent().appending(path: "screenshots/dev")
    }()

    @MainActor
    func testRenderWidgetFamilies() throws {
        let out = Self.outputDir
        try FileManager.default.createDirectory(at: out, withIntermediateDirectories: true)
        let sizes: [(String, WidgetFamily, CGSize)] = [
            ("small", .systemSmall, CGSize(width: 170, height: 170)),
            ("medium", .systemMedium, CGSize(width: 364, height: 170)),
            ("large", .systemLarge, CGSize(width: 364, height: 382)),
            ("rect", .accessoryRectangular, CGSize(width: 172, height: 76)),
            ("inline", .accessoryInline, CGSize(width: 260, height: 24)),
        ]
        let live = try slate()
        let week = try slate("live", snapshot: "games", at: date("2026-11-15T14:00Z"))
        var morning = week
        morning.games = week.games.map { g in
            var p = g
            if p.isLive || p.isFinal { p.state = "pre"; p.away.score = nil; p.home.score = nil; p.possession = nil; p.situation = nil; p.status = "Sun 12:00 PM CT" }
            return p
        }
        let flex = try slate("live_flex", snapshot: nil)
        let scenes: [(String, SlateEntry)] = [
            ("live-all", SlateEntry(date: now, scope: .all, slate: live, offline: false)),
            ("live-only", SlateEntry(date: now, scope: .live, slate: live, offline: false)),
            ("team-car", SlateEntry(date: now, scope: .team("CAR"), slate: live, offline: false)),
            ("morning", SlateEntry(date: date("2026-11-15T14:00Z"), scope: .all, slate: morning, offline: false)),
            ("cached", SlateEntry(date: now + 1800, scope: .all, slate: live, offline: true)),
            ("no-live", SlateEntry(date: now, scope: .live, slate: flex, offline: false)),
            ("bye", SlateEntry(date: now, scope: .team("ARI"), slate: live, offline: false)),
            ("unavailable", SlateEntry(date: now, scope: .all, slate: nil, offline: true)),
        ]
        for (scene, entry) in scenes {
            for (name, family, size) in sizes {
                try render(entry, family: family, size: size, to: out.appending(path: "widget-\(scene)-\(name).png"))
            }
        }
        XCTAssertGreaterThan(try FileManager.default.contentsOfDirectory(atPath: out.path).filter { $0.hasPrefix("widget-") }.count, 30)
    }

    @MainActor
    private func render(_ entry: SlateEntry, family: WidgetFamily, size: CGSize, to url: URL) throws {
        let accessory = family == .accessoryRectangular || family == .accessoryInline
        let framed = SlateContent(entry: entry, family: family)
            .padding(accessory ? 4 : 16)
            .frame(width: size.width, height: size.height)
            .background(accessory ? Color.black : SlateStyle.background)
            .clipShape(RoundedRectangle(cornerRadius: accessory ? 8 : 22))
            .environment(\.colorScheme, .dark)
            .foregroundStyle(.white)
        let renderer = ImageRenderer(content: framed)
        renderer.scale = 3
        let png = try XCTUnwrap(renderer.uiImage?.pngData())
        try png.write(to: url)
    }
}
