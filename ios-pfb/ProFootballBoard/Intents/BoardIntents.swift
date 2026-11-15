import AppIntents
import UIKit

enum IntentRouteError: Error, CustomLocalizedStringResourceConvertible {
    case badGameID

    var localizedStringResource: LocalizedStringResource { "That doesn't look like a game ID." }
}

/// Hands a `pfb://` link to the app, which routes it through `Router`.
@MainActor
private func open(_ url: URL) async {
    await UIApplication.shared.open(url)
}

struct OpenGameIntent: AppIntent {
    static let title: LocalizedStringResource = "Open Game"
    static let description = IntentDescription("Opens a game sheet by its ID.")
    static let openAppWhenRun = true

    @Parameter(title: "Game ID")
    var gameID: String

    init() {}
    init(gameID: String) { self.gameID = gameID }

    static var parameterSummary: some ParameterSummary { Summary("Open game \(\.$gameID)") }

    @MainActor
    func perform() async throws -> some IntentResult {
        let id = gameID.trimmingCharacters(in: .whitespaces)
        guard let url = URL(string: "pfb://game/\(id)"), Route(url: url) != nil else { throw IntentRouteError.badGameID }
        await open(url)
        return .result()
    }
}

struct ShowLiveGamesIntent: AppIntent {
    static let title: LocalizedStringResource = "Show Live Games"
    static let description = IntentDescription("Opens the Live tab.")
    static let openAppWhenRun = true

    @MainActor
    func perform() async throws -> some IntentResult {
        await open(URL(string: "pfb://live")!)
        return .result()
    }
}

struct OpenBoardIntent: AppIntent {
    static let title: LocalizedStringResource = "Open Board"
    static let description = IntentDescription("Opens the board with every game this week.")
    static let openAppWhenRun = true

    @MainActor
    func perform() async throws -> some IntentResult {
        await open(URL(string: "pfb://board")!)
        return .result()
    }
}

struct ProFootballBoardShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(intent: ShowLiveGamesIntent(),
                    phrases: ["Show live games in \(.applicationName)", "Live games in \(.applicationName)"],
                    shortTitle: "Live Games", systemImageName: "dot.radiowaves.left.and.right")
        AppShortcut(intent: OpenBoardIntent(),
                    phrases: ["Open \(.applicationName)", "Show the board in \(.applicationName)"],
                    shortTitle: "Open Board", systemImageName: "sportscourt")
    }
}
