"""Cancel valid companion drafts without publishing them or changing arrow state."""
import pytest
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtTest import QTest

from test_desktop_ux import app, window


@pytest.mark.parametrize('locale,language,scale', [('en_US', 'en', 80), ('de_DE', 'de', 80), ('ar_SA', 'ar', 137)])
@pytest.mark.parametrize('draft', ['value', 'empty'])
def test_companion_escape_cancels_before_blur_and_next_arrow(window, app, locale, language, scale, draft):
    window.setLocale(QtCore.QLocale(locale))
    window.set_interface_language(language)
    window.config.update(desktop_assistant_size=100, desktop_assistant_opacity=80,
                         desktop_assistant_enabled=False)
    window.set_ui_scale_percent(scale)
    if language == 'de':
        window.toggle_theme()
    window.show_settings()
    settings = window.settings_window
    settings._set_settings_page(3)
    page = settings.settings_assistant_page
    control, other = page.values['size'], page.values['opacity']
    control.editor.setLocale(QtCore.QLocale(locale))
    app.processEvents()
    assert control.value() == 100 and window.config['desktop_assistant_size'] == 100
    changes = []
    control.valueChanged.connect(changes.append)
    window.save_config.reset_mock()

    edit = control.lineEdit()
    edit.setFocus(QtCore.Qt.TabFocusReason)
    app.processEvents()
    edit.selectAll()
    if draft == 'value':
        event = QtGui.QInputMethodEvent()
        event.setCommitString(control.editor.locale().toString(130))
        QtWidgets.QApplication.sendEvent(edit, event)
    else:
        QTest.keyClick(edit, QtCore.Qt.Key_Backspace)
    assert control.value() == 100 and window.config['desktop_assistant_size'] == 100
    QTest.keyClick(edit, QtCore.Qt.Key_Escape)
    other.editor.setFocus(QtCore.Qt.TabFocusReason)
    app.processEvents()

    assert control.value() == 100 and window.config['desktop_assistant_size'] == 100
    assert edit.text() == control.editor.textFromValue(100) + control.editor.suffix()
    assert not edit.hasSelectedText()
    assert changes == []
    window.save_config.assert_not_called()
    assert settings._settings_page_index == 3
    assert control.layoutDirection() == QtCore.Qt.LeftToRight
    QTest.mouseClick(control.increase, QtCore.Qt.LeftButton)
    assert control.value() == 101 and window.config['desktop_assistant_size'] == 101
    assert changes == [101]
    window.save_config.assert_called_once_with()
