import Foundation

enum APIError: Error, Equatable {
    case badStatus(Int)
    case badPayload
    case offline
    case timeout

    var message: String {
        switch self {
        case .badStatus(let code): "The board answered with an error (\(code))."
        case .badPayload: "The board sent data this app could not read."
        case .offline: "No connection."
        case .timeout: "The board took too long to answer."
        }
    }
}

protocol BoardAPI: Sendable {
    func live(season: Int?, week: Int?) async throws -> LivePayload
    func game(id: String) async throws -> GameSheet
    func snapshot() async throws -> Snapshot
    func metrics() async throws -> Metrics
}

/// Plain GETs of the board's public endpoints: no cache-busting query, no conditional headers.
actor APIClient: BoardAPI {
    static let shared = APIClient()
    static let base = URL(string: "https://cfbgameday.app")!

    private let session: URLSession
    private let base: URL

    init(base: URL = APIClient.base, session: URLSession? = nil) {
        self.base = base
        if let session {
            self.session = session
        } else {
            let config = URLSessionConfiguration.ephemeral
            config.timeoutIntervalForRequest = 10
            config.timeoutIntervalForResource = 10
            config.requestCachePolicy = .reloadIgnoringLocalAndRemoteCacheData
            config.urlCache = nil
            config.httpAdditionalHeaders = ["Accept": "application/json"]
            self.session = URLSession(configuration: config)
        }
    }

    static func liveURL(base: URL = APIClient.base, season: Int?, week: Int?) -> URL {
        var parts = URLComponents(url: base.appending(path: "api/nfl/live"), resolvingAgainstBaseURL: false)!
        if let season, let week { parts.queryItems = [URLQueryItem(name: "st", value: String(season)), URLQueryItem(name: "week", value: String(week))] }
        return parts.url!
    }

    func live(season: Int? = nil, week: Int? = nil) async throws -> LivePayload {
        try await get(Self.liveURL(base: base, season: season, week: week))
    }

    func game(id: String) async throws -> GameSheet {
        var parts = URLComponents(url: base.appending(path: "api/nfl/game"), resolvingAgainstBaseURL: false)!
        parts.queryItems = [URLQueryItem(name: "id", value: id)]
        return try await get(parts.url!)
    }

    func snapshot() async throws -> Snapshot { try await get(base.appending(path: "nfl/games.json")) }

    func metrics() async throws -> Metrics { try await get(base.appending(path: "nfl/metrics.json")) }

    private func get<T: Decodable>(_ url: URL) async throws -> T {
        var request = URLRequest(url: url)
        request.cachePolicy = .reloadIgnoringLocalAndRemoteCacheData
        request.timeoutInterval = 10
        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch let error as URLError {
            switch error.code {
            case .cancelled: throw CancellationError()
            case .timedOut: throw APIError.timeout
            default: throw APIError.offline
            }
        }
        guard let http = response as? HTTPURLResponse else { throw APIError.badPayload }
        guard (200..<300).contains(http.statusCode) else { throw APIError.badStatus(http.statusCode) }
        do {
            return try JSONDecoder().decode(T.self, from: data)
        } catch {
            throw APIError.badPayload
        }
    }
}
