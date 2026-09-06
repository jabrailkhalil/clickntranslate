"""Native bundle smoke check; invoked explicitly by the macOS build workflow."""

import json
import os
import platform
from pathlib import Path
import tempfile
from unittest import mock


def extended_screenshots(main, app, window, report_path, screenshots):
    """Opt-in native rendering matrix; no input synthesis or user data."""
    from PyQt5 import QtCore, QtWidgets
    from settings_window import OcrLanguageManagerDialog

    def capture(widget, name, requested):
        for _ in range(5):
            app.processEvents()
        picture = widget.grab()
        filename = f'{report_path.stem}-{name}.png'
        assert not picture.isNull() and picture.save(str(report_path.with_name(filename)))
        screenshots.append({'file': filename, 'requested_percent': requested,
                            'effective_percent': window._ui_scale_controller.effective_percent,
                            'width': picture.width(), 'height': picture.height(),
                            'dpr': picture.devicePixelRatioF()})

    for theme in ('dark', 'light'):
        expected = 'Темная' if theme == 'dark' else 'Светлая'
        if window.current_theme != expected:
            window.toggle_theme()
        for language in ('en', 'ru', 'de', 'es', 'fr', 'zh'):
            window.set_interface_language(language)
            for percent in (80, 100, 125, 150, 200):
                window.set_ui_scale_percent(percent)
                prefix = f'{theme}-{language}-{percent}'
                window.show_main_screen()
                capture(window, prefix + '-main', percent)
                window.show_settings()
                for page in range(3):
                    window.settings_window._set_settings_page(page)
                    capture(window, prefix + f'-settings{page}', percent)
            if language not in ('en', 'ru'):
                continue
            window.set_ui_scale_percent(100)
            prefix = f'{theme}-{language}'
            settings = window.settings_window
            # Render package pages without starting network catalogs or
            # optional-engine probes. Their actual runtimes are tested below
            # and by the separate native installation checks.
            with mock.patch.object(QtCore.QTimer, 'singleShot'):
                packages = OcrLanguageManagerDialog(settings)
            packages.show()
            for section, tabs in enumerate((packages.ocr_tabs, packages.translation_tabs)):
                packages.tabs.setCurrentIndex(section)
                for index in range(tabs.count()):
                    tabs.setCurrentIndex(index)
                    capture(packages, prefix + f'-packages{section}-{index}', 100)
            packages.close()
            packages.deleteLater()
            for name, action in (('hotkeys', settings.show_hotkeys_screen),
                                 ('copy-history', settings.show_copy_history_view),
                                 ('translation-history', settings.show_history_view)):
                action()
                capture(window, prefix + '-' + name, 100)
            window.show_main_screen()
            document = main.DocumentTranslationDialog(window)
            document.show()
            capture(document, prefix + '-documents', 100)
            document.close()
            document.deleteLater()
            result = main.TranslationResultDialog(window, 'Привет, мир!\nHello, world!',
                         auto_copy=False, lang=language, theme=window.current_theme,
                         source_text='Hello, world!', source_lang='en', target_lang='ru')
            result.show()
            capture(result, prefix + '-result', 100)
            result.close()
            result.deleteLater()
            def close_help():
                dialog = next((w for w in app.topLevelWidgets()
                               if w.objectName() == 'helpDialogRoot' and w.isVisible()), None)
                assert dialog is not None and dialog.isVisible()
                capture(dialog, prefix + '-help', 100)
                dialog.accept()
                dialog.deleteLater()
            QtCore.QTimer.singleShot(100, close_help)
            window.show_help_dialog()
            window._guide_active = True
            window._guide_step_index = 0
            window._show_guide_step()
            capture(window, prefix + '-guide', 100)
            window.skip_first_run_guide()
            app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


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
            if os.environ.get('CLICKNTRANSLATE_EXTENDED_SMOKE') == '1':
                extended_screenshots(main, app, window, report_path, screenshots)
            hotkey = registry().register("Ctrl+Alt+Shift+F19", lambda: None)
            try:
                duplicate = registry().register("Ctrl+Alt+Shift+F19", lambda: None)
            except RuntimeError as error:
                assert 'unavailable' in str(error)
            else:
                registry().unregister(duplicate)
                raise AssertionError('Carbon accepted a conflicting shortcut')
            registry().unregister(hotkey)
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
                "hotkey_conflict_and_reregister": "ok",
                "permission_preflight": {kind: macos_desktop.permission_granted(kind)
                                         for kind in ('screen', 'accessibility')},
                "vision": "ok", "vision_languages": macos_ocr.supported_languages(),
            }, indent=2), encoding="utf-8")
            window.force_quit = True
            window.close()
            window.deleteLater()
            app.processEvents()
    return 0
