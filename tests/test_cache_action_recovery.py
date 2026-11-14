"""Cache maintenance UI outcomes with synthetic filesystem and delayed callbacks."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PyQt5 import QtCore, QtWidgets, sip

import cache_manager
import main
import ocr
import settings_window as settings
import translater
from test_desktop_ux import app

REAL_CLEAR = cache_manager.clear_all_cache


class CachePanel(QtWidgets.QWidget):
    clear_all_cache = settings.SettingsWindow.clear_all_cache

    def __init__(self):
        super().__init__()
        self.parent = SimpleNamespace(current_interface_language='en')
        self.clear_cache_btn = QtWidgets.QPushButton('Clear', self)
        self._apply_action_panel_style = Mock()


@pytest.fixture
def context(app, tmp_path, monkeypatch):
    data = tmp_path / 'data'
    data.mkdir()
    panel = CachePanel()
    callbacks = []
    cleanup = Mock(return_value=0)
    monkeypatch.setattr(main, 'get_data_file', lambda _: str(data / 'config.json'))
    monkeypatch.setattr(settings, '_portable_base_dir', lambda: str(tmp_path))
    monkeypatch.setattr(cache_manager, 'get_cache_stats', Mock(return_value={'cache_bytes': 123}))
    monkeypatch.setattr(cache_manager, 'clear_all_cache', cleanup)
    monkeypatch.setattr(cache_manager, 'invalidate_translation_cache', Mock())
    monkeypatch.setattr(main, 'invalidate_config_cache', Mock())
    monkeypatch.setattr(ocr, 'close_ocr_diagnostics_logging', Mock())
    monkeypatch.setattr(ocr, 'reopen_ocr_diagnostics_logging', Mock())
    for module, name, value in ((ocr, '_OCR_ENGINE_CACHE', {}), (ocr, '_OVERLAY_POOL', {}),
                                (ocr, '_ocr_config_cache', {}), (ocr, '_ocr_config_mtime', 1),
                                (translater, '_translator_config_cache', {}),
                                (translater, '_translator_config_mtime', 1),
                                (translater, '_argos_languages_cache', None),
                                (translater, '_argos_translations_cache', {}),
                                (translater, '_http_session', None)):
        monkeypatch.setattr(module, name, value)
    monkeypatch.setattr(translater, '_hymt_runtime_cache', None, raising=False)
    monkeypatch.setattr(QtCore.QTimer, 'singleShot', lambda _milliseconds, callback: callbacks.append(callback))
    yield panel, cleanup, callbacks, data, tmp_path
    if not sip.isdeleted(panel):
        panel.deleteLater()
    app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


@pytest.mark.parametrize('outcome', [0, OSError('audit locked cache')], ids=['nothing-removed', 'cleanup-refused'])
def test_failed_or_zero_cleanup_does_not_report_the_estimated_bytes_as_freed(context, outcome):
    panel, cleanup, callbacks, data, root = context
    if isinstance(outcome, Exception):
        cleanup.side_effect = outcome
    panel.clear_all_cache()
    cleanup.assert_called_once_with(str(data), str(root))
    assert panel.clear_cache_btn.text() == settings.settings_text('en', 'cleared').format(size='0 B')


def test_unavailable_cache_statistics_do_not_prevent_the_actual_cleanup(context, monkeypatch):
    panel, cleanup, callbacks, data, root = context
    monkeypatch.setattr(cache_manager, 'get_cache_stats', Mock(side_effect=OSError('audit metadata unavailable')))
    cleanup.return_value = 27
    panel.clear_all_cache()
    cleanup.assert_called_once_with(str(data), str(root))
    assert panel.clear_cache_btn.text() == settings.settings_text('en', 'cleared').format(size='27 B')


@pytest.mark.parametrize('locale', ['en', 'ru', 'de', 'fr', 'es', 'zh', 'pt', 'it', 'ar', 'tr', 'hi', 'id'])
def test_delayed_caption_restore_uses_the_current_interface_language(context, locale):
    panel, cleanup, callbacks, data, root = context
    panel.clear_all_cache()
    assert len(callbacks) == 1
    panel.parent.current_interface_language = locale
    callbacks[0]()
    assert panel.clear_cache_btn.text() == settings.settings_text(locale, 'clear_cache')
    assert panel.clear_cache_btn.isEnabled()


def test_old_restore_callback_does_not_touch_a_rebuilt_or_newly_busy_button(context):
    panel, cleanup, callbacks, data, root = context
    panel.clear_all_cache()
    old_button = panel.clear_cache_btn
    panel.clear_cache_btn = QtWidgets.QPushButton('Current operation', panel)
    panel.clear_cache_btn.setEnabled(False)
    callbacks[0]()
    assert panel.clear_cache_btn.text() == 'Current operation'
    assert not panel.clear_cache_btn.isEnabled()
    assert old_button is not panel.clear_cache_btn


def test_reentrant_control_rebuild_during_event_pump_keeps_the_new_button(context, monkeypatch):
    panel, cleanup, callbacks, data, root = context

    def rebuild():
        panel.clear_cache_btn = QtWidgets.QPushButton('Current controls', panel)
        panel.clear_cache_btn.setEnabled(False)

    monkeypatch.setattr(QtWidgets.QApplication, 'processEvents', rebuild)
    panel.clear_all_cache()
    assert panel.clear_cache_btn.text() == 'Current controls'
    assert not panel.clear_cache_btn.isEnabled()
    assert not callbacks


@pytest.mark.parametrize('remove', ['button', 'panel'])
def test_restore_after_owner_or_control_deletion_is_discarded(context, remove):
    panel, cleanup, callbacks, data, root = context
    panel.clear_all_cache()
    if remove == 'button':
        sip.delete(panel.clear_cache_btn)
    else:
        sip.delete(panel)
    callbacks[0]()


def test_actual_cache_cleanup_reports_only_removed_bytes_and_keeps_user_data(context):
    panel, cleanup, callbacks, data, root = context
    payloads = {'config.json': b'{"profile":"keep"}', 'copy_history.json': b'[]',
                'translation_history.json': b'[]'}
    for name, content in payloads.items():
        (data / name).write_bytes(content)
    disposable = [data / 'cache' / 'result.json', data / 'logs' / 'log.txt',
                  root / 'temp' / 'part.bin', root / '__pycache__' / 'file.pyc']
    for path in disposable:
        assert path.resolve().is_relative_to(root.resolve())
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'cache')
    cleanup.side_effect = REAL_CLEAR
    panel.clear_all_cache()
    assert all(not path.exists() for path in disposable)
    for name, content in payloads.items():
        assert (data / name).read_bytes() == content
    assert panel.clear_cache_btn.text() == settings.settings_text('en', 'cleared').format(size='20 B')
