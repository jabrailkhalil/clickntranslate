"""Exercise release preparation with GitHub's real release/asset response shape."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
from urllib.error import HTTPError

import pytest

from tools import release_download_table as table

ROOT = Path(__file__).resolve().parents[1]
REPO = 'example/clickntranslate'


def asset(name, **changes):
    record = {
        'name': name, 'state': 'uploaded', 'size': 60_487_261, 'download_count': 12,
        'digest': 'sha256:' + hashlib.sha256(name.encode()).hexdigest(),
    }
    return {**record, **changes}


@pytest.mark.parametrize(('name', 'variant'), [
    ('Click-n-Translate-1.8.3-windows-x64-installer.exe', ('Windows', 'Setup', 'x64')),
    ('Click-n-Translate-1.8.3-windows-portable-x64.zip', ('Windows', 'Portable ZIP', 'x64')),
    ('ClicknTranslate-v1.5.0-win64.zip', ('Windows', 'Portable ZIP', 'x64')),
    ('ClicknTranslate-Setup-v1.5.0-win64.exe', ('Windows', 'Setup', 'x64')),
    ('ClicknTranslate-1.8.3-store-x64.msix', ('Windows', 'MSIX', 'x64')),
    ('Click-n-Translate-1.8.3-macos-arm64.dmg', ('macOS', 'DMG', 'Apple Silicon')),
    ('Click-n-Translate-1.8.3-macos-x86_64.zip', ('macOS', 'App ZIP', 'Intel')),
    ('Click-n-Translate-1.8.3-linux-x86_64.AppImage', ('Linux', 'AppImage', 'x64')),
    ('Click-n-Translate-1.8.3-linux-aarch64.tar.gz', ('Linux', 'tar.gz', 'ARM64')),
    ('ClicknTranslate-1.8.3-arm64.apk', ('Android', 'APK', 'ARM64')),
    ('ClicknTranslate-android-arm64-v8a-1.8.3.apk', ('Android', 'APK', 'ARM64')),
    ('ClicknTranslate-1.8.3-armeabi-v7a.apk', ('Android', 'APK', 'ARMv7')),
    ('ClicknTranslate-1.8.3-universal.apk', ('Android', 'APK', 'Universal')),
    ('ClicknTranslate-1.8.3.apk', ('Android', 'APK', '')),
    ('Click-n-Translate-1.8.3-windows-x64-installer.exe.sha256', None),
    ('Click-n-Translate-1.8.3-verification.zip', None),
    ('ClicknTranslate-1.8.3-arm64-debug.apk', None),
    ('ClicknTranslate-1.8.3-arm64-code44-candidate.apk', None),
    ('ClicknTranslate-android-code44-candidate.apk', None),
    ('ClicknTranslate-RapidOCR-windows-x64-installer.exe', None),
    ('ClicknTranslate-1.8.3-RapidOCR-windows-x64-installer.exe', None),
    ('ClicknTranslate-windows-portable-engine-x64.zip', None),
    ('ClicknTranslate-v1.5.1-win64-portable-bootstrap.zip', None),
    ('ClicknTranslate-1.8.3-test-x64.msix', None),
    ('ClicknTranslate-Update-Repair.exe', None),
    ('unrelated-universal.apk', None),
])
def test_download_variants(name, variant):
    assert table.package(name) == variant


def test_table_only_links_uploaded_packages_and_exact_assets():
    apk = asset('ClicknTranslate-1.8.3-arm64.apk')
    universal = asset('ClicknTranslate-1.8.3-universal.apk', digest=None)
    windows = asset('Click-n-Translate-1.8.3-windows-portable-x64.zip')
    uploaded = [apk, windows, universal]
    ignored = [asset('ClicknTranslate-1.8.3-armv7.apk', state='starter'),
               asset('ClicknTranslate-1.8.3-x86.apk', size=0), asset('SHA256SUMS')]
    output = table.render_table(REPO, 'v1.8.3', ignored + uploaded)
    assert output == table.render_table(REPO, 'v1.8.3', reversed(uploaded))
    assert output.count('| Android |') == 2
    assert output.index('Portable ZIP') < output.index('Universal') < output.index('ARM64')
    assert '57.7 MiB' in output
    assert 'SHA-256 unavailable' in output
    for item in uploaded:
        path = f'{REPO}/releases/download/v1.8.3/{item["name"]}'
        assert f'https://github.com/{path}' in output
        assert f'https://img.shields.io/github/downloads/{REPO}/v1.8.3/{item["name"]}?' in output
    for item in (apk, windows):
        assert f'https://www.virustotal.com/gui/file/{item["digest"][7:]}/detection' in output
    for item in ignored:
        assert item['name'] not in output
    assert 'Safe' not in output
    assert 'MSIX' not in output


def test_encode_asset_name_and_tag_for_markdown_and_skip_invalid_digest():
    result = table.render_table(REPO, 'v2.0+1', [asset('ClicknTranslate-2.0+1-arm64.apk', digest='sha256:bad')])
    assert result.count('v2.0%2B1/ClicknTranslate-2.0%2B1-arm64.apk') == 2
    assert 'virustotal.com' not in result
    assert table.render_table(REPO, 'v1', [asset('README.md')]) == 'No application packages are attached to this release.'


def test_legacy_installers_and_offline_candidates_do_not_duplicate_rows():
    old = asset('ClicknTranslate-Setup-v1.6.0-win64.exe')
    current = asset('Click-n-Translate-1.6.0-windows-x64-installer.exe')
    wrong_version = asset('Click-n-Translate-1.5.0-linux-x86_64.AppImage')
    assert old['name'] in table.render_table(REPO, 'v1.6.0', [old])
    result = table.render_table(REPO, 'v1.6.0', [old, current, wrong_version])
    assert current['name'] in result and old['name'] not in result and wrong_version['name'] not in result
    early = asset('ClicknTranslate.zip')
    assert early['name'] in table.render_table(REPO, 'v1.2', [early])
    assert early['name'] not in table.render_table(REPO, 'v1.8.3', [early])


def test_vt_uses_actual_analysis_for_this_hash_and_handles_quota(monkeypatch):
    sha = 'b' * 64
    calls = []
    def get_report(request, timeout):
        calls.append(request.full_url)
        assert request.full_url.startswith('https://www.virustotal.com/api/v3/files/')
        assert request.get_method() == 'GET' and request.data is None
        if request.full_url.endswith(sha):
            stats = dict(malicious=1, suspicious=1, harmless=2, undetected=59, timeout=5)
            return io.BytesIO(json.dumps(dict(data=dict(
                id=sha, attributes=dict(last_analysis_date=1_700_000_000, last_analysis_stats=stats),
            ))).encode())
        raise HTTPError(request.full_url, 429, 'quota', {}, None)
    monkeypatch.setattr(table, 'urlopen', get_report)
    lookup = table.virus_total_reports('local-fixture')
    assets = [asset('ClicknTranslate-1.8.3-arm64.apk', digest='sha256:' + sha)]
    output = table.render_table(REPO, 'v1.8.3', assets, lookup)
    assert '[2/63 flagged]' in output and '2023-11-14 UTC' in output
    assert lookup(sha) == ('2/63 flagged', '2023-11-14')
    assert lookup('a' * 64) is None and lookup('c' * 64) is None
    assert len(calls) == 2


@pytest.mark.parametrize('document', [
    {'error': {'code': 'NotFoundError'}}, {'data': {'id': 'different hash'}},
    {'data': {'id': 'abc', 'attributes': {'last_analysis_stats': {}, 'last_analysis_date': 1}}},
])
def test_missing_virus_report_keeps_neutral_lookup(monkeypatch, document):
    monkeypatch.setattr(table, 'urlopen', lambda *args, **kwargs: io.BytesIO(json.dumps(document).encode()))
    assert table.virus_total_reports('local-fixture')('abc') is None


def test_repeated_refresh_preserves_release_notes_and_requires_whole_marker_pair():
    notes = f'Highlights before\r\n\r\n{table.BEGIN}\r\nold\r\n{table.END}\r\n\r\nAfter.'
    replaced = table.with_table(notes, 'new')
    assert replaced.startswith('Highlights before\r\n\r\n') and replaced.endswith('\r\n\r\nAfter.')
    assert table.with_table(replaced, 'new') == replaced
    assert table.with_table('Handwritten notes', 'new').endswith('\n\nHandwritten notes')
    for broken in [table.BEGIN, table.END, table.END + table.BEGIN, replaced + table.BEGIN]:
        with pytest.raises(ValueError, match='markers'):
            table.with_table(broken, 'table')


def test_refresh_reads_all_asset_pages_and_patches_only_current_notes():
    release = {'draft': True, 'tag_name': 'v1.8.3', 'body': 'Initial notes.'}
    pages = [[asset('Click-n-Translate-1.8.3-linux-x86_64.AppImage')],
             [asset('ClicknTranslate-1.8.3-arm64.apk')]]
    endpoint = f'repos/{REPO}/releases/42'
    patches = []
    def gh(*args, payload=None):
        if args == (endpoint,):
            return dict(release)
        if args == ('--paginate', '--slurp', endpoint + '/assets?per_page=100'):
            return pages
        assert args == ('--method', 'PATCH', endpoint, '--input', '-')
        assert set(payload) == {'body'}
        patches.append(payload)
        release.update(payload)
    def concurrent_edit(digest):
        release['body'] = 'The author finished editing.'
    table.refresh_release(REPO, 42, draft=True, api=gh, lookup=concurrent_edit)
    assert len(patches) == 1 and release['draft']
    assert release['body'].endswith('The author finished editing.')
    assert 'AppImage' in release['body'] and 'APK · ARM64' in release['body']
    table.refresh_release(REPO, 42, draft=True, api=gh)
    assert len(patches) == 1
    release['draft'] = False
    with pytest.raises(ValueError, match='state changed'):
        table.refresh_release(REPO, 42, draft=True, api=gh)
    pages.append([asset('Click-n-Translate-1.8.3-windows-x64-installer.exe')])
    table.refresh_release(REPO, 42, draft=False, api=gh)
    assert len(patches) == 2 and 'Setup · x64' in release['body']


def test_preparation_preview_is_read_only_and_workflow_uses_the_uploaded_release_id(tmp_path):
    release = {'tag_name': 'v1.8.3', 'body': (ROOT / 'docs/RELEASE_1.8.3.md').read_text(encoding='utf-8'),
               'assets': [asset('ClicknTranslate-1.8.3-arm64.apk')]}
    fixture = tmp_path / 'release.json'
    fixture.write_text(json.dumps(release), encoding='utf-8-sig')
    result = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'tools/release_download_table.py'),
                             '--repository', REPO, '--preview-json', str(fixture)],
                            check=True, capture_output=True, encoding='utf-8')
    assert '## What\'s new' in result.stdout and result.stdout.count('| OS | Download |') == 1
    assert json.loads(fixture.read_text(encoding='utf-8-sig')) == release
    draft = (ROOT / '.github/workflows/release.yml').read_text(encoding='utf-8')
    assert 'release_id: ${{ steps.draft.outputs.id }}' in draft
    assert 'needs: draft\n    uses: ./.github/workflows/release-download-table.yml' in draft
    refresh = (ROOT / '.github/workflows/release-download-table.yml').read_text(encoding='utf-8')
    assert 'types: [published]' in refresh and '--refresh-draft' in refresh and '--refresh-published' in refresh
