import Foundation

enum Chicago {
    static let zone = TimeZone(identifier: "America/Chicago")!

    static var calendar: Calendar {
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = zone
        cal.locale = Locale(identifier: "en_US_POSIX")
        return cal
    }

    private static func format(_ date: Date, _ pattern: String) -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = zone
        f.dateFormat = pattern
        return f.string(from: date)
    }

    /// "Sun 12:00 PM CT"
    static func kickoff(_ date: Date?, tbd: Bool = false) -> String {
        guard let date, !tbd else { return "TBD" }
        return format(date, "EEE h:mm a") + " CT"
    }

    /// "12:00 PM CT"
    static func time(_ date: Date) -> String { format(date, "h:mm a") + " CT" }

    /// "Sun, Nov 15"
    static func day(_ date: Date) -> String { format(date, "EEE, MMM d") }

    /// "2026-11-15" in Chicago time.
    static func dayKey(_ date: Date) -> String { format(date, "yyyy-MM-dd") }
}

enum PeriodLabel {
    /// 1-4 are quarters, 5 is OT, 6 is 2OT and so on; 0 or less is empty.
    static func of(_ period: Int?) -> String {
        let n = period ?? 0
        if n <= 0 { return "" }
        if n <= 4 { return "Q\(n)" }
        return n == 5 ? "OT" : "\(n - 4)OT"
    }
}
