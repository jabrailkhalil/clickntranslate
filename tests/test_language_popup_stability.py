"""A searchable language list keeps its input and rows still while filtering."""
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtTest import QTest
import pytest

from languages import LANGUAGES, language_code_from_name
from settings_window import DropDownCombo
from test_desktop_ux import app, window


def popup_rect(combo):
    popup = combo.view().window()
    proxy = popup.graphicsProxyWidget()
    root = combo.window()
    if proxy is not None and popup.testAttribute(QtCore.Qt.WA_DontShowOnScreen):
        return proxy.mapRectToItem(root.graphicsProxyWidget(), proxy.boundingRect()).toAlignedRect()
    return popup.geometry()


def settle(app):
    QTest.qWait(35)
    app.processEvents()


@pytest.mark.parametrize('percent', (80, 100, 137))
def test_main_and_hotkey_language_search_keeps_open_geometry(window, app, percent, tmp_path):
    window.set_ui_scale_percent(percent)
    window.show_main_screen()
    settle(app)
    for name in ('source_lang', 'target_lang', 'hotkey_source_combo', 'hotkey_target_combo'):
        combo = getattr(window, name)
        if combo.count() < 12:
            continue  # OCR may expose only the two installed Windows languages.
        original_text = combo.currentText()
        combo.showPopup()
        settle(app)
        try:
            search = combo._language_search
            initial = popup_rect(combo)
            search_rect = search.geometry()
            assert combo.view().window().rect().contains(search_rect), (percent, name)
            for query in ('Vietnamese', 'no-such-language', ''):
                QTest.mouseClick(search, QtCore.Qt.LeftButton)
                QTest.keyClick(search, QtCore.Qt.Key_A, QtCore.Qt.ControlModifier)
                if query:
                    QTest.keyClicks(search, query)
                else:
                    QTest.keyClick(search, QtCore.Qt.Key_Backspace)
                settle(app)
                assert popup_rect(combo) == initial, (percent, name, query, initial, popup_rect(combo))
                assert search.geometry() == search_rect, (percent, name, query)
                assert combo.view().window().isVisible(), (percent, name, query)
            if percent == 100:
                combo.view().window().grab().save(str(tmp_path / (name + '.png')))
            search.setText('Vietnamese')
            settle(app)
            if percent == 100:
                combo.view().window().grab().save(str(tmp_path / (name + '-filtered.png')))
            QTest.keyClick(search, QtCore.Qt.Key_Down)
            settle(app)
            row = combo.view().currentIndex().row()
            code = combo.itemData(row) or language_code_from_name(combo.itemText(row), window.current_interface_language)
            assert code == 'vi', (percent, name)
            QTest.keyClick(combo.view(), QtCore.Qt.Key_Return)
            settle(app)
            code = combo.currentData() or language_code_from_name(combo.currentText(), window.current_interface_language)
            assert code == 'vi', (percent, name)
            assert not combo.view().window().isVisible(), (percent, name)
        finally:
            combo.hidePopup()
            combo.setCurrentIndex(combo.findText(original_text))
            settle(app)


def test_standalone_search_at_bottom_keeps_above_anchor_and_keyboard_selection(app):
    owner = QtWidgets.QWidget()
    owner.resize(260, 150)
    bounds = app.primaryScreen().availableGeometry()
    owner.move(bounds.left() + 20, bounds.bottom() - owner.height() - 20)
    combo = DropDownCombo(owner)
    combo.setGeometry(10, 105, 220, 32)
    for language in LANGUAGES:
        combo.addItem(language.english_name, language.code)
    owner.show()
    settle(app)
    try:
        combo.showPopup()
        settle(app)
        initial = popup_rect(combo)
        anchor = combo.mapToGlobal(QtCore.QPoint())
        assert initial.bottom() < anchor.y()
        search = combo._language_search
        search.setText('Vietnamese')
        settle(app)
        assert popup_rect(combo) == initial
        QTest.keyClick(search, QtCore.Qt.Key_Return)
        settle(app)
        assert combo.currentData() == 'vi'
        assert not combo.view().window().isVisible()
    finally:
        combo.hidePopup()
        owner.close()
        owner.deleteLater()
        app.processEvents()
