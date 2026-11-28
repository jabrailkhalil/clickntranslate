"""Run the published Windows updater against the stage on a disposable CI host."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from package_windows_portable import package
from qa_published_update import download, release
from app_version import APP_VERSION
from release_manifest import MANIFEST, write_manifest


BASELINE = '1.8.2'


def main():
    if (sys.platform != 'win32' or os.environ.get('GITHUB_ACTIONS') != 'true'
            or os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted'):
        raise SystemExit('Requires a disposable GitHub-hosted Windows runner.')
    stage = ROOT / 'releases/transition-candidate/ClicknTranslate'
    out = ROOT / 'build/transition-fixtures'
    out.mkdir(parents=True, exist_ok=False)
    source_sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if source_sha != os.environ['GITHUB_SHA']:
        raise RuntimeError('The stage must be from the dispatched commit.')
    baseline = release(BASELINE)
    old, old_sha = download(baseline, f'Click-n-Translate-{BASELINE}-windows-portable-x64.zip', out)
    if old_sha != '8ee34cf794aa85764db549f7642b47630be3698c578d3ffbaeac1adc2f16429d':
        raise RuntimeError('The published 1.8.2 baseline changed.')

    receipt = dict(candidate_sha=source_sha, candidate_version=APP_VERSION,
                   old_tag=baseline['tag_name'], old_sha256=old_sha, cases={})
    for name in ('upgrade', 'rollback'):
        if name == 'rollback':
            # The successfully tested stage is now disposable. Keep the archive
            # internally consistent so the old updater exercises its startup rollback.
            (stage / 'app/ClicknTranslateApp.exe').write_bytes(b'Unlaunchable QA fixture')
            subprocess.run(['attrib', '-H', str(stage / MANIFEST)], check=True)
            write_manifest(stage, APP_VERSION)
            subprocess.run(['attrib', '+H', str(stage / MANIFEST)], check=True)
        archive = out / f'candidate-{name}.zip'
        count = package(stage, archive, APP_VERSION)
        with archive.open('rb') as stream:
            checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
        receipt['cases'][name] = dict(sha256=checksum, bytes=archive.stat().st_size, files=count)
        (out / 'build-receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
        command = [sys.executable, str(ROOT / 'tools/qa_update_transition.py'),
                   '--case', f'private-portable-{name}',
                   '--old-zip', str(old), '--old-version', BASELINE, '--old-sha256', old_sha,
                   '--new-zip', str(archive), '--new-version', APP_VERSION, '--new-sha256', checksum]
        if name == 'rollback':
            command.append('--expect-rollback')
        subprocess.run(command, cwd=ROOT, check=True, timeout=600)


if __name__ == '__main__':
    main()
