import Foundation
import Observation

/// Merges the live scoreboard, the weekly snapshot and the nflverse metrics, and keeps them fresh.
@Observable @MainActor
final class BoardStore {
    private(set) var live: LivePayload?
    private(set) var snapshot: Snapshot?
    private(set) var metrics: Metrics?
    /// Live first, then upcoming, then finals.
    private(set) var games: [BoardGame] = []
    /// The three live games most worth watching; empty when nothing is live.
    private(set) var desk: [BoardGame] = []
    private(set) var byes: [String] = []
    private(set) var lastUpdated: Date?
    private(set) var error: APIError?
    private(set) var isLoading = false
    private(set) var isActive = false

    @ObservationIgnored private let api: any BoardAPI
    @ObservationIgnored private let clock: @Sendable () -> Date
    @ObservationIgnored private var task: Task<Void, Never>?
    @ObservationIgnored private var topID: String?
    @ObservationIgnored private var rings: [String: [DeskRanking.Sample]] = [:]
    @ObservationIgnored private var snapshotFetchedAt: Date?
    @ObservationIgnored private var metricsFetchedAt: Date?

    static let snapshotMaxAge: TimeInterval = 600
    static let metricsMaxAge: TimeInterval = 3600

    init(api: any BoardAPI = APIClient.shared, clock: @escaping @Sendable () -> Date = { Date() }) {
        self.api = api
        self.clock = clock
    }

    var weekLabel: String? { live?.week.label ?? snapshot?.week.label }
    var isStale: Bool { live?.stale ?? false }
    var liveCount: Int { games.filter(\.isLive).count }

    func game(id: String) -> BoardGame? { games.first { $0.id == id } }

    func games(for filter: BoardFilter, following: FollowStore) -> [BoardGame] {
        switch filter {
        case .all: games
        case .live: games.filter(\.isLive)
        case .following: games.filter { following.follows($0) }
        }
    }

    func deskSwing(for id: String) -> (points: Double, toward: Possession?) {
        DeskRanking.swing(rings[id] ?? [], now: clock())
    }

    /// Starts or pauses polling with the app scene: polls while the app is in the foreground.
    func setActive(_ active: Bool) {
        guard active != isActive else { return }
        isActive = active
        let previous = task
        previous?.cancel()
        task = nil
        guard active else { return }
        task = Task { [weak self] in
            await previous?.value
            while !Task.isCancelled {
                guard let self else { return }
                await self.refresh()
                let wait = PollCadence.interval(for: self.games, now: self.clock())
                try? await Task.sleep(for: .seconds(wait))
            }
        }
    }

    func refresh() async {
        guard !isLoading else { return }
        isLoading = true
        defer { isLoading = false }
        let now = clock()
        async let snap: Void = refreshSnapshot(now: now)
        async let stats: Void = refreshMetrics(now: now)
        _ = await (snap, stats)
        do {
            let week = snapshot.flatMap { $0.isPast ? nil : $0 }
            let payload = try await api.live(season: week?.season.type, week: week?.week.number)
            live = payload
            lastUpdated = clock()
            error = nil
            record(payload.games, now: lastUpdated ?? now)
        } catch is CancellationError {
            return
        } catch {
            self.error = error as? APIError ?? .badPayload
        }
        rebuild()
    }

    private func refreshSnapshot(now: Date) async {
        if let at = snapshotFetchedAt, now.timeIntervalSince(at) < Self.snapshotMaxAge, snapshot != nil { return }
        if let fresh = try? await api.snapshot() {
            snapshot = fresh
            snapshotFetchedAt = now
        }
    }

    private func refreshMetrics(now: Date) async {
        if let at = metricsFetchedAt, now.timeIntervalSince(at) < Self.metricsMaxAge, metrics != nil { return }
        if let fresh = try? await api.metrics() {
            metrics = fresh
            metricsFetchedAt = now
        }
    }

    private func record(_ games: [LiveGame], now: Date) {
        var next: [String: [DeskRanking.Sample]] = [:]
        for g in games {
            guard g.state == .in, let wp = g.wp?.home else { continue }
            let kept = (rings[g.id] ?? []).filter { now.timeIntervalSince($0.time) <= DeskRanking.swingWindow }
            next[g.id] = kept + [DeskRanking.Sample(time: now, homeWP: wp)]
        }
        rings = next
    }

    private func rebuild() {
        let merged = BoardGame.sorted(BoardGame.build(live: live, snapshot: snapshot))
        games = merged
        byes = live?.teamsOnBye ?? snapshot?.teamsOnBye.map(\.abbr) ?? []
        let now = clock()
        let items = merged.compactMap { g -> DeskRanking.Item? in
            guard g.isLive, let d = g.desk else { return nil }
            let swing = DeskRanking.swing(rings[g.id] ?? [], now: now).points
            return .init(id: g.id, effective: DeskRanking.effectiveScore(d.score, swingPoints: swing),
                         progress: g.period * 1000 - g.clockSeconds, kickoff: g.kickoffSortKey)
        }
        let order = DeskRanking.order(items, previousTop: topID)
        topID = order.first
        let byID = Dictionary(merged.map { ($0.id, $0) }, uniquingKeysWith: { a, _ in a })
        desk = order.prefix(3).compactMap { byID[$0] }
    }
}
