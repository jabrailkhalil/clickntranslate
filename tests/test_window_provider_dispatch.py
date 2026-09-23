"""Exercise the real translation dispatcher for every local window provider."""
from types import SimpleNamespace
from unittest import mock

import pytest

from test_ui_polish import app, owner, workspaces  # shared isolated Qt fixtures


PROVIDERS = (
    ('google', 'google_translate'),
    ('mymemory', 'mymemory_translate'),
    ('lingva', 'lingva_translate'),
    ('libretranslate', 'libretranslate'),
    ('argos', '_try_argos_translate'),
    ('hymt', 'hymt_translate'),
)


@pytest.mark.parametrize('key,function_name', PROVIDERS)
def test_window_selection_reaches_exact_backend(workspaces, owner, monkeypatch, key, function_name):
    import translater
    cache = SimpleNamespace(get=mock.Mock(return_value=None), save=mock.Mock())
    monkeypatch.setattr(translater, '_TranslationCache', lambda *args: cache)
    calls = {}
    for provider_key, name in PROVIDERS:
        calls[name] = mock.Mock(return_value='Result from ' + provider_key)
        monkeypatch.setattr(translater, name, calls[name])
    monkeypatch.setattr(translater, 'argos_runtime_available', lambda: True)
    dialog, _, jobs = workspaces
    dialog.engine_combo.setCurrentIndex(dialog.engine_combo.findData(key))
    if not jobs:  # The initial provider is already selected.
        dialog.translate_button.click()
    jobs.pop()()
    assert dialog.text_edit.toPlainText() == 'Result from ' + key
    for name, call in calls.items():
        assert call.call_count == (1 if name == function_name else 0)
    assert owner.config['translator_engine'] == 'Lingva'
    assert cache.save.call_args.args[-1] == key
    if key == 'argos':
        assert calls[function_name].call_args.kwargs['allow_install'] is False
