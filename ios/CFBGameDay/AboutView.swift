import SwiftUI

struct AboutView: View {
    @ObservedObject var container: WebContainer

    var body: some View {
        NavigationStack {
            List {
                Section {
                    HStack(spacing: 14) {
                        Image("AppIconPreview")
                            .resizable()
                            .frame(width: 56, height: 56)
                            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                        VStack(alignment: .leading, spacing: 2) {
                            Text("CFB GameDay Board").font(.headline)
                            Text("Version \(AppConfig.version)").font(.subheadline).foregroundStyle(.secondary)
                        }
                    }
                    .padding(.vertical, 4)
                }

                Section("What it shows") {
                    Text("College football slate in one place: venue, kickoff-hour weather, TV and streaming, publicly posted lines with implied scores, then live score, clock, and cover/total state. Times in US Central.")
                        .font(.subheadline)
                }

                Section("Data") {
                    LabeledContent("Scores, schedules, lines", value: "ESPN")
                    LabeledContent("Weather", value: "Open-Meteo")
                    LabeledContent("Refresh", value: "Every 30 s while games run")
                }

                Section("Links") {
                    Link(destination: AppConfig.privacyURL) { Label("Privacy policy", systemImage: "hand.raised") }
                    Link(destination: AppConfig.supportURL) { Label("Support", systemImage: "questionmark.circle") }
                    Link(destination: AppConfig.sourceURL) { Label("Source on GitHub", systemImage: "chevron.left.forwardslash.chevron.right") }
                }

                Section {
                    Button { container.reload() } label: { Label("Reload board", systemImage: "arrow.clockwise") }
                }

                Section {
                    Text("Not a sportsbook. No wagers, deposits, or payments. Lines are shown for context only. Not betting advice.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
            }
            .navigationTitle("About")
        }
    }
}
