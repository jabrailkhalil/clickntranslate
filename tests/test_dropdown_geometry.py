"""First opening, live models and available-space limits of actual Qt lists."""
import pytest
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtTest import QTest

from settings_window import DropDownCombo, modern_combo_style
from ui_scaling import combo_popup_geometry, configure_interface_style


@pytest.fixture
def picker():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    configure_interface_style()
    owner = QtWidgets.QWidget(None, QtCore.Qt.FramelessWindowHint)
    owner.setGeometry(100, 100, 450, 220)
    combo = DropDownCombo(owner)
    combo.setGeometry(200, 120, 140, 32)
    combo.setMaxVisibleItems(9)
    combo.setStyleSheet(modern_combo_style(False))
    combo.set_popup_background('#f1edf4')
    owner.show()
    owner.activateWindow()
    QTest.qWait(50)
    yield app, owner, combo
    combo.hidePopup()
    owner.close()
    owner.deleteLater()
    app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def test_long_localized_label_fits_on_first_opening(picker):
    app, owner, combo = picker
    label = 'Перевод выделенного текста в отдельном окне'
    combo.addItems(['Короткая строка', label])
    combo.showPopup()
    QTest.qWait(70)
    view = combo.view()
    assert view.viewport().width() >= QtGui.QFontMetrics(view.font()).horizontalAdvance(label) + 12
    before = view.window().geometry()
    combo.hidePopup()
    combo.showPopup()
    QTest.qWait(70)
    assert view.window().geometry() == before


def test_live_model_grows_without_reopening_or_changing_selection(picker):
    app, owner, combo = picker
    combo.addItem('English', 'en')
    combo.showPopup()
    old_height = combo.view().window().height()
    QtCore.QTimer.singleShot(10, lambda: combo.addItems([f'Language {i}' for i in range(20)]))
    QTest.qWait(100)
    assert combo.view().window().isVisible()
    assert combo.view().window().height() > old_height
    assert combo.currentData() == 'en'
    assert combo.view().verticalScrollBar().isVisible()
    combo.view().scrollToBottom()
    app.processEvents()
    last = combo.model().index(combo.count() - 1, 0)
    assert combo.view().viewport().rect().contains(combo.view().visualRect(last).center())


@pytest.mark.parametrize('offset', [QtCore.QPoint(0, 0), QtCore.QPoint(260, 0), QtCore.QPoint(130, 100)])
def test_popup_fits_a_small_available_area_and_all_rows_remain_reachable(picker, offset):
    app, owner, combo = picker
    available = QtCore.QRect(100, 100, 360, 220)
    combo.move(offset)
    combo.addItems([('A long language name ' * 6) + str(i) for i in range(40)])
    combo.setMaxVisibleItems(30)
    combo._available_screen_rect = lambda: available
    combo.showPopup()
    QTest.qWait(70)
    view = combo.view()
    assert available.contains(view.window().geometry())
    assert view.verticalScrollBar().isVisible()
    view.scrollToBottom()
    app.processEvents()
    last = combo.model().index(combo.count() - 1, 0)
    row = view.visualRect(last)
    visible = row.intersected(view.viewport().rect())
    assert not visible.isEmpty()
    assert visible.height() == row.height()


@pytest.mark.parametrize('bounds', [QtCore.QRect(-1280, -100, 1280, 700), QtCore.QRect(0, 25, 1280, 675)])
def test_monitor_edges_include_negative_coordinates(bounds):
    anchor = QtCore.QRect(bounds.right() - 149, bounds.bottom() - 31, 150, 32)
    result = combo_popup_geometry(anchor, QtCore.QSize(2000, 1000), bounds, 3)
    assert bounds.contains(result)
    assert result.bottom() == anchor.top() - 4
    assert result.right() == bounds.right()
