"""Check the native Cocoa surface, not just Qt's transparent grab()."""

import ctypes
import sys

import pytest
from PyQt5 import QtCore, QtWidgets, sip
from PyQt5.QtTest import QTest

from styled_dialogs import StatusPopup, install_tooltip_style
from ui_scaling import configure_interface_style


@pytest.fixture
def popup_app():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    configure_interface_style()
    theme, style = app.property('ui_theme'), app.styleSheet()
    palette = QtWidgets.QToolTip.palette()
    yield app
    QtWidgets.QToolTip.hideText()
    QTest.qWait(350)
    app.setProperty('ui_theme', theme)
    app.setStyleSheet(style)
    QtWidgets.QToolTip.setPalette(palette)


def test_status_tip_paints_a_surface_and_refreshes_its_theme(popup_app):
    app = popup_app
    popup = StatusPopup()
    popup.setText('Translation completed')
    try:
        for theme in ('Темная', 'Светлая', 'Темная', 'Светлая'):
            app.setProperty('ui_theme', theme)
            install_tooltip_style(app)
            popup.adjustSize()
            popup.show()
            QTest.qWait(30)
            image = popup.grab().toImage()
            pixel = image.pixelColor(image.width() // 2, round(4 * image.devicePixelRatio()))
            assert pixel.alpha() > 240  # Previously only the text was painted.
            assert (pixel.lightness() < 90) == (theme == 'Темная')
            assert popup.testAttribute(QtCore.Qt.WA_ShowWithoutActivating)
            popup.hide()
    finally:
        popup.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def test_queued_popup_updates_survive_window_disposal(popup_app):
    install_tooltip_style(popup_app)
    # Show/resize queue a second appearance pass. The native window can be
    # destroyed before that pass runs, even while its Python wrapper survives.
    for _ in range(3):
        popup = StatusPopup()
        popup.setText('Short-lived notification')
        popup.show()
        popup.resize(popup.width() + 10, popup.height())
        sip.delete(popup)
        popup_app.processEvents()


@pytest.mark.skipif(sys.platform != 'darwin', reason='requires actual Cocoa windows')
@pytest.mark.parametrize('theme', ['Темная', 'Светлая'])
@pytest.mark.parametrize('kind', ['tooltip', 'menu'])
def test_native_popup_background_does_not_fill_transparent_corners(popup_app, theme, kind):
    app = popup_app
    if app.platformName() != 'cocoa':
        pytest.skip('offscreen transparency does not establish native Cocoa behavior')
    import objc

    app.setProperty('ui_theme', theme)
    install_tooltip_style(app)
    owner = QtWidgets.QPushButton('Popup owner')
    owner.current_theme = theme
    owner.move(200, 150)
    owner.show()
    owner.activateWindow()
    # Finish Cocoa's activation before showing QTipLabel. A delayed owner
    # activation otherwise immediately dismisses the newly created tip.
    QTest.qWait(100)
    popup = None
    try:
        if kind == 'tooltip':
            QtWidgets.QToolTip.showText(owner.mapToGlobal(QtCore.QPoint(0, 25)),
                                       'Native rounded corner check', owner)
            QTest.qWait(50)
            popup = next(w for w in app.topLevelWidgets()
                         if w.metaObject().className() == 'QTipLabel' and w.isVisible())
        else:
            popup = QtWidgets.QMenu(owner)
            color = '#211d28' if theme == 'Темная' else '#faf7fc'
            popup.setStyleSheet(f'QMenu {{ background:{color}; border:1px solid #a18caf; border-radius:8px; padding:6px; }}')
            popup.addAction('Translation')
            popup.popup(owner.mapToGlobal(QtCore.QPoint(0, 25)))
        QTest.qWait(50)
        view = objc.objc_object(c_void_p=ctypes.c_void_p(int(popup.winId())))
        native_window = view.window()
        try:
            # Qt grab() already had zero-alpha corners before the fix. The
            # NSWindow behind them was still opaque dark gray on macOS.
            assert not native_window.isOpaque()
            assert native_window.backgroundColor().alphaComponent() == 0.0
        finally:
            del native_window, view
        assert popup.windowFlags() & QtCore.Qt.FramelessWindowHint
        assert popup.mask().isEmpty()  # A logical-pixel mask aliases Retina edges.
        image = popup.grab().toImage()
        assert image.pixelColor(0, 0).alpha() == 0
    finally:
        if kind == 'tooltip':
            QtWidgets.QToolTip.hideText()
            QTest.qWait(350)
        elif popup is not None:
            popup.close()
        owner.close()
        owner.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
