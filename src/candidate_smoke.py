"""Explicit, isolated smoke checks for unpublished Windows/Linux binaries.

Only invoked by --candidate-smoke-test; never captures a desktop, uses the
clipboard, registers hotkeys or contacts a translation provider.
"""
import json
import os
from pathlib import Path
import platform
import sys
import tempfile
import traceback
from unittest import mock


_startup_profile = None


def prepare_profile():
    """Isolate import-time diagnostics too, before main imports OCR/services."""
    global _startup_profile
    import portable_paths
    if _startup_profile is None:
        _startup_profile = tempfile.TemporaryDirectory(prefix='cnt-candidate-startup-')
        portable_paths.portable_base_dir = lambda: _startup_profile.name
        for variable in ('XDG_DATA_HOME', 'XDG_CACHE_HOME', 'XDG_CONFIG_HOME'):
            path = Path(_startup_profile.name) / variable.lower()
            path.mkdir()
            os.environ[variable] = str(path)


def _check_engine_center(window, app, directory, report):
    """Check the actual frozen forms without model probes or stored API keys."""
    from PyQt5 import QtCore, QtWidgets
    from settings_window import OcrLanguageManagerDialog

    def chrome(dialog):
        return (dialog.size(), *(QtCore.QRect(widget.mapTo(dialog, QtCore.QPoint()), widget.size())
                for widget in (dialog.tabs.tabBar(), dialog.download_access_btn, dialog.close_btn)))

    for locale in ('en', 'ar'):
        window.set_interface_language(locale)
        for theme in ('Темная', 'Светлая'):
            if window.current_theme != theme:
                window.toggle_theme()
            window.show_settings()
            with (mock.patch.object(OcrLanguageManagerDialog, '_start_runtime_probe'),
                  mock.patch.object(OcrLanguageManagerDialog, '_start_argos_catalog_refresh'),
                  mock.patch('provider_secrets.get_key', return_value=''),
                  mock.patch('download_access.DownloadAccessPage.start')):
                dialog = OcrLanguageManagerDialog(window.settings_window)
                dialog._initial_probe_timer.stop()
                dialog._initial_catalog_timer.stop()
                try:
                    dialog.show()
                    app.processEvents()
                    reference = chrome(dialog)
                    for index in (0, 1, 2, 0):
                        dialog.tabs.setCurrentIndex(index)
                        app.processEvents()
                        app.processEvents()
                        assert chrome(dialog) == reference, (locale, theme, index)
                        for rect in reference[1:]:
                            assert dialog.rect().contains(rect)
                        if index == 2:
                            assert dialog.api_page.isVisible()
                            assert not dialog.api_page.key.text(), 'smoke must not read stored credentials'
                        name = f'center-{locale}-{"dark" if theme == "Темная" else "light"}-{index}.png'
                        assert dialog.grab().save(str(directory/name))
                        if name not in report['screenshots']:
                            report['screenshots'].append(name)
                    dialog.download_access_btn.click()
                    app.processEvents()
                    assert chrome(dialog) == reference, ('connection', locale, theme, reference, chrome(dialog))
                    dialog.download_access_btn.click()
                    app.processEvents()
                    assert chrome(dialog) == reference, ('back', locale, theme, reference, chrome(dialog))
                finally:
                    dialog.close()
                    dialog.deleteLater()
                    app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    report['checks']['engine_center'] = 'stationary tabs and footer; OCR/translation/API, en/ar, both themes'


def _check_popup_scroll(app, report):
    """Observe real paint delivery before any hover or forced screenshot."""
    from PyQt5 import QtCore, QtGui, QtWidgets
    from settings_window import DropDownCombo

    class PaintWatch(QtCore.QObject):
        def __init__(self, viewport):
            super().__init__(viewport)
            self.region = QtGui.QRegion()
            viewport.installEventFilter(self)

        def eventFilter(self, watched, event):
            if event.type() == QtCore.QEvent.Paint:
                self.region |= event.region()
            return False

    owner = QtWidgets.QWidget()
    owner.resize(400, 150)
    combo = DropDownCombo(owner)
    combo.setGeometry(20, 20, 300, 32)
    combo.setMaxVisibleItems(6)
    combo.addItems([f'Scroll entry {index:03d}' for index in range(80)])
    try:
        owner.show()
        combo.showPopup()
        for _ in range(4):
            app.processEvents()
        viewport = combo.view().viewport()
        watcher = PaintWatch(viewport)
        bar = combo.view().verticalScrollBar()
        assert bar.maximum() > 13
        bar.setSliderPosition(13)
        for _ in range(4):
            app.processEvents()
        assert bar.value() == 13
        assert watcher.region.contains(viewport.rect())
        report['checks']['popup_scroll'] = 'full visible list repainted after scrolling without hover'
    finally:
        combo.hidePopup()
        owner.close()
        owner.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def _check_popup_host_scaling(window, app, directory, report):
    """Exercise the retained Qt auto-proxy that an ordinary first open misses."""
    from PyQt5 import QtCore, QtGui, QtWidgets
    import ocr
    from languages import LANGUAGES
    from combo_popup import popup_font
    from settings_sections import PAGE_DYNAMIC
    from ui_scaling import widget_global_rect

    controller = window._ui_scale_controller
    previous_percent = controller.requested_percent
    codes = [language.code for language in LANGUAGES]
    with (mock.patch.object(controller, 'available_geometry', return_value=QtCore.QRect(0, 0, 3840, 2160)),
          mock.patch.object(ocr, 'installed_ocr_language_codes', return_value=codes),
          mock.patch.object(ocr, '_translation_targets_for_source', return_value=codes)):
        window.set_ui_scale_percent(135)
        for locale in ('en', 'ar'):
            window.set_interface_language(locale)
            for location in ('main', 'dynamic'):
                if location == 'main':
                    window.show_main_screen()
                    combo = window.target_lang
                else:
                    window.show_settings()
                    window.settings_window._set_settings_page(PAGE_DYNAMIC)
                    window.settings_window._populate_game_language_controls(fast=False)
                    combo = window.settings_window.game_target_combo
                app.processEvents()
                popup = combo.view().window()
                popup.setWindowFlag(QtCore.Qt.BypassGraphicsProxyWidget, False)
                QtWidgets.QComboBox.showPopup(combo)
                app.processEvents()
                QtWidgets.QComboBox.hidePopup(combo)
                for opening in (1, 2):
                    try:
                        combo.showPopup()
                        for _ in range(8):
                            app.processEvents()
                        assert popup.graphicsProxyWidget() is not None
                        field_factor = widget_global_rect(combo).width() / combo.width()
                        surface_factor = widget_global_rect(popup).width() / popup.width()
                        field_pixels = QtGui.QFontInfo(combo.font()).pixelSize() * field_factor
                        row_pixels = QtGui.QFontInfo(popup_font(combo)).pixelSize() * surface_factor
                        search_pixels = QtGui.QFontInfo(combo._language_search.font()).pixelSize() * surface_factor
                        assert .94 <= row_pixels / field_pixels <= 1.06, (locale, location, row_pixels, field_pixels)
                        assert .94 <= search_pixels / field_pixels <= 1.06, (locale, location, search_pixels, field_pixels)
                        if opening == 1:
                            name = f'popup-host-{locale}-{location}.png'
                            assert window.grab().save(str(directory / name))
                            report['screenshots'].append(name)
                        combo._language_search.setText('Vietnamese')
                        app.processEvents()
                        assert not combo.view().isRowHidden(combo.findData('vi'))
                    finally:
                        combo.hidePopup()
    window.set_ui_scale_percent(previous_percent)
    report['checks']['popup_host_scaling'] = 'retained proxy; main/dynamic, en/ar, 135%, two openings and search'


def run(main, report_path):
    from PyQt5 import QtCore, QtGui, QtWidgets
    from PIL import Image
    import portable_paths
    import ocr

    report_path = Path(report_path).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = dict(status='running', platform=sys.platform, architecture=platform.machine(),
                  frozen=bool(getattr(sys, 'frozen', False)), screenshots=[], checks={})
    window = None
    try:
        with tempfile.TemporaryDirectory(prefix='cnt-candidate-') as temporary:
            config = dict(main.DEFAULT_CONFIG, interface_language='en',
                          update_check_on_launch=False, desktop_assistant_enabled=False,
                          autostart=False, start_minimized=False,
                          first_run_guide_completed=True, show_update_info=False)
            with (mock.patch.object(portable_paths, 'portable_base_dir', return_value=temporary),
                  mock.patch.object(main, 'LAYOUT_EDITOR_MODE', True),
                  mock.patch.object(main, 'get_cached_config', return_value=config),
                  mock.patch.object(main.DarkThemeApp, 'save_config'),
                  mock.patch.object(main.DarkThemeApp, 'sync_autostart_state', return_value=False),
                  mock.patch.object(main.DarkThemeApp, '_maybe_check_updates_on_launch'),
                  mock.patch.object(main.DarkThemeApp, '_maybe_show_startup_news'),
                  mock.patch.object(main.DarkThemeApp, '_maybe_start_first_run_guide')):
                app = main._ensure_startup_application()
                app.setQuitOnLastWindowClosed(False)
                # The Windows offscreen plugin does not discover system fonts.
                # Register the real faces before taking UI pictures or drawing
                # the OCR fixture; otherwise the test image can be all white.
                if sys.platform == 'win32' and QtGui.QGuiApplication.platformName() == 'offscreen':
                    fonts = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
                    for name in ('segoeui.ttf', 'segoeuib.ttf', 'arial.ttf', 'arialbd.ttf',
                                 'msyh.ttc', 'msyhbd.ttc', 'Nirmala.ttc'):
                        QtGui.QFontDatabase.addApplicationFont(str(fonts / name))
                    app.setFont(QtGui.QFont('Segoe UI', 10))
                window = main.DarkThemeApp()
                window.show()
                app.processEvents()
                for locale in ('en', 'ru', 'ar', 'hi'):
                    window.set_interface_language(locale)
                    for theme in ('Темная', 'Светлая'):
                        if window.current_theme != theme:
                            window.toggle_theme()
                        window.show_settings()
                        for page in (0, 1, 4, 2, 3):
                            window.settings_window._set_settings_page(page)
                            app.processEvents()
                            assert window.settings_window.settings_pages.currentIndex() == page
                        name = f'{locale}-{"dark" if theme == "Темная" else "light"}.png'
                        assert window.grab().save(str(report_path.parent / name))
                        report['screenshots'].append(name)
                window.show_main_screen()
                assert window.isVisible() and window.text_input.width() > 0
                report['checks']['gui'] = 'four locales, two themes, five settings pages'
                _check_engine_center(window, app, report_path.parent, report)
                _check_popup_scroll(app, report)
                _check_popup_host_scaling(window, app, report_path.parent, report)

                # Generate the image locally: no screen capture or personal data.
                image = QtGui.QImage(1000, 180, QtGui.QImage.Format_RGB32)
                image.fill(QtGui.QColor('white'))
                painter = QtGui.QPainter(image)
                painter.setPen(QtGui.QColor('black'))
                painter.setFont(QtGui.QFont('DejaVu Sans' if sys.platform == 'linux' else 'Arial', 36))
                painter.drawText(QtCore.QRect(24, 30, 950, 120), QtCore.Qt.AlignLeft,
                                 'NATIVE OCR CHECK')
                painter.end()
                fixture = Path(temporary) / 'fixture.png'
                assert image.save(str(fixture))
                with Image.open(fixture) as source:
                    pil_image = source.convert('RGB')

                if sys.platform == 'linux':
                    import pytesseract
                    ocr._configure_pytesseract_system_environment(pytesseract)
                    version = str(pytesseract.get_tesseract_version())
                    positioned = ocr._recognize_image_layout(pil_image, 'tesseract', 'en')
                    assert 'OCR' in ' '.join(row[4] for row in positioned).upper(), positioned
                    paragraph = ocr._run_tesseract_ocr_image_with_cmd(
                        pil_image, 'tesseract', 'eng', 'candidate fixture', 'candidate',
                        join_paragraphs=True)
                    assert 'OCR' in paragraph.upper(), paragraph
                    report['checks']['tesseract'] = dict(version=version,
                        fullscreen_text=' '.join(row[4] for row in positioned),
                        paragraph_text=paragraph, process_environment='actual bundled runtime')
                if report['frozen']:
                    lines = ocr._recognize_image_layout(pil_image, 'rapidocr', 'en')
                    assert 'OCR' in ' '.join(row[4] for row in lines).upper(), lines
                    report['checks']['ocr_worker'] = 'bundled RapidOCR recognized the generated fixture'
                    response = main.translater._run_argos_worker_request(
                        {'action': 'probe', 'source_code': 'en', 'target_code': 'ru'}, timeout=90)
                    assert not response.get('error') and 'pair_installed' in response, response
                    report['checks']['argos_worker'] = 'bundled probe returned structured data'
                report['status'] = 'passed'
    except Exception:
        report['status'] = 'failed'
        report['error'] = traceback.format_exc()
    finally:
        if window is not None:
            window.force_quit = True
            # Cleanup also runs after the temporary-profile context unwinds.
            # Layout-only closeEvent saves configuration unless suppressed.
            with mock.patch.object(main.DarkThemeApp, 'save_config'):
                window.close()
            window.deleteLater()
            QtWidgets.QApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
            QtWidgets.QApplication.processEvents()
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 0 if report['status'] == 'passed' else 1
