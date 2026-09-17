import Combine
import UIKit
import WebKit

/// Owns the single WKWebView for the app. Tabs re-parent it; nothing reloads on tab switch.
@MainActor
final class WebContainer: NSObject, ObservableObject {
    @Published var isLoading = false
    @Published var failure: String?

    let webView: WKWebView
    private let refresh = UIRefreshControl()
    private var backgroundedAt: Date?
    private var observers: [NSObjectProtocol] = []

    override init() {
        let config = WKWebViewConfiguration()
        config.defaultWebpagePreferences.allowsContentJavaScript = true
        config.allowsInlineMediaPlayback = true
        // Lets app.js hide the Safari "Add to Home Screen" hint and know it is inside the app.
        let script = WKUserScript(source: "window.cfbNative = true;", injectionTime: .atDocumentStart, forMainFrameOnly: true)
        config.userContentController.addUserScript(script)

        webView = WKWebView(frame: .zero, configuration: config)
        super.init()

        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.allowsBackForwardNavigationGestures = false
        webView.scrollView.bounces = true
        webView.scrollView.contentInsetAdjustmentBehavior = .never   // site handles safe areas itself
        webView.backgroundColor = UIColor(red: 0.043, green: 0.071, blue: 0.125, alpha: 1)
        webView.isOpaque = false
        webView.scrollView.backgroundColor = webView.backgroundColor

        refresh.tintColor = .systemYellow
        refresh.addTarget(self, action: #selector(pulled), for: .valueChanged)
        webView.scrollView.refreshControl = refresh

        // willEnterForeground, not didBecomeActive: the latter also fires after a
        // dismissed alert, a Control Centre pull and app-switcher previews, which would
        // reload the board mid-scroll during a phone call.
        let center = NotificationCenter.default
        observers.append(center.addObserver(forName: UIApplication.didEnterBackgroundNotification,
                                           object: nil, queue: .main) { [weak self] _ in
            MainActor.assumeIsolated { self?.backgroundedAt = Date() }
        })
        observers.append(center.addObserver(forName: UIApplication.willEnterForegroundNotification,
                                           object: nil, queue: .main) { [weak self] _ in
            MainActor.assumeIsolated { self?.refreshIfStale() }
        })
    }

    /// Reload only when the page is actually holding a stale slate.
    ///
    /// A blind reload on every foreground would wipe scroll position and the in-page
    /// filters, which is hostile on a Saturday afternoon - and usually pointless, since
    /// app.js already polls /api/live every 30s, so scores self-heal without us. So ask
    /// the page what it is holding and decide from that. No new endpoint, works offline.
    func refreshIfStale() {
        guard failure == nil else { reload(); return }      // offline screen: nothing to keep
        let away = backgroundedAt.map { Date().timeIntervalSince($0) } ?? 0
        backgroundedAt = nil
        guard away >= 15 * 60 else { return }               // the poller has it covered
        if away >= 6 * 60 * 60 { reload(); return }         // overnight in a pocket

        // Plain multi-line JS: no trailing backslashes, so nothing here depends on Swift's
        // line-continuation rules inside the payload.
        let js = """
        (function () {
          var d = window.CFB_DATA || {}, g = d.games || [];
          var live = g.some(function (x) {
            return x.gameState === "in" || x.status === "STATUS_IN_PROGRESS" || x.status === "STATUS_HALFTIME";
          });
          return JSON.stringify({ gen: d.generated_at || "", live: live });
        })()
        """
        webView.evaluateJavaScript(js) { [weak self] value, _ in
            MainActor.assumeIsolated {
                guard let self else { return }
                guard let raw = value as? String,
                      let data = raw.data(using: .utf8),
                      let state = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
                else { self.reload(); return }              // could not ask: assume stale
                if state["live"] as? Bool == true { return } // mid-game: leave their place alone
                let fmt = ISO8601DateFormatter()
                guard let gen = (state["gen"] as? String).flatMap({ fmt.date(from: $0) }) else {
                    self.reload(); return
                }
                // 12h means a scheduled rebuild has landed since this page loaded.
                if Date().timeIntervalSince(gen) >= 12 * 60 * 60 { self.reload() }
            }
        }
    }

    func loadIfNeeded(fragment: String = "all") {
        guard webView.url == nil else { return }
        load(fragment: fragment)
    }

    func load(fragment: String) {
        var comps = URLComponents(url: AppConfig.boardURL, resolvingAgainstBaseURL: false)!
        comps.fragment = fragment
        failure = nil
        webView.load(URLRequest(url: comps.url!, cachePolicy: .reloadRevalidatingCacheData, timeoutInterval: 20))
    }

    /// Native tabs drive the site's filters through the URL hash; app.js listens for hashchange.
    func show(fragment: String) {
        guard webView.url != nil, failure == nil else { load(fragment: fragment); return }
        if webView.isLoading { load(fragment: fragment); return }   // hash set before app.js exists would be lost
        webView.evaluateJavaScript("location.hash = '#\(fragment)';", completionHandler: nil)
    }

    func reload() {
        failure = nil
        if webView.url == nil { load(fragment: "all") } else { webView.reload() }
    }

    @objc private func pulled() {
        reload()
    }

    private func isBoardHost(_ url: URL?) -> Bool {
        guard let host = url?.host?.lowercased() else { return false }
        return host == AppConfig.boardHost.lowercased()
    }
}

extension WebContainer: WKNavigationDelegate {
    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction) async -> WKNavigationActionPolicy {
        guard let url = navigationAction.request.url else { return .cancel }
        // Maps, ESPN gamecast, tickets, GitHub: leave the app instead of trapping the user in the web view.
        if navigationAction.navigationType == .linkActivated, !isBoardHost(url) {
            await UIApplication.shared.open(url)
            return .cancel
        }
        return .allow
    }

    func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
        isLoading = true
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        isLoading = false
        failure = nil
        refresh.endRefreshing()
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        finish(with: error)
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        finish(with: error)
    }

    private func finish(with error: Error) {
        isLoading = false
        refresh.endRefreshing()
        let ns = error as NSError
        if ns.domain == NSURLErrorDomain, ns.code == NSURLErrorCancelled { return }
        failure = ns.code == NSURLErrorNotConnectedToInternet
            ? "You're offline. Live scores need a connection."
            : "Couldn't reach the board. \(ns.localizedDescription)"
    }
}

extension WebContainer: WKUIDelegate {
    // target=_blank links (none today, but ESPN markup changes): open outside.
    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
                 for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        if let url = navigationAction.request.url { UIApplication.shared.open(url) }
        return nil
    }
}
