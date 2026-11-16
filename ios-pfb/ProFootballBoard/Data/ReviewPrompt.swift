import Foundation

/// Decides when asking for an App Store rating is reasonable.
///
/// StoreKit decides whether the sheet actually appears (at most three times a year, never in TestFlight), so this
/// only gates the ask: three separate days of use, a week after first launch, never twice for the same version,
/// and never while a game is live or a game sheet is open (the caller checks that). The counts stay on the device.
struct ReviewPrompt {
    static var shared: ReviewPrompt { ReviewPrompt() }

    static let minDays = 3
    static let minAge: TimeInterval = 7 * 24 * 60 * 60

    private let defaults: UserDefaults
    private let version: String
    private let daysKey = "review.days"
    private let firstKey = "review.first"
    private let askedKey = "review.askedVersion"

    init(defaults: UserDefaults = .standard,
         version: String = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "?") {
        self.defaults = defaults
        self.version = version
    }

    /// Records today as a day of use, then reports whether the thresholds are met.
    func shouldAsk(now: Date = Date()) -> Bool {
        let day = Chicago.dayKey(now)
        var days = defaults.stringArray(forKey: daysKey) ?? []
        if !days.contains(day) {
            days = Array((days + [day]).suffix(30))
            defaults.set(days, forKey: daysKey)
        }
        let first = defaults.object(forKey: firstKey) as? Date ?? now
        if defaults.object(forKey: firstKey) == nil { defaults.set(now, forKey: firstKey) }

        #if DEBUG
        // simctl launch <udid> com.hoynelabs.profootballboard -review.force YES
        if defaults.bool(forKey: "review.force") { return defaults.string(forKey: askedKey) != version }
        #endif
        guard defaults.string(forKey: askedKey) != version else { return false }
        return days.count >= Self.minDays && now.timeIntervalSince(first) >= Self.minAge
    }

    func markAsked() {
        defaults.set(version, forKey: askedKey)
    }
}
