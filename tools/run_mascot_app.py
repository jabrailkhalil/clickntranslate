"""Open the full source application for hands-on mascot review.

Run: .venv/Scripts/python.exe tools/run_mascot_app.py
Uses its own persistent profile in .tmp/mascot-app. The existing developer UI
mode keeps global hotkeys, startup dialogs and autostart sync out of this copy.
Translation buttons, settings and the desktop companion are real app widgets.
"""
from pathlib import Path
import json
import os
import sys


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / '.tmp/mascot-app'


def run():
    sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
    if sys.platform == 'win32':
        os.environ['CLICKNTRANSLATE_USE_OCR_WORKER'] = '1'

    # Set the profile before main and its providers import this path helper.
    import portable_paths
    portable_paths.portable_base_dir = lambda: str(PROFILE)
    import main
    from PyQt5 import QtCore

    main.LAYOUT_EDITOR_MODE = True
    config_path = PROFILE / 'data/config.json'
    if not config_path.exists():
        config = dict(main.DEFAULT_CONFIG,
                      interface_language='ru',
                      desktop_assistant_enabled=True,
                      desktop_assistant_mascot='pancake',
                      desktop_assistant_appearance='walking',
                      desktop_assistant_behavior='walk',
                      desktop_assistant_reactions=False,
                      desktop_assistant_position={'screen': '', 'x': .55, 'y': .85},
                      show_update_info=False, update_check_on_launch=False,
                      first_run_guide_completed=True, first_run_guide_pending=False,
                      autostart=False, start_minimized=False)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
    main.invalidate_config_cache()

    class MascotApp(main.DarkThemeApp):
        def sync_autostart_state(self, repair_stale=False):
            return False

        def has_tray(self):
            # This review copy has no tray icon; closing must dispose its pet.
            return False

    app = main._ensure_startup_application()
    app.setQuitOnLastWindowClosed(True)
    window = MascotApp()
    main._main_window_ref = window
    window.setWindowTitle("Click'n'Translate 1.8.2 — Python · маскоты")
    window._sync_desktop_assistant()
    window.show()
    window.show_assistant_settings()
    window.raise_()
    window.activateWindow()

    def ready():
        # Save this actual window for the same visual review as the open app.
        window.grab().save(str(PROFILE / 'window.png'))
        helper = getattr(window, '_desktop_assistant', None)
        if helper is not None:
            helper.anchor.setWindowTitle('ClicknTranslate — Python · маскот')
        print(f'Opened source app; profile: {PROFILE}', flush=True)

    QtCore.QTimer.singleShot(1000, ready)
    return app.exec_()


if __name__ == '__main__':
    sys.exit(run())
