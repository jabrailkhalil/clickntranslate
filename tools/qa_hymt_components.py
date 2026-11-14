"""Compare native Hy-MT candidates and test their isolated update lifecycle."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

PROJECT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(PROJECT),str(PROJECT/'src')]
sys.path.insert(0,str(PROJECT/'tools'))
import component_hymt as hymt
from component_catalog import ComponentError, parse_catalog
from component_store import ComponentStore


def run(old,new,model,docs,output):
    sys.argv[0]=str(output/'main.py')
    os.environ['CLICKNTRANSLATE_COMPONENTS_DIR']=str(output/'store')
    os.environ['CLICKNTRANSLATE_COMPONENT_CHANNEL']='preview'
    catalog=parse_catalog((old/'catalog-candidate.json').read_bytes())
    newer=parse_catalog((new/'catalog-candidate.json').read_bytes())
    assert newer['bundles'][0]['revision']>catalog['bundles'][0]['revision']
    files={}
    for path in (old,new):
        description=json.loads((path/'runtime-artifact.json').read_bytes())
        files[description['filename']]=path/description['filename']
    files.update({path.name:path for path in docs.iterdir() if path.is_file()})
    downloads=[]
    def download(url,destination):
        downloads.append(url)
        name=url.rsplit('/',1)[1].split('?',1)[0]
        if name.endswith('.gguf') and name!='invalid.gguf':raise AssertionError('A verified legacy/cached model was downloaded again')
        shutil.copyfile(files[name],destination)
    store=ComponentStore(output/'store')
    def install(**kwargs):
        return hymt.install(download,root=store.root,channel='preview',catalog_loader=lambda _:catalog,**kwargs)
    started=time.perf_counter()
    first=install(legacy_model=model)
    assert len(downloads)==3
    import translater
    cases=[('en','ru','You have found a hidden room.\n\nReturn to the village before nightfall.'),
           ('ru','en','Вы нашли тайную комнату.\n\nВернитесь в деревню до наступления ночи.'),
           ('en','ar','You have found a hidden room.\n\nReturn to the village before nightfall.'),
           ('zh','id','你好，世界！')]
    comparison=[]
    private_runtime_modules={}
    def translate_cases(label):
        from qa_windows_modules import private_modules
        original=subprocess.Popen
        def observed(command,**kwargs):
            process=original(command,**kwargs)
            try:
                deadline=time.monotonic()+5
                checked=False
                while process.poll() is None and time.monotonic()<deadline:
                    modules=private_modules(process,Path(command[0]).parent)
                    if 'llama.dll' in modules and any(name.startswith('ggml-cpu') for name in modules):
                        private_runtime_modules[label]=modules
                        checked=True
                        break
                    time.sleep(.01)
                assert checked,'Could not verify private native modules'
            except BaseException:
                if process.poll() is None:process.kill()
                process.wait(timeout=10)
                raise
            return process
        hymt.subprocess.Popen=observed
        try:
            for source,target,text in cases:
                before=time.perf_counter();result=translater.hymt_translate(text,source,target)
                assert result and result!=text
                if target=='ar':assert any('\u0600'<=c<='\u06ff' for c in result)
                if target=='ru':assert any('А'<=c<='я' for c in result)
                comparison.append({'runtime':label,'source':source,'target':target,'text':text,'result':result,
                                   'seconds':round(time.perf_counter()-before,2)})
        finally:hymt.subprocess.Popen=original
    translate_cases(first['receipt']['runner_build'])
    catalog['artifacts'].update(newer['artifacts']);catalog['bundles'].extend(newer['bundles'])
    current=install()
    assert len(downloads)==4  # only the runner changed; GGUF/docs reuse verified objects
    translate_cases(current['receipt']['runner_build'])
    store.rollback(hymt.COMPONENT,hymt.validate,catalog)
    assert store.active(hymt.COMPONENT)['receipt']['runner_build']==first['receipt']['runner_build']
    current=install();assert len(downloads)==4
    active=store.active(hymt.COMPONENT)
    # Cancel a real model-loading process, not a mocked validator callback.
    original=subprocess.Popen;children=[]
    def spawn(command,**kwargs):
        process=original(command,**kwargs)
        if '-m' in command:children.append(process)
        return process
    hymt.subprocess.Popen=spawn
    def cancel():
        if children:raise InterruptedError('QA cancel native process')
    candidate=copy.deepcopy(newer['bundles'][0]);candidate.update(id='hymt-cancel-qa',revision=3)
    catalog['bundles'].append(candidate)
    try:
        try:install(check_cancel=cancel)
        except InterruptedError:pass
        else:raise AssertionError('Validator cancellation was ignored')
        assert children and all(child.poll() is not None for child in children)
        assert store.active(hymt.COMPONENT)['folder']==active['folder']
        children.clear()
        try:translater.hymt_translate('Hello, world!','en','ru',cancel_callback=lambda:bool(children))
        except translater.TranslationCancelledError:pass
        else:raise AssertionError('Translation cancellation was ignored')
        assert children and all(child.poll() is not None for child in children)
    finally:hymt.subprocess.Popen=original
    bad=b'GGUF invalid QA model'
    bad_sha=hashlib.sha256(bad).hexdigest();bad_file=output/'invalid.gguf';bad_file.write_bytes(bad)
    files['invalid.gguf']=bad_file
    catalog['artifacts'][bad_sha]={'size':len(bad),'urls':['https://example.org/invalid.gguf']}
    rejected=copy.deepcopy(newer['bundles'][0]);rejected.update(id='hymt-invalid-model-qa',revision=4)
    for item in rejected['files']:
        if item['destination']==rejected['model']:item['sha256']=bad_sha
    catalog['bundles'].append(rejected)
    try:install()
    except ComponentError as error:assert error.code in ('validation_failed','inference_failed')
    else:raise AssertionError('A broken model was activated')
    assert store.active(hymt.COMPONENT)['folder']==active['folder']
    with store.lease(active['receipt']['generation']):
        hymt.remove(store.root)
        assert active['folder'].exists() and not translater.hymt_installed()
    assert not active['folder'].exists() and hymt.legacy_disabled(store.root)
    # No cloud/SDK modules enter the source application's parent process.
    loaded=[name for name in ('torch','onnxruntime','llama_cpp','ctranslate2') if name in sys.modules]
    assert not loaded,loaded
    report={'application_build':False,'public_catalog':False,'runtime_source':'local candidates',
        'old_runtime':first['receipt']['runner_build'],'new_runtime':current['receipt']['runner_build'],
        'model_sha256':newer['bundles'][0]['files'][1]['sha256'],
        'model_downloads_during_update':0,'artifact_downloads':len(downloads),
        'legacy_model_reuse':'passed','native_update':'passed','rollback':'passed',
        'validator_cancellation_and_reaping':'passed','translation_cancellation_and_reaping':'passed',
        'invalid_model_preserves_active':'passed','native_modules_in_parent':loaded,
        'offline_removal_waits_for_worker':'passed','private_runtime_modules':private_runtime_modules,
        'runtime_sha256':current['receipt']['files'][0]['sha256'],
        'comparison':comparison,'seconds':round(time.perf_counter()-started,2)}
    (output/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({key:value for key,value in report.items() if key!='comparison'}))


if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('old','new','model','docs','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();output=args.output.resolve()
    if output.exists() or 'ClicknTranslate-QA' not in output.parts:parser.error('Use a fresh ClicknTranslate-QA directory')
    output.mkdir(parents=True)
    run(args.old,args.new,args.model,args.docs,output)
