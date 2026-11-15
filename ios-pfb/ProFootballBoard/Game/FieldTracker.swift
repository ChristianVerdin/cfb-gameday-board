import SwiftUI

/// The current drive on a 120-unit field: end zones in team colours, red zone, start spot and the ball.
struct FieldTracker: View {
    let sheet: GameSheet
    let geometry: TrackerGeometry

    @ScaledMetric(relativeTo: .caption2) private var labelSize = 9.0

    private var tracker: DriveTracker? { sheet.tracker }
    private var offence: Team? { geometry.side == .away ? sheet.teams.away : sheet.teams.home }
    private var drive: Drive? { sheet.drives.first { $0.id == tracker?.driveID } }

    private var caption: String {
        let from = drive?.start?.yardText
        let at = YardText.fromHomeGoal(tracker?.currentYardLine, away: sheet.awayAbbr, home: sheet.homeAbbr)
            ?? drive?.end?.yardText ?? drive?.playList.last { !$0.isAdmin }?.yardText
        return [offence.map { "\($0.abbr) ball" }, from.map { "from \($0)" }, at.map { "now \($0)" }]
            .compactMap { $0 }.joined(separator: " · ")
    }

    private var meta: String {
        guard let t = tracker else { return "" }
        return [t.plays > 0 ? Plural.count(t.plays, "play") : nil, "\(t.yards) yds", t.elapsed].compactMap { $0 }.joined(separator: " · ")
    }

    var body: some View {
        SheetCard {
            VStack(alignment: .leading, spacing: 8) {
                Canvas { ctx, size in draw(&ctx, size) }
                    .aspectRatio(TrackerGeometry.width / 36, contentMode: .fit)
                    .clipShape(RoundedRectangle(cornerRadius: 6, style: .continuous))
                HStack {
                    Text(caption).font(.footnote.weight(.semibold))
                    Spacer()
                    if geometry.redZone {
                        Text("Red zone").font(.caption2.weight(.heavy))
                            .padding(.horizontal, 7).padding(.vertical, 2)
                            .background(Color.red, in: Capsule()).foregroundStyle(.white)
                    }
                }
                if !meta.isEmpty { Text(meta).font(.caption).foregroundStyle(.secondary) }
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(caption), moving \(geometry.direction > 0 ? "right" : "left")\(geometry.redZone ? ", in the red zone" : ""). \(meta)")
    }

    private func draw(_ ctx: inout GraphicsContext, _ size: CGSize) {
        let sx = size.width / TrackerGeometry.width, sy = size.height / 36
        func pt(_ x: Double, _ y: Double) -> CGPoint { CGPoint(x: x * sx, y: y * sy) }
        func rect(_ x: Double, _ w: Double) -> CGRect { CGRect(x: x * sx, y: 0, width: w * sx, height: size.height) }

        ctx.fill(Path(rect(0, TrackerGeometry.width)), with: .color(Color(red: 0.07, green: 0.2, blue: 0.13)))
        let away = sheet.teams.away?.chip.background.color ?? .gray, home = sheet.teams.home?.chip.background.color ?? .gray
        ctx.fill(Path(rect(0, 10)), with: .color(away.opacity(0.75)))
        ctx.fill(Path(rect(110, 10)), with: .color(home.opacity(0.75)))
        ctx.fill(Path(rect(geometry.redZoneX, 20)), with: .color(Color.red.opacity(geometry.redZone ? 0.35 : 0.14)))
        for x in stride(from: 20.0, through: 100, by: 10) {
            var line = Path()
            line.move(to: pt(x, 0)); line.addLine(to: pt(x, 36))
            ctx.stroke(line, with: .color(.white.opacity(0.28)), lineWidth: 1)
        }

        var path = Path()
        path.move(to: pt(geometry.startX, 18)); path.addLine(to: pt(geometry.currentX, 18))
        ctx.stroke(path, with: .color(.white), style: StrokeStyle(lineWidth: 3 * sy / 2, lineCap: .round))

        let startMark = Path(CGRect(x: (geometry.startX - 1.5) * sx, y: 12 * sy, width: 3 * sx, height: 12 * sy))
        ctx.fill(startMark, with: .color(.white.opacity(0.9)))

        var arrow = Path()
        arrow.move(to: pt(geometry.arrowTip, 18))
        arrow.addLine(to: pt(geometry.currentX + geometry.direction, 12.5))
        arrow.addLine(to: pt(geometry.currentX + geometry.direction, 23.5))
        arrow.closeSubpath()
        ctx.fill(arrow, with: .color(.white))

        let r = 3.6
        let ball = Path(ellipseIn: CGRect(x: (geometry.currentX - r) * sx, y: (18 - r) * sy, width: 2 * r * sx, height: 2 * r * sy))
        ctx.fill(ball, with: .color(.orange))
        ctx.stroke(ball, with: .color(.white), lineWidth: 1.5)

        for (abbr, x) in [(sheet.awayAbbr, 5.0), (sheet.homeAbbr, 115.0)] {
            ctx.draw(Text(abbr).font(.system(size: min(labelSize, 12), weight: .heavy)).foregroundStyle(.white.opacity(0.9)), at: pt(x, 18))
        }
    }
}
