import SwiftUI

struct RootView: View {
    @StateObject private var container = WebContainer()
    @State private var tab: BoardTab = BoardTab(rawValue: UserDefaults.standard.string(forKey: "tab") ?? "") ?? .board

    var body: some View {
        TabView(selection: $tab) {
            ForEach(BoardTab.allCases) { t in
                Group {
                    if let fragment = t.fragment {
                        WebScreen(container: container, fragment: fragment)
                    } else {
                        AboutView(container: container)
                    }
                }
                .tabItem { Label(t.title, systemImage: t.symbol) }
                .tag(t)
            }
        }
        .tint(.yellow)
        .onChange(of: tab) { _, new in
            if let fragment = new.fragment { container.show(fragment: fragment) }
        }
    }
}
