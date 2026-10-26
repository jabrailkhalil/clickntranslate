"""Describe exact prepared artifacts; this command never signs or approves them."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from component_catalog import parse_catalog
from rapidocr_models import BASE_URL, MODEL_ASSETS, LANGUAGE_MODELS


def initial_catalog(runtime_path, revision, runtime_revision=1):
    runtime = json.loads(runtime_path.read_text(encoding='utf-8'))
    recipe = runtime['recipe']
    artifacts = {runtime['sha256']: {key: runtime[key] for key in ('size', 'unpacked_size')}}
    artifacts[runtime['sha256']]['urls'] = [
        'https://github.com/jabrailkhalil/clickntranslate-components/releases/download/'
        f'rapidocr-windows-x64-r{runtime_revision}/' + runtime['filename']]
    files = [{'sha256': runtime['sha256'], 'kind': 'zip', 'destination': 'runtime'}]
    for relative, size, digest in MODEL_ASSETS.values():
        artifacts[digest] = {'size': size, 'urls': [BASE_URL + relative]}
        files.append({'sha256': digest, 'kind': 'file',
                      'destination': 'models/ppocrv5/' + Path(relative).name})
    catalog = {'schema': 1, 'revision': revision, 'artifacts': artifacts,
        'bundles': [{'id': f'rapidocr-windows-x64-ppocrv5-r{runtime_revision}', 'component': 'ocr.rapidocr',
            'revision': runtime_revision, 'upstream': '3.10.0', 'models': 'PP-OCRv5 mobile',
            'contract': 1, 'channel': 'preview', 'os': 'windows', 'arch': 'x86_64',
            'min_os': recipe['min_os'], 'app': recipe['app'],
            'python': 'runtime/python.exe', 'worker': 'runtime/adapter/ocr_worker.py',
            'languages': sorted(LANGUAGE_MODELS), 'files': files,
            'validation': {'standalone_windows': False, 'frozen_application': False,
                           'macos': False, 'linux': False}}]}
    return parse_catalog(json.dumps(catalog))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--revision', type=int, default=1)
    parser.add_argument('--runtime-revision', type=int, default=1)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.runtime_revision < 1 or args.revision < 1:
        parser.error('Revisions must be positive')
    args.output.write_text(json.dumps(initial_catalog(args.runtime, args.revision, args.runtime_revision), indent=2)+'\n', encoding='utf-8', newline='\n')
