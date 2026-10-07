// Text frames for scripts/app_video.py (this machine's ffmpeg has no drawtext/libass).
//   swift scripts/render_text.swift caption "text" out.png     1000 px wide, transparent, dark pill
//   swift scripts/render_text.swift card icon.png out.png      1080x1920 end card
import AppKit

let bg = NSColor(srgbRed: 0x0b / 255, green: 0x12 / 255, blue: 0x20 / 255, alpha: 1)
let gold = NSColor(srgbRed: 0.95, green: 0.78, blue: 0.36, alpha: 1)

func png(_ size: NSSize, _ draw: () -> Void) -> Data {
    let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: Int(size.width), pixelsHigh: Int(size.height),
                               bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
                               colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
    draw()
    NSGraphicsContext.restoreGraphicsState()
    return rep.representation(using: .png, properties: [:])!
}

func para(_ size: CGFloat, _ weight: NSFont.Weight, _ color: NSColor) -> [NSAttributedString.Key: Any] {
    let p = NSMutableParagraphStyle(); p.alignment = .center; p.lineBreakMode = .byWordWrapping
    return [.font: NSFont.systemFont(ofSize: size, weight: weight), .foregroundColor: color, .paragraphStyle: p]
}

let args = CommandLine.arguments
switch args[1] {
case "caption":
    let text = NSAttributedString(string: args[2], attributes: para(52, .bold, .white))
    let W: CGFloat = 1000, pad: CGFloat = 34
    let box = text.boundingRect(with: NSSize(width: W - 2 * pad, height: 1000), options: [.usesLineFragmentOrigin])
    let H = ceil(box.height) + 2 * pad
    try! png(NSSize(width: W, height: H)) {
        NSColor(white: 0, alpha: 0.72).setFill()
        NSBezierPath(roundedRect: NSRect(x: 0, y: 0, width: W, height: H), xRadius: 30, yRadius: 30).fill()
        text.draw(with: NSRect(x: pad, y: pad, width: W - 2 * pad, height: ceil(box.height)), options: [.usesLineFragmentOrigin])
    }.write(to: URL(fileURLWithPath: args[3]))
case "card":
    let icon = NSImage(contentsOfFile: args[2])!
    try! png(NSSize(width: 1080, height: 1920)) {
        bg.setFill(); NSRect(x: 0, y: 0, width: 1080, height: 1920).fill()
        let s: CGFloat = 300
        let r = NSRect(x: (1080 - s) / 2, y: 1150, width: s, height: s)
        NSGraphicsContext.saveGraphicsState()
        NSBezierPath(roundedRect: r, xRadius: 66, yRadius: 66).addClip()
        icon.draw(in: r)
        NSGraphicsContext.restoreGraphicsState()
        func line(_ t: String, _ y: CGFloat, _ a: [NSAttributedString.Key: Any]) {
            NSAttributedString(string: t, attributes: a).draw(in: NSRect(x: 40, y: y, width: 1000, height: 120))
        }
        line("CFB GameDay Board", 980, para(84, .heavy, .white))
        line("Every FBS game. Weather, TV, lines, live.", 850, para(44, .medium, NSColor(white: 0.75, alpha: 1)))
        line("cfbgameday.app", 680, para(72, .bold, gold))
        line("Free on the App Store", 590, para(48, .semibold, .white))
    }.write(to: URL(fileURLWithPath: args[3]))
default:
    fatalError("usage: caption TEXT OUT | card ICON OUT")
}
