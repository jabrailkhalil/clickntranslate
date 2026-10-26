"""Native lifecycle validation of one POSIX engine in an isolated profile."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

PROJECT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(PROJECT),str(PROJECT/'src'),str(PROJECT/'tools')]
from component_catalog import parse_catalog, runtime_command
from component_store import ComponentStore
from component_download import ComponentDownloader
import component_runtime as runtime
import component_easyocr as easy
import component_argos as argos
import component_hymt as hymt


def run(prepared,catalog_path,output):
    output.mkdir(parents=True);sys.argv[0]=str(output/'main.py')
    import portable_paths
    portable_paths.portable_base_dir=lambda:str(output)
    store=ComponentStore(output/'store')
    os.environ['CLICKNTRANSLATE_COMPONENTS_DIR']=str(store.root)
    os.environ['CLICKNTRANSLATE_COMPONENT_CHANNEL']='preview'
    catalog=parse_catalog(catalog_path.read_bytes());bundle=catalog['bundles'][0]
    engine=bundle['component'].split('.')[-1]
    description=json.loads((prepared/'runtime-artifact.json').read_bytes())
    downloads=[]
    def download(url,path):
        downloads.append(url)
        if url.endswith(description['filename']):shutil.copyfile(prepared/description['filename'],path)
        else:ComponentDownloader()(url,path)
    common=dict(root=store.root,channel='preview',catalog_loader=lambda _:catalog)
    def install(**kwargs):
        if engine=='rapidocr':return runtime.install_rapidocr(download,**common,**kwargs)
        if engine=='tesseract':return runtime.install_tesseract(download,**common,**kwargs)
        return {'easyocr':easy,'argos':argos,'hymt':hymt}[engine].install(download,**common,**kwargs)
    validators={'rapidocr':(runtime,'validate_rapidocr'),'tesseract':(runtime,'validate_tesseract'),
                'easyocr':(easy,'validate'),'argos':(argos,'validate'),'hymt':(hymt,'validate')}
    module,name=validators[engine];validate=getattr(module,name)
    kwargs={'tesseract':{'languages':['eng','rus','ara']},'easyocr':{'groups':bundle['languages']},
            'argos':{'pairs':[('en','ru'),('ru','en'),('en','ar'),('ar','en')]}}.get(engine,{})
    started=time.perf_counter();first=install(**kwargs)
    print('Installed and natively validated '+engine,flush=True)
    selected=first['receipt']['languages'];after=len(downloads)
    native_validation=validate(first['folder'],first['receipt'])
    newer=dict(bundle,id=bundle['id']+'-lifecycle-r2',revision=2);catalog['bundles'].append(newer)
    updated=install();assert updated['receipt']['languages']==selected and len(downloads)==after
    store.rollback(bundle['component'],validate,catalog)
    assert store.active(bundle['component'])['receipt']['revision']==1
    print('Update and rollback preserved selection without downloads.',flush=True)
    active=store.active(bundle['component'])
    # Cancel only after a real native process was spawned, and check it was reaped.
    children=[];real_popen=subprocess.Popen
    def observed(*args,**kwargs):
        child=real_popen(*args,**kwargs);children.append(child);return child
    def canceled():
        if children:raise InterruptedError('QA cancellation')
    subprocess.Popen=observed
    try:
        try:install(check_cancel=canceled)
        except InterruptedError:pass
        else:raise AssertionError('Cancellation ignored')
    finally:subprocess.Popen=real_popen
    assert children and all(child.poll() is not None for child in children)
    assert store.active(bundle['component'])['folder']==active['folder']
    print('Real child cancellation preserved the active generation.',flush=True)
    # Corrupt a staged recognizer after authenticated extraction; it must not activate.
    def invalid(folder,receipt,*args):
        if engine=='rapidocr':path=folder/'models/ppocrv5/en_PP-OCRv5_rec_mobile.onnx'
        elif engine=='tesseract':path=folder/'runtime/tessdata/ara.traineddata'
        elif engine=='easyocr':path=folder/'models/english_g2.pth'
        elif engine=='argos':path=next((folder/'models/en__ru').rglob('model.bin'))
        else:path=folder/receipt['model']
        path.write_bytes(b'invalid native model')
        return validate(folder,receipt,*args)
    setattr(module,name,invalid)
    try:
        try:install()
        except Exception as error:
            assert 'validation_failed' in str(error) or 'inference_failed' in str(error),str(error)
        else:raise AssertionError('Invalid model activated')
    finally:setattr(module,name,validate)
    assert store.active(bundle['component'])['folder']==active['folder']
    # Verify an actual recognition/translation request using the installed generation.
    samples=[]
    if engine in ('rapidocr','easyocr','tesseract'):
        from PIL import Image,ImageDraw
        from languages import easyocr_language_codes
        image=Image.new('RGB',(500,100),'white');ImageDraw.Draw(image).text((20,20),'TEST 123',fill='black',font_size=40)
        if engine=='tesseract':
            text=runtime.recognize_tesseract(image,active['command'][0],active['folder']/'runtime/tessdata','eng',6)
            assert text.strip();samples.append({'en':text})
        else:
            path=output/'probe.png';image.save(path)
            for code in ('en','ru','ar'):
                request=output/'request.json'
                request.write_text(json.dumps({'engine':engine,'root_dir':str(active['folder']),
                    'work_dir':str(output),'allow_download':False,'language_code':code,
                    'language_codes':easyocr_language_codes(code),'images':[{'path':str(path),'label':code}]}))
                child=subprocess.run([*runtime_command(active['folder'],active['receipt']),str(request)],
                    capture_output=True,text=True,timeout=180,env=runtime.worker_environment())
                result=json.loads(child.stdout)
                assert child.returncode==0 and not result.get('error'),result
                assert result['results'][0]['text'].strip(),result
                samples.append({code:result['results'][0]['text']})
    else:
        import translater
        for source,target,text in [('en','ru','Hello, world!'),('ru','en','Привет, мир!'),('en','ar','Hello, world!')]:
            result=(translater._try_argos_translate(text,source,target,allow_install=False) if engine=='argos'
                    else translater.hymt_translate(text,source,target))
            assert result and result.strip();samples.append({'source':source,'target':target,'result':result})
    def offline(*_):raise AssertionError('Deletion contacted the network')
    if engine=='easyocr':
        empty=easy.install(offline,root=store.root,remove_groups=selected,catalog_loader=offline)
        assert empty['receipt']['languages']==[] and install()['receipt']['languages']==[]
    elif engine=='tesseract':
        removed=runtime.install_tesseract(offline,root=store.root,remove_languages=['ara'],catalog_loader=offline)
        assert removed['receipt']['languages']==['eng','rus']
    elif engine=='argos':
        removed=argos.install(offline,root=store.root,remove_pairs=[('ar','en')],catalog_loader=offline)
        assert 'ar__en' not in removed['receipt']['languages']
    active=store.active(bundle['component'])
    with store.lease(active['receipt']['generation']):
        if engine=='hymt':hymt.remove(store.root)
        elif engine=='easyocr':easy.remove(store.root)
        else:store.remove(bundle['component'])
        assert store.active(bundle['component']) is None and active['folder'].exists()
    assert not active['folder'].exists()
    loaded=[name for name in ('torch','onnxruntime','ctranslate2','easyocr','cv2') if name in sys.modules]
    assert not loaded,loaded
    report={'engine':engine,'platform':runtime.current_platform() if hasattr(runtime,'current_platform') else __import__('component_catalog').current_platform(),
        'runtime_sha256':description['sha256'],'selected_languages':selected,'native_validation':native_validation,
        'update_preserves_selection':'passed','additional_update_downloads':len(downloads)-after,
        'rollback':'passed','native_cancellation_and_child_reaping':'passed','invalid_model_rejected':'passed',
        'offline_removal':'passed','generation_leases':'passed','native_modules_in_parent':loaded,
        'samples':samples,'application_build':False,'public_catalog':False,
        'seconds':round(time.perf_counter()-started,2)}
    (output/'verification.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('samples','native_validation')}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('prepared','catalog','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();output=a.output.resolve()
    if 'ClicknTranslate-QA' not in output.parts or output.exists():p.error('Use a fresh isolated QA directory')
    run(a.prepared,a.catalog,output)
