"""macOS integration. Native frameworks are loaded only on demand on a Mac."""

import os
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
import time

from platform_support import APP_ID


def user_data_dir():
    # Never write into a signed .app, including when launched from a disk image.
    return str(Path.home() / "Library" / "Application Support" / "ClicknTranslate")


def app_bundle(executable=None):
    for parent in Path(executable or sys.executable).resolve().parents:
        if parent.suffix.lower() == ".app" and (parent / "Contents" / "Info.plist").is_file():
            return str(parent)
    return ""


def launch_arguments():
    if getattr(sys, "frozen", False):
        bundle = app_bundle()
        if not bundle:
            raise RuntimeError("Autostart requires an installed .app bundle.")
        # LaunchServices gives the app its own identity for privacy permissions.
        return ["/usr/bin/open", "-a", bundle, "--args", "--autostart"]
    script = str(Path(__file__).with_name("main.py").resolve())
    return [sys.executable, script, "--autostart"]


def autostart_path():
    return Path.home() / "Library" / "LaunchAgents" / f"{APP_ID}.plist"


def autostart_enabled():
    try:
        with autostart_path().open("rb") as stream:
            entry = plistlib.load(stream)
        return (isinstance(entry, dict)
                and entry.get("Label") == APP_ID and entry.get("RunAtLoad") is True
                and not entry.get("Disabled", False)
                and entry.get("ProgramArguments") == launch_arguments())
    except (OSError, ValueError, plistlib.InvalidFileException, RuntimeError):
        return False


def set_autostart(enabled):
    path = autostart_path()
    if not enabled:
        path.unlink(missing_ok=True)
        # No KeepAlive: removing the plist is sufficient for the next login and
        # does not terminate the user's current session via launchctl bootout.
        return False
    entry = {"Label": APP_ID, "ProgramArguments": launch_arguments(),
             "RunAtLoad": True, "LimitLoadToSessionType": "Aqua"}
    if not getattr(sys, "frozen", False):
        entry["WorkingDirectory"] = str(Path(__file__).resolve().parent)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{APP_ID}-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            plistlib.dump(entry, stream)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return autostart_enabled()


def permission_granted(kind):
    if kind == "screen":
        import Quartz
        return bool(Quartz.CGPreflightScreenCaptureAccess())
    if kind == "accessibility":
        import ApplicationServices
        return bool(ApplicationServices.AXIsProcessTrusted())
    raise ValueError(f"Unknown macOS permission: {kind}")


def write_permission_report(output_path, capture=False):
    """Diagnose the installed identity without running OCR or the full UI suite.

    A capture check is explicit, respects the OS grant, and saves dimensions
    only. No screenshot pixels, clipboard content or recognized text are saved.
    """
    import json
    from datetime import datetime, timezone
    report = {'time': datetime.now(timezone.utc).isoformat(), 'pid': os.getpid(),
              'executable': sys.executable, 'bundle': app_bundle(),
              'permissions': {kind: permission_granted(kind) for kind in ('screen', 'accessibility')}}
    if capture:
        report['capture'] = {'attempted': False, 'reason': 'Screen Recording is not granted'}
        if report['permissions']['screen']:
            from PyQt5 import QtWidgets, sip
            app = QtWidgets.QApplication.instance()
            created = app is None
            if created:
                app = QtWidgets.QApplication([])
            screen = app.primaryScreen()
            pixmap = screen.grabWindow(0) if screen is not None else None
            report['capture'] = {
                'attempted': True, 'nonempty': pixmap is not None and not pixmap.isNull(),
                'width': pixmap.width() if pixmap is not None else 0,
                'height': pixmap.height() if pixmap is not None else 0,
                'dpr': pixmap.devicePixelRatioF() if pixmap is not None else 0,
            }
            del pixmap
            if created:
                sip.delete(app)
    path = Path(output_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return report


def ensure_permission(kind, parent=None, language="en"):
    """Explain a missing permission in the app's style, only on a user action.

    Do not poll or display OS prompts during startup, tests, or background OCR.
    The user grants permission in System Settings and then retries the action.
    """
    if permission_granted(kind):
        return True
    from styled_dialogs import StyledMessageBox
    from macos_text import macos_text
    message = macos_text(language, kind) + "\n\n" + macos_text(language, "retry")
    if not getattr(sys, "frozen", False):
        message += "\n\n" + macos_text(language, "python")
    box = StyledMessageBox(parent)
    box.setWindowTitle(macos_text(language, "title"))
    box.setText(message)
    box.setIcon(StyledMessageBox.Information)
    settings = box.addButton(macos_text(language, "open"), StyledMessageBox.AcceptRole)
    box.addButton(macos_text(language, "later"), StyledMessageBox.RejectRole)
    box.exec_()
    if box.clickedButton() is settings:
        if kind == "screen":
            import Quartz
            Quartz.CGRequestScreenCaptureAccess()
        else:
            import ApplicationServices as AX
            AX.AXIsProcessTrustedWithOptions({AX.kAXTrustedCheckOptionPrompt: True})
        pane = "Privacy_ScreenCapture" if kind == "screen" else "Privacy_Accessibility"
        subprocess.Popen(["/usr/bin/open", f"x-apple.systempreferences:com.apple.preference.security?{pane}"])
    box.deleteLater()
    return False


def foreground_target():
    """Identify both the foreground process and its focused accessibility window."""
    import AppKit
    import ApplicationServices as AX
    application = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
    if application is None:
        return None
    pid = int(application.processIdentifier())
    element = AX.AXUIElementCreateApplication(pid)
    error, window = AX.AXUIElementCopyAttributeValue(element, AX.kAXFocusedWindowAttribute, None)
    return (pid, window) if not error and window is not None else None


def same_foreground_target(expected):
    if expected is None:
        return False
    current = foreground_target()
    if current is None or current[0] != expected[0]:
        return False
    import CoreFoundation
    return bool(CoreFoundation.CFEqual(current[1], expected[1]))


def clipboard_sequence():
    import AppKit
    return int(AppKit.NSPasteboard.generalPasteboard().changeCount())


def window_info(number):
    import Quartz
    entries = Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionIncludingWindow, int(number))
    return next((dict(entry) for entry in entries or () if int(entry.get('kCGWindowNumber', 0)) == number), {})


def foreground_window_number():
    import AppKit
    import Quartz
    application = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
    if application is None:
        return 0
    pid = int(application.processIdentifier())
    entries = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements, 0)
    return next((int(entry['kCGWindowNumber']) for entry in entries or ()
                 if int(entry.get('kCGWindowOwnerPID', 0)) == pid
                 and int(entry.get('kCGWindowLayer', -1)) == 0), 0)


def send_edit_shortcut(key, validate_target=None):
    """Send Cmd+C/V without synthesizing releases of keys the user is holding."""
    import Quartz
    if not permission_granted("accessibility"):
        raise RuntimeError("macOS Accessibility permission is required.")
    codes = {"c": 8, "v": 9}
    code = codes[key]
    mask = (Quartz.kCGEventFlagMaskControl | Quartz.kCGEventFlagMaskAlternate
            | Quartz.kCGEventFlagMaskShift | Quartz.kCGEventFlagMaskCommand)
    deadline = time.monotonic() + 1.5
    while Quartz.CGEventSourceFlagsState(Quartz.kCGEventSourceStateCombinedSessionState) & mask:
        if time.monotonic() >= deadline:
            raise RuntimeError("Release the shortcut keys and try again.")
        time.sleep(0.02)
    if validate_target is not None and not validate_target():
        return False
    for pressed in (True, False):
        event = Quartz.CGEventCreateKeyboardEvent(None, code, pressed)
        # Leaving Command on the key-up event also leaves it in Quartz's
        # combined session flags. The following Cmd+V then mistakes our own
        # synthetic Cmd+C for a modifier the user is still holding.
        Quartz.CGEventSetFlags(event, Quartz.kCGEventFlagMaskCommand if pressed else 0)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
    return True


def set_dock_visible(visible):
    """Keep the status item usable while shadow mode opts out of the Dock."""
    import AppKit
    application = AppKit.NSApplication.sharedApplication()
    policy = (AppKit.NSApplicationActivationPolicyRegular if visible
              else AppKit.NSApplicationActivationPolicyAccessory)
    if application.activationPolicy() != policy and not application.setActivationPolicy_(policy):
        raise RuntimeError("macOS could not change the application's Dock visibility.")


def restore_minimized_window(window):
    """Let AppKit restore its frame without Qt forcing a subsequent zoom."""
    import ctypes
    import objc
    if window.isMinimized():
        view = objc.objc_object(c_void_p=ctypes.c_void_p(int(window.winId())))
        view.window().deminiaturize_(None)


def install_status_item_click_handler(tray_icon):
    """Open Qt's native menu outside NSStatusBarButton's mouse tracking loop.

    Qt 5 opens NSMenu synchronously on mouseDown. The menu can consume the
    mouseUp, leaving NSButton tracking forever after the menu closes. Only
    intercept our own status button; Command-drag must still reach AppKit.
    """
    import AppKit
    import weakref
    from PyQt5 import QtCore, sip

    tray_ref = weakref.ref(tray_icon)
    application = AppKit.NSApplication.sharedApplication()

    def handle_event(event):
        tray = tray_ref()
        if (tray is None or sip.isdeleted(tray) or not tray.isVisible()
                or event.modifierFlags() & AppKit.NSEventModifierFlagCommand):
            return event
        window = event.window()
        if window is None:
            return event
        content = window.contentView()
        if content is None:
            return event
        point = content.convertPoint_fromView_(event.locationInWindow(), None)
        view = content.hitTest_(point)
        while view is not None and not isinstance(view, AppKit.NSStatusBarButton):
            view = view.superview()
        if view is None or view.target() is None or view.action() is None:
            return event
        target, action = view.target(), view.action()

        def open_menu():
            current = tray_ref()
            if current is not None and not sip.isdeleted(current) and current.isVisible():
                application.sendAction_to_from_(action, target, view)

        QtCore.QTimer.singleShot(0, open_menu)
        return None  # NSButton must not start its own nested tracking loop.

    mask = (AppKit.NSEventMaskLeftMouseDown | AppKit.NSEventMaskRightMouseDown
            | AppKit.NSEventMaskOtherMouseDown)
    monitor = AppKit.NSEvent.addLocalMonitorForEventsMatchingMask_handler_(mask, handle_event)
    tray_icon.destroyed.connect(lambda: AppKit.NSEvent.removeMonitor_(monitor))
    return monitor


def install_dock_reopen_handler(app, show_window):
    import Foundation
    import objc
    from PyQt5 import QtCore

    class ClicknTranslateReopenHandler(Foundation.NSObject):
        @objc.typedSelector(b'v@:@@')
        def handleReopen_withReplyEvent_(self, event, reply):
            QtCore.QTimer.singleShot(0, show_window)

    handler = ClicknTranslateReopenHandler.alloc().init()
    # Only override the Dock reopen Apple event. Keep Qt's delegate, activation
    # events and file-open handling intact; activating an OCR overlay must not
    # bring the main window back in front of the captured screen.
    Foundation.NSAppleEventManager.sharedAppleEventManager().setEventHandler_andSelector_forEventClass_andEventID_(
        handler, 'handleReopen:withReplyEvent:', int.from_bytes(b'aevt', 'big'), int.from_bytes(b'rapp', 'big'))
    return handler
