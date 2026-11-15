import SwiftUI

struct GameCard: View {
    let game: BoardGame
    let metrics: Metrics?
    let seasonYear: Int?
    @Environment(FollowStore.self) private var following
    @Environment(Router.self) private var router

    private var info: StateInfo? { StateInfo(game) }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            meta
            if game.placeholder {
                Text(game.flexNote ?? "Teams to be determined").font(.subheadline).foregroundStyle(BoardTheme.muted)
            } else {
                teams
                liveRow
            }
            footer
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(BoardTheme.card, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .stroke(game.isLive ? BoardTheme.green.opacity(0.55) : BoardTheme.line.opacity(0.7), lineWidth: 1))
        .contentShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        .onTapGesture { router.open(.game(game.id)) }
        .accessibilityElement(children: .contain)
        .accessibilityAction(named: "Open game") { router.open(.game(game.id)) }
    }

    private var meta: some View {
        ViewThatFits(in: .horizontal) {
            HStack(spacing: 8) {
                BoardTag(text: game.window.label, tint: BoardTheme.gold).fixedSize()
                Text(kickoff).font(.footnote).foregroundStyle(BoardTheme.muted).lineLimit(1)
                Spacer(minLength: 4)
                if !game.tv.isEmpty { Text(game.tv).font(.footnote.weight(.semibold)).foregroundStyle(BoardTheme.blue).lineLimit(1) }
            }
            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 8) {
                    BoardTag(text: game.window.label, tint: BoardTheme.gold).fixedSize()
                    if !game.tv.isEmpty { Text(game.tv).font(.footnote.weight(.semibold)).foregroundStyle(BoardTheme.blue) }
                }
                Text(kickoff).font(.footnote).foregroundStyle(BoardTheme.muted)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private var kickoff: String {
        var s = game.kickoffText
        if game.timeTBD, let note = game.flexNote { s += " \u{00B7} \(note)" }
        return s
    }

    @ViewBuilder private var teams: some View {
        if let away = game.away, let home = game.home {
            VStack(spacing: 6) {
                teamRow(away, side: .away)
                if game.neutral {
                    Text("vs \u{00B7} neutral site").font(.caption2).foregroundStyle(BoardTheme.muted)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                teamRow(home, side: .home)
            }
        }
    }

    private func teamRow(_ team: Team, side: Possession) -> some View {
        let started = game.state != .pre
        let lost = game.state == .post && game.result.map { $0 != .tie && $0.rawValue != side.rawValue } == true
        let hasBall = game.isLive && game.situation?.possession == side
        return HStack(spacing: 10) {
            TeamChip(team: team)
            VStack(alignment: .leading, spacing: 0) {
                Text(team.name.isEmpty ? team.abbr : team.name).font(.headline).lineLimit(2)
                if let r = team.record { Text(r.text).font(.caption).foregroundStyle(BoardTheme.muted) }
            }
            Spacer(minLength: 4)
            if hasBall {
                Circle().fill(BoardTheme.gold).frame(width: 9, height: 9).accessibilityHidden(true)
            }
            if started, let score = team.score {
                Text("\(score)").font(.title2.weight(.bold).monospacedDigit())
            }
            FollowStar(abbr: team.abbr, name: team.displayName)
        }
        .opacity(lost ? 0.55 : 1)
        .accessibilityElement(children: .combine)
        .accessibilityLabel(spokenRow(team, started: started, hasBall: hasBall))
    }

    private func spokenRow(_ t: Team, started: Bool, hasBall: Bool) -> String {
        var s = t.displayName.isEmpty ? t.abbr : t.displayName
        if let r = t.record { s += ", record \(r.text)" }
        if started, let score = t.score { s += ", \(score)" }
        if hasBall { s += ", has the ball" }
        return s
    }

    @ViewBuilder private var liveRow: some View {
        if let info {
            VStack(alignment: .leading, spacing: 6) {
                HStack(spacing: 8) {
                    BoardTag(text: info.pill, tint: tint(info.tone), filled: info.tone == .live)
                    if !info.text.isEmpty { Text(info.text).font(.subheadline.weight(.semibold).monospacedDigit()) }
                    if game.isLive, let s = game.situation {
                        let bits = [s.possessionAbbr.map { "\($0) ball" }, s.stoppage ? "Stoppage" : s.text].compactMap { $0 }
                        if !bits.isEmpty { Text(bits.joined(separator: " \u{00B7} ")).font(.subheadline).foregroundStyle(BoardTheme.muted).lineLimit(3) }
                        if s.isRedZone { BoardTag(text: s.goalToGo ? "Goal to go" : "Red zone", tint: BoardTheme.red) }
                    }
                }
                if game.isLive, let s = game.situation, let away = game.away, let home = game.home {
                    FieldStrip(situation: s, away: away, home: home)
                    if let play = s.lastPlay?.text, !play.isEmpty {
                        Text(play).font(.footnote).foregroundStyle(BoardTheme.muted).lineLimit(2)
                    }
                }
            }
        }
    }

    private func tint(_ tone: StateInfo.Tone) -> Color {
        switch tone {
        case .live: BoardTheme.green
        case .half: BoardTheme.orange
        case .final: BoardTheme.muted
        case .alert: BoardTheme.red
        }
    }

    @ViewBuilder private var footer: some View {
        if let v = game.venue {
            Divider().overlay(BoardTheme.line.opacity(0.6))
            HStack(spacing: 6) {
                Text(v.name).font(.footnote.weight(.semibold)).lineLimit(1).layoutPriority(1)
                if !v.place.isEmpty { Text(v.place).font(.footnote).foregroundStyle(BoardTheme.muted).lineLimit(1) }
                Spacer(minLength: 0)
                if let roof = roofName(v.roof) { BoardTag(text: roof).fixedSize() }
            }
            WeatherRow(venue: v, weather: game.weather, status: game.weatherStatus)
        }
        MetricsBlock(game: game, metrics: metrics, seasonYear: seasonYear)
    }

    private func roofName(_ roof: Roof?) -> String? {
        switch roof {
        case .dome: "Dome"
        case .retractable: "Retractable"
        case .canopy: "Canopy"
        default: nil
        }
    }
}

struct FollowStar: View {
    let abbr: String
    let name: String
    @Environment(FollowStore.self) private var following

    var body: some View {
        let on = following.isFollowing(abbr)
        Button { following.toggle(abbr) } label: {
            Image(systemName: on ? "star.fill" : "star")
                .foregroundStyle(on ? BoardTheme.gold : BoardTheme.muted)
                .frame(width: 44, height: 44)
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(on ? "Unfollow \(name)" : "Follow \(name)")
    }
}
