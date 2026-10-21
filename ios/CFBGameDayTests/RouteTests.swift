import XCTest
@testable import CFBGameDay

final class RouteTests: XCTestCase {
    private func route(_ s: String) -> Route? { Route(url: URL(string: s)!) }

    func testDeepLinks() {
        XCTAssertEqual(route("cfbgameday://rivalry"), Route(tab: .board, fragment: "rivalry"))
        XCTAssertEqual(route("cfbgameday://live"), Route(tab: .live, fragment: "live"))
        XCTAssertEqual(route("cfbgameday://starred"), Route(tab: .starred, fragment: "starred"))
        XCTAssertEqual(route("cfbgameday://tv"), Route(tab: .board, fragment: "tv"))
        XCTAssertEqual(route("cfbgameday://board"), Route(tab: .board, fragment: "all"))
        XCTAssertEqual(route("cfbgameday://"), Route(tab: .board, fragment: "all"))
        XCTAssertEqual(route("cfbgameday://game/401864525"), Route(tab: .board, fragment: "game/401864525"))
        XCTAssertNil(route("cfbgameday://game/12"))
        XCTAssertNil(route("cfbgameday://game/40186452x"))
        XCTAssertNil(route("cfbgameday://settings"))
    }

    func testUniversalLinks() {
        XCTAssertEqual(route("https://cfbgameday.app/#rivalry"), Route(tab: .board, fragment: "rivalry"))
        XCTAssertEqual(route("https://cfbgameday.app/#live"), Route(tab: .live, fragment: "live"))
        XCTAssertEqual(route("https://cfbgameday.app/#starred"), Route(tab: .starred, fragment: "starred"))
        XCTAssertEqual(route("https://cfbgameday.app/#lines"), Route(tab: .board, fragment: "lines"))
        XCTAssertEqual(route("https://www.cfbgameday.app/#tv"), Route(tab: .board, fragment: "tv"))
        XCTAssertEqual(route("https://cfbgameday.app/"), Route(tab: .board, fragment: "all"))
        XCTAssertEqual(route("https://cfbgameday.app"), Route(tab: .board, fragment: "all"))
        XCTAssertEqual(route("https://cfbgameday.app/index.html#game/401864525"), Route(tab: .board, fragment: "game/401864525"))
        XCTAssertNil(route("https://cfbgameday.app/privacy"))
        XCTAssertNil(route("https://cfbgameday.app/support#x"))
        XCTAssertNil(route("https://cfbgameday.app/#game/1"))
        XCTAssertNil(route("https://example.com/#rivalry"))
        XCTAssertNil(route("http://cfbgameday.app/#rivalry"))
    }
}
