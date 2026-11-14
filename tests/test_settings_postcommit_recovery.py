"""A saved imported profile survives isolated UI finalizer failures and can retry."""
import json

import pytest

import settings_window as sw
from test_settings_import_reliability import import_context
from test_desktop_ux import app


LOCALES = ('en', 'ru', 'es', 'de', 'fr', 'zh', 'pt', 'it', 'ar', 'tr', 'hi', 'id')
CALLBACKS = ('parent-theme', 'selection-sync', 'language-refresh',
             'settings-rebuild', 'settings-theme', 'page-reset')


def finalizers(owner, panel):
    return {
        'listener-restart': owner.restart_all_hotkey_listeners,
        'parent-theme': owner.apply_theme,
        'selection-sync': owner._sync_selection_quick_translate,
        'language-refresh': owner.refresh_interface_language_ui,
        'settings-rebuild': panel.init_ui,
        'settings-theme': panel.apply_theme,
        'page-reset': panel._set_settings_page,
    }


def incoming_profile(path, locale, *, autostart=False):
    source = path.with_name('import.json')
    source.write_text(json.dumps(sw.settings_export_payload({
        'interface_language': locale, 'autostart': autostart, 'copy_history': False,
        'main_translation_source_language': 'ja', 'main_translation_target_language': 'de',
    })), encoding='utf-8')
    return source


def assert_committed_recovery(import_context, locale, callback):
    owner, panel, path, warning, information = import_context
    incoming = incoming_profile(path, locale)
    operations = finalizers(owner, panel)
    operations[callback].side_effect = RuntimeError('audit-only disposed Qt callback detail')
    applied = panel.import_settings()
    persisted = json.loads(path.read_text(encoding='utf-8'))
    assert owner.config['copy_history'] is persisted['copy_history'] is False
    assert owner.current_interface_language == persisted['interface_language'] == locale
    assert persisted['main_translation_source_language'] == 'ja'
    assert persisted['main_translation_target_language'] == 'de'
    assert applied == incoming
    owner.set_autostart.assert_not_called()
    owner.restart_all_hotkey_listeners.assert_called_once_with()
    for operation in operations.values():
        operation.assert_called_once()
    warning.assert_called_once()
    information.assert_not_called()
    message = warning.call_args.args[2]
    assert sw.settings_text(locale, 'settings_imported') in message
    assert sw.SETTINGS_TEXT[locale]['settings_refresh_incomplete'] in message
    assert 'audit-only' not in message and 'RuntimeError' not in message

    # Retrying a repaired callback completes normally without stale warnings.
    durable = path.read_bytes()
    operations[callback].side_effect = None
    for operation in operations.values():
        operation.reset_mock()
    owner.restart_all_hotkey_listeners.reset_mock()
    warning.reset_mock()
    information.reset_mock()
    assert panel.import_settings() == incoming
    assert path.read_bytes() == durable
    owner.restart_all_hotkey_listeners.assert_called_once_with()
    for operation in operations.values():
        operation.assert_called_once()
    warning.assert_not_called()
    information.assert_called_once()


@pytest.mark.parametrize('locale', LOCALES)
@pytest.mark.parametrize('callback', CALLBACKS)
def test_committed_import_continues_after_each_finalizer_failure_and_can_retry(import_context, locale, callback):
    assert_committed_recovery(import_context, locale, callback)


def test_unexpected_listener_restart_error_cannot_abandon_remaining_finalizers_or_retry(import_context):
    assert_committed_recovery(import_context, 'en', 'listener-restart')


@pytest.mark.parametrize('locale', LOCALES)
def test_ui_and_autostart_followup_failures_share_one_localized_applied_warning(import_context, locale):
    owner, panel, path, warning, information = import_context
    incoming = incoming_profile(path, locale, autostart=True)
    owner.set_autostart.return_value = False
    owner.apply_theme.side_effect = RuntimeError('audit-only disposed Qt callback detail')
    assert panel.import_settings() == incoming
    persisted = json.loads(path.read_text(encoding='utf-8'))
    assert persisted['autostart'] is owner.config['autostart'] is False
    assert persisted['interface_language'] == locale
    assert persisted['copy_history'] is False
    owner.set_autostart.assert_called_once_with(True)
    for operation in finalizers(owner, panel).values():
        operation.assert_called_once()
    warning.assert_called_once()
    information.assert_not_called()
    message = warning.call_args.args[2]
    imported = sw.settings_text(locale, 'settings_imported')
    refresh = sw.SETTINGS_TEXT[locale]['settings_refresh_incomplete']
    assert imported in message and refresh in message
    assert len(message) > len(imported) + len(refresh) + 10
    assert 'audit-only' not in message and 'RuntimeError' not in message
