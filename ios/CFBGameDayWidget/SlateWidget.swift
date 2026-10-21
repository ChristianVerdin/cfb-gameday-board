import AppIntents
import SwiftUI
import WidgetKit

@main
struct CFBGameDayWidgets: WidgetBundle {
    var body: some Widget {
        SlateWidget()
    }
}

/// Literal statics: the App Intents metadata step reads them at build time.
enum SlateShow: String, AppEnum {
    case all, ranked, rivalry

    static var typeDisplayRepresentation: TypeDisplayRepresentation = "Games"
    static var caseDisplayRepresentations: [SlateShow: DisplayRepresentation] = [
        .all: "All games",
        .ranked: "Top 25",
        .rivalry: "Rivalry games",
    ]

    var filter: SlateFilter { SlateFilter(rawValue: rawValue) ?? .all }
}

struct SlateIntent: WidgetConfigurationIntent {
    static var title: LocalizedStringResource = "Games"
    static var description = IntentDescription("Choose which games the widget shows.")

    @Parameter(title: "Show", default: .all)
    var show: SlateShow
}

struct SlateEntry: TimelineEntry {
    let date: Date
    let content: SlateContent
}

struct SlateProvider: AppIntentTimelineProvider {
    func placeholder(in context: Context) -> SlateEntry {
        SlateEntry(date: .now, content: .placeholder)
    }

    func snapshot(for configuration: SlateIntent, in context: Context) async -> SlateEntry {
        let now = Date()
        // The widget gallery wants an answer fast: the last copy if there is one, else the network.
        var loaded = await SlateStore.load(now: now, cachedOnly: context.isPreview)
        if loaded.games.isEmpty, context.isPreview { loaded = await SlateStore.load(now: now) }
        return SlateEntry(date: now, content: SlateContent(loaded, filter: configuration.show.filter, now: now))
    }

    func timeline(for configuration: SlateIntent, in context: Context) async -> Timeline<SlateEntry> {
        let now = Date()
        let filter = configuration.show.filter
        let loaded = await SlateStore.load(now: now)
        let content = SlateContent(loaded, filter: filter, now: now)
        // Nothing loaded at all (first run offline): try again soon rather than in hours.
        let next = loaded.games.isEmpty ? now.addingTimeInterval(15 * 60)
            : Slate.nextRefresh(content.day, games: loaded.games, filter: filter, now: now)
        return Timeline(entries: [SlateEntry(date: now, content: content)], policy: .after(next))
    }
}

struct SlateWidgetView: View {
    @Environment(\.widgetFamily) private var family
    let entry: SlateEntry

    var body: some View {
        SlateView(content: entry.content, family: family)   // each layout sets its own widgetURL
            .containerBackground(for: .widget) {
                switch family {
                case .accessoryInline, .accessoryRectangular, .accessoryCircular: Color.clear
                default: SlateStyle.bg
                }
            }
    }
}

struct SlateWidget: Widget {
    var body: some WidgetConfiguration {
        AppIntentConfiguration(kind: "Slate", intent: SlateIntent.self, provider: SlateProvider()) { entry in
            SlateWidgetView(entry: entry)
        }
        .configurationDisplayName("Today's Games")
        .description("Live scores, kickoff times and TV for the day's college football games.")
        .supportedFamilies([.systemSmall, .systemMedium, .systemLarge, .accessoryRectangular, .accessoryInline])
    }
}
