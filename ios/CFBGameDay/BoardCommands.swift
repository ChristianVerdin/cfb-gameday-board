import SwiftUI
import UIKit

/// What the menu bar and hardware-keyboard shortcuts can do to the focused window's board.
struct BoardActions {
    let select: (BoardTab) -> Void
    let reload: () -> Void
    let find: () -> Void
}

extension FocusedValues {
    @Entry var boardActions: BoardActions?
}

/// Board menu: the Mac menu bar, the iPadOS menu bar, and the Command-key shortcut list.
struct BoardCommands: Commands {
    @FocusedValue(\.boardActions) private var actions

    var body: some Commands {
        CommandMenu("Board") {
            ForEach(Array(BoardTab.allCases.enumerated()), id: \.element) { i, t in
                Button(t.title) { actions?.select(t) }
                    .keyboardShortcut(KeyEquivalent(Character(String(i + 1))), modifiers: .command)
            }
            Divider()
            Button("Find Game") { actions?.find() }
                .keyboardShortcut("f")
            Button("Reload Board") { actions?.reload() }
                .keyboardShortcut("r")
        }
    }
}

/// Resizable windows (Mac "Designed for iPad", iPadOS windowing): never narrower than a
/// phone, so the board's one-column layout is the smallest it ever has to draw.
enum WindowSizing {
    static let minimum = CGSize(width: 390, height: 600)

    static func apply() {
        for case let scene as UIWindowScene in UIApplication.shared.connectedScenes {
            scene.sizeRestrictions?.minimumSize = minimum
        }
    }
}
