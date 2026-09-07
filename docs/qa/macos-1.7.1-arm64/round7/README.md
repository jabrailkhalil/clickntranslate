# Menu-bar shadow mode — native macOS QA, 7 September 2026

Shadow mode uses NSApplicationActivationPolicyAccessory. The main window and Dock
icon disappear while the QSystemTrayIcon and global shortcuts remain available.
Open restores the normal application. The main Close button and saved minimized
startup use the same shadow path; ordinary minimization still uses the Dock.

The native smoke exercises 13 transitions, including an initially hidden window,
menu Open, shadow button, menu activation and rebuilding, a translation-result
window while hidden, hotkey toggling, Close, normal Dock minimization/restoration,
and the no-tray fallback. It checks AppKit's actual activation policy, Qt window
state, the status item's geometry and six menu actions, provider selection, and
window position. Carbon delivers ten callbacks while the Dock is hidden.

Restoration also avoids an unwanted Qt/Cocoa zoom after deminiaturization, which
moved a window from (40, 75) to (258, 113). Native AppKit restoration keeps the frame.

Ice is installed on this Mac. Initially the status item was off-screen in Ice's
hidden section. The user subsequently reported opening that section and seeing
the icon. Ice settings were not modified. Reports retain actual tray coordinates
and an on-screen flag; the application cannot guarantee visibility while a separate
menu-bar manager hides its status item.

Native actions were triggered inside the application's Qt event loop. This does
not claim physical mouse/Dock acceptance; CUA still could not start. Signing and
permission status remain explicitly recorded in validation.json and MACOS_QA.md.

The old Linux fallback test searched only the first 400 characters of a method.
It was replaced with a behavioral test after the method grew. The original failed
full run is retained separately; it did not reveal a broken fallback.
