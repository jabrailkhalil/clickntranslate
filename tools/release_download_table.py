"""Render the GitHub release download table from uploaded asset metadata."""
import argparse
from datetime import datetime, timezone
from functools import cache
from http.client import HTTPException
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from release_assets import release_distribution

BEGIN = '<!-- clickntranslate-downloads:start -->'
END = '<!-- clickntranslate-downloads:end -->'
PLATFORMS = ('Windows', 'macOS', 'Linux', 'Android')
FORMATS = ('Setup', 'MSIX', 'Portable ZIP', 'DMG', 'App ZIP', 'AppImage', 'tar.gz', 'APK')

def package(name, tag=None):
    variant = release_distribution(name, tag)
    if variant and variant[0] == 'macOS':
        platform, kind, arch = variant
        return platform, kind, {'ARM64': 'Apple Silicon', 'x64': 'Intel'}.get(arch, arch)
    return variant


def virus_total_reports(api_key):
    @cache
    def lookup(digest):
        nonlocal api_key
        if not api_key:
            return None
        request = Request(f'https://www.virustotal.com/api/v3/files/{digest}',
                          headers={'User-Agent': 'ClicknTranslate-release-notes'})
        request.add_unredirected_header('x-apikey', api_key)
        try:
            with urlopen(request, timeout=5) as response:
                data = json.load(response)['data']
            if data['id'] != digest:
                return None
            attrs = data['attributes']
            stats = attrs['last_analysis_stats']
            counts = [stats[key] for key in ('malicious', 'suspicious', 'harmless', 'undetected')]
            if any(type(count) is not int or count < 0 for count in counts) or not sum(counts):
                return None
            day = datetime.fromtimestamp(attrs['last_analysis_date'], timezone.utc).date()
            return f'{counts[0] + counts[1]}/{sum(counts)} flagged', day.isoformat()
        except HTTPError as error:
            if error.code in (401, 403, 429):
                api_key = None
        except (OSError, HTTPException, KeyError, ValueError, TypeError, OverflowError):
            pass
        return None
    return lookup


def render_table(repository, tag, assets, lookup=None):
    if not re.fullmatch(r'[\w.-]+/[\w.-]+', repository, flags=re.ASCII):
        raise ValueError('Expected a GitHub repository in owner/name form')
    rows = []
    for asset in assets:
        variant = package(asset['name'], tag)
        if variant and asset.get('state') == 'uploaded' and asset['size'] > 0:
            rows.append((*variant, asset))
    rows.sort(key=lambda row: (PLATFORMS.index(row[0]), FORMATS.index(row[1]),
                               row[2] != 'Universal', row[2], row[3]['name']))
    # Some older tags also attached the network setup used by their legacy updater.
    installers = {arch for platform, kind, arch, asset in rows if platform == 'Windows' and kind == 'Setup'
                  and '-windows-' in asset['name'].lower()}
    if not rows:
        return 'No application packages are attached to this release.'
    lines = ['| OS | Download | Downloads | VirusTotal |', '| --- | --- | ---: | --- |']
    for platform, kind, arch, asset in rows:
        if arch in installers and asset['name'].lower().startswith('clickntranslate-setup-'):
            continue
        name = quote(asset['name'], safe='')
        path = f'{quote(tag, safe="")}/{name}'
        url = f'https://github.com/{repository}/releases/download/{path}'
        label = f'{kind} · {arch}' if arch else kind
        size = asset['size']
        amount = f'{size / (1024 * 1024):.1f} MiB' if size >= 1024 * 1024 else f'{(size + 1023) // 1024} KiB'
        download = f'[`{label}`]({url}) · {amount}'
        badge = (f'https://img.shields.io/github/downloads/{repository}/{path}'
                 '?displayAssetName=false&label=&color=39744c')
        counter = f'![Download count]({badge})'
        digest = re.fullmatch(r'sha256:([0-9a-fA-F]{64})', asset.get('digest') or '')
        verification = 'SHA-256 unavailable'
        if digest:
            sha = digest.group(1).lower()
            report_url = f'https://www.virustotal.com/gui/file/{sha}/detection'
            report = lookup(sha) if lookup else None
            verification = (f'[{report[0]}]({report_url} "VirusTotal analysis on {report[1]} UTC")'
                            if report else f'[Look up hash]({report_url})')
        lines.append(f'| {platform} | {download} | {counter} | {verification} |')
    return '\n'.join(lines)


def with_table(body, table):
    block = f'{BEGIN}\n{table}\n{END}'
    if BEGIN not in body and END not in body:
        return block + ('\n\n' + body if body else '')
    before, _, rest = body.partition(BEGIN)
    if body.count(BEGIN) != 1 or body.count(END) != 1 or END not in rest:
        raise ValueError('Ambiguous download table markers in release notes')
    return before + block + rest.partition(END)[2]


def github_api(*args, payload=None):
    content = json.dumps(payload).encode() if payload is not None else None
    output = subprocess.check_output(['gh', 'api', *args], input=content)
    return json.loads(output)


def refresh_release(repository, release_id, draft, api=github_api, lookup=None):
    if release_id < 1:
        raise ValueError('Invalid GitHub release ID')
    endpoint = f'repos/{repository}/releases/{release_id}'
    release = api(endpoint)
    if release['draft'] is not draft:
        raise ValueError('Release state changed. Refresh the intended release.')
    pages = api('--paginate', '--slurp', endpoint + '/assets?per_page=100')
    table = render_table(repository, release['tag_name'], (asset for page in pages for asset in page), lookup)
    # Read the current notes once more after any optional VirusTotal queries.
    current = api(endpoint)
    if current['draft'] is not draft or current['tag_name'] != release['tag_name']:
        raise ValueError('Release state or tag changed while preparing the notes')
    body = with_table(current.get('body') or '', table)
    if body != current.get('body'):
        api('--method', 'PATCH', endpoint, '--input', '-', payload={'body': body})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', required=True, help='GitHub owner/repository')
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--preview-json', type=Path, help='Render a saved GitHub release to stdout')
    source.add_argument('--refresh-draft', type=int, metavar='ID', help='Update the notes of this existing draft')
    source.add_argument('--refresh-published', type=int, metavar='ID', help='Update these published notes')
    args = parser.parse_args()
    if args.preview_json:
        release = json.loads(args.preview_json.read_text(encoding='utf-8-sig'))
        table = render_table(args.repository, release['tag_name'], release['assets'])
        print(with_table(release.get('body') or '', table))
        return
    lookup = virus_total_reports(os.environ.get('VIRUSTOTAL_API_KEY'))
    refresh_release(args.repository, args.refresh_draft if args.refresh_draft is not None else args.refresh_published,
                    draft=args.refresh_draft is not None, lookup=lookup)


if __name__ == '__main__':
    main()
