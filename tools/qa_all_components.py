"""Exercise five approved local candidates together, without network or app builds."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import time

PROJECT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(PROJECT),str(PROJECT/'src')]
from component_catalog import parse_catalog
from component_store import ComponentStore
import component_runtime as runtime
import component_easyocr as easy
import component_argos as argos
import component_hymt as hymt


def run(plan,output):
    sys.argv[0]=str(output/'main.py')
    os.environ['CLICKNTRANSLATE_COMPONENTS_DIR']=str(output/'store')
    os.environ['CLICKNTRANSLATE_COMPONENT_CHANNEL']='preview'
    description=json.loads(plan.read_bytes())
    catalog=parse_catalog(json.dumps(description['catalog']))
    objects={sha:Path(path) for sha,path in description['objects'].items()}
    store=ComponentStore(output/'store');downloads=[];snapshots={};results={}
    def download(url,path):
        sha=next(sha for sha,artifact in catalog['artifacts'].items() if url in artifact['urls'])
        downloads.append(sha);shutil.copyfile(objects[sha],path)
    common=dict(root=store.root,channel='preview',catalog_loader=lambda _:catalog)
    calls=[('ocr.rapidocr',lambda:runtime.install_rapidocr(download,**common)),
           ('ocr.tesseract',lambda:runtime.install_tesseract(download,languages=['eng','rus','ara'],**common)),
           ('ocr.easyocr',lambda:easy.install(download,groups=['english_g2','cyrillic_g2','arabic'],**common)),
           ('translation.argos',lambda:argos.install(download,pairs=[('en','ru'),('ru','en'),('en','ar'),('ar','en')],**common)),
           ('translation.hymt',lambda:hymt.install(download,**common))]
    started=time.perf_counter()
    for component,install in calls:
        installed=install();snapshots[component]=installed['receipt']['generation']
        for name,generation in snapshots.items():
            assert store.active(name)['receipt']['generation']==generation
        print('Native installation validated: '+component,flush=True)
    import ocr,translater
    from languages import easyocr_language_codes
    from PIL import Image
    for code in ('en','ru','ar'):
        with Image.open(Path(description['images'])/(code+'.png')) as opened:image=opened.convert('RGB')
        for engine in ('rapidocr','easyocr'):
            result=ocr._call_native_ocr_worker({'engine':engine,'language_code':code,
                'language_codes':easyocr_language_codes(code),'allow_download':False},[(code,image)])['results'][0]
            assert result['text'].strip() and not result.get('error')
            results[engine+'-'+code]=result['text']
        tess=store.active('ocr.tesseract')
        result=ocr._run_tesseract_ocr_image_with_cmd(image,tess['command'][0],
            {'en':'eng','ru':'rus','ar':'ara'}[code],'combined-components',code,join_paragraphs=True)
        assert result.strip();results['tesseract-'+code]=result
    for code in ('ru','ar'):
        result=translater._try_argos_translate('Hello, world!','en',code,allow_install=False)
        assert result and result.strip();results['argos-'+code]=result
        result=translater.hymt_translate('Hello, world!','en',code)
        assert result and result.strip();results['hymt-'+code]=result
    loaded=[name for name in ('torch','torchvision','easyocr','cv2','ctranslate2','sentencepiece','onnxruntime') if name in sys.modules]
    assert not loaded,loaded
    before=len(downloads)
    current=next(b for b in catalog['bundles'] if b['component']==easy.COMPONENT)
    catalog['bundles'].append(dict(current,id='easyocr-combined-update',revision=current['revision']+1))
    rapid=store.active('ocr.rapidocr')
    with store.lease(rapid['receipt']['generation']):
        updated=easy.install(download,**common)
        assert updated['receipt']['languages']==['arabic','cyrillic_g2','english_g2']
        assert len(downloads)==before
        easy.remove(store.root)
        assert rapid['folder'].is_dir()
    for name,generation in snapshots.items():
        if name!=easy.COMPONENT:assert store.active(name)['receipt']['generation']==generation
    with Image.open(Path(description['images'])/'en.png') as opened:image=opened.convert('RGB')
    again=ocr._call_native_ocr_worker({'engine':'rapidocr','language_code':'en'},[('en',image)])
    assert not again.get('error') and again['results'][0]['text'].strip()
    report={'components':list(snapshots),'native_recognition_and_translation':results,
        'engine_isolation':'passed','update_and_remove_do_not_change_other_generations':'passed',
        'additional_model_downloads_on_update':len(downloads)-before,'native_modules_in_parent':loaded,
        'artifact_downloads':len(downloads),'seconds':round(time.perf_counter()-started,2),
        'catalog_source':'explicit local candidates, not public approval',
        'application_build':False,'foreground_windows':False}
    (output/'verification.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({key:value for key,value in report.items() if key!='native_recognition_and_translation'}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();output=args.output.resolve()
    if 'ClicknTranslate-QA' not in output.parts or output.exists():parser.error('Use a fresh ClicknTranslate-QA directory')
    output.mkdir(parents=True);run(args.plan,output)
