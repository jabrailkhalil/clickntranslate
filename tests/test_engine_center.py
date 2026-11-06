"""A single entry, explicit update acceptance, and truthful download diagnostics."""
import copy
from unittest import mock
from types import SimpleNamespace

import pytest
import requests
from PyQt5 import QtCore, QtWidgets, QtTest

from engine_center import TEXT, KEYS, compare_update, text
from download_access import sources, probe
from settings_window import OcrLanguageManagerDialog
from test_desktop_ux import app, window
from test_language_package_manager import _AppParent, _ManagerOwner
from test_package_presentation import size_catalog


TARGET = dict(os='windows', arch='x86_64', os_version='10')


def test_all_center_strings_are_complete():
    assert len(TEXT) == 12
    for row in TEXT.values():
        assert len(row) == len(KEYS)
        assert all(value.strip() for value in row)


def test_update_comparison_preserves_installed_language_compatibility_and_shared_sizes():
    catalog = size_catalog()
    old = copy.deepcopy(catalog['bundles'][0])
    old.update(bundle=old['id'], languages=['latin_g2'])
    old['files'] += [dict(item, language='latin_g2') for item in old['language_files']['latin_g2']]
    store = SimpleNamespace(describe=lambda _: dict(receipt=old))
    newer = copy.deepcopy(catalog['bundles'][0])
    newer.update(id='newer-without-installed-script', revision=2, languages=['english_g2'])
    newer['language_files'].pop('latin_g2')
    catalog['bundles'].append(newer)
    result = compare_update(catalog, 'easyocr', store=store, target=TARGET)
    assert result['current'] is True
    assert result['bundle'] == old['bundle']
    assert result['size'] == 292000000
    store = SimpleNamespace(describe=lambda _: None)
    result = compare_update(catalog, 'easyocr', store=store, target=TARGET)
    assert result['current'] is False
    assert result['size'] == 287000000  # Base runtime, detector, default English only.


def test_access_check_does_not_treat_a_release_webpage_as_download_proof():
    assert dict(sources())['files'] is None
    head = mock.Mock()
    assert probe(None, head=head)['status'] == 'unchecked'
    head.assert_not_called()
    catalog = {'artifacts': {'one': {'size': 22, 'urls': [
        'https://github.com/jabrailkhalil/clickntranslate-components/releases/download/r/a.zip']}}}
    assert dict(sources(catalog))['files'].endswith('/r/a.zip')


def test_update_comparison_cannot_hide_archive_member_changes():
    catalog = size_catalog()
    old = copy.deepcopy(catalog['bundles'][0])
    old.update(bundle=old['id'], languages=['english_g2'])
    old['files'] += [dict(item, language='english_g2') for item in old['language_files']['english_g2']]
    store = SimpleNamespace(describe=lambda _: dict(receipt=old))
    assert compare_update(catalog, 'easyocr', store=store, target=TARGET)['current']
    old['files'][0]['member'] = 'old/worker.py'
    assert not compare_update(catalog, 'easyocr', store=store, target=TARGET)['current']


@pytest.mark.parametrize('code,expected', [(200, 'ok'), (403, 'restricted'), (405, 'unchecked'), (429, 'restricted'), (500, 'failed')])
def test_connection_probe_uses_head_and_distinguishes_restriction(code, expected):
    response = mock.MagicMock(status_code=code, url='https://release-assets.githubusercontent.com/asset')
    response.__enter__.return_value = response
    head = mock.Mock(return_value=response)
    result = probe('https://github.com/package', head=head)
    assert result['status'] == expected
    assert head.call_args.kwargs['timeout'] == (3, 5)
    assert head.call_args.kwargs['allow_redirects'] is True
    failure = mock.Mock(side_effect=requests.ConnectionError('offline'))
    assert probe('https://github.com/package', head=failure)['status'] == 'failed'


def test_connectivity_redirect_to_an_unrelated_portal_is_not_github_access():
    response = mock.MagicMock(status_code=200, url='https://portal.example.org/blocked')
    response.__enter__.return_value = response
    assert probe('https://api.github.com/public', head=mock.Mock(return_value=response))['status'] == 'restricted'


def test_engine_center_is_one_widget_on_application_and_opens_from_a_real_click(window, app):
    window.show_settings()
    settings = window.settings_window
    button = settings.engines_button
    assert settings.translation_api_button is settings.ocr_api_button is button
    assert settings.translation_offline_button is settings.ocr_languages_btn is button
    assert settings.settings_general_page.isAncestorOf(button)
    with (mock.patch.object(OcrLanguageManagerDialog, '_start_runtime_probe'),
          mock.patch.object(OcrLanguageManagerDialog, '_start_argos_catalog_refresh')):
        QtTest.QTest.mouseClick(button, QtCore.Qt.LeftButton)
        app.processEvents()
        dialog = settings._language_manager_dialog
        assert dialog.isVisible()
        assert dialog.windowTitle() == text(window.current_interface_language, 'title')
        dialog.close()
    for page in (1, 4):
        settings._set_settings_page(page)
        app.processEvents()
        assert not button.isVisible()


def test_check_updates_never_installs_until_a_second_explicit_click(app):
    parent = _AppParent()
    owner = _ManagerOwner(parent)
    owner.easyocr_status = (True, '')
    with (mock.patch.object(OcrLanguageManagerDialog, '_start_runtime_probe'),
          mock.patch.object(OcrLanguageManagerDialog, '_start_argos_catalog_refresh')):
        dialog = OcrLanguageManagerDialog(owner)
    dialog._initial_probe_timer.stop()
    dialog._initial_catalog_timer.stop()
    try:
        table = dialog.easyocr_table
        button = next(b for b in table._package_engine_actions if b.property('packageAction') == 'update')
        with mock.patch('settings_window.threading.Thread') as thread:
            button.trigger()
            assert owner.easyocr_installs == 0
            thread.assert_called_once()
            assert button.text() == text('en', 'checking')
        plan = dict(current=False, installed='1 · r1', available='2 · r2', size=123000000)
        dialog._on_update_plan_ready('easyocr', plan)
        assert button.text() == 'Update · 123.0 MB'
        assert 'r1' in table._package_size_label.text()
        assert 'r2' in table._package_size_label.text()
        button.trigger()
        assert owner.easyocr_installs == 1
    finally:
        dialog.close()
        owner.close()
        parent.close()


@pytest.mark.parametrize('locale', tuple(TEXT))
@pytest.mark.parametrize('theme', ('Темная', 'Светлая'))
def test_center_network_subpage_and_primary_footer_fit_all_locales(window, app, locale, theme, tmp_path):
    window.set_interface_language(locale)
    if window.current_theme != theme:
        window.toggle_theme()
    window.show_settings()
    settings = window.settings_window
    panel = settings.application_action_panel
    app.processEvents()
    button = settings.engines_button
    assert panel.rect().contains(button.geometry())
    assert button.width() >= button.fontMetrics().horizontalAdvance(button.text()) + 16
    with (mock.patch.object(OcrLanguageManagerDialog, '_start_runtime_probe'),
          mock.patch.object(OcrLanguageManagerDialog, '_start_argos_catalog_refresh'),
          mock.patch('download_access.DownloadAccessPage.start')):
        button.click()
        app.processEvents()
        dialog = settings._language_manager_dialog
        dialog.download_access_btn.click()
        app.processEvents()
        page = dialog._download_access_page
        assert page.isVisible() and not dialog.tabs.isVisible()
        for widget in (page.check, page.description):
            assert page.rect().contains(QtCore.QRect(widget.mapTo(page, QtCore.QPoint()), widget.size()))
        for item in (dialog.download_access_btn, dialog.close_btn):
            assert item.width() >= item.minimumSizeHint().width()
            assert dialog.rect().contains(QtCore.QRect(item.mapTo(dialog, QtCore.QPoint()), item.size()))
        assert dialog.grab().save(str(tmp_path / f'network-{locale}-{theme}.png'))
        dialog.download_access_btn.click()
        assert dialog.tabs.isVisible()
        dialog.close()
