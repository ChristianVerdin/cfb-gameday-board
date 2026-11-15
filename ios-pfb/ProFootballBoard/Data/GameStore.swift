import Foundation
import Observation

/// One game's sheet: drives, plays, win probability and team stats. Polls every 20 s while the game is live.
@Observable @MainActor
final class GameStore {
    let gameID: String
    private(set) var sheet: GameSheet?
    private(set) var lastUpdated: Date?
    private(set) var error: APIError?
    private(set) var isLoading = false

    @ObservationIgnored private let api: any BoardAPI
    @ObservationIgnored private let clock: @Sendable () -> Date
    @ObservationIgnored private var task: Task<Void, Never>?
    @ObservationIgnored private var stopping: Task<Void, Never>?

    init(gameID: String, api: any BoardAPI = APIClient.shared, clock: @escaping @Sendable () -> Date = { Date() }) {
        self.gameID = gameID
        self.api = api
        self.clock = clock
    }

    /// Seconds until the next fetch, nil when the game is over and nothing more will change.
    nonisolated static func interval(for state: GameState?) -> TimeInterval? {
        switch state {
        case .in: 20
        case .pre, nil: 60
        case .post: nil
        }
    }

    func start() {
        guard task == nil else { return }
        let previous = stopping
        task = Task { [weak self] in
            await previous?.value
            while !Task.isCancelled {
                guard let self else { return }
                await self.refresh()
                let wait: TimeInterval? = self.sheet == nil ? 30 : Self.interval(for: self.sheet?.state)
                guard let wait else {
                    self.task = nil
                    return
                }
                try? await Task.sleep(for: .seconds(wait))
            }
        }
    }

    func stop() {
        task?.cancel()
        stopping = task
        task = nil
    }

    func refresh() async {
        guard !isLoading else { return }
        isLoading = true
        defer { isLoading = false }
        do {
            sheet = try await api.game(id: gameID)
            lastUpdated = clock()
            error = nil
        } catch is CancellationError {
            return
        } catch {
            self.error = error as? APIError ?? .badPayload
        }
    }
}
