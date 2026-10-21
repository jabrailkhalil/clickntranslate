"""Open the full source application for hands-on mascot review.

Run: .venv/Scripts/python.exe tools/run_mascot_app.py
Add --general-settings to open the general settings page for UI review.
Uses its own persistent profile in .tmp/mascot-app. Translation, optional quick
selection and global hotkeys are active. Startup announcements, tray creation
and OS autostart changes are disabled for this review copy.
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
    from assistant_text import assistant_text
    from PyQt5 import QtCore

    main.LAYOUT_EDITOR_MODE = False
    config_path = PROFILE / 'data/config.json'
    if not config_path.exists():
        config = dict(main.DEFAULT_CONFIG,
                      interface_language='ru',
                      desktop_assistant_enabled=True,
                      desktop_assistant_mascot='click',
                      desktop_assistant_appearance='animated',
                      desktop_assistant_behavior='idle',
                      desktop_assistant_reactions=True,
                      desktop_assistant_position={'screen': '', 'x': .55, 'y': .85},
                      show_update_info=False, update_check_on_launch=False,
                      first_run_guide_completed=True, first_run_guide_pending=False,
                      autostart=False, start_minimized=False)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
    main.invalidate_config_cache()

    class MascotApp(main.DarkThemeApp):
        def create_tray_icon(self):
            pass

        def _maybe_show_startup_news(self):
            pass

        def _maybe_start_first_run_guide(self):
            pass

        def _maybe_check_updates_on_launch(self):
            pass

        def sync_autostart_state(self, repair_stale=False):
            return False

        def has_tray(self):
            # This review copy has no tray icon; closing must dispose its pet.
            return False

    app = main._ensure_startup_application()
    app.setQuitOnLastWindowClosed(True)
    window = MascotApp()
    main._main_window_ref = window
    window.setWindowTitle(f"Click'n'Translate {main.APP_VERSION} — Python · Pets v18")
    window._sync_desktop_assistant()
    window.show()
    if '--general-settings' in sys.argv:
        window.show_settings()
    else:
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
