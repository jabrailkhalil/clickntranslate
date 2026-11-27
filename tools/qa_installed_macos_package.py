"""Probe a staged DMG after installation on an isolated GitHub Mac."""
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import subprocess
import tempfile


candidate = Path(os.environ['CANDIDATE'])
app = Path('/Applications/ClicknTranslate.app')
trace = Path('build/macos/trace').resolve()
trace.mkdir(parents=True, exist_ok=True)
manifest = json.loads((candidate / 'BUILD.json').read_text())
arch = platform.machine()
assert manifest['architecture'] == arch
assert manifest['source_commit'] == os.environ['EXPECTED_SHA']
assert manifest['workflow_run'] == os.environ['TARGET_RUN']
assert manifest['runtime_tested'] and not manifest['published_release']
assert (manifest['version'], manifest['minimum_macos']) == ('1.8.3', '13.4')
info = plistlib.loads((app / 'Contents' / 'Info.plist').read_bytes())
assert (info['CFBundleVersion'], info['CFBundleShortVersionString'],
        info['LSMinimumSystemVersion']) == ('1.8.3', '1.8.3', '13.4')
assert info['CFBundleIdentifier'] == 'io.github.jabrailkhalil.clickntranslate'
evidence = {'source_sha': manifest['source_commit'], 'run': manifest['workflow_run'],
            'architecture': arch, 'os': platform.mac_ver()[0], 'app': str(app),
            'version': info['CFBundleVersion'], 'codesign_deep_strict': True,
            'signer_sha1': manifest['signer_sha1'], 'minimum_macos': info['LSMinimumSystemVersion'],
            'notarized': manifest['notarized'], 'ocr': {}}


def record():
    (trace / 'installed-package.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2))


record()
with tempfile.TemporaryDirectory(prefix='cnt-installed-') as directory:
    temp = Path(directory)
    permission_file = temp / 'frozen-permissions.json'
    subprocess.run(['/usr/bin/open', '-n', '-W', '-a', str(app), '--args',
                    '--macos-permission-report', str(permission_file), '--macos-capture-check'],
                   check=True, timeout=120)
    permissions = json.loads(permission_file.read_text())
    (trace / permission_file.name).write_bytes(permission_file.read_bytes())
    assert permissions['executable'] == str(app / 'Contents/MacOS/ClicknTranslate'), permissions
    evidence['permissions'] = permissions['permissions']
    evidence['capture'] = permissions['capture']
    record()
    fixtures = Path(__file__).with_name('qa_macos_ocr_fixtures')
    corpus = {'en': {'release': 'CLICK TRANSLATE', 'win-independent': 'This is a sample line.',
                     'compact-11': 'Book 1684'},
              'ru': {'Arial-30': 'Проверка перевода текста', 'Arial-40': 'Проверка перевода текста',
                     'Segoe-40': 'Проверка перевода текста', 'Arial-40-vopros': 'Сохранить перевод текста',
                     'Segoe-32-vopros': 'Доброе утро'}}
    errors = []
    for lang, cases in corpus.items():
        images = [{'label': name, 'path': str(fixtures / (name + '.png'))} for name in cases]
        request = {'action': 'recognize', 'engine': 'rapidocr', 'root_dir': str(temp),
                   'language_code': lang, 'allow_download': False, 'images': images}
        request_file = temp / (lang + '.json')
        request_file.write_text(json.dumps(request))
        output = subprocess.run([str(app / 'Contents/MacOS/OcrWorker'), str(request_file)],
                                capture_output=True, text=True, timeout=150, check=True)
        response = json.loads(output.stdout)
        assert not response['error'], response
        assert {r['label'] for r in response['results']} == set(cases)
        for result in response['results']:
            name = result['label']
            expected = cases[name]
            exact = result['text'] == expected and not result['error']
            digest = hashlib.sha256((fixtures / (name + '.png')).read_bytes()).hexdigest()
            evidence['ocr'][name] = {**result, 'expected': expected, 'exact': exact, 'png_sha256': digest}
            if not exact:
                errors.append(name)
        record()

quarantine = subprocess.run(['/usr/bin/xattr', '-p', 'com.apple.quarantine', str(app)],
                            capture_output=True, text=True)
assessment = subprocess.run(['/usr/sbin/spctl', '--assess', '--type', 'execute', '--verbose=4', str(app)],
                            capture_output=True, text=True, timeout=90)
evidence['quarantined'] = quarantine.returncode == 0
evidence['gatekeeper_assessment'] = {'status': assessment.returncode,
                                    'verdict': (assessment.stdout + assessment.stderr).strip()}
record()
print(f"Installed package on {arch}: {len(evidence['ocr']) - len(errors)}/{len(evidence['ocr'])} exact")
assert not errors, errors
