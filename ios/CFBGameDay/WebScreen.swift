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
            container.loadIfNeeded()
            container.show(fragment: fragment)
        }
    }
}

private struct WebHost: UIViewRepresentable {
    let container: WebContainer

    func makeUIView(context: Context) -> UIView {
        let host = UIView()
        host.backgroundColor = .clear
        return host
    }

    func updateUIView(_ host: UIView, context: Context) {
        let web = container.webView
        guard web.superview !== host else { return }
        web.removeFromSuperview()
        web.translatesAutoresizingMaskIntoConstraints = false
        host.addSubview(web)
        NSLayoutConstraint.activate([
            web.leadingAnchor.constraint(equalTo: host.leadingAnchor),
            web.trailingAnchor.constraint(equalTo: host.trailingAnchor),
            web.topAnchor.constraint(equalTo: host.topAnchor),
            web.bottomAnchor.constraint(equalTo: host.bottomAnchor),
        ])
    }
}
