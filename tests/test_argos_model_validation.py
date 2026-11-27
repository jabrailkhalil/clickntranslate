"""Installation probes reject decoder loops without changing normal inference."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import component_argos_worker as worker


def runtime(translate, pairs=(('es', 'en'),)):
    packages = [SimpleNamespace(from_code=source, to_code=target) for source, target in pairs]
    languages = Mock(return_value=[])
    return SimpleNamespace(
        arg_pkg=SimpleNamespace(get_installed_packages=lambda: packages, settings=SimpleNamespace()),
        arg_tr=SimpleNamespace(get_installed_languages=languages),
        _ensure_argos_available=lambda: True,
        _invalidate_argos_cache=Mock(),
        _try_argos_translate_local=Mock(side_effect=translate),
    )


def test_spanish_probe_tests_meaningful_text_and_reuses_model_between_inputs():
    backend = runtime(Mock(side_effect=['Hello, world!', 'Today the weather is good.']))
    assert worker._validate_models(backend, ['es__en']) == ['es__en']
    calls = backend._try_argos_translate_local.call_args_list
    assert len(calls) == 2
    assert calls[0].args == ('Hola, mundo!', 'es', 'en')
    assert calls[1].args == ('Hoy hace buen tiempo.', 'es', 'en')
    assert all(call.kwargs == {'allow_install': False} for call in calls)
    backend._invalidate_argos_cache.assert_called_once_with()
    backend.arg_tr.get_installed_languages.cache_clear.assert_called_once_with()


@pytest.mark.parametrize('bad', [
    None, '', ' \n ', '... !!!',
    'mainstre' * 120,
    'mainstre ' * 120,
    'MainSTRE.\n' * 120,
    'The result: ' + 'mainstre' * 120 + ' @@',
    'x' * 5000,
])
def test_bad_new_model_is_not_approved_just_because_output_is_nonempty(bad):
    backend = runtime(lambda *_args, **_kwargs: bad)
    with pytest.raises(RuntimeError, match='Argos validation failed'):
        worker._validate_models(backend, ['es__en'])


def test_model_returning_one_canned_answer_for_different_sentences_is_rejected():
    backend = runtime(Mock(side_effect=['Mainstream', '  MAINSTREAM!\n']))
    with pytest.raises(RuntimeError, match='identical output'):
        worker._validate_models(backend, ['es__en'])
    assert backend._try_argos_translate_local.call_count == 2


@pytest.mark.parametrize('answers', [
    ('Hello, world!', 'Today the weather is good.'),
    ('مرحبا بالعالم!', 'الطقس جميل اليوم.'),
    ('Привет, мир!', 'Сегодня хорошая погода.'),
    ('こんにちは、世界！', '今日はいい天気です。'),
    ('Hello, hello, world!', 'The good weather makes today a good day.'),
])
def test_normal_wording_punctuation_rtl_and_scripts_remain_acceptable(answers):
    backend = runtime(Mock(side_effect=answers))
    assert worker._validate_models(backend, ['es__en']) == ['es__en']


def test_new_source_language_needs_samples_instead_of_numeric_fallback():
    backend = runtime(lambda *_args, **_kwargs: '12345', pairs=(('unknown', 'en'),))
    with pytest.raises(RuntimeError, match='No Argos validation samples'):
        worker._validate_models(backend, ['unknown__en'])
    backend._try_argos_translate_local.assert_not_called()


@pytest.mark.parametrize('pairs,expected', [
    ((('es', 'en'), ('es', 'en')), ['es__en']),
    ((('es', 'en'),), ['en__es']),
])
def test_duplicate_versions_and_mismatching_metadata_stop_before_translation(pairs, expected):
    backend = runtime(lambda *_args, **_kwargs: 'unused', pairs=pairs)
    with pytest.raises(RuntimeError, match='metadata does not match'):
        worker._validate_models(backend, expected)
    backend._try_argos_translate_local.assert_not_called()


def test_real_worker_entrypoint_runs_decoder_probes_before_reporting_success(tmp_path, monkeypatch, capsys):
    import sys
    import portable_paths
    backend = runtime(Mock(side_effect=['Hello, world!', 'Today the weather is good.']))
    monkeypatch.setitem(sys.modules, 'translater', backend)
    monkeypatch.setattr(portable_paths, 'portable_base_dir', portable_paths.portable_base_dir)
    request = tmp_path / 'request.json'
    request.write_text(json.dumps({'action': 'validate', 'directions': ['es__en'],
                                   'root_dir': str(tmp_path), 'work_dir': str(tmp_path)}))
    monkeypatch.setattr(worker.sys, 'argv', ['worker', str(request)])
    # Keep the worker's deliberately isolated process environment within this test.
    import os
    from unittest.mock import patch
    with patch.dict(os.environ):
        assert worker.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload['validated'] == ['es__en'] and not payload['error']
    assert backend._try_argos_translate_local.call_count == 2


def test_all_argos_runtime_recipes_include_the_validated_worker():
    root = Path(__file__).resolve().parents[1]
    recipes = [root / 'components/recipes/argos-windows-x64.json',
               *sorted((root / 'components/recipes/posix').glob('argos-*.json'))]
    assert len(recipes) == 4
    for recipe in recipes:
        assert 'component_argos_worker.py' in json.loads(recipe.read_bytes())['adapter_files']
