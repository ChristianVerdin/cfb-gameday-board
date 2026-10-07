import Foundation

/// Decides when asking for an App Store rating is reasonable.
///
/// StoreKit decides whether the sheet actually appears (at most three times a year,
/// never in TestFlight), so this only gates the ask: three separate days of use, a week
/// after first launch, never twice for the same version, and never from a button.
enum ReviewPrompt {
    private static let defaults = UserDefaults.standard
    private static let daysKey = "review.days"
    private static let firstKey = "review.first"
    private static let askedKey = "review.askedVersion"

    static let minDays = 3
    static let minAge: TimeInterval = 7 * 24 * 60 * 60

    private static var version: String {
        Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "?"
    }

    /// Records today as a day of use, then reports whether to ask now.
    static func shouldAsk(now: Date = Date()) -> Bool {
        let day = ISO8601DateFormatter.string(from: now, timeZone: .current, formatOptions: [.withFullDate])
        var days = defaults.stringArray(forKey: daysKey) ?? []
        if !days.contains(day) {
            days = Array((days + [day]).suffix(30))
            defaults.set(days, forKey: daysKey)
        }
        let first = defaults.object(forKey: firstKey) as? Date ?? now
        if defaults.object(forKey: firstKey) == nil { defaults.set(now, forKey: firstKey) }

        #if DEBUG
        // simctl launch <udid> com.hoynelabs.cfbgameday -review.force YES
        if defaults.bool(forKey: "review.force") { return true }
        #endif
        guard defaults.string(forKey: askedKey) != version else { return false }
        return days.count >= minDays && now.timeIntervalSince(first) >= minAge
    }

    static func markAsked() {
        defaults.set(version, forKey: askedKey)
    }
}
