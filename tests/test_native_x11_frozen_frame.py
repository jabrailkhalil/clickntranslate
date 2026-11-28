"""Run only on the opt-in, disposable X11 display used by native desktop QA."""

import os
from unittest import mock

import pytest
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtTest import QTest

import api_ocr
import api_providers
import ocr


@pytest.mark.skipif(os.environ.get('CNT_QA_PRIVATE_X11') != '1',
                    reason='requires the opt-in disposable X11 display')
def test_native_drag_paints_and_submits_the_original_frozen_pixels(monkeypatch, tmp_path):
    app = QtWidgets.QApplication.instance()
    assert app.platformName() == 'xcb'
    screen = app.primaryScreen()
    assert len(app.screens()) == 1 and screen.devicePixelRatio() == 1
    size = screen.geometry().size()
    marker = QtCore.QRect(size.width() // 2 - 140, size.height() // 2 - 80, 280, 160)
    left = marker.center() - QtCore.QPoint(65, 0)
    right = marker.center() + QtCore.QPoint(65, 0)
    original = [QtGui.QColor('#38b870'), QtGui.QColor('#f2c84c')]
    changed = [QtGui.QColor('#d94242'), QtGui.QColor('#51cfea')]

    class SyntheticDocument(QtWidgets.QWidget):
        colors = original

        def paintEvent(self, event):
            painter = QtGui.QPainter(self)
            painter.fillRect(self.rect(), QtGui.QColor('#283956'))
            painter.fillRect(marker, self.colors[0])
            painter.fillRect(marker.adjusted(marker.width() // 2, 0, 0, 0), self.colors[1])
            painter.setPen(QtGui.QColor('white'))
            painter.drawText(marker.adjusted(0, -42, 0, -marker.height()), QtCore.Qt.AlignCenter,
                             'Synthetic document  /  ' + ('original' if self.colors == original else 'changed'))
            painter.end()

    def root_frame(label):
        app.processEvents()
        app.sync()
        image = screen.grabWindow(0).toImage()
        assert not image.isNull() and image.save(str(tmp_path / (label + '.png')))
        return [image.pixelColor(point) for point in (left, right)]

    config = dict(interface_language='en', last_ocr_language='en', freeze_screen_on_ocr=False,
                  dim_screen_during_ocr=True, ocr_dim_strength=50, ocr_engine=next(iter(api_providers.VISION_ENGINES)))
    monkeypatch.setattr(ocr, 'get_cached_ocr_config', lambda: config)
    monkeypatch.setattr(ocr, 'installed_ocr_language_codes', lambda **kwargs: ['en'])
    monkeypatch.setattr(ocr, '_safe_prepare_overlay', mock.Mock())
    monkeypatch.setattr(ocr, 'notify_current_activity', mock.Mock())
    worker = mock.Mock()
    monkeypatch.setattr(api_ocr, 'ApiOCRWorker', worker)
    grabs = mock.Mock(wraps=ocr.grab_screen_pixmap)
    monkeypatch.setattr(ocr, 'grab_screen_pixmap', grabs)
    document = SyntheticDocument()
    document.setWindowFlags(QtCore.Qt.FramelessWindowHint)
    overlay = None
    try:
        document.setGeometry(screen.geometry())
        document.show()
        document.raise_()
        assert QTest.qWaitForWindowExposed(document, 3000)
        assert root_frame('01-source-original') == original
        overlay = ocr.ScreenCaptureOverlay('copy', defer_show=True)
        overlay.show_overlay()
        assert QTest.qWaitForWindowExposed(overlay, 3000)
        dimmed = root_frame('02-selector-before-drag')
        for sample, source in zip(dimmed, original):
            assert all(abs(2 * value - expected) <= 2 for value, expected in zip(
                sample.getRgb()[:3], source.getRgb()[:3]))

        document.colors = changed
        document.update()
        selected = marker.adjusted(12, 12, -12, -12)
        QTest.mousePress(overlay, QtCore.Qt.LeftButton, pos=selected.topLeft())
        QTest.mouseMove(overlay, pos=selected.bottomRight())
        QTest.qWait(100)
        assert overlay.end_point == selected.bottomRight()
        assert root_frame('03-selector-during-drag') == original
        QTest.mouseRelease(overlay, QtCore.Qt.LeftButton, pos=selected.bottomRight())
        worker.assert_called_once()
        submitted = worker.call_args.args[1]
        submitted.save(tmp_path / '04-submitted-ocr-input.png')
        assert submitted.size == (selected.width(), selected.height())
        for point, color in zip((left, right), original):
            relative = point - selected.topLeft()
            assert submitted.getpixel((relative.x(), relative.y()))[:3] == color.getRgb()[:3]
        grabs.assert_called_once()
        overlay.close()
        QTest.qWait(150)
        assert root_frame('05-source-changed') == changed
    finally:
        if overlay is not None:
            overlay.close()
        document.close()
        app.processEvents()
