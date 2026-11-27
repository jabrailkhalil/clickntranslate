import copy
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

import pytest

import component_catalog
import component_easyocr as easy
from component_catalog import ComponentError, parse_catalog, choose_bundle
from component_store import ComponentStore
from easyocr_models import MODEL_FILES, group_for_language


@pytest.fixture
def installation(tmp_path, monkeypatch):
    monkeypatch.setenv('CLICKNTRANSLATE_COMPONENTS_DIR',str(tmp_path/'store'))
    monkeypatch.setattr(component_catalog,'current_platform',lambda: {
        'os':'windows','arch':'x86_64','os_version':'10'})
    objects,artifacts,language_files={},{},{}
    def archive(name,files):
        path=tmp_path/(name+'.zip')
        with zipfile.ZipFile(path,'w') as z:
            for member,data in files.items():z.writestr(member,data)
        sha=hashlib.sha256(path.read_bytes()).hexdigest();objects[sha]=path
        artifacts[sha]={'size':path.stat().st_size,'unpacked_size':8192,'urls':['https://example.org/'+sha]}
        return sha
    runtime=archive('runtime',{'python.exe':'private fixture','adapter/worker.py':'worker'})
    craft=archive('craft',{'craft_mlt_25k.pth':'detector'})
    for group in ('english_g2','cyrillic_g2','latin_g2','arabic','tamil'):
        filename=MODEL_FILES[group];sha=archive(group,{'nested/'+filename:group})
        language_files[group]=[{'sha256':sha,'kind':'zip_member','member':'nested/'+filename,'destination':'models/'+filename}]
    bundle={'id':'easy-r1','component':easy.COMPONENT,'revision':1,'contract':2,'channel':'preview',
        'os':'windows','arch':'x86_64','min_os':'10','app':'>=1.8.2,<2','python':'runtime/python.exe',
        'worker':'runtime/adapter/worker.py','languages':list(language_files),'language_files':language_files,
        'language_groups':{'en':'english_g2','ru':'cyrillic_g2','fr':'latin_g2','de':'latin_g2','id':'latin_g2','ar':'arabic','ta':'tamil'},
        'model_files':{g:MODEL_FILES[g] for g in language_files},
        'files':[{'sha256':runtime,'kind':'zip','destination':'runtime'},
                 {'sha256':craft,'kind':'zip_member','member':'craft_mlt_25k.pth','destination':'models/craft_mlt_25k.pth'}]}
    catalog=parse_catalog(json.dumps({'schema':1,'revision':6,'artifacts':artifacts,'bundles':[bundle]}))
    downloads=[]
    def download(url,destination):
        downloads.append(url);shutil.copyfile(objects[url.rsplit('/',1)[1]],destination)
    def validate(folder,receipt,check_cancel=lambda:None):
        check_cancel()
        for group in receipt['languages']:
            path=folder/'models'/MODEL_FILES[group]
            if not path.is_file() or path.read_text()!=group:
                raise ComponentError('validation_failed',group)
    monkeypatch.setattr(easy,'validate',validate)
    def install(**kwargs):
        return easy.install(download,root=tmp_path/'store',channel='preview',catalog_loader=lambda _:catalog,**kwargs)
    return ComponentStore(tmp_path/'store'),catalog,objects,downloads,install


def test_shared_models_are_downloaded_once_and_original_archives_are_reused(installation):
    import ocr
    store,catalog,_,downloads,install=installation
    first=install(groups=['latin_g2','arabic'])
    assert len(downloads)==4
    assert {'de','fr','id','ar'}.issubset(ocr._easyocr_installed_language_codes())
    again=install(groups=['latin_g2'])
    assert again['folder']==first['folder'] and len(downloads)==4
    newer=dict(catalog['bundles'][0],id='easy-r2',revision=2)
    catalog['bundles'].append(newer);updated=install()
    assert updated['folder']!=first['folder'] and updated['receipt']['languages']==['arabic','latin_g2']
    assert len(downloads)==4
    store.rollback(easy.COMPONENT,easy.validate,catalog)
    assert store.active(easy.COMPONENT)['folder']==first['folder']
    assert not list(first['folder'].glob('.unpack_*'))


def test_remove_all_groups_works_offline_and_update_does_not_restore_defaults(installation):
    store,_,_,_,install=installation
    install(groups=['cyrillic_g2','english_g2'])
    def offline(*_):pytest.fail('Model removal contacted a server')
    result=easy.install(offline,root=store.root,remove_groups=['cyrillic_g2','english_g2'],catalog_loader=offline)
    assert result['receipt']['languages']==[] and (result['folder']/'models/craft_mlt_25k.pth').is_file()
    assert install()['receipt']['languages']==[]


def test_repair_missing_interpreter_preserves_the_saved_group_selection(installation):
    store,_,_,downloads,install=installation
    old=install(groups=['arabic','cyrillic_g2'])
    (old['folder']/'runtime/python.exe').unlink()
    with pytest.raises(ComponentError):store.active(easy.COMPONENT)
    assert store.describe(easy.COMPONENT)['receipt']['languages']==['arabic','cyrillic_g2']
    repaired=install()
    assert repaired['receipt']['languages']==['arabic','cyrillic_g2']
    assert (repaired['folder']/'runtime/python.exe').is_file() and len(downloads)==4


def test_repair_identical_bundle_rebuilds_a_corrupted_model_from_verified_cache(installation):
    store,_,_,downloads,install=installation
    old=install(groups=['english_g2'])
    (old['folder']/'models/english_g2.pth').write_text('corrupted')
    repaired=install()
    assert repaired['folder']!=old['folder']
    assert (repaired['folder']/'models/english_g2.pth').read_text()=='english_g2' and len(downloads)==3
    with pytest.raises(ComponentError,match='no_previous_version'):
        store.rollback(easy.COMPONENT,easy.validate,{'bundles':[]})


def test_cancellation_during_member_extraction_cleans_temp_paths_and_keeps_active(installation):
    store,_,_,_,install=installation
    old=install()
    def cancel():
        if any((store.root/'generations').glob('*/.unpack_*')):
            raise InterruptedError('Canceled archive member extraction')
    with pytest.raises(InterruptedError):install(groups=['arabic'],check_cancel=cancel)
    assert store.active(easy.COMPONENT)['folder']==old['folder']
    assert not list((store.root/'generations').glob('*/.unpack_*'))


def test_declared_member_must_exist_and_cannot_escape_the_archive(installation):
    store,catalog,_,_,install=installation
    old=install()
    item=catalog['bundles'][0]['language_files']['arabic'][0]
    item['member']='missing.pth'
    with pytest.raises(ComponentError,match='unsafe_archive'):install(groups=['arabic'])
    assert store.active(easy.COMPONENT)['folder']==old['folder']
    item['member']='../escape.pth'
    with pytest.raises(ComponentError,match='invalid_path'):parse_catalog(json.dumps(catalog))


def test_old_clients_skip_contract_two_profiles_and_keep_using_contract_one(installation,monkeypatch):
    _,catalog,_,_,_=installation
    older=copy.deepcopy(catalog['bundles'][0]);older.update(id='legacy-contract',component='ocr.rapidocr',contract=1)
    older['files']=older['files'][:1];older.pop('language_files');catalog['bundles'].append(older)
    monkeypatch.setattr(component_catalog,'CONTRACT',1)
    loaded=parse_catalog(json.dumps(catalog))
    assert choose_bundle(loaded,'ocr.rapidocr','1.8.2',channel='preview')['id']=='legacy-contract'
    with pytest.raises(ComponentError,match='no_compatible_update'):
        choose_bundle(loaded,easy.COMPONENT,'1.8.2',channel='preview')


def test_indonesian_and_extended_languages_use_the_actual_vendor_model_families():
    from languages import easyocr_language_codes
    assert group_for_language('id')=='latin_g2'
    assert group_for_language('bn')=='bengali'
    assert group_for_language('ta')=='tamil'
    assert easyocr_language_codes('sr')==['rs_cyrillic','en']


def test_tamil_alphabet_matches_the_released_checkpoint():
    from easyocr_models import TAMIL_ALPHABET_FIX
    assert len(TAMIL_ALPHABET_FIX['characters'])==142
    assert TAMIL_ALPHABET_FIX['model_md5']=='4b93972fdacdcdabe6d57097025d4dc2'
