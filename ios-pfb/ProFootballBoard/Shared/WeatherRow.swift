import SwiftUI

/// Kickoff-hour forecast, or "Indoors" for a dome. Hidden when the snapshot has no weather for the game.
struct WeatherRow: View {
    let venue: Venue?
    let weather: Weather?
    let status: String?

    private static let staleAfter: TimeInterval = 6 * 3600

    var body: some View {
        if status == "dome" || (venue?.roof == .dome && weather == nil) {
            HStack(spacing: 8) {
                Image(systemName: "building.2").foregroundStyle(BoardTheme.blue)
                Text("Indoors").font(.subheadline.weight(.semibold))
                Text("Dome").font(.caption).foregroundStyle(BoardTheme.muted)
            }
            .accessibilityElement(children: .combine)
            .accessibilityLabel("Weather: indoors, dome")
        } else if let w = weather {
            forecast(w)
        }
    }

    private func forecast(_ w: Weather) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(alignment: .top, spacing: 14) {
                if let t = w.temp {
                    VStack(alignment: .leading, spacing: 0) {
                        Text(degrees(t)).font(.title3.weight(.bold))
                        if let l = w.label { Text(l).font(.caption2).foregroundStyle(BoardTheme.muted).lineLimit(1) }
                    }
                }
                cell("Wind", w.wind.map { "\(Int($0.rounded())) mph" + (w.compass.map { " \($0)" } ?? "") })
                cell("Gusts", w.gusts.map { "\(Int($0.rounded())) mph" })
                cell("Rain", w.precipChance.map { "\(Int($0.rounded()))%" })
                cell("Feels", w.apparent.map(degrees))
                Spacer(minLength: 0)
            }
            if !w.flags.isEmpty {
                HStack(spacing: 6) { ForEach(w.flags, id: \.self) { BoardTag(text: $0, tint: BoardTheme.orange) } }
            }
            if let note = notes(w) {
                Text(note).font(.caption).foregroundStyle(BoardTheme.muted)
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(spoken(w))
    }

    @ViewBuilder private func cell(_ title: String, _ value: String?) -> some View {
        if let value {
            VStack(alignment: .leading, spacing: 1) {
                Text(title).font(.caption2).foregroundStyle(BoardTheme.muted)
                Text(value).font(.footnote.weight(.semibold)).lineLimit(1).minimumScaleFactor(0.8)
            }
        }
    }

    private func degrees(_ v: Double) -> String { "\(Int(v.rounded()))\u{00B0}" }

    private func notes(_ w: Weather) -> String? {
        var parts: [String] = []
        if let roof = w.roofNote { parts.append(roof) }
        if let at = w.fetchedAt, Date().timeIntervalSince(at) > Self.staleAfter {
            parts.append("Forecast from \(Chicago.time(at)), may be out of date.")
        }
        return parts.isEmpty ? nil : parts.joined(separator: " ")
    }

    private func spoken(_ w: Weather) -> String {
        var s = "Weather"
        if let t = w.temp { s += ", \(degrees(t))" }
        if let l = w.label { s += ", \(l)" }
        if let wind = w.wind { s += ", wind \(Int(wind.rounded())) miles per hour" }
        if let g = w.gusts { s += ", gusts \(Int(g.rounded()))" }
        if let p = w.precipChance { s += ", \(Int(p.rounded())) percent chance of rain" }
        if let n = notes(w) { s += ". \(n)" }
        return s
    }
}
