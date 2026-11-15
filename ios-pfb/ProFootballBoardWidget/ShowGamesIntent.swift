import AppIntents
import WidgetKit

enum ShowMode: String, AppEnum {
    case all, live, team

    static let typeDisplayRepresentation = TypeDisplayRepresentation(name: "Show")
    static let caseDisplayRepresentations: [ShowMode: DisplayRepresentation] = [
        .all: "All games", .live: "Live now", .team: "One team",
    ]
}

struct ShowGamesIntent: WidgetConfigurationIntent {
    static let title: LocalizedStringResource = "Games to show"
    static let description = IntentDescription("Choose all games, live games, or one team.")

    @Parameter(title: "Show", default: .all)
    var mode: ShowMode

    @Parameter(title: "Team", default: .KC)
    var team: TeamOption

    static var parameterSummary: some ParameterSummary {
        When(\.$mode, .equalTo, ShowMode.team) {
            Summary("Show \(\.$mode): \(\.$team)")
        } otherwise: {
            Summary("Show \(\.$mode)")
        }
    }

    var scope: WidgetScope {
        switch mode {
        case .all: .all
        case .live: .live
        case .team: .team(team.abbr)
        }
    }
}
