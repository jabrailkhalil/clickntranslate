"""Verify actual desktop capture beneath visible live translation windows.

Uses a generated fixture window and deterministic translation. Only the fixture
crop is inspected or saved; no provider calls, global hotkeys or user settings.
Run with a real Windows Qt platform (not offscreen).
"""

from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import sys
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.argv[0] = str(ROOT / 'main.py')
if sys.platform != 'win32' or os.environ.get('QT_QPA_PLATFORM', '').startswith('offscreen'):
    raise SystemExit('This check requires the native Windows desktop.')

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtTest import QTest
import game_mode
import ocr


def digest(image):
    image = image.convertToFormat(QtGui.QImage.Format_RGB32)
    bits = image.bits()
    bits.setsize(image.byteCount())
    return hashlib.sha256(bytes(bits)).hexdigest()


def run():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    screen = app.primaryScreen()
    available = screen.availableGeometry()
    fixture = QtWidgets.QLabel('SOURCE WINDOW\nOnly selected pixels enter OCR')
    fixture.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)
    fixture.setStyleSheet('background:#17644d; color:white; font:20px "Arial";')
    fixture.setAlignment(QtCore.Qt.AlignCenter)
    fixture.setGeometry(available.x() + 50, available.y() + 100, 600, 240)
    fixture.show()
    fixture.raise_()
    QTest.qWait(200)
    rect = fixture.geometry()
    local = rect.translated(-screen.geometry().topLeft())
    baseline = ocr.grab_screen_pixmap(screen, *local.getRect())
    density = baseline.width() / rect.width()
    config = {'theme': 'Темная', 'interface_language': 'en', 'ocr_engine': 'Windows',
              'translator_engine': 'Google', 'history': False, 'game_pause_when_inactive': False}
    report = {'density': density, 'region_frames': 0, 'fullscreen_frames': 0}
    output = ROOT / '.tmp/windows-live-capture-qa'
    output.mkdir(parents=True, exist_ok=True)
    try:
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(ocr, 'get_cached_ocr_config', return_value=config))
            stack.enter_context(mock.patch.object(game_mode.GameTranslationOverlay, '_start_scanning'))
            stack.enter_context(mock.patch.object(game_mode.GameFullscreenOverlay, '_scan_once'))
            area = game_mode.GameTranslationOverlay(rect, 'en', 'ru')
            try:
                assert area._capture_excluded, 'Windows rejected region capture exclusion'
                area._source_frame = baseline.toImage()
                area._apply_translation(0, 'SOURCE WINDOW', 'ПЕРЕВОД В ВЫДЕЛЕННОЙ ОБЛАСТИ', '')
                QTest.qWait(150)
                assert not area.mask().contains(area.rect().topLeft())
                with mock.patch.object(area, 'setWindowOpacity', side_effect=AssertionError('Region blink')):
                    for frame in range(3):
                        image = area._grab_region().toImage()
                        assert image.size() == baseline.size()
                        assert digest(image) == digest(baseline.toImage()), 'The region captured its own translation'
                        report['region_frames'] += 1
                area.grab().save(str(output / 'region-rendered.png'))
            finally:
                area.close()
                app.processEvents()
            whole = game_mode.GameFullscreenOverlay('en', 'ru', screen=screen)
            try:
                assert whole._capture_excluded, 'Windows rejected fullscreen exclusion'
                assert whole.controls._capture_excluded, 'Windows rejected controls exclusion'
                whole.controls.move(rect.left() + 20, rect.bottom() - whole.controls.height() - 8)
                # A synthetic background is enough for these synthetic text boxes.
                whole.screenshot = QtGui.QPixmap(screen.geometry().size())
                whole.screenshot.fill(QtGui.QColor('#17644d'))
                whole._has_shown_translation = True
                whole._status = ''
                with mock.patch.object(whole, 'setWindowOpacity', side_effect=AssertionError('Fullscreen blink')), \
                     mock.patch.object(whole.controls, 'setWindowOpacity', side_effect=AssertionError('Controls blink')):
                    for offset in (0, 25, 50):
                        whole._blocks = [(local.x()+30+offset, local.y()+40, 280, 30, 'SOURCE WINDOW', 'ПЕРЕВОД ВСЕГО ЭКРАНА')]
                        whole.update()
                        QTest.qWait(100)
                        assert not whole.mask().contains(QtCore.QPoint(0, whole.height()-1))
                        captured = whole._grab_screen()
                        scale = captured.width() / screen.geometry().width()
                        crop = captured.copy(QtCore.QRect(round(local.x()*scale), round(local.y()*scale),
                                                         round(local.width()*scale), round(local.height()*scale)))
                        assert digest(crop.toImage()) == digest(baseline.toImage()), 'Fullscreen captured its own layer or controls'
                        report['fullscreen_frames'] += 1
                    whole._toggle_pause()
                    assert whole.mask().intersected(QtGui.QRegion(whole.rect())).isEmpty()
                    assert whole.isVisible(), 'Pause must not unmap the capture surface'
                whole.controls.grab().save(str(output / 'controls-rendered.png'))
            finally:
                whole.close()
                app.processEvents()
        report['passed'] = True
        (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report), flush=True)
    finally:
        fixture.close()
        app.processEvents()


if __name__ == '__main__':
    run()
