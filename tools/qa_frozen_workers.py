"""Run packaged RapidOCR and Argos against generated input in isolated data."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    package, output = args.package.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    suffix = '.exe' if sys.platform == 'win32' else ''
    candidates = (package / 'app/_internal', package / '_internal', package / 'Contents/MacOS')
    internal = next(path for path in candidates if (path / ('OcrWorker' + suffix)).is_file())
    env = dict(os.environ, OMP_NUM_THREADS='2')
    for name in ('XDG_DATA_HOME', 'XDG_CACHE_HOME', 'XDG_CONFIG_HOME'):
        env[name] = str(output / name.lower())

    font = next((path for path in (
        Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts/arial.ttf',
        Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
        Path('/System/Library/Fonts/Supplemental/Arial.ttf'),
    ) if path.is_file()), None)
    image = Image.new('RGB', (720, 150), 'white')
    ImageDraw.Draw(image).text((30, 40), 'HELLO WORLD', fill='black',
                              font=ImageFont.truetype(str(font), 48) if font else ImageFont.load_default(size=48))
    fixture = output / 'fixture.png'
    image.save(fixture)

    report = {}
    for name, request in (
        ('OcrWorker', {'engine': 'rapidocr', 'root_dir': str(output / 'ocr'),
                       'images': [{'label': 'generated', 'path': str(fixture)}]}),
        ('ArgosWorker', {'action': 'probe', 'source_code': 'en', 'target_code': 'ru'}),
    ):
        request_file = output / (name + '-request.json')
        request_file.write_text(json.dumps(request), encoding='utf-8')
        result = subprocess.run([str(internal / (name + suffix)), str(request_file)],
                                cwd=output, env=env, capture_output=True, text=True,
                                encoding='utf-8', errors='replace', timeout=120,
                                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
        (output / (name + '.stderr.log')).write_text(result.stderr, encoding='utf-8')
        (output / (name + '.stdout.log')).write_text(result.stdout, encoding='utf-8')
        assert result.returncode == 0, (name, result.returncode, result.stderr[-2000:])
        payload = json.loads(result.stdout.splitlines()[-1])
        assert not payload.get('error'), (name, payload)
        if name == 'OcrWorker':
            recognized = payload['results'][0]
            assert not recognized.get('error'), recognized
            assert 'HELLO WORLD' in recognized['text'].upper(), recognized
        report[name] = payload
    report['passed'] = True
    report['argos_scope'] = 'Native runtime import and empty local package probe; no translation model downloaded.'
    (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    run()
