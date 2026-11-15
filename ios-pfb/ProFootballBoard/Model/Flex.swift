import Foundation

/// Decodes one array element, turning a malformed element into nil instead of failing the array.
struct Lossy<T: Decodable>: Decodable {
    let value: T?
    init(from decoder: Decoder) throws {
        value = try? T(from: decoder)
    }
}

extension KeyedDecodingContainer {
    func str(_ key: Key) -> String? {
        if let s = try? decodeIfPresent(String.self, forKey: key) { return s }
        if let i = try? decodeIfPresent(Int.self, forKey: key) { return String(i) }
        return nil
    }

    func int(_ key: Key) -> Int? {
        if let i = try? decodeIfPresent(Int.self, forKey: key) { return i }
        if let d = try? decodeIfPresent(Double.self, forKey: key), d.isFinite { return Int(d.rounded()) }
        if let s = try? decodeIfPresent(String.self, forKey: key) {
            let t = s.trimmingCharacters(in: .whitespaces)
            if let i = Int(t) { return i }
            if let d = Double(t), d.isFinite { return Int(d.rounded()) }
        }
        return nil
    }

    func dbl(_ key: Key) -> Double? {
        if let d = try? decodeIfPresent(Double.self, forKey: key), d.isFinite { return d }
        if let s = try? decodeIfPresent(String.self, forKey: key), let d = Double(s.trimmingCharacters(in: .whitespaces)), d.isFinite { return d }
        return nil
    }

    func flag(_ key: Key) -> Bool? {
        if let b = try? decodeIfPresent(Bool.self, forKey: key) { return b }
        if let i = try? decodeIfPresent(Int.self, forKey: key) { return i != 0 }
        if let s = try? decodeIfPresent(String.self, forKey: key) { return ["true", "1", "yes"].contains(s.lowercased()) }
        return nil
    }

    func obj<T: Decodable>(_ key: Key, as type: T.Type = T.self) -> T? {
        (try? decodeIfPresent(T.self, forKey: key)) ?? nil
    }

    /// An array whose bad elements are dropped; a missing or non-array value is empty.
    func list<T: Decodable>(_ key: Key, of type: T.Type = T.self) -> [T] {
        ((try? decodeIfPresent([Lossy<T>].self, forKey: key)) ?? nil)?.compactMap(\.value) ?? []
    }

    func strings(_ key: Key) -> [String] {
        list(key, of: String.self)
    }
}

enum ISODate {
    /// Parses ESPN and board timestamps: `2026-11-15T18:00Z`, `...T18:00:30Z`, `...T14:52:51-06:00`.
    static func parse(_ raw: String?) -> Date? {
        guard let raw = raw?.trimmingCharacters(in: .whitespaces), raw.count >= 16 else { return nil }
        let chars = Array(raw.utf8)
        func num(_ from: Int, _ len: Int) -> Int? {
            guard from + len <= chars.count else { return nil }
            var n = 0
            for b in chars[from..<(from + len)] {
                guard (48...57).contains(b) else { return nil }
                n = n * 10 + Int(b - 48)
            }
            return n
        }
        guard let y = num(0, 4), let mo = num(5, 2), let d = num(8, 2), let h = num(11, 2), let mi = num(14, 2),
              chars[4] == 45, chars[7] == 45, chars[10] == 84 || chars[10] == 32, chars[13] == 58 else { return nil }
        var idx = 16
        var sec = 0
        if idx < chars.count, chars[idx] == 58 {
            guard let s = num(idx + 1, 2) else { return nil }
            sec = s
            idx += 3
            if idx < chars.count, chars[idx] == 46 {
                idx += 1
                while idx < chars.count, (48...57).contains(chars[idx]) { idx += 1 }
            }
        }
        var offset = 0
        if idx < chars.count, chars[idx] == 43 || chars[idx] == 45 {
            let sign = chars[idx] == 45 ? -1 : 1
            guard let oh = num(idx + 1, 2) else { return nil }
            var om = 0
            if idx + 3 < chars.count {
                let at = chars[idx + 3] == 58 ? idx + 4 : idx + 3
                om = num(at, 2) ?? 0
            }
            offset = sign * (oh * 3600 + om * 60)
        }
        var comps = DateComponents()
        comps.year = y; comps.month = mo; comps.day = d; comps.hour = h; comps.minute = mi; comps.second = sec
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = TimeZone(secondsFromGMT: 0)!
        guard let date = cal.date(from: comps) else { return nil }
        return date.addingTimeInterval(TimeInterval(-offset))
    }
}
