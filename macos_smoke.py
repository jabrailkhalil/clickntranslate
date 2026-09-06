"""Native bundle smoke check; invoked explicitly by the macOS build workflow."""

import json
import os
import platform
from pathlib import Path
import tempfile
from unittest import mock


def popup_screenshots(app, window, report_path, screenshots):
    """Check the real NSWindow background as well as Qt's painted corners."""
    import ctypes
    import objc
    from PyQt5 import QtCore, QtWidgets
    from PyQt5.QtTest import QTest
    from styled_dialogs import StatusPopup

    result = {}
    for theme in ('dark', 'light'):
        expected = 'Темная' if theme == 'dark' else 'Светлая'
        if window.current_theme != expected:
            window.toggle_theme()
        window.activateWindow()
        QTest.qWait(100)
        for name in ('tooltip', 'status', 'menu'):
            # A menu or another tooltip can destroy the shared QTipLabel.
            # Inspect and capture each popup before opening the next one.
            if name == 'tooltip':
                button = window.help_button
                QtWidgets.QToolTip.showText(button.mapToGlobal(QtCore.QPoint(0, 25)),
                                           'Native tooltip / Подсказка', button)
                QTest.qWait(50)
                widget = next(w for w in app.topLevelWidgets()
                              if w.metaObject().className() == 'QTipLabel' and w.isVisible())
            elif name == 'status':
                widget = StatusPopup()
                widget.setText('Translation completed / Перевод завершён')
                widget.adjustSize()
                widget.show()
            else:
                widget = QtWidgets.QMenu(window)
                window._apply_main_context_menu_style(widget)
                widget.addAction('Translate / Перевести')
                widget.popup(window.mapToGlobal(QtCore.QPoint(40, 100)))
            QTest.qWait(30)
            try:
                native_view = objc.objc_object(c_void_p=ctypes.c_void_p(int(widget.winId())))
                native_window = native_view.window()
                try:
                    assert not native_window.isOpaque()
                    assert native_window.backgroundColor().alphaComponent() == 0.0
                finally:
                    del native_window, native_view
                picture = widget.grab()
                image = picture.toImage()
                assert image.pixelColor(0, 0).alpha() == 0
                assert widget.mask().isEmpty()
                background = image.pixelColor(image.width() // 2, round(4 * picture.devicePixelRatioF()))
                assert background.alpha() > 240
                filename = f'{report_path.stem}-{theme}-{name}.png'
                assert picture.save(str(report_path.with_name(filename)))
                screenshots.append({'file': filename, 'requested_percent': 100,
                                    'effective_percent': 100, 'width': picture.width(),
                                    'height': picture.height(), 'dpr': picture.devicePixelRatioF()})
                result[f'{theme}_{name}'] = 'transparent Cocoa background; painted surface'
            finally:
                if name == 'tooltip':
                    QtWidgets.QToolTip.hideText()
                    QTest.qWait(350)
                else:
                    widget.close()
                    widget.deleteLater()
                app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    return result


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
            drafts = result.source_edit.toPlainText(), result.text_edit.toPlainText()
            result.resize(420, 620)
            capture(result, prefix + '-result-narrow', 100)
            assert result._panel_orientation is False
            assert drafts == (result.source_edit.toPlainText(), result.text_edit.toPlainText())
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
            popup_results = popup_screenshots(app, window, report_path, screenshots)
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
                "native_popup_surfaces": popup_results,
            }, indent=2), encoding="utf-8")
            window.force_quit = True
            window.close()
            window.deleteLater()
            app.processEvents()
    return 0
