"""Maintainer-only GitHub setup. Credentials come from git's credential helper.

Never prints or persists an access token. Only online TUF role keys are sent to
the component repository's encrypted Actions secrets, never application keys.
"""
import argparse
import base64
import json
from pathlib import Path
import subprocess
import time

import requests


def session():
    result = subprocess.run(['git', 'credential', 'fill'],
        input='protocol=https\nhost=github.com\n\n', text=True, capture_output=True, timeout=30)
    values = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
    if result.returncode or not values.get('password'):
        raise RuntimeError('GitHub authorization is unavailable')
    client = requests.Session()
    client.headers.update({'Authorization': 'Bearer ' + values['password'],
        'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'})
    return client


def request(client, method, path, **kwargs):
    result = client.request(method, 'https://api.github.com/' + path,
                            timeout=kwargs.pop('timeout', 90), **kwargs)
    if not result.ok:
        # Server messages are useful; do not print request headers or tokens.
        raise RuntimeError(f'GitHub {method} {path}: {result.status_code} {result.json().get("message", "request failed")}')
    return result.json() if result.content else {}


def setup(client, repo, keys):
    from nacl.public import PublicKey, SealedBox
    who = request(client, 'GET', 'user')
    if who['login'] != repo.split('/')[0]:
        raise RuntimeError('The authenticated GitHub account does not own the requested repository')
    found = client.get('https://api.github.com/repos/' + repo, timeout=30)
    if found.status_code == 404:
        request(client, 'POST', 'user/repos', json={'name': repo.split('/')[1], 'private': False,
            'description': 'Verified OCR and translation components for ClicknTranslate', 'auto_init': False})
    elif not found.ok:
        raise RuntimeError('Cannot inspect existing component repository')
    key = request(client, 'GET', f'repos/{repo}/actions/secrets/public-key')
    box = SealedBox(PublicKey(base64.b64decode(key['key'])))
    for role in ('snapshot', 'timestamp'):
        value = base64.b64encode((keys / (role + '.pem')).read_bytes())
        encrypted = base64.b64encode(box.encrypt(value)).decode()
        request(client, 'PUT', f'repos/{repo}/actions/secrets/COMPONENT_{role.upper()}_KEY',
                json={'key_id': key['key_id'], 'encrypted_value': encrypted})
    print('Component repository ready; two restricted online role keys configured.')


def release(client, repo, archive):
    tag = 'rapidocr-windows-x64-r1'
    existing = client.get(f'https://api.github.com/repos/{repo}/releases/tags/{tag}', timeout=30)
    if existing.status_code == 404:
        value = request(client, 'POST', f'repos/{repo}/releases', json={'tag_name': tag,
            'name': 'RapidOCR Windows x64 — preview 1', 'draft': True, 'prerelease': True,
            'make_latest': 'false', 'body': 'Preview component runtime. Install through ClicknTranslate; this is not an application release.'})
    else:
        existing.raise_for_status()
        value = existing.json()
    if any(asset['name'] == archive.name for asset in value['assets']):
        raise RuntimeError('Artifact already exists; refusing to overwrite released bytes')
    with archive.open('rb') as stream:
        result = client.post(value['upload_url'].split('{')[0], params={'name': archive.name},
            headers={'Content-Type': 'application/zip'}, data=stream, timeout=900)
        result.raise_for_status()
    request(client, 'PATCH', f'repos/{repo}/releases/{value["id"]}', json={'draft': False})
    print('Preview component artifact published:', tag)


def pages(client, repo):
    existing = client.get(f'https://api.github.com/repos/{repo}/pages', timeout=30)
    if existing.status_code == 404:
        request(client, 'POST', f'repos/{repo}/pages', json={'build_type': 'workflow'})
    elif existing.ok:
        request(client, 'PUT', f'repos/{repo}/pages', json={'build_type': 'workflow'})
    else:
        raise RuntimeError('Cannot inspect Pages configuration')
    request(client, 'POST', f'repos/{repo}/actions/workflows/metadata.yml/dispatches', json={'ref': 'main'})
    print('Public metadata deployment requested.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('setup', 'release', 'pages'))
    parser.add_argument('--repo', default='jabrailkhalil/clickntranslate-components')
    parser.add_argument('--keys', type=Path)
    parser.add_argument('--archive', type=Path)
    args = parser.parse_args()
    api = session()
    if args.action == 'setup':
        setup(api, args.repo, args.keys)
    elif args.action == 'release':
        release(api, args.repo, args.archive)
    else:
        pages(api, args.repo)
