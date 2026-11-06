"""Scrolling paints the visible list before any mouse hover can repair it.

QWidget.grab()/render() are deliberately not used: those repaint the widget and
can hide a stale backing-store bug. The offscreen-only pixel check reads Qt's
existing synthetic backing store through its offscreen QScreen implementation.
"""
import pytest
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtTest import QTest

from settings_window import DropDownCombo
from test_desktop_ux import app


class _PaintWatch(QtCore.QObject):
    def __init__(self, viewport):
        super().__init__(viewport)
        self.regions = []
        viewport.installEventFilter(self)

    def eventFilter(self, watched, event):
        if event.type() == QtCore.QEvent.Paint:
            self.regions.append(QtGui.QRegion(event.region()))
        return False


def _settle(app):
    app.processEvents()
    QTest.qWait(25)
    app.processEvents()


@pytest.fixture
def picker(app):
    widgets = []
    def create(dark, embedded=False, legacy=False):
        owner = QtWidgets.QWidget()
        owner.resize(500, 400)
        combo = DropDownCombo(owner)
        combo.setGeometry(20, 20, 330, 32)
        combo.setMaxVisibleItems(6)
        if legacy:
            combo.setView(QtWidgets.QListView(combo))
            from combo_popup import PopupRowDelegate
            combo.setItemDelegate(PopupRowDelegate(combo))
            combo.view().setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        combo.set_popup_background('#17181d' if dark else '#e9e4ed')
        for row in range(80):
            pixmap = QtGui.QPixmap(18, 12)
            pixmap.fill(QtGui.QColor.fromHsv((row * 37) % 360, 170, 215))
            combo.addItem(QtGui.QIcon(pixmap), f'Row {row:03d} / scrolling label', f'entry-{row}')
        if embedded:
            scene = QtWidgets.QGraphicsScene()
            proxy = scene.addWidget(owner)
            view = QtWidgets.QGraphicsView(scene)
            view.resize(600, 480)
            view.show()
            widgets.extend((view, scene))
        else:
            owner.show()
        widgets.append(owner)
        _settle(app)
        combo.showPopup()
        _settle(app)
        if legacy:
            combo.view().setStyleSheet('QAbstractItemView { background:transparent; border:0; padding:0; }')
            combo.view().viewport().setAutoFillBackground(False)
            _settle(app)
        assert combo.view().verticalScrollBar().maximum() > 0
        return combo
    yield create
    for widget in widgets:
        if isinstance(widget, QtWidgets.QWidget):
            for combo in widget.findChildren(DropDownCombo):
                combo.hidePopup()
            widget.close()
        widget.deleteLater()
    app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def _scroll(combo, method, app):
    view = combo.view()
    bar = view.verticalScrollBar()
    old = bar.value()
    if method == 'wheel':
        point = view.viewport().rect().center()
        event = QtGui.QWheelEvent(QtCore.QPointF(point), QtCore.QPointF(view.viewport().mapToGlobal(point)),
            QtCore.QPoint(), QtCore.QPoint(0, -120), QtCore.Qt.NoButton, QtCore.Qt.NoModifier,
            QtCore.Qt.NoScrollPhase, False)
        QtWidgets.QApplication.sendEvent(view.viewport(), event)
    else:
        # A small thumb movement exercises the same valueChanged/scroll path
        # as dragging without moving a cursor across the list's stale rows.
        bar.setSliderPosition(old + 13)
    _settle(app)
    assert old < bar.value() < old + view.viewport().height()


@pytest.mark.parametrize('dark', (True, False))
@pytest.mark.parametrize('embedded', (False, True))
@pytest.mark.parametrize('method', ('wheel', 'scrollbar'))
def test_scrolling_repaints_the_whole_visible_list_without_hover(app, picker, dark, embedded, method):
    combo = picker(dark, embedded)
    viewport = combo.view().viewport()
    watcher = _PaintWatch(viewport)
    _scroll(combo, method, app)
    painted = QtGui.QRegion()
    for region in watcher.regions:
        painted |= region
    assert painted.contains(viewport.rect()), (embedded, method, viewport.rect(), painted.boundingRect())


def _cached_popup_image(app, popup, watcher):
    assert app.platformName().split(':')[0] == 'offscreen', 'never capture a real desktop'
    before = len(watcher.regions)
    image = app.primaryScreen().grabWindow(int(popup.winId())).toImage()
    assert not image.isNull()
    assert len(watcher.regions) == before, 'reading cached pixels must not repaint'
    return image


@pytest.mark.parametrize('dark', (True, False))
@pytest.mark.parametrize('method', ('wheel', 'scrollbar'))
def test_cached_offscreen_pixels_after_scroll_match_explicit_refresh(app, picker, dark, method):
    if app.platformName().split(':')[0] != 'offscreen':
        pytest.skip('reads only the isolated offscreen backing store')
    combo = picker(dark)
    popup, viewport = combo.view().window(), combo.view().viewport()
    popup.winId()
    _settle(app)
    watcher = _PaintWatch(viewport)
    _scroll(combo, method, app)
    cached = _cached_popup_image(app, popup, watcher)
    viewport.update()
    _settle(app)
    refreshed = _cached_popup_image(app, popup, watcher)
    logical = QtCore.QRect(viewport.mapTo(popup, QtCore.QPoint()), viewport.size())
    factor = cached.devicePixelRatio()
    rect = QtCore.QRect(round(logical.x()*factor), round(logical.y()*factor),
                       round(logical.width()*factor), round(logical.height()*factor))
    assert cached.copy(rect) == refreshed.copy(rect), 'hover/full update repaired stale scroll pixels'
