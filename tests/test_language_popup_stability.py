"""A searchable language list keeps its input and rows still while filtering."""
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtTest import QTest
import pytest
from unittest import mock

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
def test_main_and_hotkey_language_search_shrinks_without_moving_input(window, app, percent, tmp_path):
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
                actual = popup_rect(combo)
                assert actual.topLeft() == initial.topLeft(), (percent, name, query, initial, actual)
                assert actual.width() == initial.width(), (percent, name, query, initial, actual)
                assert actual.height() < initial.height() if query else actual.height() == initial.height()
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
        assert popup_rect(combo).topLeft() == initial.topLeft()
        assert popup_rect(combo).width() == initial.width()
        assert popup_rect(combo).height() < initial.height()
        QTest.keyClick(search, QtCore.Qt.Key_Return)
        settle(app)
        assert combo.currentData() == 'vi'
        assert not combo.view().window().isVisible()
    finally:
        combo.hidePopup()
        owner.close()
        owner.deleteLater()
        app.processEvents()


def test_another_field_opens_on_the_first_press_and_outside_closes_synchronously(app):
    owner = QtWidgets.QWidget()
    owner.resize(640, 640)
    first, second = DropDownCombo(owner), DropDownCombo(owner)
    first.setGeometry(10, 10, 250, 32)
    second.setGeometry(350, 10, 250, 32)
    for combo in (first, second):
        for language in LANGUAGES:
            combo.addItem(language.english_name, language.code)
    outside = QtWidgets.QPushButton('Another action', owner)
    outside.setGeometry(350, 560, 150, 32)
    clicks = []
    outside.clicked.connect(lambda: clicks.append(True))
    owner.show()
    settle(app)
    try:
        QTest.mouseClick(first, QtCore.Qt.LeftButton)
        assert first.view().window().isVisible()
        QTest.mousePress(second, QtCore.Qt.LeftButton)
        assert not first.view().window().isVisible()
        assert second.view().window().isVisible()
        QTest.mouseRelease(second, QtCore.Qt.LeftButton)
        assert second.view().window().isVisible()
        QTest.mousePress(outside, QtCore.Qt.LeftButton)
        assert not second.view().window().isVisible()
        QTest.mouseRelease(outside, QtCore.Qt.LeftButton)
        assert clicks == [True]
    finally:
        first.hidePopup()
        second.hidePopup()
        owner.close()
        owner.deleteLater()
        app.processEvents()


@pytest.mark.parametrize('embedded', (False, True))
def test_scaled_canvas_switches_fields_on_the_first_press(window, app, embedded):
    window.show_main_screen()
    settle(app)
    first, second = window.source_lang, window.target_lang
    with (mock.patch.object(first, '_prepare_native_popup', wraps=(lambda: None) if embedded else first._prepare_native_popup),
          mock.patch.object(second, '_prepare_native_popup', wraps=(lambda: None) if embedded else second._prepare_native_popup)):
        first.showPopup()
        settle(app)
        controller = window._ui_scale_controller
        point = controller.map_widget_to_view(second, second.rect().center())
        QTest.mousePress(controller.view.viewport(), QtCore.Qt.LeftButton, pos=point)
        assert not first.view().window().isVisible()
        assert second.view().window().isVisible()
        QTest.mouseRelease(controller.view.viewport(), QtCore.Qt.LeftButton, pos=point)
        assert second.view().window().isVisible()
        second.hidePopup()


def test_mouse_grab_delivers_outside_press_to_the_old_popup_but_opens_the_new_field(app):
    owner = QtWidgets.QWidget()
    owner.resize(640, 300)
    first, second = DropDownCombo(owner), DropDownCombo(owner)
    first.setGeometry(10, 10, 250, 32)
    second.setGeometry(350, 10, 250, 32)
    for combo in (first, second):
        combo.addItems(['One', 'Two', 'Three'])
    owner.show()
    settle(app)
    try:
        first.showPopup()
        settle(app)
        popup = first.view().window()
        global_point = second.mapToGlobal(second.rect().center())
        QTest.mousePress(popup, QtCore.Qt.LeftButton, pos=popup.mapFromGlobal(global_point))
        assert not popup.isVisible()
        assert second.view().window().isVisible()
        opened = second.view().window()
        QTest.mouseRelease(opened, QtCore.Qt.LeftButton, pos=opened.mapFromGlobal(global_point))
        assert second.view().window().isVisible()
    finally:
        first.hidePopup()
        second.hidePopup()
        owner.close()
        owner.deleteLater()
        app.processEvents()


def test_dragged_scroll_position_is_not_reset_by_popup_layout(app):
    combo = DropDownCombo()
    for language in LANGUAGES:
        combo.addItem(language.english_name, language.code)
    combo.show()
    combo.showPopup()
    settle(app)
    try:
        scrollbar = combo.view().verticalScrollBar()
        assert scrollbar.maximum() > 0
        scrollbar.setValue(scrollbar.maximum())
        expected = scrollbar.value()
        combo._queue_popup_layout()
        settle(app)
        assert scrollbar.value() == expected
        combo._language_search.setText('Vietnamese')
        settle(app)
        assert scrollbar.value() == 0
        combo._language_search.clear()
        settle(app)
        assert scrollbar.value() == 0
    finally:
        combo.hidePopup()
        combo.close()
        combo.deleteLater()


def test_keyboard_escape_closes_search_popup_without_selecting_a_result(app):
    combo = DropDownCombo()
    for language in LANGUAGES:
        combo.addItem(language.english_name, language.code)
    combo.setCurrentIndex(combo.findData('ru'))
    combo.show()
    combo.showPopup()
    settle(app)
    try:
        combo._language_search.setText('Vietnamese')
        settle(app)
        QTest.keyClick(combo._language_search, QtCore.Qt.Key_Escape)
        assert not combo.view().window().isVisible()
        assert combo.currentData() == 'ru'
    finally:
        combo.hidePopup()
        combo.close()
        combo.deleteLater()


@pytest.mark.parametrize('direction', (QtCore.Qt.LeftToRight, QtCore.Qt.RightToLeft))
def test_filtering_preserves_flag_column_when_scrollbar_disappears(app, direction):
    combo = DropDownCombo()
    combo.setLayoutDirection(direction)
    for language in LANGUAGES:
        combo.addItem(language.english_name, language.code)
    combo.show()
    combo.showPopup()
    settle(app)
    popup = combo.view().window()
    viewport = combo.view().viewport()
    column = (lambda: viewport.mapTo(popup, QtCore.QPoint(
        viewport.width() if direction == QtCore.Qt.RightToLeft else 0, 0)).x())
    before = column()
    try:
        assert combo.view().verticalScrollBar().isVisible()
        combo._language_search.setText('Vietnamese')
        settle(app)
        assert not combo.view().verticalScrollBar().isVisible()
        assert column() == before
        combo._language_search.clear()
        settle(app)
        assert column() == before
    finally:
        combo.hidePopup()
        combo.close()
        combo.deleteLater()
