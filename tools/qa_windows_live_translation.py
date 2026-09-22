"""Exercise live scene changes using native Windows OCR on generated images.

No desktop capture, global shortcuts, real provider requests or user settings.
Outputs reproducible PNGs and JSON to .tmp/windows-live-qa.
"""
from pathlib import Path
import json
import os
import sys
import time
import logging
from unittest import mock

root = Path(__file__).resolve().parents[1]
if sys.platform != 'win32':
    raise SystemExit('Windows OCR with its English pack is required.')
sys.path.insert(0, str(root))
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.argv[0] = str(root / 'main.py')
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtTest import QSignalSpy, QTest
import ocr
import game_mode
logging.basicConfig(level=logging.INFO, force=True)

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
fonts = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
for name in ('arial.ttf', 'arialbd.ttf', 'segoeui.ttf', 'segoeuib.ttf'):
    QtGui.QFontDatabase.addApplicationFont(str(fonts / name))
app.setFont(QtGui.QFont('Segoe UI', 10))
output = root / '.tmp/windows-live-qa'
output.mkdir(parents=True, exist_ok=True)
translations = {'Open the gate': 'Открой ворота', 'Close the gate': 'Закрой ворота',
                'A new quest': 'Новое задание', 'Settings': 'Настройки'}
requests = []
def translate(text, source, target, **kwargs):
    assert kwargs['engine'] == 'Google'
    requests.append(text)
    for original, result in translations.items():
        text = text.replace(original, result)
    return text

scenes = [
    [(70, 170, 'Open the gate'), (540, 350, 'A new quest'), (1020, 530, 'Settings')],
    [(70, 120, 'Open the gate'), (540, 300, 'A new quest'), (1020, 480, 'Settings')],
    [(70, 120, 'Close the gate'), (1020, 480, 'Settings')],
]
config = {'theme': 'Темная', 'interface_language': 'ru', 'translator_engine': 'Google',
          'ocr_engine': 'Windows', 'history': False, 'game_pause_when_inactive': False,
          'game_translate_source_language': 'en', 'game_translate_target_language': 'ru'}
report = {'native_ocr': 'Windows', 'provider': 'deterministic fixture, no network', 'frames': []}
with mock.patch.object(ocr, 'get_cached_ocr_config', return_value=config), \
     mock.patch.object(game_mode.GameFullscreenOverlay, '_scan_once'), \
     mock.patch.object(game_mode, '_exclude_from_windows_capture', return_value=True), \
     mock.patch('translater.translate_text', side_effect=translate):
    overlay = game_mode.GameFullscreenOverlay('en', 'ru')
    overlay._timer.stop()
    overlay.setGeometry(0, 0, 1440, 900)
    try:
        for frame_index, scene in enumerate(scenes):
            image = QtGui.QImage(1440, 900, QtGui.QImage.Format_RGB32)
            image.fill(QtGui.QColor('#24212b'))
            painter = QtGui.QPainter(image)
            painter.setPen(QtGui.QColor('#f4f1fa'))
            painter.setFont(QtGui.QFont('Arial', 22))
            for x, y, text in scene:
                painter.drawText(QtCore.QRect(x, y, 390, 90), QtCore.Qt.AlignLeft, text)
            painter.end()
            image.save(str(output / f'source-{frame_index + 1}.png'))
            capture = image.scaled(2160, 1350, transformMode=QtCore.Qt.SmoothTransformation)
            worker = ocr.create_position_ocr_worker(capture, 'en', 'Windows')
            assert worker is not None
            signal = QSignalSpy(worker.result_ready)
            worker.start()
            if not signal:
                assert signal.wait(20000)
            assert worker.wait(3000)
            lines = ocr._group_screen_ocr_lines(signal[0][0])
            assert {item[4] for item in lines} == {item[2] for item in scene}, lines
            overlay.screenshot = QtGui.QPixmap.fromImage(capture)
            overlay._ocr_scale_x = overlay._ocr_scale_y = 1.5
            before = len(requests)
            now = time.monotonic()
            with mock.patch.object(game_mode.time, 'monotonic', return_value=now):
                overlay._on_position_ocr_result(lines)
            with mock.patch.object(game_mode.time, 'monotonic', return_value=now + .2):
                overlay._on_position_ocr_result(lines)
            for _ in range(200):
                app.processEvents()
                if not overlay._translation_busy:
                    break
                QTest.qWait(5)
            assert not overlay._translation_busy
            assert len(overlay._blocks) == len(scene), overlay._blocks
            assert len(requests) - before == (0 if frame_index == 1 else 1), requests
            for x, y, w, h, text, translated in overlay._blocks:
                original = next(item for item in scene if item[2] == text)
                assert abs(x / 1.5 - original[0]) < 15 and abs(y / 1.5 - original[1]) < 15
                assert translated == translations[text]
            rendered = image.copy()
            painter = QtGui.QPainter(rendered)
            painter.drawPixmap(0, 0, overlay.grab())
            painter.end()
            rendered.save(str(output / f'frame-{frame_index + 1}.png'))
            report['frames'].append({'source': lines, 'displayed': overlay._blocks, 'requests': len(requests) - before})
            worker.deleteLater()
        overlay.controls.grab().save(str(output / 'controls-dark.png'))
        overlay._on_position_ocr_result([])
        overlay._on_position_ocr_result([])
        assert not overlay._blocks
        report['cleared_after_empty_frames'] = True
    finally:
        overlay.close()
    for theme in ('Темная', 'Светлая'):
        config['theme'] = theme
        suffix = 'dark' if theme == 'Темная' else 'light'
        with mock.patch.object(ocr, 'installed_ocr_language_codes', return_value=['en', 'ru']), \
             mock.patch.object(ocr, '_translation_targets_for_source', return_value=['ru']), \
             mock.patch.object(ocr, '_write_ocr_config_updates'):
            selector = game_mode.GameRegionSelector()
            selector.resize(800, 520)
            selector._layout_controls()
            selector.grab().save(str(output / f'selector-{suffix}.png'))
            selector.close()
        controls_owner = game_mode.GameFullscreenOverlay('en', 'ru')
        controls_owner._timer.stop()
        controls_owner.controls.grab().save(str(output / f'controls-{suffix}.png'))
        controls_owner.close()
report['passed'] = True
(output / 'native-live.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print('Native live OCR passed: new scene 1 request, scrolling 0, changed dialogue 1; stale text cleared.')
