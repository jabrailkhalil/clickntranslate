"""Describe exact EasyOCR CPU runtime/model ZIPs without approving publication."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from component_catalog import parse_catalog
from easyocr_models import LANGUAGE_GROUPS, MODEL_FILES, PROBE_CODES, SDK_ALIASES


def prepare(runtime, models):
    artifacts={runtime['sha256']:{'size':runtime['size'],'unpacked_size':runtime['unpacked_size'],
        'urls':['https://github.com/jabrailkhalil/clickntranslate-components/releases/download/'
                'easyocr-windows-x64-r1/'+runtime['filename']]}}
    files=[{'sha256':runtime['sha256'],'kind':'zip','destination':'runtime'}]
    language_files={}
    for model in models['artifacts']:
        artifacts[model['sha256']]={'size':model['size'],'unpacked_size':model['unpacked_size'],'urls':[model['url']]}
        item={'sha256':model['sha256'],'kind':'zip_member','member':model['member'],
              'destination':'models/'+model['filename']}
        if model['group']=='craft':files.append(item)
        else:language_files[model['group']]=[item]
    return parse_catalog(json.dumps({'schema':1,'revision':6,'artifacts':artifacts,'bundles':[
        {'id':'easyocr-windows-x64-r1','component':'ocr.easyocr','revision':1,'contract':2,
         'channel':'preview','os':'windows','arch':'x86_64','min_os':'10','app':'>=1.8.2,<2',
         'python':'runtime/python.exe','worker':'runtime/adapter/ocr_worker.py',
         'upstream':'EasyOCR 1.7.2 / Torch 2.14.1 CPU / torchvision 0.29.1 CPU',
         'languages':sorted(language_files),'language_files':language_files,'files':files,
         'language_groups':LANGUAGE_GROUPS,'model_files':MODEL_FILES,'probe_codes':PROBE_CODES,
         'sdk_codes':SDK_ALIASES,'sdk_source_commit':models['source_commit'],
         'validation':{'standalone_windows':False,'frozen_application':False,'macos':False,'linux':False},
         'redistribution_review':False}]}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('runtime','models','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    args.output.write_text(json.dumps(prepare(json.loads(args.runtime.read_bytes()),
        json.loads(args.models.read_bytes())),indent=2)+'\n',encoding='utf-8')
