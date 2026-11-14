"""Secondary surfaces stay with their actual, possibly scene-rendered owner."""
from copy import deepcopy
from unittest import mock

import pytest
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtTest import QTest

import main
from settings_window import OcrLanguageManagerDialog
from styled_dialogs import StyledMessageBox
from test_desktop_assistant import app
from test_language_package_manager import _AppParent, _ManagerOwner
from ui_scaling import widget_global_rect
from window_appearance import install_window_appearance


@pytest.mark.parametrize('section', [0, 1])
@pytest.mark.parametrize('percent', [80, 137])
@pytest.mark.parametrize('locale,theme', [('ru', 'Темная'), ('ar', 'Светлая')])
def test_engine_tools_menu_follows_dialog_across_connected_monitors(app, section, percent, locale, theme):
    if app.platformName() == 'offscreen':
        pytest.skip('Requires native QMenu placement on the connected monitors')
    parent = _AppParent()
    parent.current_interface_language = locale
    parent.current_theme = theme
    parent.config = deepcopy(main.DEFAULT_CONFIG)
    owner = _ManagerOwner(parent)
    install_window_appearance(app, percent, theme)
    dialog = None
    with (mock.patch.object(OcrLanguageManagerDialog, '_start_runtime_probe'),
          mock.patch.object(OcrLanguageManagerDialog, '_start_argos_catalog_refresh')):
        try:
            dialog = OcrLanguageManagerDialog(owner)
            dialog.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
            dialog.show()
            dialog.tabs.setCurrentIndex(section)
            app.processEvents()
            tabs = (dialog.ocr_tabs, dialog.translation_tabs)[section]
            button, menu = tabs._tools_button, tabs._tools_menu
            observations = []
            screens = app.screens()
            for visit, screen in enumerate(list(reversed(screens)) + screens):
                bounds = screen.availableGeometry()
                if visit < len(screens):
                    dialog.move(bounds.topLeft() + QtCore.QPoint(100, 80))
                else:
                    dialog.move(bounds.bottomRight() - QtCore.QPoint(dialog.width() + 8, dialog.height() + 8))
                QTest.qWait(30)
                anchor = widget_global_rect(button)

                def inspect_and_close():
                    observations.append((QtCore.QRect(menu.frameGeometry()), menu.screen()))
                    menu.close()

                QtCore.QTimer.singleShot(100, inspect_and_close)
                QTest.mouseClick(button, QtCore.Qt.LeftButton)
                QTest.qWait(120)
                geometry, actual_screen = observations[-1]
                assert actual_screen is screen, (anchor, geometry, actual_screen.name(), screen.name())
                assert bounds.contains(geometry), (bounds, geometry)
                # Qt can clamp the menu horizontally at the screen edge. It
                # must still overlap the button's horizontal span.
                assert geometry.left() <= anchor.center().x() <= geometry.right()
                assert (abs(geometry.top() - anchor.bottom()) <= 5
                        or abs(geometry.bottom() - anchor.top()) <= 5)
        finally:
            if dialog is not None:
                dialog.close()
                dialog.deleteLater()
            owner.deleteLater()
            parent.deleteLater()
            app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
            app.processEvents()


def test_secondary_dialog_and_engine_picker_stay_on_their_owner_monitor(app):
    if app.platformName() == 'offscreen':
        pytest.skip('Requires native dialog and combo placement')
    parent = _AppParent()
    parent.config = deepcopy(main.DEFAULT_CONFIG)
    parent.setGeometry(40, 40, 800, 500)
    parent.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
    parent.show()
    owner = _ManagerOwner(parent)
    install_window_appearance(app, 100, 'Темная')
    dialog = box = None
    with (mock.patch.object(OcrLanguageManagerDialog, '_start_runtime_probe'),
          mock.patch.object(OcrLanguageManagerDialog, '_start_argos_catalog_refresh')):
        try:
            for screen in reversed(app.screens()):
                bounds = screen.availableGeometry()
                parent.move(bounds.topLeft() + QtCore.QPoint(100, 100))
                QTest.qWait(30)
                dialog = OcrLanguageManagerDialog(owner)
                dialog.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
                dialog.show()
                QTest.qWait(40)
                assert dialog.screen() is screen
                assert bounds.contains(dialog.frameGeometry())
                for picker in dialog._engine_selectors:
                    dialog.tabs.setCurrentIndex(dialog._engine_selectors.index(picker))
                    app.processEvents()
                    picker.showPopup()
                    QTest.qWait(40)
                    popup = picker.view().window()
                    assert popup.screen() is screen
                    assert bounds.contains(popup.frameGeometry())
                    assert abs(popup.x() - widget_global_rect(picker).left()) <= 5
                    picker.hidePopup()
                box = StyledMessageBox(dialog)
                box.setText('Engine message on the same monitor')
                box.setStandardButtons(StyledMessageBox.Ok)
                box.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
                box.show()
                QTest.qWait(40)
                assert box.screen() is screen
                assert bounds.contains(box.frameGeometry())
                box.close()
                box.deleteLater()
                box = None
                dialog.close()
                dialog.deleteLater()
                dialog = None
        finally:
            for widget in (box, dialog, owner, parent):
                if widget is not None:
                    widget.close()
                    widget.deleteLater()
            app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
            app.processEvents()
