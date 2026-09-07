import SwiftUI
import WebKit

/// Hosts the shared WKWebView for one tab. On appear it adopts the web view and sets the hash.
struct WebScreen: View {
    @ObservedObject var container: WebContainer
    let fragment: String

    var body: some View {
        ZStack {
            Color(red: 0.043, green: 0.071, blue: 0.125).ignoresSafeArea()
            WebHost(container: container)
                .ignoresSafeArea(edges: .top)
            if let failure = container.failure {
                ContentUnavailableView {
                    Label("Board unavailable", systemImage: "wifi.slash")
                } description: {
                    Text(failure)
                } actions: {
                    Button("Retry") { container.reload() }
                        .buttonStyle(.borderedProminent)
                }
                .background(Color(red: 0.043, green: 0.071, blue: 0.125))
            } else if container.isLoading && container.webView.url == nil {
                ProgressView().tint(.yellow)
            }
        }
        .onAppear {
            if container.webView.url == nil { container.loadIfNeeded(fragment: fragment) }
            else { container.show(fragment: fragment) }
        }
    }
}

private struct WebHost: UIViewRepresentable {
    let container: WebContainer

    func makeUIView(context: Context) -> HostView {
        let host = HostView()
        host.backgroundColor = .clear
        host.container = container
        return host
    }

    func updateUIView(_ host: HostView, context: Context) {
        host.adoptIfVisible()
    }
}

/// Re-parents the shared web view whenever this tab comes on screen. SwiftUI only
/// calls updateUIView when a view's inputs change, and a revisited tab's inputs never
/// do, so the web view used to stay in the previous tab's host and the tab showed blank.
final class HostView: UIView {
    weak var container: WebContainer?

    override func didMoveToWindow() {
        super.didMoveToWindow()
        adoptIfVisible()
    }

    func adoptIfVisible() {
        guard window != nil, let web = container?.webView, web.superview !== self else { return }
        web.removeFromSuperview()
        web.translatesAutoresizingMaskIntoConstraints = false
        addSubview(web)
        NSLayoutConstraint.activate([
            web.leadingAnchor.constraint(equalTo: leadingAnchor),
            web.trailingAnchor.constraint(equalTo: trailingAnchor),
            web.topAnchor.constraint(equalTo: topAnchor),
            web.bottomAnchor.constraint(equalTo: bottomAnchor),
        ])
    }
}
