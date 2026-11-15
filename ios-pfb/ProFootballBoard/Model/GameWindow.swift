import Foundation

/// The broadcast slot a game belongs to; ports nflWindowOf from the web board.
enum GameWindow: Hashable, Sendable {
    case flex, christmas, thanksgiving, wednesday, blackFriday, thursdayNight, friday, saturday
    case international, sundayEarly, sundayLate, sundayNight, mondayNight, proBowl, other
    case postseason(String)

    var label: String {
        switch self {
        case .flex: "Flex TBD"
        case .christmas: "Christmas"
        case .thanksgiving: "Thanksgiving"
        case .wednesday: "Wed night"
        case .blackFriday: "Black Friday"
        case .thursdayNight: "TNF"
        case .friday: "Friday"
        case .saturday: "Saturday"
        case .international: "Int'l AM"
        case .sundayEarly: "Sun early"
        case .sundayLate: "Sun late"
        case .sundayNight: "SNF"
        case .mondayNight: "MNF"
        case .proBowl: "Pro Bowl"
        case .other: "Other"
        case .postseason(let round): round
        }
    }

    static func classify(date: Date?, timeTBD: Bool, kind: GameKind, round: String?, abroad: Bool) -> GameWindow {
        if kind == .allStar { return .proBowl }
        if kind == .playoff { return .postseason(round ?? "Playoffs") }
        guard let date, !timeTBD else { return .flex }
        let cal = Chicago.calendar
        let p = cal.dateComponents([.month, .day, .weekday, .hour, .minute], from: date)
        let month = p.month ?? 0, day = p.day ?? 0
        let minutes = (p.hour ?? 0) * 60 + (p.minute ?? 0)
        if month == 12 && (day == 24 || day == 25) { return .christmas }
        switch p.weekday ?? 0 {
        case 5 where month == 11 && (22...28).contains(day): return .thanksgiving
        case 4: return .wednesday
        case 6 where month == 11 && (23...29).contains(day): return .blackFriday
        case 5: return .thursdayNight
        case 6: return .friday
        case 7: return .saturday
        case 1:
            if minutes < 11 * 60 && abroad { return .international }
            if minutes < 12 * 60 + 30 { return .sundayEarly }
            if minutes < 18 * 60 { return .sundayLate }
            return .sundayNight
        case 2: return .mondayNight
        default: return .other
        }
    }

    /// Windows in the order of their earliest kickoff.
    static func ordered(_ games: [BoardGame]) -> [GameWindow] {
        var first: [GameWindow: TimeInterval] = [:]
        for g in games {
            let t = g.kickoffSortKey
            if first[g.window].map({ t < $0 }) ?? true { first[g.window] = t }
        }
        return first.sorted { a, b in a.value != b.value ? a.value < b.value : a.key.label < b.key.label }.map(\.key)
    }
}
