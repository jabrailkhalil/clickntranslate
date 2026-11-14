"""Local native child boundaries must not inherit unrelated credentials."""
import json
import os
import subprocess
from unittest import mock

import pytest

import component_runtime
import ocr
import platform_support
import translater


SECRETS = ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'GEMINI_API_KEY', 'DEEPL_API_KEY',
           'CLICKNTRANSLATE_UPDATE_TOKEN', 'GITHUB_TOKEN', 'GH_TOKEN')
INJECTION = ('LD_LIBRARY_PATH', 'LD_PRELOAD', 'LD_AUDIT', 'DYLD_LIBRARY_PATH',
             'DYLD_INSERT_LIBRARIES', 'PYTHONPATH', 'PYTHONHOME')


@pytest.mark.parametrize('engine', ['argos', 'ocr'])
@pytest.mark.parametrize('system', ['windows', 'linux', 'macos'])
def test_legacy_worker_invocation_scrubs_credentials_and_keeps_runtime_preferences(monkeypatch, tmp_path, engine, system):
    monkeypatch.setattr(platform_support, 'IS_WINDOWS', system == 'windows')
    monkeypatch.setattr(platform_support, 'IS_LINUX', system == 'linux')
    monkeypatch.setattr(platform_support, 'IS_MAC', system == 'macos')
    for key in (*SECRETS, *INJECTION):
        monkeypatch.setenv(key, 'audit-placeholder-only')
    preferences = {'OMP_NUM_THREADS': '2', 'ARGOS_PACKAGES_DIR': str(tmp_path / 'packages'),
                   'CLICKNTRANSLATE_RAPIDOCR_MODEL_DIR': str(tmp_path / 'verified-models'),
                   'XDG_DATA_HOME': str(tmp_path / 'xdg-data')}
    for key, value in preferences.items():
        monkeypatch.setenv(key, value)
    observed = {}
    def inspect(environment):
        # Record only these synthetic fields, never the inherited environment.
        observed['present_sensitive_names'] = sorted(key for key in (*SECRETS, *INJECTION) if key in environment)
        observed['preferences'] = {key: environment.get(key) for key in preferences}
    if engine == 'argos':
        def spawn(*_args, **kwargs):
            inspect(kwargs.get('env', os.environ))
            kwargs['stdout'].write(json.dumps({'packages': [], 'statuses': []}))
            kwargs['stdout'].flush()
            return mock.Mock(poll=mock.Mock(return_value=0), wait=mock.Mock(return_value=0))
        monkeypatch.setattr(translater, '_argos_worker_path', lambda: 'qa-no-execution.exe')
        monkeypatch.setattr(translater.subprocess, 'Popen', spawn)
        assert translater._run_argos_worker_request_inner({'action': 'catalog'})['packages'] == []
    else:
        def run(command, **kwargs):
            inspect(kwargs.get('env', os.environ))
            return subprocess.CompletedProcess(command, 0, '{}', '')
        monkeypatch.setattr(component_runtime, 'managed_runtime', lambda _engine: None)
        monkeypatch.setattr(ocr, '_native_ocr_worker_command', lambda: ['qa-no-execution.exe'])
        monkeypatch.setattr(ocr.subprocess, 'run', run)
        assert ocr._call_native_ocr_worker({'action': 'recognize', 'engine': 'rapidocr'}) == {}
    assert observed['present_sensitive_names'] == []
    assert observed['preferences'] == preferences
    assert all(os.environ[key] == 'audit-placeholder-only' for key in (*SECRETS, *INJECTION))


def test_managed_workers_keep_their_approved_model_directory(monkeypatch):
    monkeypatch.setenv('CLICKNTRANSLATE_RAPIDOCR_MODEL_DIR', 'audit-external-model-path')
    assert 'CLICKNTRANSLATE_RAPIDOCR_MODEL_DIR' not in component_runtime.worker_environment()
