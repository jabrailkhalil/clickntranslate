import copy
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

import pytest

import component_argos as argos
import component_catalog
from component_catalog import ComponentError, parse_catalog
from component_store import ComponentStore


@pytest.fixture
def installation(tmp_path, monkeypatch):
    monkeypatch.setattr(component_catalog, 'current_platform', lambda: {
        'os':'windows', 'arch':'x86_64', 'os_version':'10'})
    monkeypatch.delenv('CLICKNTRANSLATE_ARGOS_WORKER', raising=False)
    root = tmp_path / 'store'
    monkeypatch.setenv('CLICKNTRANSLATE_COMPONENTS_DIR', str(root))
    objects, artifacts, language_files = {}, {}, {}
    def artifact(name, contents):
        archive = tmp_path / name
        with zipfile.ZipFile(archive, 'w') as output:
            for path, value in contents.items():
                output.writestr(path, value)
        sha = hashlib.sha256(archive.read_bytes()).hexdigest()
        objects[sha] = archive
        artifacts[sha] = {'size':archive.stat().st_size, 'unpacked_size':10000,
                          'urls':['https://example.org/' + sha]}
        return sha
    runtime = artifact('runtime.zip', {'python.exe':'runtime fixture', 'adapter/worker.py':'adapter fixture'})
    for source, target in (('en','ru'), ('ru','en'), ('en','ar'), ('ar','en')):
        tag = argos.direction_id((source, target))
        sha = artifact(tag + '.zip', {'package/metadata.json':json.dumps({'from_code':source, 'to_code':target}),
                                     'package/model/model.bin':'model fixture'})
        language_files[tag] = [{'sha256':sha, 'kind':'zip', 'destination':'models/' + tag}]
    bundle = {'id':'argos-r1', 'component':argos.COMPONENT, 'revision':1, 'contract':1,
        'channel':'preview', 'os':'windows', 'arch':'x86_64', 'min_os':'10', 'app':'>=1.8.2,<2',
        'python':'runtime/python.exe', 'worker':'runtime/adapter/worker.py',
        'languages':list(language_files), 'language_files':language_files,
        'files':[{'sha256':runtime, 'kind':'zip', 'destination':'runtime'}]}
    catalog = parse_catalog(json.dumps({'schema':1, 'revision':4, 'artifacts':artifacts, 'bundles':[bundle]}))
    downloads = []
    def download(url, destination):
        downloads.append(url)
        shutil.copyfile(objects[url.rsplit('/',1)[1]], destination)
    def validate(folder, receipt, check_cancel=lambda: None):
        for tag in receipt['languages']:
            assert json.loads((folder / ('models/' + tag + '/package/metadata.json')).read_bytes()) == dict(
                zip(('from_code','to_code'), argos.direction_pair(tag)))
    monkeypatch.setattr(argos, 'validate', validate)
    def install(**kwargs):
        return argos.install(download, root=root, channel='preview', catalog_loader=lambda _:catalog, **kwargs)
    return root, catalog, downloads, install


def test_runtime_update_preserves_directions_and_needs_no_repeat_download(installation):
    root, catalog, downloads, install = installation
    old = install(pairs=[('en','ru')])
    assert old['receipt']['languages'] == ['en__ru'] and len(downloads) == 2
    new = copy.deepcopy(catalog['bundles'][0])
    new.update(id='argos-r2', revision=2)
    catalog['bundles'].append(new)
    updated = install()
    assert updated['receipt']['revision'] == 2 and updated['receipt']['languages'] == ['en__ru']
    assert len(downloads) == 2
    ComponentStore(root).rollback(argos.COMPONENT, argos.validate, catalog)
    assert ComponentStore(root).active(argos.COMPONENT)['receipt']['revision'] == 1


def test_remove_direction_offline_without_catalog_or_download(installation):
    root, _, downloads, install = installation
    install(pairs=[('en','ru'), ('ru','en')])
    before = len(downloads)
    def unavailable(*_):
        pytest.fail('Pure removal must not contact metadata or artifact servers')
    result = argos.install(unavailable, root=root, remove_pairs=[('en','ru')], catalog_loader=unavailable)
    assert result['receipt']['languages'] == ['ru__en']
    assert len(downloads) == before


def test_cached_rows_remain_available_offline_after_direction_removal(installation):
    root, _, _, install = installation
    install(pairs=[('en','ru'), ('ru','en')])
    def unavailable(*_):
        pytest.fail('Cached UI rows must not fetch a catalog')
    argos.install(unavailable, root=root, remove_pairs=[('ru','en')], catalog_loader=unavailable)
    rows = argos.catalog_rows(root=root, refresh=False, catalog_loader=unavailable)
    assert len(rows) == 4
    assert {(row['source_code'],row['target_code']) for row in rows if row['installed']} == {('en','ru')}
    assert all(row['available'] for row in rows)


def test_model_changes_preserve_old_generation_during_translation(installation, monkeypatch):
    root, _, _, install = installation
    old = install(pairs=[('en','ru')])
    import translater
    monkeypatch.setattr(translater, '_ensure_argos_available', lambda: pytest.fail('Native SDK imported in parent'))
    assert translater.preload_argos_runtime()
    assert translater.argos_unavailable_reason() == ''
    assert translater.argos_installed_direct_pairs_fast() == {('en','ru')}
    assert translater.argos_pair_installed('en','ru')
    def translate(*args):
        runtime = args[-1]
        assert runtime['receipt']['generation'] == old['receipt']['generation']
        ComponentStore(root).remove(argos.COMPONENT)
        assert old['folder'].is_dir()
        return {'result':'Привет'}
    monkeypatch.setattr(translater, '_run_argos_worker_request_inner', translate)
    assert translater._run_argos_worker_request({'action':'translate'})['result'] == 'Привет'
    assert not old['folder'].exists()


def test_unsupported_legacy_direction_is_not_silently_dropped(installation):
    root, _, _, install = installation
    with pytest.raises(ComponentError, match='no_compatible_update'):
        install(legacy_pairs=[('fr','de')])
    assert ComponentStore(root).active(argos.COMPONENT) is None


def test_invalid_model_keeps_working_direction(installation, monkeypatch):
    root, _, _, install = installation
    old = install(pairs=[('en','ru')])
    def fail(*_):
        raise ComponentError('validation_failed')
    monkeypatch.setattr(argos, 'validate', fail)
    with pytest.raises(ComponentError, match='validation_failed'):
        install(pairs=[('en','ar')])
    assert ComponentStore(root).active(argos.COMPONENT)['folder'] == old['folder']


@pytest.mark.parametrize('pair', [('', 'en'), ('en','en'), ('../ru','en'), ('en__ru','ar'), ('en',)])
def test_invalid_direction_is_rejected(pair):
    with pytest.raises(ComponentError):
        argos.direction_id(pair)


def test_managed_adapter_rejects_installation_and_catalog_network_actions(tmp_path, monkeypatch):
    import component_argos_worker
    request = tmp_path / 'request.json'
    request.write_text(json.dumps({'root_dir':str(tmp_path), 'action':'install_packages'}))
    monkeypatch.setattr(component_argos_worker.sys, 'argv', ['worker', str(request)])
    with pytest.raises(ValueError, match='does not modify models'):
        component_argos_worker.main()


def test_managed_adapter_ignores_inherited_remote_provider_setting(tmp_path, monkeypatch, capsys):
    import os
    import sys
    from types import SimpleNamespace
    from unittest.mock import patch
    import component_argos_worker
    checked = []
    def load():
        checked.append(os.environ['ARGOS_MODEL_PROVIDER'])
        return True
    fake = SimpleNamespace(_ensure_argos_available=load,
        arg_pkg=SimpleNamespace(settings=SimpleNamespace(), get_installed_packages=lambda:[]),
        _invalidate_argos_cache=lambda:None)
    monkeypatch.setitem(sys.modules, 'translater', fake)
    request = tmp_path / 'request.json'
    request.write_text(json.dumps({'root_dir':str(tmp_path), 'action':'validate', 'directions':[]}))
    monkeypatch.setattr(component_argos_worker.sys, 'argv', ['worker', str(request)])
    with patch.dict(os.environ, {'ARGOS_MODEL_PROVIDER':'OPENAI'}):
        assert component_argos_worker.main() == 0
        assert os.environ['ARGOS_MODEL_PROVIDER'] == 'OPENNMT'
    assert checked == ['OPENNMT']
    assert json.loads(capsys.readouterr().out)['validated'] == []
