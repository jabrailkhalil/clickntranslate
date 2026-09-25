"""Offscreen screenshots and an optional CPU/timer sample with disposable data.

python tools/qa_ui_polish.py --benchmark-seconds 5
No global hotkeys, autostart changes, translation requests, or user preferences.
Numbers describe this machine/backend, not a promise about a Windows desktop.
"""
from contextlib import ExitStack
from pathlib import Path
from unittest import mock
import argparse
import faulthandler
import json
import os
import sys
import tempfile
import time
import traceback


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('.tmp/ui-polish-qa'))
    parser.add_argument('--benchmark-seconds', type=float, default=0)
    args = parser.parse_args()
    if not 0 <= args.benchmark_seconds <= 60:
        parser.error('--benchmark-seconds must be between 0 and 60')
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    sys.path[:0] = [str(root), str(root / 'src'), str(root / 'tests')]
    os.chdir(root)  # Application resource paths are relative to the source root.
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    import portable_paths

    with tempfile.TemporaryDirectory(prefix='cnt-ui-qa-') as sandbox, ExitStack() as stack:
        stack.enter_context(mock.patch.object(portable_paths, 'portable_base_dir', return_value=sandbox))
        stack.enter_context(mock.patch.dict(os.environ, {
            key: str(Path(sandbox) / key.lower())
            for key in ('XDG_DATA_HOME', 'XDG_CACHE_HOME', 'XDG_CONFIG_HOME')
        }))
        stack.enter_context(mock.patch.object(sys, 'argv', [str(Path(sandbox) / 'main.py')]))
        # Match real startup: CTranslate2 must load before any Qt module on
        # Windows. Loading Qt first can terminate the native runtime without
        # a Python traceback, even before constructing QApplication.
        print('UI QA: importing application before Qt', flush=True)
        import main
        from PyQt5 import QtCore, QtWidgets
        from PyQt5.QtTest import QTest
        from qt_layout_test_support import ensure_layout_fonts
        from ui_scaling import MainWindowScaleController
        print('UI QA: application imported; preparing disposable windows', flush=True)

        def save_capture(widget, name):
            path = output / name
            if not widget.grab().save(str(path), 'PNG'):
                raise RuntimeError('Could not save UI capture: ' + str(path))

        config = dict(main.DEFAULT_CONFIG, interface_language='ru', show_update_info=False,
                      desktop_assistant_enabled=False, translator_engine='Google')
        data = Path(sandbox) / 'data'
        data.mkdir(exist_ok=True)
        (data / 'config.json').write_text(json.dumps(config), encoding='utf-8')
        for patch in (
            mock.patch.object(main, 'LAYOUT_EDITOR_MODE', True),
            mock.patch.object(main, 'get_cached_config', side_effect=lambda: dict(config)),
            mock.patch.object(main.DarkThemeApp, 'sync_autostart_state', return_value=False),
            mock.patch.object(main.DarkThemeApp, '_maybe_check_updates_on_launch'),
            mock.patch.object(MainWindowScaleController, 'available_geometry', return_value=QtCore.QRect(0, 0, 1920, 1080)),
        ):
            stack.enter_context(patch)
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        app.setQuitOnLastWindowClosed(False)
        ensure_layout_fonts(app)
        window = main.DarkThemeApp()
        window.show()
        window.set_ui_scale_percent(100)
        window.text_input.setPlainText('Hello! Translate the text or choose another language.')
        window._show_inline_main_result('Привет! Переведите текст или выберите другой язык.',
                                        window.text_input.toPlainText(), 'en', 'ru')
        for theme, suffix in (('Темная', 'dark'), ('Светлая', 'light')):
            window.current_theme = theme
            window.config['theme'] = theme
            window.apply_theme()
            QTest.qWait(50)
            save_capture(window, 'main-' + suffix + '.png')
            window.show_assistant_settings()
            QTest.qWait(50)
            save_capture(window, 'companion-settings-' + suffix + '.png')
            window.show_main_screen()
            QTest.qWait(50)
            dialog = main.TranslationResultDialog(window, 'Здесь появится перевод', auto_copy=False,
                lang='ru', theme=theme, source_text='Choose a provider for this window.', source_lang='en', target_lang='ru')
            dialog.show()
            for width, name in ((700, 'wide'), (420, 'compact')):
                dialog.resize(width, 620 if width < 600 else 420)
                QTest.qWait(30)
                save_capture(dialog, 'workspace-' + suffix + '-' + name + '.png')
            dialog.close()
            dialog.deleteLater()
        welcome = main.WelcomeDialog(window)
        welcome.show()
        QTest.qWait(40)
        save_capture(welcome, 'welcome-unchecked.png')
        welcome.checkbox.click()
        app.processEvents()
        save_capture(welcome, 'welcome-checked.png')
        welcome.close()
        welcome.deleteLater()
        app.processEvents()

        from assistant_preview import preview_frames
        report = dict(platform=sys.platform, backend=app.platformName(),
            qt_version=QtCore.QT_VERSION_STR, sprite_frames=len(preview_frames()[0]),
            sprite_rgba_bytes=sum(p.width()*p.height()*4 for row in preview_frames() for p in row))
        if args.benchmark_seconds:
            class PaintMeter(QtCore.QObject):
                def __init__(self, viewport):
                    super().__init__(viewport)
                    self.areas = []
                    self.area = viewport.width() * viewport.height()
                    viewport.installEventFilter(self)
                def eventFilter(self, watched, event):
                    if event.type() == QtCore.QEvent.Paint:
                        r = event.region().boundingRect()
                        self.areas.append(r.width() * r.height() / self.area)
                    return False
            meter = PaintMeter(window._ui_scale_controller.view.viewport())
            rail = window.assistant_preview
            results = {}
            for state in ('visible-running', 'inactive', 'minimized', 'hidden'):
                window.showNormal()
                window.activateWindow()
                rail.button.clearFocus()
                rail._hovered = False
                rail._sync_animation()
                if state == 'inactive':
                    app.sendEvent(window, QtCore.QEvent(QtCore.QEvent.WindowDeactivate))
                elif state == 'minimized':
                    window.showMinimized()
                elif state == 'hidden':
                    window.hide()
                QTest.qWait(100)
                ticks = [0]
                def tick():
                    ticks[0] += 1
                rail.timer.timeout.connect(tick)
                meter.areas.clear()
                loop = QtCore.QEventLoop()
                QtCore.QTimer.singleShot(round(args.benchmark_seconds*1000), loop.quit)
                cpu, wall = time.process_time(), time.perf_counter()
                loop.exec_()
                cpu, wall = time.process_time()-cpu, time.perf_counter()-wall
                rail.timer.timeout.disconnect(tick)
                results[state] = dict(seconds=round(wall, 3), process_cpu_seconds=round(cpu, 6),
                    percent_of_one_core=round(100*cpu/wall, 3), timer_ticks=ticks[0],
                    timer_active=rail.timer.isActive(), viewport_paints=len(meter.areas),
                    max_viewport_paint_fraction=round(max(meter.areas, default=0), 5))
            report['samples'] = results
        (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report, indent=2))
        window.force_quit = True
        window.close()
        window.deleteLater()
        app.processEvents()
        import logging
        logging.shutdown()
    return 0


if __name__ == '__main__':
    faulthandler.enable()
    try:
        code = run()
    except Exception:
        traceback.print_exc(file=sys.__stderr__)
        code = 1
    raise SystemExit(code)
