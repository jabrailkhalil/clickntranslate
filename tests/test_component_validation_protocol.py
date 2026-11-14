"""Health validation requires an affirmative worker acknowledgement before activation."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from component_catalog import ComponentError
import component_runtime as runtime
from component_store import ComponentStore
from test_component_updates import fixture_catalog


@pytest.fixture
def validator(tmp_path, monkeypatch):
    script = tmp_path / 'validation standin.py'
    original_spawn = subprocess.Popen
    original_temporary = runtime.tempfile.TemporaryDirectory
    environment = {name: os.environ[name] for name in ('SYSTEMROOT', 'SystemRoot', 'WINDIR') if name in os.environ}
    environment.update(PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1',
                       TEMP=str(tmp_path), TMP=str(tmp_path))
    for name in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS',
                 'VECLIB_MAXIMUM_THREADS', 'BLIS_NUM_THREADS', 'NUMBA_NUM_THREADS'):
        environment[name] = '1'
    children = []
    def spawn(*args, **kwargs):
        kwargs['creationflags'] = kwargs.get('creationflags', 0) | getattr(subprocess, 'BELOW_NORMAL_PRIORITY_CLASS', 0)
        child = original_spawn(*args, **kwargs)
        children.append(child)
        return child
    def temporary(*args, **kwargs):
        kwargs.setdefault('dir', tmp_path)
        return original_temporary(*args, **kwargs)
    monkeypatch.setattr(runtime.subprocess, 'Popen', spawn)
    monkeypatch.setattr(runtime.tempfile, 'TemporaryDirectory', temporary)
    monkeypatch.setattr(runtime, 'worker_environment', lambda: environment)
    monkeypatch.setattr(runtime, 'runtime_command', lambda *_: [sys.executable, str(script)])
    def configure(payload, exitcode=0):
        script.write_text('import json,sys\nfrom pathlib import Path\n'
            'request=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))\n'
            'assert request["action"]=="validate" and request["engine"]=="rapidocr"\n'
            'assert request["allow_download"] is False\n'
            f'sys.stdout.write({json.dumps(payload)!r})\n'
            f'raise SystemExit({exitcode})\n', encoding='utf-8')
        return runtime.validate_rapidocr
    try:
        yield configure
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=5)


@pytest.mark.parametrize('payload', [None, [], {}, {'available': False}, {'available': None},
                                   {'available': 1}, {'available': 'true'}],
                         ids=['null', 'array', 'missing', 'unavailable', 'unknown', 'integer', 'text'])
def test_zero_exit_without_an_affirmative_validation_ack_is_rejected(validator, tmp_path, payload):
    validate = validator(payload)
    with pytest.raises(ComponentError, match='validation_failed'):
        validate(tmp_path, {})


@pytest.mark.parametrize('payload', [{'available': True}, {'available': True, 'error': '', 'dll_runtime': 'fixture'}])
def test_affirmative_validation_ack_remains_accepted(validator, tmp_path, payload):
    assert validator(payload)(tmp_path, {}) == payload


@pytest.mark.parametrize('payload', [
    {'available': True, 'error': 'controlled worker failure'},
    {'available': False, 'error': 'controlled worker failure'},
    {'error': 'controlled worker failure'},
])
def test_explicit_worker_failure_still_rejects_validation(validator, tmp_path, payload):
    with pytest.raises(ComponentError, match='controlled worker failure'):
        validator(payload)(tmp_path, {})


def test_nonzero_worker_exit_still_rejects_an_affirmative_ack(validator, tmp_path):
    with pytest.raises(ComponentError, match='worker exit'):
        validator({'available': True, 'error': ''}, exitcode=5)(tmp_path, {})


def test_unavailable_worker_cannot_replace_an_active_generation(validator, tmp_path):
    catalog, archive = fixture_catalog(tmp_path)
    store = ComponentStore(tmp_path / 'store')
    download = lambda _, target: shutil.copyfile(archive, target)
    with store.lock():
        first = store.install(catalog, catalog['bundles'][0], download, lambda *_: None)
        original_receipt = (first['folder'] / 'receipt.json').read_bytes()
        newer = dict(catalog['bundles'][0], id='rapidocr-r2', revision=2)
        failure = None
        try:
            store.install(catalog, newer, download, validator({'available': False, 'error': ''}))
        except ComponentError as error:
            failure = error
        assert store.active('ocr.rapidocr')['receipt']['revision'] == 1
        assert failure is not None and failure.code == 'validation_failed'
        assert (first['folder'] / 'receipt.json').read_bytes() == original_receipt
