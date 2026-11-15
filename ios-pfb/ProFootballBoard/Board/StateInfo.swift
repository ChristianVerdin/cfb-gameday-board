import Foundation

/// The pill and clock text a game shows, following the web board's stateInfo.
struct StateInfo: Equatable {
    enum Tone { case live, half, final, alert }
    var pill: String
    var text: String
    var tone: Tone

    init?(_ g: BoardGame) {
        switch g.status {
        case "STATUS_POSTPONED": self = .init(pill: "Postponed", text: "", tone: .alert)
        case "STATUS_CANCELED": self = .init(pill: "Canceled", text: "", tone: .alert)
        default:
            switch g.state {
            case .post: self = .init(pill: g.ot ? "Final/OT" : "Final", text: g.result == .tie ? "Tie game" : "", tone: .final)
            case .pre: return nil
            case .in:
                let period = g.periodLabel.isEmpty ? PeriodLabel.of(g.period) : g.periodLabel
                switch g.status {
                case "STATUS_HALFTIME": self = .init(pill: "Half", text: "Halftime", tone: .half)
                case "STATUS_END_PERIOD": self = .init(pill: "Live", text: "End of \(period)", tone: .live)
                case "STATUS_DELAYED": self = .init(pill: "Delayed", text: "\(period) \(g.clock)", tone: .alert)
                case "STATUS_SUSPENDED": self = .init(pill: "Suspended", text: "\(period) \(g.clock)", tone: .alert)
                default:
                    if g.statusShort.hasPrefix("End of ") {
                        self = .init(pill: "Live", text: g.statusShort, tone: .live)
                    } else {
                        self = .init(pill: "Live", text: "\(period) \(g.clock)".trimmingCharacters(in: .whitespaces), tone: .live)
                    }
                }
            }
        }
    }

    private init(pill: String, text: String, tone: Tone) { self.pill = pill; self.text = text; self.tone = tone }
}
