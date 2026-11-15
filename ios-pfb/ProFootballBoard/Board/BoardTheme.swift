import SwiftUI

/// Colours shared with the web board's stylesheet.
enum BoardTheme {
    static let bg = Color(red: 0x0b / 255, green: 0x12 / 255, blue: 0x20 / 255)
    static let card = RGB.card.color
    static let card2 = Color(red: 0x1b / 255, green: 0x27 / 255, blue: 0x40 / 255)
    static let line = RGB.neutralBG.color
    static let text = RGB.neutralFG.color
    static let muted = Color(red: 0x9a / 255, green: 0xa8 / 255, blue: 0xbf / 255)
    static let gold = Color(red: 0xe8 / 255, green: 0xc3 / 255, blue: 0x6a / 255)
    static let blue = Color(red: 0x7e / 255, green: 0xb6 / 255, blue: 0xff / 255)
    static let green = Color(red: 0x5d / 255, green: 0xca / 255, blue: 0xa5 / 255)
    static let red = Color(red: 1, green: 0x7a / 255, blue: 0x7a / 255)
    static let orange = Color(red: 1, green: 0xb0 / 255, blue: 0x60 / 255)
    static let chip = Color(red: 0x22 / 255, green: 0x31 / 255, blue: 0x4d / 255)
}

struct BoardTag: View {
    let text: String
    var tint: Color = BoardTheme.muted
    var filled = false

    var body: some View {
        Text(text)
            .font(.caption2.weight(.semibold))
            .textCase(.uppercase)
            .padding(.horizontal, 7)
            .padding(.vertical, 3)
            .foregroundStyle(filled ? Color.black : tint)
            .background(filled ? tint : tint.opacity(0.14), in: Capsule())
            .lineLimit(1)
    }
}
