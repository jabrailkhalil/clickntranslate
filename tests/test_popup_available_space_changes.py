"""An open searchable list follows changing available space without losing input."""
from types import SimpleNamespace

import pytest
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtTest import QTest

from languages import LANGUAGES
from settings_window import DropDownCombo, modern_combo_style


def settle(app):
    app.processEvents()
    QTest.qWait(35)
    app.processEvents()


@pytest.fixture
def picker():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    owner = QtWidgets.QWidget(None, QtCore.Qt.FramelessWindowHint)
    owner.setLayoutDirection(QtCore.Qt.LeftToRight)
    owner.setGeometry(0, 0, 700, 600)
    combo = DropDownCombo(owner)
    combo.setGeometry(20, 450, 220, 32)
    font = QtGui.QFont(combo.font())
    font.setPixelSize(14)
    combo.setFont(font)
    combo.setStyleSheet(modern_combo_style(True, 14))
    for language in LANGUAGES:
        combo.addItem(language.english_name, language.code)
    available = [QtCore.QRect(0, 0, 800, 600)]
    combo._available_screen_rect = lambda: QtCore.QRect(available[0])
    owner.show()
    settle(app)
    yield SimpleNamespace(app=app, owner=owner, combo=combo, available=available)
    combo.hidePopup()
    owner.close()
    owner.deleteLater()
    app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    app.processEvents()


@pytest.mark.parametrize('origin,next_bounds', [
    (QtCore.QPoint(0, 0), QtCore.QRect(0, 0, 800, 560)),
    (QtCore.QPoint(-800, -120), QtCore.QRect(-840, -160, 800, 560)),
], ids=('taskbar-height', 'negative-monitor-origin'))
def test_open_search_popup_refits_changed_available_bounds_and_still_selects_with_keyboard(
        picker, origin, next_bounds):
    app, owner, combo = picker.app, picker.owner, picker.combo
    owner.move(origin)
    picker.available[0] = QtCore.QRect(origin, QtCore.QSize(800, 600))
    settle(app)
    combo.showPopup()
    settle(app)
    popup = combo.view().window()
    before = QtCore.QRect(popup.geometry())
    anchor = QtCore.QRect(combo.mapToGlobal(QtCore.QPoint()), combo.size())
    assert picker.available[0].contains(before)
    assert before.top() > anchor.bottom()  # Initially use the short space below.

    picker.available[0] = next_bounds
    combo._layout_open_popup()
    settle(app)
    fitted = QtCore.QRect(popup.geometry())
    assert next_bounds.contains(fitted), (before, fitted, next_bounds)
    assert fitted.bottom() < anchor.top()
    assert popup.isVisible()

    search = combo._language_search
    search.setFocus(QtCore.Qt.PopupFocusReason)
    QTest.keyClicks(search, 'Vietnamese')
    settle(app)
    filtered = QtCore.QRect(popup.geometry())
    assert filtered.topLeft() == fitted.topLeft()
    assert filtered.width() == fitted.width() and filtered.height() < fitted.height()
    assert next_bounds.contains(filtered)
    assert popup.rect().contains(search.geometry())
    QTest.keyClick(search, QtCore.Qt.Key_Down)
    QTest.keyClick(combo.view(), QtCore.Qt.Key_Return)
    settle(app)
    assert combo.currentData() == 'vi'
    assert not popup.isVisible()


def test_filtering_stays_put_and_new_matching_rows_remain_reachable_after_growth(picker):
    app, combo = picker.app, picker.combo
    combo.move(20, 100)
    combo.clear()
    for language in LANGUAGES[:12]:
        combo.addItem(language.english_name, language.code)
    combo.showPopup()
    settle(app)
    popup = combo.view().window()
    initial = QtCore.QRect(popup.geometry())
    search = combo._language_search
    search_geometry = QtCore.QRect(search.geometry())
    QTest.keyClicks(search, 'ian')
    settle(app)
    filtered = QtCore.QRect(popup.geometry())
    assert filtered.topLeft() == initial.topLeft() and filtered.width() == initial.width()
    assert filtered.height() < initial.height()
    assert search.geometry() == search_geometry

    # A live provider catalog can add matching rows while the filter is active.
    added = [language for language in LANGUAGES[12:] if 'ian' in language.english_name.casefold()]
    assert len(added) > 5
    for language in added:
        combo.addItem(language.english_name, language.code)
    settle(app)
    grown = QtCore.QRect(popup.geometry())
    assert grown.topLeft() == initial.topLeft()
    assert grown.height() > filtered.height()
    assert picker.available[0].contains(grown)
    assert search.text() == 'ian' and search.geometry() == search_geometry
    view = combo.view()
    view.scrollToBottom()
    settle(app)
    last = combo.model().index(combo.count() - 1, combo.modelColumn())
    row = view.visualRect(last)
    assert row.height() > 0 and view.viewport().rect().contains(row.center())
    assert row.intersected(view.viewport().rect()).height() == row.height()
    QTest.mouseClick(view.viewport(), QtCore.Qt.LeftButton, pos=row.center())
    settle(app)
    assert combo.currentIndex() == combo.count() - 1
    assert combo.currentData() == added[-1].code
    assert not popup.isVisible()
