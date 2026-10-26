"""Describe a prepared Argos runtime and exact model bytes; never approves them."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from component_argos import direction_id
from component_catalog import parse_catalog


def prepare(runtime, models):
    release = 'https://github.com/jabrailkhalil/clickntranslate-components/releases/download/argos-windows-x64-r1/'
    artifacts = {runtime['sha256']:{'size':runtime['size'], 'unpacked_size':runtime['unpacked_size'],
                                  'urls':[release + runtime['filename']]}}
    languages, versions = {}, {}
    for model in models['artifacts']:
        metadata = model['metadata']
        code = direction_id((metadata['from_code'], metadata['to_code']))
        artifacts[model['sha256']] = {'size':model['size'], 'unpacked_size':model['unpacked_size'],
                                      'urls':[model['url']]}
        languages[code] = [{'sha256':model['sha256'], 'kind':'zip', 'destination':'models/' + code}]
        versions[code] = metadata['package_version']
    return parse_catalog(json.dumps({'schema':1, 'revision':4, 'artifacts':artifacts,
        'bundles':[{'id':'argos-windows-x64-r1', 'component':'translation.argos', 'revision':1,
            'contract':1, 'channel':'preview', 'os':'windows', 'arch':'x86_64', 'min_os':'10',
            'app':'>=1.8.2,<2', 'upstream':'1.11.0', 'backend':'CTranslate2 4.8.2 CPU',
            'python':'runtime/python.exe', 'worker':'runtime/adapter/component_argos_worker.py',
            'languages':sorted(languages), 'language_files':languages, 'model_versions':versions,
            'model_index':'argosopentech/argospm-index@' + models['index_commit'],
            'files':[{'sha256':runtime['sha256'], 'kind':'zip', 'destination':'runtime'}],
            'validation':{'standalone_windows':False, 'frozen_application':False,
                          'macos':False, 'linux':False},
            'notes':'Initial preview directions: English, Russian and Arabic. Other engines and directions are unchanged.'}]}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--models', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(prepare(json.loads(args.runtime.read_bytes()),
        json.loads(args.models.read_bytes())), indent=2) + '\n', encoding='utf-8')
