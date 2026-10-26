"""Native CPU EasyOCR validation and transactional lifecycle in an isolated profile."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

PROJECT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PROJECT), str(PROJECT/'src'), str(PROJECT/'tools')]
import component_easyocr as easy
from component_catalog import ComponentError, parse_catalog
from component_store import ComponentStore


def run(catalog_path, runtime, models, output):
    sys.argv[0] = str(output/'main.py')
    os.environ['CLICKNTRANSLATE_COMPONENTS_DIR'] = str(output/'store')
    os.environ['CLICKNTRANSLATE_COMPONENT_CHANNEL'] = 'preview'
    catalog = parse_catalog(catalog_path.read_bytes())
    store = ComponentStore(output/'store')
    sources = json.loads((models/'model-artifacts.json').read_bytes())
    files = {item['sha256']:models/'archives'/(item['group']+'.zip') for item in sources['artifacts']}
    with runtime.open('rb') as stream:
        runtime_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
    files[runtime_hash] = runtime
    downloads = []
    def download(url, destination):
        sha = next(sha for sha, item in catalog['artifacts'].items() if url in item['urls'])
        downloads.append(sha)
        shutil.copyfile(files[sha], destination)
    def install(**kwargs):
        return easy.install(download, root=store.root, channel='preview',
                            catalog_loader=lambda _:catalog, **kwargs)
    started = time.perf_counter()
    first = install(groups=['english_g2','cyrillic_g2','arabic'])
    print('Initial CPU runtime and EN/RU/AR models validated.',flush=True)
    assert len(downloads) == 5  # one runtime, detector and three shared recognizers
    all_groups = catalog['bundles'][0]['languages']
    installed = install(groups=all_groups)
    print('All 14 model families installed and validated.',flush=True)
    assert len(downloads) == 16
    validation = easy.validate(installed['folder'], installed['receipt'])
    assert set(validation['validated']) == set(all_groups)
    assert validation['cuda'] is None and '+cpu' in validation['torch']
    assert validation['dll_runtime'] == dict.fromkeys(
        ('msvcp140.dll','msvcp140_1.dll','msvcp140_2.dll'), 'bundled')
    from component_catalog import runtime_command
    from component_runtime import worker_environment
    from easyocr_models import installed_languages
    from languages import LANGUAGES
    from languages import easyocr_language_codes
    from PIL import Image, ImageDraw, ImageFont, features
    # QA image generation handles both Pillow builds, including Windows builds
    # without RAQM. These helper packages are not application dependencies.
    fonts = Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'
    samples = [('en','Hello world 123','arial.ttf'),
               ('ru','Привет мир 123','arial.ttf'),
               ('ar','مرحبا بالعالم','arial.ttf'),
               ('ta','தமிழ் மொழி','Nirmala.ttc')]
    recognition = []
    for code, text, name in samples:
        image = Image.new('RGB',(900,150),'white')
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype(str(fonts/name),52)
        rendered=text
        options={}
        if code=='ar':
            if features.check_feature('raqm'):options['direction']='rtl'
            else:
                import arabic_reshaper
                from bidi.algorithm import get_display
                rendered=get_display(arabic_reshaper.reshape(text))
        draw.text((35,35),rendered,font=font,fill='black',**options)
        image.save(output/(code+'.png'))
        request=output/'recognition-request.json'
        request.write_text(json.dumps({'engine':'easyocr','root_dir':str(installed['folder']),
            'language_codes':easyocr_language_codes(code),'allow_download':False,'work_dir':str(output),
            'images':[{'path':str(output/(code+'.png')),'label':code}]}),encoding='utf-8')
        child=subprocess.run([*runtime_command(installed['folder'],installed['receipt']),str(request)],
            capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180,
            env=worker_environment(),creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        response=json.loads(child.stdout)
        assert child.returncode==0 and not response.get('error'),response
        result=response['results'][0]
        assert not result.get('error') and result.get('text') and result.get('items'), result
        if code=='en':assert 'hello' in result['text'].lower() and '123' in result['text']
        if code=='ru':assert 'привет' in result['text'].lower()
        if code=='ar':assert any('\u0600'<=c<='\u06ff' for c in result['text'])
        if code=='ta':assert any('\u0b80'<=c<='\u0bff' for c in result['text'])
        recognition.append({'language':code,'source':text,'result':result['text'],
                            'boxes':result['boxes_count'],'confidence':result['confidence']})
    print('EN/RU/AR/Tamil recognition through the private worker passed.',flush=True)
    assert {'ar','ru','en','ta','bn','id'}.issubset(installed_languages(installed['folder'],[item.code for item in LANGUAGES]))
    native_in_parent = [name for name in ('torch','torchvision','easyocr','cv2') if name in sys.modules]
    assert not native_in_parent, native_in_parent
    # A controlled profile revision exercises updates; the SDK bytes remain identical.
    newer = dict(catalog['bundles'][0],id='easyocr-lifecycle-r2',revision=2)
    catalog['bundles'].append(newer)
    updated = install()
    assert set(updated['receipt']['languages']) == set(all_groups) and len(downloads)==16
    store.rollback(easy.COMPONENT,easy.validate,catalog)
    assert store.active(easy.COMPONENT)['receipt']['revision']==1
    active = store.active(easy.COMPONENT)
    # Exercise cancellation after the real private interpreter has been spawned.
    real_popen = easy.subprocess.Popen
    children = []
    def observed(*args,**kwargs):
        child = real_popen(*args,**kwargs);children.append(child);return child
    def cancel():
        if children:raise InterruptedError('QA cancel')
    easy.subprocess.Popen = observed
    try:
        try:install(check_cancel=cancel)
        except InterruptedError:pass
        else:raise AssertionError('Native validator ignored cancellation')
    finally:easy.subprocess.Popen = real_popen
    assert children and all(child.poll() is not None for child in children)
    assert store.active(easy.COMPONENT)['folder']==active['folder']
    # Reject a corrupted staged model before activation, keeping the working generation.
    real_validate = easy.validate
    def bad_model(folder,receipt,check_cancel=lambda:None):
        (folder/'models/english_g2.pth').write_bytes(b'not a checkpoint')
        return real_validate(folder,receipt,check_cancel)
    easy.validate = bad_model
    try:
        try:install()
        except ComponentError as error:assert error.code=='validation_failed'
        else:raise AssertionError('Corrupted model was activated')
    finally:easy.validate = real_validate
    assert store.active(easy.COMPONENT)['folder']==active['folder']
    def offline(*_):raise AssertionError('Model removal contacted a server')
    empty = easy.install(offline,root=store.root,remove_groups=all_groups,catalog_loader=offline)
    assert empty['receipt']['languages']==[]
    assert install()['receipt']['languages']==[]  # no unexpected English default on update
    store.rollback(easy.COMPONENT,easy.validate,catalog)
    # Removal respects readers and cannot resurrect the preserved legacy SDK.
    active = store.active(easy.COMPONENT)
    with store.lease(active['receipt']['generation']):
        easy.remove(store.root)
        assert store.active(easy.COMPONENT) is None and active['folder'].exists()
    assert not active['folder'].exists() and easy.legacy_disabled(store.root)
    report = {'runtime_sha256':runtime_hash,'all_model_groups':all_groups,
        'native_validation':validation,'recognition':recognition,
        'artifact_downloads':len(downloads),'update_additional_downloads':len(downloads)-16,
        'model_addition':'passed','selected_groups_preserved':'passed','rollback':'passed',
        'native_cancellation_and_child_reaping':'passed','invalid_checkpoint_rejected':'passed',
        'offline_remove_all':'passed','empty_selection_preserved':'passed',
        'generation_leases_and_removal':'passed','legacy_resurrection_blocked':'passed',
        'native_modules_in_parent':native_in_parent,'controlled_revision_same_sdk_bytes':True,
        'seconds':round(time.perf_counter()-started,2),'application_build':False}
    (output/'verification.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({key:value for key,value in report.items() if key!='recognition'}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('catalog','runtime','models','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();output=args.output.resolve()
    if 'ClicknTranslate-QA' not in output.parts or output.exists():
        parser.error('Use a fresh directory below ClicknTranslate-QA')
    output.mkdir(parents=True)
    run(args.catalog,args.runtime,args.models,output)
