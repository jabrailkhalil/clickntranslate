"""Usage selection is independent for text/OCR and never reads real credentials."""
from pathlib import Path
from unittest import mock

import pytest
from PyQt5 import QtCore, QtWidgets

import api_providers
import main
import provider_secrets
import settings_window
from provider_settings import show_provider_settings, routing_text
from test_desktop_ux import app, window


@pytest.fixture
def page(window, app):
    window.config.update(translator_engine='Google', ocr_engine='Windows', api_providers={})
    window.show_settings()
    with (mock.patch.object(provider_secrets, 'get_key', return_value='qa-only-key'),
          mock.patch.object(provider_secrets, 'set_key', return_value=True) as store,
          mock.patch.object(settings_window.OcrLanguageManagerDialog, '_start_runtime_probe'),
          mock.patch.object(settings_window.OcrLanguageManagerDialog, '_start_argos_catalog_refresh')):
        editor = show_provider_settings(window.settings_window, 'gemini')
        editor.model.setText('qa-model')
        yield editor, window, store
        window.settings_window._language_manager_dialog.close()
        app.processEvents()


@pytest.mark.parametrize('usage,translator,ocr', [('text', 'gemini', 'Windows'),
                                               ('ocr', 'Google', 'Gemini API'),
                                               ('direct', 'gemini', 'Gemini API')])
def test_save_and_select_changes_only_the_requested_engines(page, usage, translator, ocr):
    editor, owner, store = page
    editor.usage.setCurrentIndex(editor.usage.findData(usage))
    editor.use.click()
    assert owner.config['translator_engine'] == translator
    assert owner.config['ocr_engine'] == ocr
    assert editor.settings.translator_combo.currentData() == translator.lower()
    assert editor.settings.ocr_engine_combo.currentData() == ocr
    assert owner.config['api_providers']['gemini']['vision'] == (usage != 'text')
    assert owner.config['api_providers']['gemini']['direct'] == (usage == 'direct')
    if usage == 'ocr':
        assert routing_text(editor.lang, 4) in editor.status.text()


@pytest.mark.parametrize('usage', ('text', 'ocr', 'direct'))
def test_save_without_selection_keeps_both_engine_choices(page, usage):
    editor, owner, store = page
    before = (owner.config['translator_engine'], owner.config['ocr_engine'])
    editor.usage.setCurrentIndex(editor.usage.findData(usage))
    editor.key.setText('qa-draft-key')
    assert editor.save_profile()
    assert (owner.config['translator_engine'], owner.config['ocr_engine']) == before
    assert 'qa-draft-key' not in repr(owner.config)
    store.assert_called_once_with('gemini', api_providers.BY_KEY['gemini'].url, 'qa-draft-key')


def test_disabling_images_for_the_active_ocr_service_is_blocked_before_any_write(page):
    editor, owner, store = page
    owner.config['ocr_engine'] = 'Gemini API'
    owner.config['api_providers'] = {'gemini': {'url': api_providers.BY_KEY['gemini'].url,
                                               'model': 'old-vision-model', 'vision': True, 'direct': False}}
    original = dict(owner.config['api_providers']['gemini'])
    editor.usage.setCurrentIndex(editor.usage.findData('ocr'))
    editor.usage.setCurrentIndex(editor.usage.findData('text'))
    editor.key.setText('must-not-store')
    assert routing_text(editor.lang, 6) in editor.routing_label.text()
    assert not editor.save_profile()
    assert editor.status.text() == routing_text(editor.lang, 6)
    assert owner.config['api_providers']['gemini'] == original
    assert owner.config['ocr_engine'] == 'Gemini API'
    assert owner.config['translator_engine'] == 'Google'
    store.assert_not_called()


def test_invalid_connection_does_not_change_the_active_engines(page):
    editor, owner, store = page
    editor.usage.setCurrentIndex(editor.usage.findData('ocr'))
    with mock.patch.object(api_providers, 'validate', side_effect=api_providers.ProviderError('Add an API key')):
        editor.use.click()
    assert owner.config['translator_engine'] == 'Google'
    assert owner.config['ocr_engine'] == 'Windows'


def test_preview_updates_from_model_and_usage_without_saving_or_using_the_key(page):
    editor, owner, store = page
    before = dict(owner.config)
    editor.key.setText('never-display-this')
    editor.model.setText('<model & test>')
    editor.usage.setCurrentIndex(editor.usage.findData('ocr'))
    assert '<model & test>' in editor.routing_label.text()
    assert 'Google' in editor.routing_label.text()
    assert editor.routing_label.textFormat() == QtCore.Qt.PlainText
    assert 'never-display-this' not in editor.routing_label.text()
    assert 'never-display-this' not in editor.routing_label.toolTip()
    assert '&lt;model' in editor.routing_label.toolTip()
    assert owner.config == before
    store.assert_not_called()


@pytest.mark.parametrize('locale', tuple(main.INTERFACE_LANGUAGE_BY_CODE))
@pytest.mark.parametrize('dark', (True, False))
def test_routing_preview_is_localized_and_fits_the_existing_api_page(window, app, locale, dark):
    window.set_interface_language(locale)
    window.current_theme = 'Темная' if dark else 'Светлая'
    window.show_settings()
    with (mock.patch.object(provider_secrets, 'get_key', return_value=''),
          mock.patch.object(settings_window.OcrLanguageManagerDialog, '_start_runtime_probe'),
          mock.patch.object(settings_window.OcrLanguageManagerDialog, '_start_argos_catalog_refresh')):
        editor = show_provider_settings(window.settings_window, 'gemini')
        editor.model.setText('qa-vision-model')
        editor.usage.setCurrentIndex(editor.usage.findData('ocr'))
        for _ in range(3):
            app.processEvents()
        assert routing_text(locale, 0) in editor.routing_label.text()
        if locale != 'en':
            assert routing_text(locale, 0) != routing_text('en', 0)
        assert editor.routing_label.isVisible()
        assert editor.routing_label.height() >= editor.routing_label.heightForWidth(editor.routing_label.width())
        assert editor.scroll.horizontalScrollBar().maximum() == 0
        for control in (editor.service, editor.address, editor.model, editor.usage, editor.save, editor.use):
            assert control.isVisible()
            assert editor.rect().contains(QtCore.QRect(control.mapTo(editor, QtCore.QPoint()), control.size()))
        if locale in ('ru', 'ar'):
            folder = Path('.tmp/provider-routing-images')
            folder.mkdir(parents=True, exist_ok=True)
            assert window.settings_window._language_manager_dialog.grab().save(str(folder/f'{locale}-{dark}.png'))
        window.settings_window._language_manager_dialog.close()
