"""Inject interrupted writes without touching the user's files."""
import json
from types import SimpleNamespace
from unittest import mock

import pytest

import document_storage
import atomic_storage
import main


@pytest.fixture
def interrupted_json(monkeypatch):
    def broken_encoder(self, value, *args, **kwargs):
        yield '{"partial":'
        raise OSError('simulated disk full')
    monkeypatch.setattr(json.JSONEncoder, 'iterencode', broken_encoder)


def test_failed_session_save_preserves_previous_document(tmp_path, interrupted_json):
    path = tmp_path / 'session.json'
    previous = b'{"original_text":"keep this draft","translated_text":"saved"}'
    path.write_bytes(previous)
    with pytest.raises(OSError, match='disk full'):
        document_storage.save_session(path, {'translated_text': 'replacement'})
    assert path.read_bytes() == previous
    assert list(tmp_path.iterdir()) == [path]


def test_failed_settings_save_preserves_previous_configuration(tmp_path, monkeypatch, interrupted_json):
    path = tmp_path / 'config.json'
    previous = b'{"theme":"dark","translator_engine":"Lingva"}'
    path.write_bytes(previous)
    monkeypatch.setattr(main, 'get_data_file', lambda name: str(path))
    window = SimpleNamespace(
        _capture_main_translation_languages=lambda: None, config={},
        current_theme='light', current_interface_language='en',
    )
    with pytest.raises(OSError, match='disk full'):
        main.DarkThemeApp.save_config(window)
    assert path.read_bytes() == previous
    assert list(tmp_path.iterdir()) == [path]


def test_invalid_session_value_does_not_truncate_previous_file(tmp_path):
    path = tmp_path / 'session.json'
    document_storage.save_session(path, {'translated_text': 'saved'})
    previous = path.read_bytes()
    with pytest.raises(TypeError):
        document_storage.save_session(path, {'invalid': object()})
    assert path.read_bytes() == previous


@pytest.mark.parametrize('operation', ['fsync', 'replace'])
@pytest.mark.parametrize('existing', [False, True])
def test_disk_failure_never_publishes_partial_text(tmp_path, monkeypatch, operation, existing):
    path = tmp_path / 'translation.txt'
    if existing:
        path.write_text('previous translation', encoding='utf-8')
    def fail(*args):
        raise PermissionError('simulated locked file')
    monkeypatch.setattr(atomic_storage.os, operation, fail)
    with pytest.raises(PermissionError, match='locked file'):
        document_storage.save_text(path, 'replacement' * 10000)
    assert path.exists() == existing
    assert sorted(tmp_path.iterdir()) == ([path] if existing else [])
    if existing:
        assert path.read_text(encoding='utf-8') == 'previous translation'
