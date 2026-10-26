"""Trusted component descriptions; no Qt, native engines or network at import."""
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import sys
from urllib.parse import urlparse

CATALOG_URL = 'https://jabrailkhalil.github.io/clickntranslate-components/metadata/'
TARGET_URL = 'https://jabrailkhalil.github.io/clickntranslate-components/targets/'
CONTRACT = 1
SAFE_ID = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$')
SHA256 = re.compile(r'^[0-9a-f]{64}$')


class ComponentError(RuntimeError):
    def __init__(self, code, detail=''):
        self.code = code
        super().__init__(f'{code}: {detail}' if detail else code)


def safe_relative(value):
    if not isinstance(value, str) or not value or '\\' in value or ':' in value:
        raise ComponentError('invalid_path', str(value))
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ('', '.', '..') for part in value.split('/')):
        raise ComponentError('invalid_path', value)
    return value


def current_platform():
    machine = platform.machine().lower()
    arch = {'amd64': 'x86_64', 'aarch64': 'arm64'}.get(machine, machine)
    name = {'win32': 'windows', 'darwin': 'macos'}.get(sys.platform, sys.platform)
    # release() is a marketing label on Windows Server (e.g. 2022Server),
    # whereas compatibility requires the NT kernel version. Linux kernels
    # can carry distribution suffixes which are not package-version syntax.
    version = (platform.mac_ver()[0] if name == 'macos' else
               platform.version() if name == 'windows' else platform.release())
    numeric = re.match(r'^\d+(?:\.\d+)*', version)
    version = numeric.group() if numeric else '0'  # unknown OS fails minimum-version checks
    return {'os': name, 'arch': arch, 'os_version': version}


def parse_catalog(data):
    if len(data) > 2 * 1024 * 1024:
        raise ComponentError('invalid_catalog', 'too large')
    try:
        catalog = json.loads(data)
    except (ValueError, TypeError) as exc:
        raise ComponentError('invalid_catalog', 'JSON') from exc
    if not isinstance(catalog, dict) or catalog.get('schema') != 1 or not isinstance(catalog.get('revision'), int):
        raise ComponentError('invalid_catalog', 'schema/revision')
    artifacts = catalog.get('artifacts')
    bundles = catalog.get('bundles')
    if not isinstance(artifacts, dict) or not isinstance(bundles, list):
        raise ComponentError('invalid_catalog', 'artifacts/bundles')
    for digest, item in artifacts.items():
        if not SHA256.fullmatch(digest) or not isinstance(item, dict):
            raise ComponentError('invalid_catalog', 'artifact digest')
        if not isinstance(item.get('size'), int) or not 0 < item['size'] < 20 * 1024**3:
            raise ComponentError('invalid_catalog', 'artifact size')
        if 'unpacked_size' in item and (not isinstance(item['unpacked_size'], int)
                or not 0 < item['unpacked_size'] < 40 * 1024**3):
            raise ComponentError('invalid_catalog', 'expanded size')
        urls = item.get('urls')
        if not isinstance(urls, list) or not urls:
            raise ComponentError('invalid_catalog', 'artifact sources')
        for url in urls:
            parsed = urlparse(url)
            if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
                raise ComponentError('invalid_catalog', 'HTTPS sources required')
    seen = set()
    for bundle in bundles:
        if not isinstance(bundle, dict):
            raise ComponentError('invalid_catalog', 'bundle')
        for key in ('id', 'component'):
            if not SAFE_ID.fullmatch(str(bundle.get(key, ''))):
                raise ComponentError('invalid_catalog', key)
        if bundle['id'] in seen:
            raise ComponentError('invalid_catalog', 'duplicate bundle')
        seen.add(bundle['id'])
        if not isinstance(bundle.get('contract'), int) or bundle['contract'] < 1 or bundle.get('channel') not in ('preview', 'stable'):
            raise ComponentError('invalid_catalog', 'contract/channel')
        if not isinstance(bundle.get('revision'), int) or bundle['revision'] < 1:
            raise ComponentError('invalid_catalog', 'bundle revision')
        if bundle['contract'] > CONTRACT:
            # A future engine adapter must not prevent older clients updating
            # the components they still understand. Selection ignores it too.
            continue
        for key in ('os', 'arch', 'min_os', 'app'):
            if not isinstance(bundle.get(key), str):
                raise ComponentError('invalid_catalog', key)
        if bundle.get('runtime', 'python') == 'python':
            safe_relative(bundle.get('python'))
            safe_relative(bundle.get('worker'))
        elif bundle['runtime'] == 'native':
            safe_relative(bundle.get('executable'))
        else:
            raise ComponentError('invalid_catalog', 'runtime kind')
        if not isinstance(bundle.get('files'), list) or not bundle['files']:
            raise ComponentError('invalid_catalog', 'bundle files')
        destinations = set()
        language_files = bundle.get('language_files', {})
        if not isinstance(language_files, dict):
            raise ComponentError('invalid_catalog', 'language files')
        for language, items in language_files.items():
            if not SAFE_ID.fullmatch(language) or not isinstance(items, list) or not items:
                raise ComponentError('invalid_catalog', 'language files')
        for item in [*bundle['files'], *(item for items in language_files.values() for item in items)]:
            if not isinstance(item, dict):
                raise ComponentError('invalid_catalog', 'file')
            digest = item.get('sha256')
            if digest not in artifacts or item.get('kind') not in ('zip', 'file'):
                raise ComponentError('invalid_catalog', 'unknown artifact')
            if item['kind'] == 'zip' and 'unpacked_size' not in artifacts[digest]:
                raise ComponentError('invalid_catalog', 'archive expansion limit')
            destination = safe_relative(item.get('destination'))
            if destination.casefold() in destinations:
                raise ComponentError('invalid_catalog', 'duplicate destination')
            destinations.add(destination.casefold())
        if not isinstance(bundle.get('languages'), list):
            raise ComponentError('invalid_catalog', 'languages')
        if any(not isinstance(code, str) or not SAFE_ID.fullmatch(code) for code in bundle['languages']):
            raise ComponentError('invalid_catalog', 'language code')
        if language_files and set(bundle['languages']) != set(language_files):
            raise ComponentError('invalid_catalog', 'language capability mismatch')
    return catalog


def materialize_bundle(bundle, languages):
    """Choose language artifacts without changing the signed catalog description."""
    selected = sorted(set(languages))
    if not set(selected).issubset(bundle['languages']):
        raise ComponentError('no_compatible_update', 'installed languages')
    if not bundle.get('language_files'):
        return dict(bundle)
    files = [*bundle['files']]
    for code in selected:
        files.extend(dict(item, language=code) for item in bundle['language_files'][code])
    return {key: value for key, value in dict(bundle, files=files, languages=selected,
                                             available_languages=list(bundle['languages'])).items()
            if key != 'language_files'}


def runtime_command(folder, receipt):
    paths = ([receipt['executable']] if receipt.get('runtime') == 'native'
             else [receipt['python'], receipt['worker']])
    command = [folder / safe_relative(path) for path in paths]
    if any(not path.is_file() for path in command):
        raise ComponentError('installed_component_damaged', 'incomplete runtime')
    return [str(path) for path in command]


def choose_bundle(catalog, component, app_version, *, channel='stable', target=None, languages=()):
    from packaging.specifiers import SpecifierSet
    from packaging.version import Version, InvalidVersion
    target = target or current_platform()
    try:
        os_version = Version(target['os_version'])
    except InvalidVersion as error:
        raise ComponentError('no_compatible_update', 'unknown operating system version') from error
    candidates = []
    for bundle in catalog['bundles']:
        if bundle['component'] != component or bundle.get('revoked') or bundle['contract'] != CONTRACT:
            continue
        if bundle['channel'] != channel or bundle['os'] != target['os'] or bundle['arch'] != target['arch']:
            continue
        if Version(app_version) not in SpecifierSet(bundle['app']):
            continue
        if bundle['min_os'] and os_version < Version(bundle['min_os']):
            continue
        if not set(languages).issubset(bundle['languages']):
            continue
        candidates.append(bundle)
    if not candidates:
        raise ComponentError('no_compatible_update', component)
    return max(candidates, key=lambda item: item['revision'])


def bootstrap_path():
    return Path(__file__).resolve().with_name('component_root.json')


def trusted_catalog(root, *, metadata_url=CATALOG_URL, target_url=TARGET_URL, bootstrap=None):
    """Only TUF-authenticated bytes become a catalog. The caller holds store lock."""
    try:
        from tuf.ngclient import Updater
    except ImportError as exc:
        raise ComponentError('update_client_missing', 'tuf') from exc
    root = Path(root)
    metadata = root / 'trust'
    targets = root / 'catalog'
    metadata.mkdir(parents=True, exist_ok=True)
    targets.mkdir(parents=True, exist_ok=True)
    try:
        embedded = bootstrap if bootstrap is not None else bootstrap_path().read_bytes()
        updater = Updater(str(metadata), metadata_url, str(targets), target_url, bootstrap=embedded)
        updater.refresh()
        info = updater.get_targetinfo('catalog.json')
        if info is None or info.length > 2 * 1024 * 1024:
            raise ComponentError('invalid_catalog', 'missing target')
        path = updater.find_cached_target(info) or updater.download_target(info)
        return parse_catalog(Path(path).read_bytes())
    except ComponentError:
        raise
    except Exception as exc:
        # Preserve cached trust state; failure never downgrades to unsigned data.
        raise ComponentError('catalog_unavailable', type(exc).__name__) from exc


def component_store_path():
    override = os.environ.get('CLICKNTRANSLATE_COMPONENTS_DIR')
    if override:
        return Path(override).resolve()
    import portable_paths
    return Path(portable_paths.portable_base_dir()) / 'components'
