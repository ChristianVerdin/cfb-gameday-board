import SwiftUI
import WidgetKit
import XCTest

/// The widget's logic against a frozen Week 8 snapshot (Tue 10/20 - Sat 10/24, built 10/21).
final class SlateTests: XCTestCase {
    private static let fixture = URL(fileURLWithPath: #filePath).deletingLastPathComponent()
        .appending(path: "Fixtures/week8.json")
    private var games: [SlateGame] = []

    override func setUpWithError() throws {
        games = try JSONDecoder().decode(Snapshot.self, from: Data(contentsOf: Self.fixture)).games
    }

    /// A Central wall-clock time in Week 8.
    private func ct(_ s: String) -> Date {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = Slate.chicago
        f.dateFormat = "yyyy-MM-dd HH:mm"
        return f.date(from: s)!
    }

    /// Saturday afternoon, made up: games kicked off 3.5+ hours ago are final, the rest that started are live.
    private func liveFeed(at now: Date) -> [String: LiveGame] {
        var feed: [String: LiveGame] = [:]
        for g in games {
            guard let kick = g.date, kick <= now, g.gameState != "post" else { continue }
            let n = Int(g.id.suffix(3)) ?? 7
            let final = now.timeIntervalSince(kick) > 3.5 * 3600
            let home = SlateTeam(abbr: g.home.abbr, score: 10 + n % 31, winner: final ? n % 2 == 0 : nil)
            let away = SlateTeam(abbr: g.away.abbr, score: 7 + n % 27, winner: final ? n % 2 != 0 : nil)
            feed[g.id] = LiveGame(id: g.id, state: final ? "post" : "in", statusShort: final ? "Final" : "8:12 - 2nd",
                                  completed: final, home: home, away: away)
        }
        return feed
    }

    func testDecodesEveryGame() {
        XCTAssertEqual(games.count, 56)
        XCTAssertTrue(games.allSatisfy { $0.date != nil })
        XCTAssertEqual(Slate.parseDate("2026-10-24T01:00Z")?.timeIntervalSince1970, 1_792_803_600)
    }

    func testTodayFirst() throws {
        let day = try XCTUnwrap(Slate.day(games, live: [:], filter: .all, now: ct("2026-10-21 12:00")))
        XCTAssertTrue(day.isToday)
        XCTAssertEqual(day.rows.count, 1)               // one Wednesday game
        XCTAssertEqual(day.rows.first?.phase, .upcoming)
    }

    func testSaturdayMorningOrder() throws {
        let day = try XCTUnwrap(Slate.day(games, live: [:], filter: .all, now: ct("2026-10-24 09:00")))
        XCTAssertEqual(day.rows.count, 44)
        let kicks = day.rows.compactMap(\.kickoff)
        XCTAssertEqual(kicks, kicks.sorted())
        XCTAssertNotNil(day.rows.first { $0.weather != nil })   // outdoor kickoffs carry the snapshot forecast
    }

    func testSundayShowsSaturdayFinals() throws {
        let sunday = ct("2026-10-25 10:00")
        let day = try XCTUnwrap(Slate.day(games, live: liveFeed(at: sunday), filter: .all, now: sunday))
        XCTAssertFalse(day.isToday)
        XCTAssertEqual(day.rows.count, 44)
        XCTAssertTrue(day.rows.allSatisfy { $0.phase == .final && $0.showScore })
    }

    func testLiveGamesLead() throws {
        let now = ct("2026-10-24 15:15")
        let day = try XCTUnwrap(Slate.day(games, live: liveFeed(at: now), filter: .all, now: now))
        XCTAssertGreaterThan(day.liveCount, 0)
        XCTAssertEqual(day.rows.first?.phase, .live)
        XCTAssertEqual(day.rows.last?.phase, .final)
        XCTAssertEqual(day.rows.first?.link?.absoluteString.hasPrefix("cfbgameday://game/"), true)
        XCTAssertNil(day.rows.first { $0.phase == .upcoming }?.link)   // the game sheet needs a started game
    }

    func testKickedOffWithoutLiveData() throws {
        let day = try XCTUnwrap(Slate.day(games, live: [:], filter: .all, now: ct("2026-10-24 15:15")))
        XCTAssertEqual(day.liveCount, 0)
        XCTAssertTrue(day.rows.contains { $0.phase == .unknown && !$0.showScore })   // never a made-up 0-0
    }

    func testFilters() throws {
        let sat = ct("2026-10-24 09:00")
        let ranked = try XCTUnwrap(Slate.day(games, live: [:], filter: .ranked, now: sat))
        XCTAssertTrue(ranked.rows.allSatisfy(\.ranked))
        let rivalry = try XCTUnwrap(Slate.day(games, live: [:], filter: .rivalry, now: sat))
        XCTAssertEqual(rivalry.rows.count, 2)            // Floyd of Rosedale, Wagon Wheel
        XCTAssertTrue(rivalry.rows.allSatisfy(\.rivalry))
        // Rivalry on a Wednesday: no trophy game today, so the next day that has one.
        let wed = try XCTUnwrap(Slate.day(games, live: [:], filter: .rivalry, now: ct("2026-10-21 12:00")))
        XCTAssertFalse(wed.isToday)
        XCTAssertEqual(wed.rows.count, 2)
    }

    func testLiveDates() {
        XCTAssertEqual(Slate.liveDates(games, now: ct("2026-10-24 15:15")), ["20261024"])
        XCTAssertEqual(Slate.liveDates(games, now: ct("2026-10-25 10:00")), ["20261024"])   // Saturday's finals
        XCTAssertEqual(Slate.liveDates(games, now: ct("2026-10-24 01:00")), ["20261023"])   // Friday's late games
        XCTAssertTrue(Slate.liveDates(games, now: ct("2026-10-24 06:00")).isEmpty)          // nothing on yet
        XCTAssertTrue(Slate.liveDates(games, now: ct("2026-10-21 12:00")).isEmpty)          // before the Wednesday game
    }

    func testRefreshTiming() {
        let now = ct("2026-10-24 15:15")
        let day = Slate.day(games, live: liveFeed(at: now), filter: .all, now: now)
        XCTAssertEqual(Slate.nextRefresh(day, games: games, filter: .all, now: now), now.addingTimeInterval(600))
        // Wednesday noon: the 7 PM kickoff is past the 3-hour cap.
        let wed = ct("2026-10-21 12:00")
        let wedDay = Slate.day(games, live: [:], filter: .all, now: wed)
        XCTAssertEqual(Slate.nextRefresh(wedDay, games: games, filter: .all, now: wed), wed.addingTimeInterval(3 * 3600))
        // 11:30 PM: the next Central midnight comes first.
        let late = ct("2026-10-21 23:30")
        XCTAssertEqual(Slate.nextRefresh(nil, games: games, filter: .all, now: late), ct("2026-10-22 00:01"))
    }

    // MARK: - Rendered previews (look at them; nothing asserts on pixels)

    @MainActor
    func testRenderWidgets() throws {
        guard let dir = ProcessInfo.processInfo.environment["SNAPSHOT_DIR"] else {
            throw XCTSkip("set TEST_RUNNER_SNAPSHOT_DIR to write widget previews")
        }
        let out = URL(fileURLWithPath: dir)
        try FileManager.default.createDirectory(at: out, withIntermediateDirectories: true)
        let sizes: [(String, WidgetFamily, CGSize)] = [
            ("small", .systemSmall, CGSize(width: 170, height: 170)),
            ("medium", .systemMedium, CGSize(width: 364, height: 170)),
            ("large", .systemLarge, CGSize(width: 364, height: 382)),
            ("rect", .accessoryRectangular, CGSize(width: 172, height: 76)),
            ("inline", .accessoryInline, CGSize(width: 260, height: 24)),
        ]
        let scenes: [(String, Date, SlateFilter, Bool)] = [
            ("sat-live", ct("2026-10-24 15:15"), .all, true),
            ("sat-morning", ct("2026-10-24 09:00"), .all, false),
            ("sat-ranked", ct("2026-10-24 15:15"), .ranked, true),
            ("wed-rivalry", ct("2026-10-21 12:00"), .rivalry, false),
            ("sunday", ct("2026-10-25 10:00"), .all, true),
        ]
        for (scene, now, filter, live) in scenes {
            let feed = live ? liveFeed(at: now) : [:]
            let content = SlateContent(day: Slate.day(games, live: feed, filter: filter, now: now),
                                       filter: filter, updated: now, offline: false)
            for (name, family, size) in sizes {
                try render(SlateView(content: content, family: family), family: family, size: size,
                           to: out.appending(path: "\(scene)-\(name).png"))
            }
        }
        let empty = SlateContent(day: nil, filter: .rivalry, updated: ct("2026-10-21 12:00"), offline: true)
        try render(SlateView(content: empty, family: .systemMedium), family: .systemMedium,
                   size: CGSize(width: 364, height: 170), to: out.appending(path: "empty-medium.png"))
    }

    @MainActor
    private func render(_ view: SlateView, family: WidgetFamily, size: CGSize, to url: URL) throws {
        let accessory = family == .accessoryRectangular || family == .accessoryInline
        let framed = view
            .padding(accessory ? 4 : 16)
            .frame(width: size.width, height: size.height)
            .background(accessory ? Color.black : SlateStyle.bg)
            .clipShape(RoundedRectangle(cornerRadius: accessory ? 8 : 22))
            .environment(\.colorScheme, .dark)
            .foregroundStyle(.white)
        let renderer = ImageRenderer(content: framed)
        renderer.scale = 3
        let png = try XCTUnwrap(renderer.uiImage?.pngData())
        try png.write(to: url)
    }
}
