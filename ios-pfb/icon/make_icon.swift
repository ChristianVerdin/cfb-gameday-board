// Draws the 1024x1024 app icon. Usage: swift icon/make_icon.swift <output.png>
import AppKit
import CoreGraphics

let size = 1024
let out = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "icon.png"
let space = CGColorSpace(name: CGColorSpace.sRGB)!
let ctx = CGContext(data: nil, width: size, height: size, bitsPerComponent: 8, bytesPerRow: 0,
                    space: space, bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue)!

func rgb(_ r: Int, _ g: Int, _ b: Int, _ a: CGFloat = 1) -> CGColor {
    CGColor(colorSpace: space, components: [CGFloat(r) / 255, CGFloat(g) / 255, CGFloat(b) / 255, a])!
}
let gold = rgb(240, 180, 41)
let S = CGFloat(size)

let bg = CGGradient(colorsSpace: space, colors: [rgb(18, 38, 84), rgb(6, 12, 30)] as CFArray, locations: [0, 1])!
ctx.drawRadialGradient(bg, startCenter: CGPoint(x: S / 2, y: S * 0.62), startRadius: 0,
                       endCenter: CGPoint(x: S / 2, y: S * 0.62), endRadius: S * 0.85, options: .drawsAfterEndLocation)

// Yard lines with hash marks, receding into a faint perspective fade.
ctx.setStrokeColor(rgb(240, 180, 41, 0.34))
ctx.setLineWidth(10)
for i in 0..<7 {
    let y = S * (0.10 + CGFloat(i) * 0.135)
    ctx.move(to: CGPoint(x: 0, y: y)); ctx.addLine(to: CGPoint(x: S, y: y))
}
ctx.strokePath()
ctx.setLineWidth(6)
for i in 0..<7 {
    let y = S * (0.10 + CGFloat(i) * 0.135)
    for j in 1..<5 {
        let ys = y + S * 0.135 * CGFloat(j) / 5
        for x in [S * 0.16, S * 0.84] {
            ctx.move(to: CGPoint(x: x - 18, y: ys)); ctx.addLine(to: CGPoint(x: x + 18, y: ys))
        }
    }
}
ctx.strokePath()

// Football: two arcs forming a pointed ellipse, tilted, with laces.
ctx.saveGState()
ctx.translateBy(x: S / 2, y: S / 2)
ctx.rotate(by: .pi / 5.2)
let L: CGFloat = 330, H: CGFloat = 175
let ball = CGMutablePath()
ball.move(to: CGPoint(x: -L, y: 0))
ball.addQuadCurve(to: CGPoint(x: L, y: 0), control: CGPoint(x: 0, y: H * 2))
ball.addQuadCurve(to: CGPoint(x: -L, y: 0), control: CGPoint(x: 0, y: -H * 2))
ball.closeSubpath()
ctx.setShadow(offset: CGSize(width: 0, height: -26), blur: 50, color: rgb(0, 0, 0, 0.55))
ctx.addPath(ball); ctx.setFillColor(gold); ctx.fillPath()
ctx.setShadow(offset: .zero, blur: 0, color: nil)
ctx.addPath(ball); ctx.clip()
let shade = CGGradient(colorsSpace: space, colors: [rgb(255, 214, 102, 0.0), rgb(150, 92, 10, 0.55)] as CFArray, locations: [0, 1])!
ctx.drawLinearGradient(shade, start: CGPoint(x: 0, y: H), end: CGPoint(x: 0, y: -H), options: [])
ctx.resetClip()

let navy = rgb(10, 22, 52)
ctx.setStrokeColor(navy); ctx.setLineCap(.butt)
ctx.addPath(ball); ctx.clip()
ctx.setLineWidth(22)
for sx: CGFloat in [-1, 1] {   // end stripes
    let x = sx * (L - 110)
    ctx.move(to: CGPoint(x: x, y: -78)); ctx.addLine(to: CGPoint(x: x, y: 78))
    ctx.move(to: CGPoint(x: x + sx * 42, y: -64)); ctx.addLine(to: CGPoint(x: x + sx * 42, y: 64))
}
ctx.strokePath()
ctx.resetClip()
ctx.setLineCap(.round)
ctx.setLineWidth(18)
ctx.move(to: CGPoint(x: -120, y: 0)); ctx.addLine(to: CGPoint(x: 120, y: 0))
for k in -2...2 {
    let x = CGFloat(k) * 56
    ctx.move(to: CGPoint(x: x, y: -40)); ctx.addLine(to: CGPoint(x: x, y: 40))
}
ctx.strokePath()
ctx.restoreGState()

let rep = NSBitmapImageRep(cgImage: ctx.makeImage()!)
try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: out))
