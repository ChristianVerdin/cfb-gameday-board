import SwiftUI

struct RGB: Equatable, Sendable {
    var r: Double
    var g: Double
    var b: Double

    init(r: Double, g: Double, b: Double) { self.r = r; self.g = g; self.b = b }

    /// Six hex digits, with or without a leading `#`; anything else is nil.
    init?(hex: String?) {
        guard let hex else { return nil }
        let s = hex.hasPrefix("#") ? String(hex.dropFirst()) : hex
        guard s.count == 6, let v = UInt32(s, radix: 16) else { return nil }
        self.init(r: Double((v >> 16) & 0xFF) / 255, g: Double((v >> 8) & 0xFF) / 255, b: Double(v & 0xFF) / 255)
    }

    var luminance: Double {
        func lin(_ c: Double) -> Double { c <= 0.03928 ? c / 12.92 : pow((c + 0.055) / 1.055, 2.4) }
        return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
    }

    func contrast(with other: RGB) -> Double {
        let x = luminance, y = other.luminance
        return (max(x, y) + 0.05) / (min(x, y) + 0.05)
    }

    var color: Color { Color(red: r, green: g, blue: b) }

    static let white = RGB(hex: "ffffff")!
    static let ink = RGB(hex: "111111")!
    static let card = RGB(hex: "162036")!
    static let neutralBG = RGB(hex: "2a3a5a")!
    static let neutralFG = RGB(hex: "f4f7fb")!
}

struct ChipColors: Equatable, Sendable {
    var background: RGB
    var foreground: RGB
}

enum TeamColors {
    /// The team colour, else its alternate, when readable on the card and able to carry white or dark text;
    /// otherwise a neutral navy chip.
    static func chip(color: String?, alt: String?, card: RGB = .card) -> ChipColors {
        for hex in [color, alt] {
            guard let bg = RGB(hex: hex), bg.contrast(with: card) >= 1.4 else { continue }
            let w = bg.contrast(with: .white), k = bg.contrast(with: .ink)
            if max(w, k) >= 3.5 { return ChipColors(background: bg, foreground: w >= k ? .white : .ink) }
        }
        return ChipColors(background: .neutralBG, foreground: .neutralFG)
    }
}
