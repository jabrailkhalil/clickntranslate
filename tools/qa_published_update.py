"""Download immutable GitHub release assets and run a real Windows transition.

This is intentionally separate from source/unit tests. It neither creates nor
publishes a release. The destination release may be a prerelease.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.request

REPO = 'jabrailkhalil/clickntranslate'
ROOT = Path(__file__).resolve().parents[1]


def release(version):
    url = f'https://api.github.com/repos/{REPO}/releases/tags/v{version}'
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'ClicknTranslate-transition-QA'}
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if token:
        headers['Authorization'] = 'Bearer ' + token
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as response:
        value = json.load(response)
    if value['tag_name'] != 'v' + version or value['draft']:
        raise RuntimeError('Unexpected release or unpublished draft')
    return value


def download(info, name, destination):
    matching = [asset for asset in info['assets'] if asset['name'] == name]
    if len(matching) != 1:
        raise RuntimeError('Expected exactly one asset: ' + name)
    asset = matching[0]
    if not re.fullmatch('sha256:[a-f0-9]{64}', asset.get('digest') or ''):
        raise RuntimeError('GitHub did not provide an asset digest: ' + name)
    url = asset['browser_download_url']
    if not url.startswith(f'https://github.com/{REPO}/releases/download/'):
        raise RuntimeError('Unexpected download origin')
    target = destination / name
    partial = target.with_name(target.name + '.part')
    checksum = hashlib.sha256()
    # Public asset request carries no token, including across CDN redirects.
    with urllib.request.urlopen(url, timeout=120) as source, partial.open('wb') as output:
        while block := source.read(1024 * 1024):
            output.write(block)
            checksum.update(block)
    if partial.stat().st_size != asset['size'] or 'sha256:' + checksum.hexdigest() != asset['digest']:
        raise RuntimeError('Downloaded size or SHA256 mismatch: ' + name)
    partial.replace(target)
    return target, checksum.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--old-version', required=True)
    parser.add_argument('--new-version', required=True)
    parser.add_argument('--mode', choices=('zip', 'setup'), default='zip')
    args = parser.parse_args()
    for version in (args.old_version, args.new_version):
        if not re.fullmatch(r'\d+\.\d+\.\d+', version):
            parser.error('Use a numeric three-part version without v')
    if tuple(map(int, args.old_version.split('.'))) >= tuple(map(int, args.new_version.split('.'))):
        parser.error('The target must be newer than the baseline')
    case = f'published-{args.old_version.replace(".", "-")}-to-{args.new_version.replace(".", "-")}-{args.mode}'
    downloads = ROOT / 'build/update-downloads' / case
    downloads.mkdir(parents=True, exist_ok=False)
    command = [sys.executable, str(ROOT / 'tools/qa_update_transition.py'), '--case', case]
    metadata = {}
    for label, version in (('old', args.old_version), ('new', args.new_version)):
        info = release(version)
        metadata[label] = {'id': info['id'], 'tag': info['tag_name'], 'prerelease': info['prerelease']}
        name = f'Click-n-Translate-{version}-windows-portable-x64.zip'
        path, checksum = download(info, name, downloads)
        command += ['--' + label + '-zip', str(path), '--' + label + '-sha256', checksum,
                    '--' + label + '-version', version]
        if args.mode == 'setup':
            name = f'Click-n-Translate-{version}-windows-x64-installer.exe'
            path, checksum = download(info, name, downloads)
            command += ['--' + label + '-setup', str(path), '--' + label + '-setup-sha256', checksum]
        if label == 'new':
            name = f'Click-n-Translate-{version}-windows-' + ('portable-x64.zip' if args.mode == 'zip' else 'x64-installer.exe')
            sidecar, _ = download(info, name + '.sha256', downloads)
            expected = next(asset['digest'].removeprefix('sha256:') for asset in info['assets'] if asset['name'] == name)
            lines = sidecar.read_text(encoding='utf-8-sig').strip().splitlines()
            if lines != [expected + '  ' + name] and lines != [expected + ' *' + name]:
                raise RuntimeError('Legacy SHA256 sidecar does not identify the candidate exactly')
    (downloads / 'releases.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    return subprocess.run(command, cwd=ROOT, check=False).returncode


if __name__ == '__main__':
    raise SystemExit(main())
