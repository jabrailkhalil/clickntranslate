"""Theme changes must work through Qt signals and the scaled visible button."""
import sys

import pytest
from PyQt5 import QtCore, QtGui
from PyQt5.QtTest import QTest

import main
from test_desktop_ux import app, window


def test_theme_clicked_signal_accepts_qt_checked_argument(window, app, monkeypatch):
    errors = []
    monkeypatch.setattr(sys, 'excepthook', lambda *error: errors.append(error))
    original = window.current_theme
    for expected in (('Светлая' if original == 'Темная' else 'Темная'), original):
        window.theme_button.click()
        app.processEvents()
        assert not errors, [(kind.__name__, str(error)) for kind, error, _ in errors]
        assert window.current_theme == expected
    assert window.save_config.call_count == 2


@pytest.mark.parametrize('percent', [80, 100, 137, 200])
@pytest.mark.parametrize('page', ['main', 'settings'])
def test_visible_theme_button_changes_both_palettes(window, app, monkeypatch, percent, page):
    errors = []
    monkeypatch.setattr(sys, 'excepthook', lambda *error: errors.append(error))
    window.set_ui_scale_percent(percent)
    if page == 'settings':
        window.show_settings()
    app.processEvents()
    controller = window._ui_scale_controller
    original = window.current_theme
    for expected in (('Светлая' if original == 'Темная' else 'Темная'), original):
        QTest.mouseClick(controller.view.viewport(), QtCore.Qt.LeftButton,
                         pos=controller.map_widget_to_view(window.theme_button))
        app.processEvents()
        assert not errors, [(kind.__name__, str(error)) for kind, error, _ in errors]
        assert window.current_theme == expected
        assert window.updatesEnabled() and window.ui_root.updatesEnabled()
        background = QtGui.QColor(main.THEMES[expected]['background'])
        assert controller.scene.backgroundBrush().color() == background
        if page == 'settings':
            assert window.settings_window._ui_theme == expected
        # The native frame must also change; checking the current palette alone
        # lets a swallowed clicked(bool) exception produce a false positive.
        image = window.grab().toImage()
        assert image.pixelColor(1, image.height() // 2) == background
