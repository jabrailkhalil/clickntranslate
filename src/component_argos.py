"""Trusted Argos runtime/direction transactions, independent of Qt and the SDK."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

from component_catalog import (ComponentError, SAFE_ID, choose_bundle, component_store_path,
                               materialize_bundle, runtime_command, trusted_catalog)
from component_runtime import worker_environment
from component_store import ComponentStore

COMPONENT = 'translation.argos'


def direction_id(pair):
    if not isinstance(pair, (list, tuple)) or len(pair) != 2:
        raise ComponentError('invalid_direction')
    values = [str(value).lower() for value in pair]
    if values[0] == values[1] or any(not SAFE_ID.fullmatch(value) or '__' in value for value in values):
        raise ComponentError('invalid_direction')
    return '__'.join(values)


def direction_pair(value):
    parts = value.split('__')
    if direction_id(parts) != value:
        raise ComponentError('invalid_direction')
    return tuple(parts)


def validate(folder, receipt, check_cancel=lambda: None):
    """Load and translate with each selected model, allowing prompt cancellation."""
    command = runtime_command(Path(folder), receipt)
    with tempfile.TemporaryDirectory(prefix='clickntranslate_argos_probe_') as temporary:
        work = Path(temporary)
        request = work / 'request.json'
        request.write_text(json.dumps({'root_dir':str(folder), 'action':'validate',
                                       'directions':receipt['languages'], 'work_dir':temporary}), encoding='utf-8')
        with (work / 'stdout.json').open('w', encoding='utf-8') as stdout, \
                (work / 'stderr.txt').open('w', encoding='utf-8') as stderr:
            process = subprocess.Popen([*command, str(request)], stdout=stdout, stderr=stderr,
                env=worker_environment(), creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            try:
                deadline = time.monotonic() + max(60, 60 * len(receipt['languages']))
                while process.poll() is None:
                    check_cancel()
                    if time.monotonic() > deadline:
                        raise ComponentError('validation_failed', 'Argos timeout')
                    time.sleep(.05)
            finally:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=10)
        try:
            output = (work / 'stdout.json').read_text(encoding='utf-8')
            if len(output) > 1024 * 1024:
                raise ValueError('response too large')
            result = json.loads(output)
        except (ValueError, OSError) as error:
            raise ComponentError('validation_failed', 'Argos response') from error
        if (process.returncode or result.get('error')
                or set(result.get('validated', ())) != set(receipt['languages'])):
            raise ComponentError('validation_failed', str(result.get('error') or 'Argos models')[:300])
        return result


def install(download, *, pairs=(), remove_pairs=(), legacy_pairs=(), root=None,
            check_cancel=lambda: None, progress=lambda *_: None,
            channel=None, catalog_loader=trusted_catalog):
    from app_version import APP_VERSION
    store = ComponentStore(root or component_store_path())
    with store.lock():
        check_cancel()
        try:
            old = store.active(COMPONENT)
        except ComponentError:
            old = store.describe(COMPONENT)
        if old and remove_pairs and not pairs:
            return store.remove_languages(COMPONENT, [direction_id(pair) for pair in remove_pairs],
                lambda folder, receipt: validate(folder, receipt, check_cancel), check_cancel, progress)
        catalog = catalog_loader(store.root)
        selected = set(old['receipt']['languages']) if old else {direction_id(pair) for pair in legacy_pairs}
        selected.update(direction_id(pair) for pair in pairs)
        selected.difference_update(direction_id(pair) for pair in remove_pairs)
        bundle = choose_bundle(catalog, COMPONENT, APP_VERSION, languages=selected,
            channel=channel or os.environ.get('CLICKNTRANSLATE_COMPONENT_CHANNEL', 'stable'))
        return store.install(catalog, materialize_bundle(bundle, selected), download,
            lambda folder, receipt: validate(folder, receipt, check_cancel), check_cancel, progress)


def catalog_rows(*, root=None, channel=None, refresh=True, catalog_loader=trusted_catalog):
    from app_version import APP_VERSION
    store = ComponentStore(root or component_store_path())
    with store.lock():
        active = store.active(COMPONENT)
        installed = set(active['receipt']['languages']) if active else set()
        if refresh:
            catalog = catalog_loader(store.root)
            bundle = choose_bundle(catalog, COMPONENT, APP_VERSION,
                channel=channel or os.environ.get('CLICKNTRANSLATE_COMPONENT_CHANNEL', 'stable'))
            available = set(bundle['languages'])
        elif active:
            # UI presentation only. Installation still requires a fresh trusted
            # catalog; removal/translation remain usable without the network.
            bundle = active['receipt']
            available = set(bundle.get('available_languages', installed))
        else:
            return []
        rows = []
        for code in sorted(available | installed):
            source, target = direction_pair(code)
            receipt = active['receipt'] if code in installed else bundle
            rows.append({'source_code':source, 'target_code':target,
                'version':str(receipt.get('model_versions', {}).get(code, '')),
                'installed':code in installed, 'available':code in available,
                'package_name':'translate-' + source + '_' + target})
        return rows
