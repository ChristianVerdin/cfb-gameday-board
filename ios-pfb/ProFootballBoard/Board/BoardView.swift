import SwiftUI

struct BoardView: View {
    var filter: BoardFilter = .all
    @Environment(BoardStore.self) private var board
    @Environment(FollowStore.self) private var following

    private enum Pick: Hashable { case auto, all, window(GameWindow) }
    @State private var pick: Pick = .auto

    private var games: [BoardGame] { board.games(for: filter, following: following) }
    private var windows: [GameWindow] { GameWindow.ordered(games) }

    /// The first window with a live game, else the first with an unfinished one.
    private var defaultWindow: GameWindow? {
        windows.first { w in games.contains { $0.window == w && $0.isLive } }
            ?? windows.first { w in games.contains { $0.window == w && $0.state != .post } }
    }

    private var activeWindow: GameWindow? {
        switch pick {
        case .all: nil
        case .window(let w): windows.contains(w) ? w : defaultWindow
        case .auto: filter == .all ? defaultWindow : nil
        }
    }

    private var visible: [BoardGame] {
        guard let w = activeWindow else { return games }
        return games.filter { $0.window == w }
    }

    private var seasonYear: Int? { board.live?.season.year ?? board.snapshot?.season.year }

    private let columns = [GridItem(.adaptive(minimum: 380), spacing: 12, alignment: .top)]

    var body: some View {
        NavigationStack {
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 14) {
                    if let error = board.error { errorBanner(error) }
                    if filter != .following || !games.isEmpty { chips }
                    if filter == .all {
                        DeskSection(desk: board.desk, upcoming: board.games)
                    }
                    if visible.isEmpty { empty } else {
                        LazyVGrid(columns: columns, spacing: 12) {
                            ForEach(visible) { GameCard(game: $0, metrics: board.metrics, seasonYear: seasonYear) }
                        }
                    }
                    if filter != .live { byes }
                    caption
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 12)
            }
            .refreshable { await board.refresh() }
            .background(BoardTheme.bg.ignoresSafeArea())
            .navigationTitle(title)
            .toolbarBackground(BoardTheme.bg, for: .navigationBar)
        }
    }

    private var title: String {
        switch filter {
        case .all: board.weekLabel ?? "Pro Football Board"
        case .live: "Live"
        case .following: "Following"
        }
    }

    @ViewBuilder private var chips: some View {
        if windows.count > 1 || filter == .all && windows.count > 0 {
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    chip("All", selected: activeWindow == nil) { pick = .all }
                    ForEach(windows, id: \.self) { w in
                        chip(w.label, selected: activeWindow == w, live: games.contains { $0.window == w && $0.isLive }) {
                            pick = .window(w)
                        }
                    }
                }
                .padding(.vertical, 2)
            }
        }
    }

    private func chip(_ title: String, selected: Bool, live: Bool = false, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 5) {
                if live { Circle().fill(BoardTheme.green).frame(width: 7, height: 7) }
                Text(title).font(.subheadline.weight(.semibold))
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 7)
            .foregroundStyle(selected ? Color.black : BoardTheme.text)
            .background(selected ? BoardTheme.gold : BoardTheme.chip, in: Capsule())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(live ? "\(title), live" : title)
        .accessibilityAddTraits(selected ? .isSelected : [])
    }

    private func errorBanner(_ error: APIError) -> some View {
        HStack(spacing: 8) {
            Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(BoardTheme.orange)
            Text(board.games.isEmpty ? error.message : error.message + " Showing the last data.").font(.footnote)
            Spacer(minLength: 0)
        }
        .padding(10)
        .background(BoardTheme.orange.opacity(0.15), in: RoundedRectangle(cornerRadius: 10, style: .continuous))
        .accessibilityElement(children: .combine)
    }

    @ViewBuilder private var empty: some View {
        VStack(spacing: 8) {
            if board.games.isEmpty && board.lastUpdated == nil && board.error == nil {
                ProgressView().tint(BoardTheme.gold)
                Text("Loading the board").foregroundStyle(BoardTheme.muted)
            } else {
                Text(emptyTitle).font(.headline)
                Text(emptyDetail).font(.subheadline).foregroundStyle(BoardTheme.muted).multilineTextAlignment(.center)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 40)
    }

    private var emptyTitle: String {
        switch filter {
        case .live: "No live games"
        case .following: following.teams.isEmpty ? "No teams followed" : "No games for your teams"
        case .all: "No games"
        }
    }

    private var emptyDetail: String {
        switch filter {
        case .live: "Games show here while they are in progress."
        case .following: following.teams.isEmpty ? "Tap the star next to a team on any game to follow it." : "Your teams are not playing this week."
        case .all: "Pull down to refresh."
        }
    }

    @ViewBuilder private var byes: some View {
        let list = filter == .following ? board.byes.filter(following.isFollowing) : board.byes
        if !list.isEmpty {
            HStack(spacing: 8) {
                Text("On bye").font(.footnote.weight(.semibold)).foregroundStyle(BoardTheme.gold)
                Text(list.joined(separator: ", ")).font(.footnote).foregroundStyle(BoardTheme.muted)
                Spacer(minLength: 0)
            }
            .padding(12)
            .background(BoardTheme.card, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
            .accessibilityElement(children: .combine)
        }
    }

    @ViewBuilder private var caption: some View {
        if let at = board.lastUpdated {
            Text("Updated \(at.formatted(Date.FormatStyle(timeZone: Chicago.zone).hour().minute().second())) CT"
                 + (board.isStale ? " \u{00B7} data may be delayed" : ""))
                .font(.caption).foregroundStyle(BoardTheme.muted)
                .frame(maxWidth: .infinity)
        }
    }
}
