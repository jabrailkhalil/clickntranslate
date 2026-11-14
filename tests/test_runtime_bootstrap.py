import json
from pathlib import Path
import sys

import pytest

import runtime_bootstrap as bootstrap


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch):
    monkeypatch.setattr(bootstrap, '_INFO', None)


def test_normal_source_interpreter_does_not_load_or_change_dll_search_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, 'executable', str(tmp_path / 'python.exe'))
    monkeypatch.setattr(bootstrap.os, 'add_dll_directory', lambda *_: pytest.fail('Source GUI changed DLL paths'))
    assert bootstrap.activate() == {}


def test_frozen_application_retains_its_existing_runtime(monkeypatch, tmp_path):
    (tmp_path / 'COMPONENT.json').write_text(json.dumps({'component':'ocr.rapidocr'}))
    (tmp_path / 'python312._pth').write_text('.')
    monkeypatch.setattr(sys, 'executable', str(tmp_path / 'python.exe'))
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    assert bootstrap.activate() == {}


@pytest.mark.skipif(sys.platform != 'win32', reason='Private Windows loader')
def test_managed_runtime_rejects_missing_dll_instead_of_using_system_copy(monkeypatch, tmp_path):
    (tmp_path / 'COMPONENT.json').write_text(json.dumps({'component':'translation.argos'}))
    (tmp_path / 'python312._pth').write_text('.')
    monkeypatch.setattr(sys, 'executable', str(tmp_path / 'python.exe'))
    monkeypatch.setattr(bootstrap.os, 'add_dll_directory', lambda *_: None)
    with pytest.raises(RuntimeError, match='Private MSVC runtime is missing'):
        bootstrap.activate()
    with pytest.raises(RuntimeError, match='Private MSVC runtime is missing'):
        bootstrap.activate()  # a failed first attempt must not cache success
