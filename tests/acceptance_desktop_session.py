"""Opt-in hosted desktop session with repeated view changes and an idle period."""
from collections import Counter
import gc
import json
import os
import sys
import time
from unittest import mock

import psutil
import pytest
from PyQt5 import QtCore, QtTest, QtWidgets, sip

from settings_window import OcrLanguageManagerDialog
from test_desktop_ux import app, window


pytestmark = pytest.mark.skipif(os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted',
                                reason='Long-running native desktop acceptance')


def test_repeated_navigation_and_idle_ownership(window, app, tmp_path):
    process = psutil.Process()
    report = {'platform': app.platformName(), 'cycles': [], 'status': 'running'}
    report_path = tmp_path / 'session.json'

    def save():
        report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')

    def settle():
        app.processEvents()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        app.processEvents()
        gc.collect()

    def sample():
        widgets = app.allWidgets()
        usage = process.cpu_times()
        return {
            'widgets': len(widgets),
            'types': dict(Counter(w.metaObject().className() for w in widgets)),
            'centers': sum(isinstance(w, OcrLanguageManagerDialog) for w in widgets),
            'rss_bytes': process.memory_info().rss,
            'process_cpu_seconds': usage.user + usage.system,
            'children': len(process.children()),
            'heavy_modules': sorted({'torch', 'easyocr', 'onnxruntime'}.intersection(sys.modules)),
        }

    draft = 'A local, unfinished translation.'
    window.set_interface_language('de')
    window.show_main_screen()
    window.text_input.setPlainText(draft)
    baseline = sample()
    report['initial'] = baseline
    with (mock.patch.object(OcrLanguageManagerDialog, '_start_runtime_probe'),
          mock.patch.object(OcrLanguageManagerDialog, '_start_argos_catalog_refresh'),
          mock.patch('provider_secrets.get_key', return_value='')):
        for iteration in range(24):
            started = time.monotonic()
            locale = ('ar', 'en', 'zh', 'ru')[iteration % 4]
            window.show_settings()
            settings = window.settings_window
            for index in (0, 1, 2, 3, 4):
                settings._set_settings_page(index)
                assert settings.settings_pages.currentIndex() == index
            window.set_ui_scale_percent((100, 135)[iteration % 2])
            window.toggle_theme()
            settings.show_ocr_language_manager()
            previous = settings._language_manager_dialog
            page = previous.show_api('gemini')
            page.model.setText(draft)
            window.set_interface_language(locale)
            current = settings._language_manager_dialog
            assert current.isVisible() and current.lang == locale
            assert current.api_page.model.text() == draft
            current.close_btn.click()
            window.show_main_screen()
            picker = window.target_lang
            picker.showPopup()
            app.processEvents()
            picker._language_search.setText('qa-no-such-language')
            app.processEvents()
            assert picker._language_empty.isVisible()
            picker.hidePopup()
            assert window.text_input.toPlainText() == draft
            QtTest.QTest.qWait(150)
            settle()
            after = sample()
            after.update(index=iteration, locale=locale, seconds=time.monotonic() - started)
            report['cycles'].append(after)
            save()
            assert sip.isdeleted(previous)
            assert after['centers'] <= 1
            assert after['heavy_modules'] == baseline['heavy_modules']
            if iteration in (3, 23):
                assert window.grab().save(str(tmp_path / f'home-{iteration + 1}.png'))

    # Compare like-for-like after all four locales and both scale factors
    # have already been used twice. RSS is recorded separately from live widgets.
    warm = report['cycles'][7]
    final = report['cycles'][-1]
    growth = Counter(final['types']) - Counter(warm['types'])
    assert final['widgets'] <= warm['widgets'] + 4, dict(growth)
    before_idle = sample()
    started = time.monotonic()
    QtTest.QTest.qWait(65000)
    settle()
    after_idle = sample()
    report['idle'] = {'seconds': time.monotonic() - started,
                      'cpu_seconds': after_idle['process_cpu_seconds'] - before_idle['process_cpu_seconds'],
                      'before': before_idle, 'after': after_idle}
    save()
    assert after_idle['children'] <= baseline['children']
    assert after_idle['widgets'] <= before_idle['widgets']
    assert after_idle['heavy_modules'] == baseline['heavy_modules']
    report['status'] = 'passed'
    save()
