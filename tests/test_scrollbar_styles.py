"""Shared scrollbar geometry, rendering and input on native and offscreen Qt."""

import pytest
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtTest import QTest

from scrollbar_styles import SCROLLBAR_WIDTH
from styled_dialogs import install_tooltip_style
from window_appearance import install_window_appearance


@pytest.fixture
def app():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    app.setQuitOnLastWindowClosed(False)
    theme, scale = app.property('ui_theme'), app.property('ui_scale_percent')
    manager = getattr(app, '_dialog_appearance', None)
    appearance = (manager.percent, manager.theme) if manager is not None else None
    install_tooltip_style(app)
    yield app
    app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    current = getattr(app, '_dialog_appearance', None)
    if current is not manager and current is not None:
        app.removeEventFilter(current)
        del app._dialog_appearance
        current.deleteLater()
    elif manager is not None:
        manager.refresh(*appearance)
    app.setProperty('ui_theme', theme)
    app.setProperty('ui_scale_percent', scale)
    app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    app.processEvents()


def _area(kind, owner):
    if kind == 'scroll':
        area = QtWidgets.QScrollArea(owner)
        content = QtWidgets.QWidget()
        content.setMinimumSize(1000, 2000)
        area.setWidget(content)
    elif kind == 'table':
        area = QtWidgets.QTableWidget(100, 20, owner)
    elif kind == 'list':
        area = QtWidgets.QListWidget(owner)
        area.addItems([f'{i}: ' + 'Long item ' * 30 for i in range(100)])
    else:
        area = (QtWidgets.QTextBrowser if kind == 'browser' else QtWidgets.QTextEdit)(owner)
        area.setLineWrapMode(QtWidgets.QTextEdit.NoWrap)
        area.setPlainText('\n'.join('Long line ' * 30 for _ in range(100)))
    area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
    area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
    return area


def _option(bar):
    option = QtWidgets.QStyleOptionSlider()
    option.initFrom(bar)
    option.orientation = bar.orientation()
    option.minimum, option.maximum = bar.minimum(), bar.maximum()
    option.sliderPosition, option.sliderValue = bar.sliderPosition(), bar.value()
    option.singleStep, option.pageStep = bar.singleStep(), bar.pageStep()
    return option


def _rect(bar, part):
    return bar.style().subControlRect(QtWidgets.QStyle.CC_ScrollBar, _option(bar), part, bar)


@pytest.mark.parametrize('dark', [False, True])
@pytest.mark.parametrize('kind', ['scroll', 'table', 'list', 'editor', 'browser'])
def test_scrollbars_are_slim_in_both_axes_and_keep_input(app, dark, kind):
    owner = QtWidgets.QWidget()
    # Explicit owner theme takes precedence over the application's theme.
    owner.current_theme = 'Темная' if dark else 'Светлая'
    app.setProperty('ui_theme', 'Светлая' if dark else 'Темная')
    area = _area(kind, owner)
    owner.setStyleSheet('QWidget { color: #cccccc; }')
    QtWidgets.QVBoxLayout(owner).addWidget(area)
    owner.resize(420, 300)
    owner.show()
    app.processEvents()
    try:
        for bar in (area.verticalScrollBar(), area.horizontalScrollBar()):
            assert bar.maximum() > 0
            vertical = bar.orientation() == QtCore.Qt.Vertical
            assert (bar.width() if vertical else bar.height()) == SCROLLBAR_WIDTH
            for part in (QtWidgets.QStyle.SC_ScrollBarAddLine, QtWidgets.QStyle.SC_ScrollBarSubLine):
                assert _rect(bar, part).isEmpty()
            assert bar.property('_cntScrollDark') is dark
            bar.setValue(bar.maximum() // 2)
            point = _rect(bar, QtWidgets.QStyle.SC_ScrollBarSlider).center()
            QTest.mouseMove(bar, point)
            QTest.mousePress(bar, QtCore.Qt.LeftButton, pos=point)
            QTest.qWait(20)
            image = bar.grab().toImage()
            dpr = image.devicePixelRatioF()
            color = image.pixelColor(round(point.x() * dpr), round(point.y() * dpr))
            assert color.name() == ('#aa91c9' if dark else '#7a5fa1')
            before = bar.value()
            end = point + (QtCore.QPoint(0, 30) if vertical else QtCore.QPoint(30, 0))
            move = QtGui.QMouseEvent(QtCore.QEvent.MouseMove, end,
                                    QtCore.Qt.NoButton, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier)
            app.sendEvent(bar, move)
            QTest.mouseRelease(bar, QtCore.Qt.LeftButton, pos=end)
            assert bar.value() > before
            before = bar.value()
            wheel = QtGui.QWheelEvent(QtCore.QPointF(end), QtCore.QPointF(bar.mapToGlobal(end)),
                                     QtCore.QPoint(), QtCore.QPoint(0, 120),
                                     QtCore.Qt.NoButton, QtCore.Qt.NoModifier, QtCore.Qt.NoScrollPhase, False)
            app.sendEvent(bar, wheel)
            assert bar.value() < before
    finally:
        owner.close()
        owner.deleteLater()


def test_theme_switch_does_not_replace_application_stylesheet(app):
    area = _area('editor', None)
    area.show()
    app.processEvents()
    try:
        original = app.styleSheet()
        for dark in (True, False, True):
            app.setProperty('ui_theme', 'Темная' if dark else 'Светлая')
            install_tooltip_style(app, dark)
            app.processEvents()
            assert app.styleSheet() == original
            assert app.styleSheet().count('/* clickntranslate-scrollbars */') == 1
            assert area.verticalScrollBar().property('_cntScrollDark') is dark
    finally:
        area.close()
        area.deleteLater()


@pytest.mark.parametrize('percent', [80, 100, 150, 200])
def test_scrollbars_stay_slim_when_dialog_text_is_scaled(app, percent):
    manager = install_window_appearance(app, percent, 'Светлая')
    dialog = QtWidgets.QDialog()
    area = _area('editor', dialog)
    QtWidgets.QVBoxLayout(dialog).addWidget(area)
    dialog.resize(420, 300)
    dialog.show()
    app.processEvents()
    try:
        for _ in range(3):
            manager.apply(dialog)
            app.processEvents()
            assert area.verticalScrollBar().width() == SCROLLBAR_WIDTH
            assert area.horizontalScrollBar().height() == SCROLLBAR_WIDTH
    finally:
        dialog.close()
        dialog.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
