"""Native region selection, OCR, focus handoff and in-place output on generated text.

The source is a separate process so focus/pause checks exercise a real external
window. Only generated text is captured; translation is a deterministic stub.
All app state and diagnostics go to the supplied output directory.
"""
import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'.tmp/qa-native-region')
    parser.add_argument('--fixture', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if sys.platform != 'win32' or os.environ.get('QT_QPA_PLATFORM') == 'offscreen':
        raise SystemExit('Native Windows Qt is required')
    sys.argv[0] = str(output/'main.py')
    from PyQt5 import QtCore, QtWidgets, sip
    from PyQt5.QtTest import QTest
    app = QtWidgets.QApplication([])
    app.setQuitOnLastWindowClosed(False)
    ready = output/'fixture.json'
    command = output/'command.txt'
    if args.fixture:
        source = QtWidgets.QLabel('START HERE')
        source.setWindowTitle('ClicknTranslate generated OCR fixture')
        source.setStyleSheet('background:#fff; color:#111; font:34px "Arial"; padding:16px;')
        source.setAlignment(QtCore.Qt.AlignCenter)
        source.setGeometry(120, 340, 700, 160)
        source.show()
        source.raise_()
        source.activateWindow()
        app.processEvents()
        rect = source.rect().adjusted(8, 8, -8, -8).translated(source.mapToGlobal(QtCore.QPoint()))
        ready.write_text(json.dumps({'hwnd': int(source.winId()), 'rect': rect.getRect()}), encoding='utf-8')
        def update():
            value = command.read_text(encoding='utf-8') if command.exists() else ''
            if value == 'stop':
                app.quit()
            elif value:
                source.setText(value)
        timer = QtCore.QTimer()
        timer.timeout.connect(update)
        timer.start(100)
        QtCore.QTimer.singleShot(45000, app.quit)
        app.exec_()
        return

    import game_mode
    import ocr
    import dynamic_workspace as workspace
    import translater
    from dynamic_templates import TemplateStore
    command.write_text('START HERE', encoding='utf-8')
    ready.unlink(missing_ok=True)
    helper = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--fixture', '--output', str(output)],
                              creationflags=subprocess.CREATE_NO_WINDOW)
    windows = []
    try:
        deadline = time.monotonic()+8
        while not ready.exists() and time.monotonic() < deadline:
            QTest.qWait(50)
        state = json.loads(ready.read_text(encoding='utf-8'))
        source = QtCore.QRect(*state['rect'])
        assert game_mode._window_at_point(source.center()) == state['hwnd']
        config = {'theme':'Светлая', 'interface_language':'ru', 'ocr_engine':'Windows',
                  'translator_engine':'Google', 'game_pause_when_inactive':True,
                  'game_capture_interval_ms':450, 'game_manual_output':False,
                  'game_translate_source_language':'en', 'game_translate_target_language':'ru',
                  'history':False, 'game_show_toolbar':True}
        def translated(value, *_args, **_kwargs):
            if 'START' in value.upper():
                return 'Начните здесь'
            if 'READ' in value.upper():
                return 'Прочитайте снова'
            raise AssertionError('Unexpected OCR text from generated fixture')
        with ExitStack() as patches:
            patches.enter_context(mock.patch.object(ocr, 'get_cached_ocr_config', return_value=config))
            patches.enter_context(mock.patch.object(ocr, '_write_ocr_config_updates', return_value=True))
            patches.enter_context(mock.patch.object(translater, 'translate_text', side_effect=translated))
            patches.enter_context(mock.patch.object(workspace, 'TemplateStore', return_value=TemplateStore(output/'templates.json')))
            selector = workspace.PairedRegionSelector(target_window=0xdead)
            windows.append(selector)
            QTest.qWait(100)
            local = source.translated(-selector.geometry().topLeft())
            QTest.mousePress(selector, QtCore.Qt.LeftButton, pos=local.topLeft())
            QTest.mouseRelease(selector, QtCore.Qt.LeftButton, pos=local.bottomRight())
            selector._start_selected_regions()
            assert len(game_mode._game_overlay_refs) == 1
            overlay = game_mode._game_overlay_refs[0]
            windows.append(overlay)
            assert overlay.target_window == state['hwnd']
            assert overlay.output_rect == overlay.region == source
            def wait_result(expected):
                deadline = time.monotonic()+12
                while time.monotonic() < deadline:
                    QTest.qWait(50)
                    if overlay.card.isVisible() and overlay.translation_label.text() == expected:
                        return
                raise AssertionError((overlay._diagnostic_status, overlay.translation_label.text(),
                                      overlay._target_is_active(), game_mode._foreground_window()))
            wait_result('Начните здесь')
            QTest.qWait(1200)  # Past the startup focus grace period.
            assert overlay._target_is_active() and overlay.card.isVisible()
            overlay.grab().save(str(output/'overlay-first.png'))
            overlay.controls.set_toolbar_visible(False)
            assert not overlay.controls.isVisible()
            command.write_text('READ AGAIN', encoding='utf-8')
            wait_result('Прочитайте снова')
            overlay.grab().save(str(output/'overlay-updated.png'))
            assert overlay._capture_excluded
            game_mode.stop_game_mode()
            assert not game_mode.game_mode_active()
        report = {'passed':True, 'real_windows_ocr':True, 'external_source_binding':True,
                  'output_overlays_source':True, 'continued_after_focus_grace':True,
                  'updated_with_toolbar_hidden':True, 'translation':'deterministic generated-text stub'}
        (output/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report))
    finally:
        game_mode.stop_game_mode()
        for window in windows:
            if not sip.isdeleted(window):
                window.close()
        command.write_text('stop', encoding='utf-8')
        try:
            helper.wait(timeout=3)
        except subprocess.TimeoutExpired:
            helper.terminate()
            helper.wait(timeout=3)
        app.processEvents()


if __name__ == '__main__':
    run()
