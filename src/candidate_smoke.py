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
