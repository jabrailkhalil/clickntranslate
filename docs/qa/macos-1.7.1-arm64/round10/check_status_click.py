"""One native reproduction: right press, dismiss menu, no mouse release.

Only sends in-process events to this probe's own status button.
"""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
import AppKit
import Foundation
from PyQt5 import QtCore, QtGui, QtWidgets, sip
from macos_desktop import install_status_item_click_handler

app = QtWidgets.QApplication([])
app.setQuitOnLastWindowClosed(False)
tray = QtWidgets.QSystemTrayIcon(QtGui.QIcon('icons/icon.png'))
menu = QtWidgets.QMenu()
menu.addAction('Open')
tray.setContextMenu(menu)
tray.show()
monitor = install_status_item_click_handler(tray)
native = AppKit.NSApplication.sharedApplication()
result = {'native_menu_opened': False, 'event_loop_resumed': False}
menu.aboutToShow.connect(lambda: result.update(native_menu_opened=True))

def escape(timer):
    event = AppKit.NSEvent.keyEventWithType_location_modifierFlags_timestamp_windowNumber_context_characters_charactersIgnoringModifiers_isARepeat_keyCode_(
        AppKit.NSEventTypeKeyDown, (0, 0), 0, 0, 0, None, '\x1b', '\x1b', False, 53)
    native.postEvent_atStart_(event, True)

def find_button(view):
    if isinstance(view, AppKit.NSStatusBarButton):
        return view
    for child in view.subviews():
        button = find_button(child)
        if button is not None:
            return button

def finish():
    result['event_loop_resumed'] = True
    tray.hide()
    app.quit()

def press():
    button = next(filter(None, (find_button(w.contentView()) for w in native.windows() if w.contentView())))
    point = button.convertPoint_toView_((button.bounds().size.width / 2, button.bounds().size.height / 2), None)
    event = AppKit.NSEvent.mouseEventWithType_location_modifierFlags_timestamp_windowNumber_context_eventNumber_clickCount_pressure_(
        AppKit.NSEventTypeRightMouseDown, point, 0, 0, button.window().windowNumber(), None, 1, 1, 1.0)
    # An AppKit timer remains live in native menu tracking mode. Escape dismisses
    # the menu; deliberately never deliver a rightMouseUp to expose the hang.
    timer = Foundation.NSTimer.timerWithTimeInterval_repeats_block_(0.4, False, escape)
    Foundation.NSRunLoop.mainRunLoop().addTimer_forMode_(timer, Foundation.NSRunLoopCommonModes)
    native.sendEvent_(event)
    QtCore.QTimer.singleShot(700, finish)

QtCore.QTimer.singleShot(200, press)
app.exec_()
assert all(result.values()), result
print(json.dumps(result))
sip.delete(tray)
sip.delete(menu)
sip.delete(app)
