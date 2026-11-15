import SwiftUI

/// A flat field drawn left to right: away end zone, 100 yards, home end zone. Marks the ball, the first-down
/// marker and the red zone in front of the goal being attacked.
struct FieldStrip: View {
    let situation: Situation
    let away: Team
    let home: Team

    var body: some View {
        if let pos = FieldPosition(situation) {
            strip(pos)
                .frame(height: 16)
                .accessibilityElement()
                .accessibilityLabel(label(pos))
        }
    }

    private func label(_ pos: FieldPosition) -> String {
        let offense = situation.possessionAbbr ?? (pos.possession == .away ? away.abbr : home.abbr)
        let yards = Int(pos.yardsToGoal.rounded())
        return "\(offense) ball, \(yards) yards from the goal line" + (situation.isRedZone ? ", red zone" : "")
    }

    private func strip(_ pos: FieldPosition) -> some View {
        GeometryReader { geo in
            let w = geo.size.width, h = geo.size.height
            let unit = w / 120
            let x = { (yard: Double) -> CGFloat in (10 + yard) * unit }
            ZStack(alignment: .topLeading) {
                RoundedRectangle(cornerRadius: 4, style: .continuous).fill(Color(red: 0.10, green: 0.19, blue: 0.16))
                Rectangle().fill(away.chip.background.color.opacity(0.85)).frame(width: 10 * unit)
                Rectangle().fill(home.chip.background.color.opacity(0.85)).frame(width: 10 * unit).offset(x: 110 * unit)
                if situation.isRedZone {
                    let from = pos.attackingGoal == 100 ? 80.0 : 0.0
                    Rectangle().fill(BoardTheme.red.opacity(0.28)).frame(width: 20 * unit).offset(x: x(from))
                }
                ForEach(1..<10, id: \.self) { i in
                    Rectangle().fill(.white.opacity(0.14)).frame(width: 1).offset(x: x(Double(i) * 10))
                }
                if let fd = pos.firstDownLine {
                    Rectangle().fill(BoardTheme.gold).frame(width: 2.5, height: h).offset(x: x(fd) - 1.25)
                }
                Circle().fill(.white).frame(width: h * 0.7, height: h * 0.7)
                    .overlay(Circle().stroke(Color.black.opacity(0.5), lineWidth: 1))
                    .offset(x: x(pos.ball) - h * 0.35, y: h * 0.15)
            }
            .clipShape(RoundedRectangle(cornerRadius: 4, style: .continuous))
        }
    }
}
