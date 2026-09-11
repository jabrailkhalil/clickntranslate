"""Native Windows OCR placement probe; translations are deterministic test text.

Run with the Windows project venv. Writes only generated fixtures/reports into
.tmp/windows-mac-qa; never captures the user's desktop or calls a provider.
"""
from pathlib import Path
import sys
import json
from types import SimpleNamespace
from unittest import mock

root = Path(__file__).resolve().parents[1]
if sys.platform != 'win32':
    raise SystemExit('This probe requires Windows OCR and its English language pack.')
sys.path.insert(0, str(root))
sys.argv[0] = str(root / 'main.py')
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtTest import QSignalSpy
import ocr

app = QtWidgets.QApplication([])
output = root / '.tmp/windows-mac-qa'
output.mkdir(parents=True, exist_ok=True)
base = QtGui.QImage(1440, 900, QtGui.QImage.Format_RGB32)
base.fill(QtGui.QColor('#f4f4f4'))
painter = QtGui.QPainter(base)
painter.setPen(QtGui.QColor('#222222'))
painter.setFont(QtGui.QFont('Arial', 22))
fixtures = [(70, 170, 'Left column'), (540, 350, 'Middle column'), (1020, 530, 'Right column')]
for x, y, text in fixtures:
    painter.drawText(QtCore.QRect(x, y, 380, 100), QtCore.Qt.AlignLeft, text)
painter.end()
base.save(str(output / 'fullscreen-original.png'))
reports = []
for scale in [1, 1.25, 1.5, 2]:
    capture = base.scaled(round(1440 * scale), round(900 * scale), transformMode=QtCore.Qt.SmoothTransformation)
    worker = ocr.create_position_ocr_worker(capture, 'en', 'Windows')
    assert worker is not None
    signals = QSignalSpy(worker.result_ready)
    worker.start()
    if not signals:
        assert signals.wait(20000), 'Windows OCR did not finish'
    worker.wait(3000)
    lines = ocr._group_screen_ocr_lines(signals[0][0])
    assert len(lines) == 3, lines
    for x, y, w, h, text in lines:
        fixture = next(item for item in fixtures if item[2].lower() == text.lower())
        assert abs(x / scale - fixture[0]) < 15, (scale, text, x)
        assert abs(y / scale - fixture[1]) < 15, (scale, text, y)
    signal = mock.Mock()
    overlay = SimpleNamespace(_ocr_scale_x=scale, _ocr_scale_y=scale,
                              _translation_run_id=1, _translation_result_ready=signal,
                              width=lambda: 1440, height=lambda: 900, screenshot=QtGui.QPixmap.fromImage(base))
    translations = {'Left column': 'Левая колонка', 'Middle column': 'Средняя колонка', 'Right column': 'Правая колонка'}
    def translate(text, *args, **kwargs):
        for source, target in translations.items():
            text = text.replace(source, target)
        return text
    with mock.patch('translater.translate_text', side_effect=translate), mock.patch.object(ocr, 'get_cached_ocr_config', return_value={'translator_engine': 'Google'}):
        ocr.FullScreenTranslateOverlay._translate_all(overlay, 1, lines, 'en', 'ru')
    _, blocks, error = signal.emit.call_args.args
    assert not error and len(blocks) == 3
    overlay._replacement_palette = lambda rect: ocr.FullScreenTranslateOverlay._replacement_palette(overlay, rect)
    overlay._translation_block_layout = lambda *a, **kw: ocr.FullScreenTranslateOverlay._translation_block_layout(overlay, *a, **kw)
    rendered = base.copy()
    painter = QtGui.QPainter(rendered)
    for rect, original, translated in blocks:
        ocr.FullScreenTranslateOverlay._paint_block(overlay, painter, rect, original, translated)
    painter.end()
    rendered.save(str(output / f'fullscreen-translated-{scale}.png'))
    reports.append({'scale': scale, 'engine': worker.engine, 'ocr_boxes': lines,
                    'logical_boxes': [list(rect.getRect()) for rect, _, _ in blocks]})
    worker.deleteLater()
    app.processEvents()
(output / 'fullscreen-native.json').write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding='utf-8')
print('Native Windows OCR positions verified at 100%, 125%, 150%, 200%; 3 columns each.')
