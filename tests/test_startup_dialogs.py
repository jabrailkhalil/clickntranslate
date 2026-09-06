import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import threading
from unittest import mock

from PyQt5 import QtCore, QtTest, QtWidgets

from startup_dialogs import TEXT, replacement_dialog, ask_replacement, close_with_progress
from window_appearance import install_window_appearance
from qt_layout_test_support import ensure_layout_fonts

_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
_APP.setQuitOnLastWindowClosed(False)
ensure_layout_fonts(_APP)


def test_replacement_dialog_fits_every_language_theme_and_scale():
    manager = install_window_appearance(_APP, 100, 'Темная')
    try:
        with mock.patch.object(manager, 'available_geometry', return_value=QtCore.QRect(0, 0, 3840, 2160)):
            for theme in ('Темная', 'Светлая'):
                manager.refresh(theme=theme)
                for lang in TEXT:
                    box = replacement_dialog(lang, '1.7.1')
                    box.show()
                    for percent in (80, 100, 150):
                        manager.refresh(percent)
                        _APP.processEvents()
                        assert box.windowFlags() & QtCore.Qt.FramelessWindowHint
                        assert box._dark == (theme == 'Темная')
                        for button in (box.replace_button, box.existing_button):
                            assert button.width() >= button.fontMetrics().horizontalAdvance(button.text()) + 10, (theme, lang, percent, box.size(), button.font().pixelSize(), button.sizeHint())
                            rect = QtCore.QRect(button.mapTo(box, QtCore.QPoint()), button.size())
                            assert box.rect().contains(rect)
                        assert not box.replace_button.geometry().intersects(box.existing_button.geometry())
                    box.close()
                    box.deleteLater()
                    _APP.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    finally:
        for box in _APP.topLevelWidgets():
            if hasattr(box, 'replace_button'):
                box.close()
                box.deleteLater()
        _APP.removeEventFilter(manager)
        del _APP._dialog_appearance
        manager.deleteLater()


def test_replacement_requires_the_explicit_button_and_escape_keeps_old_copy():
    for choice in ('replace', 'existing', 'escape'):
        def choose():
            box = next(w for w in _APP.topLevelWidgets() if hasattr(w, 'replace_button') and w.isVisible())
            if choice == 'escape':
                QtTest.QTest.keyClick(box, QtCore.Qt.Key_Escape)
            else:
                getattr(box, choice + '_button').click()
        QtCore.QTimer.singleShot(0, choose)
        assert ask_replacement('ru', '1.7.1') == (choice == 'replace')


def test_closing_wait_keeps_the_ui_responsive_and_reports_failure():
    for success in (False, True):
        released = threading.Event()
        observed = []
        def close():
            assert released.wait(timeout=3)
            return success
        def tick():
            observed.append(True)
            released.set()
        QtCore.QTimer.singleShot(20, tick)
        assert close_with_progress('ru', close) == success
        assert observed
