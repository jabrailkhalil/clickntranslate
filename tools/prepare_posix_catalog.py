"""Describe portable native candidates using the existing pinned model plans."""
import argparse
import copy
import json
from pathlib import Path
import sys
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'src'),str(Path(__file__).resolve().parent)]
from component_catalog import parse_catalog


def describe(runtime_path,recipes):
    runtime=json.loads(runtime_path.read_bytes());recipe=runtime['recipe'];engine=recipe['engine']
    if engine=='rapidocr':
        from component_catalog_recipe import initial_catalog
        catalog=initial_catalog(runtime_path,7)
    elif engine=='easyocr':
        from prepare_easyocr_catalog import prepare
        catalog=prepare(runtime,json.loads((recipes/'easyocr-windows-models.json').read_bytes()))
    elif engine=='argos':
        from prepare_argos_catalog import prepare
        catalog=prepare(runtime,json.loads((recipes/'argos-windows-models.json').read_bytes()))
    elif engine=='tesseract':
        catalog=json.loads((recipes/'posix/tesseract-model-plan.json').read_bytes())
    else:
        from prepare_hymt_component import describe as describe_hymt
        original=json.loads((recipes/'hymt-windows-x64.json').read_bytes())
        catalog=describe_hymt(dict(runtime,recipe=original))
    bundle=catalog['bundles'][0]
    release=engine+'-'+recipe['profile']+'-r1'
    artifact={'size':runtime['size'],'unpacked_size':runtime['unpacked_size'],
        'urls':['https://github.com/jabrailkhalil/clickntranslate-components/releases/download/'+release+'/'+runtime['filename']]}
    catalog['artifacts'][runtime['sha256']]=artifact
    # Tesseract's shared plan has no runtime; all other helpers supplied this file.
    if engine=='tesseract':bundle['files'].insert(0,{'kind':'zip','sha256':runtime['sha256'],'destination':'runtime'})
    bundle.update(id=release,contract=3,os=recipe['os'],arch=recipe['arch'],min_os=recipe['min_os'],
                  app=recipe['app'],channel='preview',revision=1,redistribution_review=False)
    if recipe.get('libc'):bundle['libc']=recipe['libc']
    if engine in ('tesseract','hymt'):
        bundle['runtime']='native'
        bundle['executable']='runtime/bin/'+('tesseract' if engine=='tesseract' else 'llama-cli')
        if engine=='tesseract':
            bundle['version_prefix']='tesseract '+recipe['version']
            bundle['upstream']=recipe['version']+' source build'
    else:
        bundle['isolated_python']=True
        bundle['python']='runtime/python/bin/python3.12'
        bundle['worker']='runtime/python/lib/python3.12/site-packages/'+('component_argos_worker.py' if engine=='argos' else 'ocr_worker.py')
    bundle['validation']={'native_candidate':False,'frozen_application':False}
    catalog['revision']=7
    return parse_catalog(json.dumps(catalog))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('runtime','recipes','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();a.output.write_text(json.dumps(describe(a.runtime,a.recipes),indent=2)+'\n')
