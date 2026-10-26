import copy
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest import mock
import pytest

from component_catalog import ComponentError,choose_bundle,parse_catalog,runtime_command
import component_catalog as catalog_module
import component_runtime as runtime
from test_component_updates import fixture_catalog


@pytest.mark.parametrize('libc,version,compatible',[('glibc','2.35',True),('glibc','2.39',True),
    ('glibc','2.34',False),('musl','1.2.5',False),('','0',False)])
def test_linux_abi_constraints_are_checked_before_download(tmp_path,libc,version,compatible):
    catalog,_=fixture_catalog(tmp_path);bundle=catalog['bundles'][0]
    bundle.update(contract=3,os='linux',min_os='5.15',libc={'name':'glibc','min':'2.35'},isolated_python=True)
    target=dict(os='linux',arch='x86_64',os_version='6.8',libc=libc,libc_version=version)
    catalog=parse_catalog(json.dumps(catalog))
    if compatible:assert choose_bundle(catalog,'ocr.rapidocr','1.8.2',channel='preview',target=target)==bundle
    else:
        with pytest.raises(ComponentError,match='no_compatible_update'):
            choose_bundle(catalog,'ocr.rapidocr','1.8.2',channel='preview',target=target)


def test_isolated_python_argv_is_explicit_and_older_contracts_are_rejected(tmp_path):
    py=tmp_path/'python';worker=tmp_path/'worker.py';py.touch();worker.touch()
    assert runtime_command(tmp_path,{'python':'python','worker':'worker.py','isolated_python':True})==[str(py),'-I',str(worker)]
    catalog,_=fixture_catalog(tmp_path);catalog['bundles'][0]['isolated_python']=True
    with pytest.raises(ComponentError,match='requires contract 3'):parse_catalog(json.dumps(catalog))


def test_old_clients_skip_posix_contract_and_keep_existing_windows_updates(tmp_path,monkeypatch):
    catalog,_=fixture_catalog(tmp_path);posix=dict(catalog['bundles'][0],id='linux-private',contract=3,os='linux')
    catalog['bundles'].append(posix);monkeypatch.setattr(catalog_module,'CONTRACT',2)
    loaded=parse_catalog(json.dumps(catalog))
    assert choose_bundle(loaded,'ocr.rapidocr','1.8.2',channel='preview',target={'os':'windows','arch':'x86_64','os_version':'10'})['contract']==1


def test_private_workers_drop_inherited_library_injection(monkeypatch):
    for name in ('LD_PRELOAD','LD_LIBRARY_PATH','DYLD_LIBRARY_PATH','DYLD_INSERT_LIBRARIES'):
        monkeypatch.setenv(name,'external-app-library')
    env=runtime.worker_environment()
    assert not any(name in env for name in ('LD_PRELOAD','LD_LIBRARY_PATH','DYLD_LIBRARY_PATH','DYLD_INSERT_LIBRARIES'))


def test_cancellable_native_runner_reaps_a_real_child(monkeypatch):
    children=[];popen=subprocess.Popen
    def observed(*args,**kwargs):
        child=popen(*args,**kwargs);children.append(child);return child
    def cancel():
        if children:raise InterruptedError('test cancellation')
    monkeypatch.setattr(subprocess,'Popen',observed)
    with pytest.raises(InterruptedError):
        runtime.run_cancellable([sys.executable,'-c','import time; time.sleep(30)'],timeout=10,check_cancel=cancel,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    assert children and all(child.poll() is not None for child in children)
