"""Native preview lifecycle QA. Requires an explicit, pre-installed QA store.

Terminates its own installer child at the pre-activation boundary. Never builds
or publishes the application, opens windows or accesses the user's clipboard.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

PROJECT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PROJECT), str(PROJECT / 'src')]
from component_catalog import trusted_catalog
from component_store import ComponentStore
import component_runtime


def child(root, marker):
    original = component_runtime.validate_rapidocr
    def stop_before_activation(folder, receipt):
        original(folder, receipt)
        marker.write_text('validated; not activated', encoding='utf-8')
        time.sleep(120)
    component_runtime.validate_rapidocr = stop_before_activation
    component_runtime.install_rapidocr(lambda *_: (_ for _ in ()).throw(AssertionError('Unexpected download')),
                                     root=root, channel='preview')


def run(root):
    store = ComponentStore(root)
    active = store.active('ocr.rapidocr')
    if not active or active['receipt']['revision'] != 1:
        raise RuntimeError('QA requires the initial r1 preview installed in the explicit test directory')
    previous = active['receipt']['generation']
    marker = root.parent / 'before-activation.txt'
    marker.unlink(missing_ok=True)
    log = root.parent / 'interrupted-installer.log'
    with log.open('w', encoding='utf-8') as output:
        process = subprocess.Popen([sys.executable, __file__, '--store', str(root), '--child'],
            stdout=output, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            deadline = time.monotonic() + 90
            while not marker.exists() and time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError('Installer exited before the interruption boundary; inspect ' + str(log))
                time.sleep(.1)
            if not marker.exists():
                raise RuntimeError('Installer did not reach the interruption boundary')
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
    assert store.active('ocr.rapidocr')['receipt']['generation'] == previous
    with store.database() as db:
        assert db.execute('SELECT COUNT(*) FROM operations').fetchone()[0] == 1
    print('Forced termination preserved active r1; durable recovery record exists.', flush=True)
    downloads = []
    def no_download(url, path):
        downloads.append(url)
        raise AssertionError('Unchanged verified artifacts must be reused')
    started = time.perf_counter()
    installed = component_runtime.install_rapidocr(no_download, root=root, channel='preview')
    assert installed['receipt']['revision'] == 2
    assert not downloads
    with store.database() as db:
        assert db.execute('SELECT COUNT(*) FROM operations').fetchone()[0] == 0
    with store.lock():
        catalog = trusted_catalog(root)
    store.rollback('ocr.rapidocr', component_runtime.validate_rapidocr, catalog)
    assert store.active('ocr.rapidocr')['receipt']['revision'] == 1
    component_runtime.install_rapidocr(no_download, root=root, channel='preview')
    assert store.active('ocr.rapidocr')['receipt']['revision'] == 2
    result = {'forced_installer_termination': 'previous generation preserved',
              'recovery': 'uncommitted generation removed', 'revision_update': 'r1 -> r2',
              'additional_downloads': len(downloads), 'rollback': 'r2 -> r1 passed',
              'repeat_update': 'r1 -> r2 passed',
              'lifecycle_seconds': round(time.perf_counter() - started, 2)}
    (root.parent / 'lifecycle.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store', type=Path, required=True)
    parser.add_argument('--child', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    test_root = args.store.resolve()
    if 'ClicknTranslate-QA' not in test_root.parts:
        parser.error('Only a directory below ClicknTranslate-QA is permitted')
    if args.child:
        child(test_root, test_root.parent / 'before-activation.txt')
    else:
        run(test_root)
