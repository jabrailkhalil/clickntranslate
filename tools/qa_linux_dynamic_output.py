"""Exercise paired translation on an actual X11 desktop using a generated fixture.

Run with the application's Linux Python environment inside an X11 session.
Writes fixture screenshots and a JSON report under .tmp/linux-dynamic-output.
OCR is real Tesseract; translation responses are deterministic.
"""

from contextlib import ExitStack
import json
import os
from pathlib import Path
import sys
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.argv[0] = str(ROOT / 'main.py')

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtTest import QSignalSpy, QTest

import dynamic_workspace as workspace
from dynamic_templates import TemplateStore, decode_rect
import game_mode
import ocr


def run():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    if not sys.platform.startswith('linux') or app.platformName() != 'xcb':
        raise SystemExit('Run on Linux with an actual X11 desktop (QT_QPA_PLATFORM=xcb).')
    folder = Path(os.environ.get('CNT_QA_OUTPUT', str(ROOT / '.tmp/linux-dynamic-output')))
    folder.mkdir(parents=True, exist_ok=True)
    screen = app.primaryScreen()
    bounds = screen.availableGeometry()
    fixture = QtWidgets.QWidget(None, QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint)
    fixture.setGeometry(bounds.x()+20, bounds.y()+120, 720, 460)
    fixture.setStyleSheet('background:#263555')
    label = QtWidgets.QLabel('SOURCE TEXT', fixture)
    label.setAlignment(QtCore.Qt.AlignCenter)
    label.setStyleSheet('background:#14644d; color:white; font:36px "DejaVu Sans"')
    label.setGeometry(20, 80, 270, 100)
    fixture.show()
    fixture.raise_()
    QTest.qWait(400)
    origin = fixture.geometry().topLeft()
    source = label.geometry().translated(origin)
    output = QtCore.QRect(350, 230, 310, 120).translated(origin)

    def capture(rect):
        local = rect.translated(-screen.geometry().topLeft())
        return ocr.grab_screen_pixmap(screen, *local.getRect()).toImage()

    baseline = capture(source)
    baseline.save(str(folder/'source.png'))
    results = {'platform': app.platformName(), 'density': baseline.width()/source.width(),
               'source': source.getRect(), 'output': output.getRect()}
    failures = []

    def check(key, condition):
        results[key] = bool(condition)
        if not condition:
            failures.append(key)

    config = {'theme': os.environ.get('CNT_QA_THEME', 'Темная'), 'interface_language': 'ru',
              'ocr_engine': 'Tesseract', 'translator_engine': 'Google', 'history': False,
              'game_pause_when_inactive': False, 'game_show_original_text': True}
    try:
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(ocr, 'get_cached_ocr_config', return_value=config))
            stack.enter_context(mock.patch.object(game_mode.GameTranslationOverlay, '_start_scanning'))
            stack.enter_context(mock.patch.object(game_mode.GameTranslationOverlay, '_start_ocr'))
            store = TemplateStore(folder/'templates.json')
            stack.enter_context(mock.patch.object(workspace, 'TemplateStore', return_value=store))
            worker = ocr.create_position_ocr_worker(baseline, 'en', 'Tesseract')
            if worker is None:
                raise AssertionError('Tesseract position worker is unavailable')
            spy = QSignalSpy(worker.result_ready)
            worker.start()
            if not spy:
                spy.wait(15000)
            if not worker.wait(5000):
                raise AssertionError('Tesseract did not finish')
            recognized = ' '.join(item[4] for item in spy[0][0]) if spy else ''
            check('native_ocr', 'SOURCE TEXT' in recognized)
            worker.deleteLater()
            overlay = workspace.PairedTranslationOverlay(source, 'en', 'ru', output_region=output)
            game_mode._game_overlay_refs = [overlay]
            try:
                overlay._apply_translation(0, 'SOURCE TEXT', 'Перевод только в выбранной области', '')
                QTest.qWait(250)
                check('independent_output', overlay.geometry() == output and overlay.region == source)
                check('translation_only', all(widget.isHidden() for widget in
                    (overlay.original_label, overlay.status_label, overlay.title_label, overlay.pair_label)))
                with (mock.patch.object(overlay, 'setWindowOpacity', wraps=overlay.setWindowOpacity) as opacity,
                      mock.patch.object(overlay.controls, 'setWindowOpacity', wraps=overlay.controls.setWindowOpacity) as controls_opacity):
                    frames = [overlay._grab_region().toImage() for _ in range(3)]
                    check('disjoint_capture', all(frame == baseline for frame in frames))
                    check('disjoint_no_flicker', opacity.call_count == 0 and controls_opacity.call_count == 0)
                overlay.grab().save(str(folder/'output.png'))
                overlay.set_output_geometry(source)
                QTest.qWait(250)
                check('overlap_visible', capture(source) != baseline)
                frame = overlay._grab_region().toImage()
                frame.save(str(folder/'overlap-captured.png'))
                check('overlap_excluded', frame == baseline)
                QTest.qWait(250)
                check('overlap_restored', overlay.isVisible() and capture(source) != baseline)
                overlay.set_output_geometry(output)
                controls = overlay.controls
                controls.gear.click()
                controls.font_size.setValue(26)
                controls.opacity.setValue(65)
                controls.locked.setChecked(False)
                QTest.qWait(100)
                controls.grab().save(str(folder/'settings.png'))
                before = QtCore.QRect(overlay.output_rect)
                for button, delta in ((controls.move_button, QtCore.QPoint(10, 5)),
                                      (controls.resize_button, QtCore.QPoint(20, 10))):
                    destination = button.mapToGlobal(button.rect().center())+delta
                    QTest.mousePress(button, QtCore.Qt.LeftButton, pos=button.rect().center())
                    QTest.mouseRelease(button, QtCore.Qt.LeftButton, pos=button.mapFromGlobal(destination))
                expected = before.translated(10, 5)
                expected.setSize(expected.size()+QtCore.QSize(20, 10))
                check('move_resize', overlay.output_rect == expected and overlay.region == source)
                controls.template_name.setText('Linux native fixture')
                controls.save_button.click()
                saved = TemplateStore(store.path).load()[0]
                check('template_roundtrip',
                    decode_rect(saved['pairs'][0]['source'], app.screens()) == source and
                    decode_rect(saved['pairs'][0]['output'], app.screens()) == overlay.output_rect and
                    saved['pairs'][0]['style'] == {'font_size': 26, 'opacity': 65, 'locked': False})
                controls.stop_button.click()
                check('stop_session', overlay._closed and not game_mode._game_overlay_refs)
            finally:
                game_mode.stop_game_mode()
                app.processEvents()
    finally:
        fixture.close()
        app.processEvents()
    results['failures'] = failures
    results['passed'] = not failures
    (folder/'report.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(json.dumps(results), flush=True)
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(run())
