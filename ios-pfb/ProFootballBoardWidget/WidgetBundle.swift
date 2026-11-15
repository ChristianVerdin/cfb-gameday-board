import SwiftUI
import WidgetKit

struct SlateWidget: Widget {
    static let kind = "ProFootballBoardSlate"

    var body: some WidgetConfiguration {
        AppIntentConfiguration(kind: Self.kind, intent: ShowGamesIntent.self, provider: SlateProvider()) { entry in
            SlateEntryView(entry: entry)
        }
        .configurationDisplayName("Pro Football Board")
        .description("Scores, clock and kickoff times for every game, live games only, or one team.")
        .supportedFamilies([.systemSmall, .systemMedium, .systemLarge, .accessoryRectangular, .accessoryInline])
    }
}

@main
struct ProFootballBoardWidgets: WidgetBundle {
    var body: some Widget { SlateWidget() }
}
