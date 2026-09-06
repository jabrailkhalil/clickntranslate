"""Native bundle smoke check; invoked explicitly by the macOS build workflow."""

import json
import platform
from pathlib import Path
import tempfile
from unittest import mock


def run(main, report_path):
    import macos_desktop
    import macos_ocr
    from macos_hotkeys import registry
    from PIL import Image, ImageDraw, ImageFont
    from PyQt5.QtCore import QT_VERSION_STR, PYQT_VERSION_STR

    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="cnt-macos-smoke-") as temporary:
        with (mock.patch.object(macos_desktop, "user_data_dir", return_value=temporary),
              mock.patch.object(main, "WelcomeDialog"),
              mock.patch.object(main, "HotkeyListenerThread"),
              mock.patch.object(main.DarkThemeApp, "_maybe_check_updates_on_launch"),
              mock.patch.object(main.DarkThemeApp, "_maybe_show_startup_news"),
              mock.patch.object(main.DarkThemeApp, "_maybe_start_first_run_guide")):
            main.invalidate_config_cache()
            app = main._ensure_startup_application()
            app._mac_reopen_handler = macos_desktop.install_dock_reopen_handler(app, lambda: None)
            window = main.DarkThemeApp()
            window.show()
            for _ in range(5):
                app.processEvents()
            assert window.isVisible() and window.text_input.width() > 0
            screenshots = []
            for theme in ('dark', 'light'):
                expected_theme = 'Темная' if theme == 'dark' else 'Светлая'
                if window.current_theme != expected_theme:
                    window.toggle_theme()
                for percent in (100, 150):
                    actual = window.set_ui_scale_percent(percent)
                    for page in ('main', 'settings'):
                        if page == 'main':
                            window.show_main_screen()
                        else:
                            window.show_settings()
                        for _ in range(5):
                            app.processEvents()
                        picture = window.grab()
                        assert not picture.isNull()
                        name = f'{report_path.stem}-{theme}-{page}-{percent}.png'
                        assert picture.save(str(report_path.with_name(name)))
                        screenshots.append({'file': name, 'requested_percent': percent,
                                            'effective_percent': actual, 'width': picture.width(),
                                            'height': picture.height(), 'dpr': picture.devicePixelRatioF()})
                        if page == 'settings':
                            assert window.settings_window.ocr_engine_combo.currentData() == "Apple Vision"
            # Exercise all four position engines' dispatch separately in unit
            # tests; this smoke check runs the actual native Vision framework.
            window.grab().save(str(report_path.with_suffix(".png")))
            hotkey = registry().register("Ctrl+Alt+Shift+F19", lambda: None)
            registry().unregister(hotkey)
            image = Image.new("RGB", (900, 130), "white")
            font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 54)
            ImageDraw.Draw(image).text((30, 25), "CLICK TRANSLATE", font=font, fill="black")
            items = macos_ocr.recognize_image(image, "en")
            assert "TRANSLATE" in " ".join(item[1] for item in items).upper(), items
            report_path.write_text(json.dumps({
                "macos": platform.mac_ver()[0], "architecture": platform.machine(),
                "python": platform.python_version(), "qt": QT_VERSION_STR, "pyqt": PYQT_VERSION_STR,
                "screenshots": screenshots,
                "gui": "ok", "settings": "ok", "theme": "ok", "hotkey_registration": "ok",
                "vision": "ok", "vision_languages": macos_ocr.supported_languages(),
            }, indent=2), encoding="utf-8")
            window.force_quit = True
            window.close()
            window.deleteLater()
            app.processEvents()
    return 0
