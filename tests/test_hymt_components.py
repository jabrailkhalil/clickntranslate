import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

import pytest

import component_catalog
import component_hymt as hymt
from component_catalog import ComponentError, parse_catalog
from component_store import ComponentStore


@pytest.fixture
def installation(tmp_path, monkeypatch):
    monkeypatch.setattr(component_catalog, 'current_platform', lambda: {
        'os':'windows','arch':'x86_64','os_version':'10'})
    monkeypatch.setenv('CLICKNTRANSLATE_COMPONENTS_DIR',str(tmp_path/'store'))
    artifacts, objects = {}, {}
    for name, data in [('runtime.zip',None),('model.gguf',b'GGUF model fixture')]:
        path=tmp_path/name
        if data is None:
            with zipfile.ZipFile(path,'w') as archive:archive.writestr('llama-cli.exe','native fixture')
        else:path.write_bytes(data)
        sha=hashlib.sha256(path.read_bytes()).hexdigest();objects[sha]=path
        artifacts[sha]={'size':path.stat().st_size,'urls':['https://example.org/'+sha],'unpacked_size':4096}
    runtime,model=objects
    bundle={'id':'hymt-r1','component':hymt.COMPONENT,'revision':1,'contract':1,'channel':'preview',
        'os':'windows','arch':'x86_64','min_os':'10','app':'>=1.8.2,<2','runtime':'native',
        'executable':'runtime/llama-cli.exe','model':'models/model.gguf','runner_build':'9048',
        'languages':['en','ru','ar'],'files':[{'sha256':runtime,'kind':'zip','destination':'runtime'},
        {'sha256':model,'kind':'file','destination':'models/model.gguf'}]}
    catalog=parse_catalog(json.dumps({'schema':1,'revision':5,'artifacts':artifacts,'bundles':[bundle]}))
    def validate(folder,receipt,check_cancel=lambda:None):
        check_cancel();assert (folder/'models/model.gguf').read_bytes().startswith(b'GGUF')
    monkeypatch.setattr(hymt,'validate',validate)
    downloads=[]
    def download(url,destination):
        downloads.append(url);shutil.copyfile(objects[url.rsplit('/',1)[1]],destination)
    def install(**kwargs):
        return hymt.install(download,root=tmp_path/'store',channel='preview',catalog_loader=lambda _:catalog,**kwargs)
    return ComponentStore(tmp_path/'store'),catalog,objects,downloads,install


def test_update_preserves_model_and_rollback_reuses_objects(installation):
    store,catalog,_,downloads,install=installation
    first=install();assert len(downloads)==2
    catalog['bundles'].append(dict(catalog['bundles'][0],id='hymt-r2',revision=2))
    updated=install();assert updated['folder']!=first['folder'] and len(downloads)==2
    store.rollback(hymt.COMPONENT,hymt.validate,catalog)
    assert store.active(hymt.COMPONENT)['folder']==first['folder']


def test_legacy_model_is_verified_and_reused_without_modifying_original(installation):
    _,_,objects,downloads,install=installation
    source=next(p for p in objects.values() if p.suffix=='.gguf');before=source.read_bytes()
    install(legacy_model=source)
    assert len(downloads)==1 and source.read_bytes()==before


def test_custom_legacy_model_is_not_silently_replaced(installation,tmp_path):
    store,_,_,downloads,install=installation
    custom=tmp_path/'custom.gguf';custom.write_bytes(b'GGUF custom model')
    with pytest.raises(ComponentError,match='custom_model_not_approved'):install(legacy_model=custom)
    assert store.active(hymt.COMPONENT) is None and not downloads
    assert custom.read_bytes()==b'GGUF custom model'


def test_validation_failure_preserves_active_generation(installation,monkeypatch):
    store,catalog,_,_,install=installation
    active=install();catalog['bundles'].append(dict(catalog['bundles'][0],id='hymt-bad',revision=2))
    def reject(*_):raise ComponentError('validation_failed')
    monkeypatch.setattr(hymt,'validate',reject)
    with pytest.raises(ComponentError,match='validation_failed'):install()
    assert store.active(hymt.COMPONENT)['folder']==active['folder']


def test_real_child_is_killed_and_reaped_on_cancellation(tmp_path,monkeypatch):
    children=[];original=subprocess.Popen
    def spawn(*args,**kwargs):
        child=original(*args,**kwargs);children.append(child);return child
    monkeypatch.setattr(hymt.subprocess,'Popen',spawn)
    def cancel():
        if children:raise InterruptedError('Cancel active inference')
    with pytest.raises(InterruptedError):
        hymt._run([sys.executable,'-c','import time; time.sleep(60)'],
                  cwd=tmp_path,check_cancel=cancel,timeout=90)
    assert len(children)==1 and children[0].poll() is not None


def test_managed_cli_does_not_inherit_argument_overrides(tmp_path,monkeypatch):
    monkeypatch.setenv('LLAMA_ARG_MODEL','unrelated-model.gguf')
    monkeypatch.setenv('OPENAI_API_KEY','test-only-secret')
    command=[sys.executable,'-c',
        'import os,json; print(json.dumps({k:v for k,v in os.environ.items() if k.startswith("LLAMA_ARG_") or k=="OPENAI_API_KEY"}))']
    result=hymt._run(command,cwd=tmp_path,check_cancel=lambda:None,timeout=10)
    assert result.returncode==0 and json.loads(result.stdout)=={}


def test_new_runtime_uses_a_separate_translation_cache_identity(installation):
    _,catalog,_,_,install=installation
    old=install();first=hymt.cache_identity(old['receipt'])
    assert hymt.cache_identity(dict(old['receipt'],generation='different-uuid'))==first
    changed=copy.deepcopy(catalog['bundles'][0]);changed['files'][0]['sha256']='a'*64
    assert hymt.cache_identity(changed)!=first


def test_all_chunks_pin_one_generation_and_cleanup_waits_for_last_chunk(installation,monkeypatch):
    import translater
    store,catalog,_,_,install=installation
    first=install();seen=[]
    cache=translater._TranslationCache('en','ru',config={})
    cache.data_dir=None
    def translate(folder,receipt,text,*_,**kwargs):
        seen.append(folder)
        if len(seen)==1:
            for revision in (2,3):
                catalog['bundles'].append(dict(catalog['bundles'][0],id=f'hymt-r{revision}',revision=revision))
                install()
        assert first['folder'].is_dir()
        return 'result'
    monkeypatch.setattr(hymt,'translate',translate)
    result=translater.hymt_translate('A sentence. '*240,'en','ru',_cache=cache)
    assert result and len(seen)>1 and set(seen)=={first['folder']}
    assert not first['folder'].exists()
    assert cache._bound_engine_key('hymt')==hymt.cache_identity(first['receipt'])


def test_chinese_to_indonesian_uses_the_correct_target_name():
    from translater import _build_hymt_prompt
    prompt=_build_hymt_prompt('你好','zh','id')
    assert '印尼语' in prompt and '英语' not in prompt


@pytest.mark.parametrize('locale',('en','ru','es','de','fr','zh','pt','it','ar','tr','hi','id'))
def test_custom_model_migration_warning_is_localized(locale):
    from component_texts import CUSTOM_MODEL, error_text
    error=ComponentError('custom_model_not_approved')
    assert error_text(locale,error)==CUSTOM_MODEL[locale]
    assert 'Hy-MT' in error_text(locale,error)


def test_uninstall_waits_for_workers_and_does_not_resurrect_preserved_legacy(installation,tmp_path,monkeypatch):
    import translater
    store,_,_,_,install=installation
    active=install()
    legacy=tmp_path/'legacy';legacy.mkdir()
    model=legacy/translater.HYMT_MODEL_FILE;runner=legacy/'llama-cli.exe'
    model.write_bytes(b'GGUF legacy model');runner.write_bytes(b'legacy executable')
    monkeypatch.setattr(translater,'_local_hymt_dir',lambda:str(legacy))
    monkeypatch.setattr(translater,'_hymt_runtime_cache',{'model':str(model),'runner':str(runner)})
    with store.lease(active['receipt']['generation']):
        hymt.remove(store.root)
        assert active['folder'].exists() and not translater.hymt_installed()
    assert not active['folder'].exists()
    assert model.read_bytes()==b'GGUF legacy model' and runner.is_file()
    assert hymt.legacy_disabled(store.root)
    assert install()['folder'].exists() and translater.hymt_installed()
