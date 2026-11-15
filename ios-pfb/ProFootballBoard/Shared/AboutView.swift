import SwiftUI

struct AboutView: View {
    static let disclaimer = "Independent and unofficial. Not affiliated with, endorsed or sponsored by the National Football League or any team. Scores and play data via ESPN. Season metrics from nflverse (CC BY 4.0). Weather by Open-Meteo.com (CC BY 4.0)."

    private static let privacyURL = URL(string: "https://cfbgameday.app/nfl/privacy")!
    private static let supportURL = URL(string: "https://cfbgameday.app/nfl/support")!

    private var version: String {
        let info = Bundle.main.infoDictionary
        let short = info?["CFBundleShortVersionString"] as? String ?? "1.0.0"
        let build = info?["CFBundleVersion"] as? String ?? "1"
        return "\(short) (\(build))"
    }

    var body: some View {
        NavigationStack {
            List {
                Section {
                    Text("Pro Football Board puts the week's pro football slate on one screen: kickoff times in Central, TV, venue and kickoff-hour weather, then live score, clock, down and distance, drives, win probability and season metrics once games start.")
                    Text("Stats only. No accounts, no ads, no tracking.")
                        .foregroundStyle(.secondary)
                }
                Section("Data") {
                    Label("Scores and play data via ESPN", systemImage: "sportscourt")
                    Label("Season metrics from nflverse (CC BY 4.0)", systemImage: "chart.bar")
                    Label("Weather by Open-Meteo.com (CC BY 4.0)", systemImage: "cloud.sun")
                }
                Section("Links") {
                    Link(destination: Self.supportURL) { Label("Support", systemImage: "questionmark.circle") }
                    Link(destination: Self.privacyURL) { Label("Privacy policy", systemImage: "hand.raised") }
                }
                Section {
                    Text(Self.disclaimer)
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
                Section {
                    LabeledContent("Version", value: version)
                }
            }
            .scrollContentBackground(.hidden)
            .background(BoardTheme.bg.ignoresSafeArea())
            .navigationTitle("About")
        }
    }
}

#Preview { AboutView() }
