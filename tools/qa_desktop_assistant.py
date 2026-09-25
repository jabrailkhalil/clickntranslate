"""Render the companion with isolated data, or preview its real Windows UI.

No global hotkeys, autostart changes, network calls or user configuration.
Capture actions in the native preview are recorded and simulated for 1 second.
"""
from pathlib import Path
from contextlib import ExitStack
import argparse
import json
import os
import sys
import tempfile
from unittest import mock


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument('--preview', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path[:0] = [str(root), str(root / 'src'), str(root / 'tests')]
    sys.argv[0] = str(root / 'main.py')
    os.environ['QT_QPA_PLATFORM'] = 'windows:fontengine=freetype' if args.preview and sys.platform == 'win32' else 'offscreen'
    from PyQt5 import QtCore, QtWidgets
    import portable_paths
    from qt_layout_test_support import ensure_layout_fonts
    from assistant_text import ASSISTANT_TEXT
    import mode_coordinator
    from ui_scaling import MainWindowScaleController

    output = root / '.tmp/desktop-assistant-qa'
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='cnt-assistant-qa-') as sandbox, ExitStack() as stack:
        stack.enter_context(mock.patch.object(portable_paths, 'portable_base_dir', return_value=sandbox))
        import main
        config = dict(main.DEFAULT_CONFIG, interface_language='ru', desktop_assistant_enabled=True)
        data = Path(sandbox) / 'data'
        data.mkdir(exist_ok=True)
        (data / 'config.json').write_text(json.dumps(config), encoding='utf-8')
        for patch in (
            mock.patch.object(main, 'LAYOUT_EDITOR_MODE', True),
            mock.patch.object(main, 'get_cached_config', side_effect=lambda: dict(config)),
            mock.patch.object(main.DarkThemeApp, 'sync_autostart_state', return_value=False),
        ):
            stack.enter_context(patch)
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        ensure_layout_fonts(app)
        app.setQuitOnLastWindowClosed(False)
        window = main.DarkThemeApp()
        window.setWindowTitle('ClicknTranslate Assistant QA')
        helper = window._desktop_assistant
        helper.anchor.setWindowTitle('ClicknTranslate Companion QA')
        window.show()
        window.show_settings()
        window.move(100, 100)
        actions = []

        def capture(action):
            actions.append({'action': action, 'anchor_hidden': not helper.anchor.isVisible(),
                            'menu_hidden': helper.menu is None or not helper.menu.isVisible()})
            (output / 'native-actions.json').write_text(json.dumps(actions, indent=2), encoding='utf-8')
            mode_coordinator.request_mode('assistant-qa', lambda: None)
            QtCore.QTimer.singleShot(1000, lambda: mode_coordinator.release_mode('assistant-qa'))

        for action, method in (('screen', 'launch_fullscreen_translate'), ('area', 'launch_translate'),
                               ('copy', 'launch_copy'), ('dynamic', 'launch_game_translate')):
            stack.enter_context(mock.patch.object(window, method, side_effect=lambda key=action: capture(key)))

        def settle():
            for _ in range(6):
                app.processEvents()

        try:
            if args.preview:
                helper.anchor.move(1100, 700)
                helper.save_position()
                settle()
                QtCore.QTimer.singleShot(300000, window.exit_app)
                app.exec_()
            else:
                stack.enter_context(mock.patch.object(MainWindowScaleController, 'available_geometry',
                    return_value=QtCore.QRect(0, 0, 2560, 1440)))
                captures = []
                for language in ASSISTANT_TEXT:
                    window.current_interface_language = language
                    for theme, suffix in (('Темная', 'dark'), ('Светлая', 'light')):
                        window.current_theme = theme
                        window.config.update(interface_language=language, theme=theme)
                        window.apply_theme()
                        window.settings_window.update_language()
                        helper.refresh()
                        for percent in (80, 100, 137, 200):
                            window.set_ui_scale_percent(percent)
                            settle()
                            filename = f'settings-{language}-{suffix}-{percent}.png'
                            window.grab().save(str(output / filename))
                            captures.append(filename)
                        helper.anchor.show()
                        helper.toggle_menu()
                        settle()
                        filename = f'menu-{language}-{suffix}.png'
                        helper.menu.grab().save(str(output / filename))
                        captures.append(filename)
                        helper.menu.hide()
                helper.anchor.grab().save(str(output / 'companion.png'))
                (output / 'render-report.json').write_text(json.dumps(captures, indent=2), encoding='utf-8')
                print(f'Rendered {len(captures)} settings/menu states and the animated companion frame.', flush=True)
        finally:
            window.force_quit = True
            window.close()
            window.deleteLater()
            app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
            app.processEvents()


if __name__ == '__main__':
    run()
