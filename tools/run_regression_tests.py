"""Run pytest with isolated app data and report any changes to real user data.

Usage: python tools/run_regression_tests.py [--output DIRECTORY] [pytest arguments]
Requires the project's development Python environment, including pytest and Qt.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys


def run():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qt-platform', default='offscreen',
                        help='Qt backend, e.g. windows:fontengine=freetype for native layout checks')
    parser.add_argument('--output', type=Path, default=Path(os.environ.get(
        'CNT_QA_OUTPUT', str(root / '.tmp' / ('regression-' + sys.platform)))))
    options, arguments = parser.parse_known_args()
    output = options.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    sys.path[:0] = [str(root), str(root / 'src'), str(root / 'tests')]
    # Child Python probes need the same source layout as this runner.
    os.environ['PYTHONPATH'] = os.pathsep.join(
        [str(root), str(root / 'src'), os.environ.get('PYTHONPATH', '')])
    os.chdir(root)
    os.environ['QT_QPA_PLATFORM'] = options.qt_platform
    os.environ['PYTHONUTF8'] = '1'
    for key in ('XDG_DATA_HOME', 'XDG_CACHE_HOME', 'XDG_CONFIG_HOME'):
        os.environ[key] = str(output / key.lower())
    shutil.copytree(root / 'src/icons', output / 'icons', dirs_exist_ok=True)
    sys.argv[0] = str(output / 'main.py')
    if sys.platform == 'darwin':
        import macos_desktop
        macos_desktop.user_data_dir = lambda: str(output)

    def data_hashes():
        return {str(path.relative_to(root / 'data')): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in (root / 'data').rglob('*') if path.is_file()}

    before = data_hashes()
    import main
    main.LAYOUT_EDITOR_MODE = True
    from PyQt5.QtWidgets import QApplication
    from qt_layout_test_support import ensure_layout_fonts
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    ensure_layout_fonts(app)
    import pytest
    code = pytest.main(['-q', '-ra', '--tb=short', '--disable-warnings',
                        '-o', 'faulthandler_timeout=90',
                        '-o', 'cache_dir=' + str(output / 'pytest-cache'),
                        '--junitxml=' + str(output / 'results.xml'), *(arguments or ['tests'])])
    after = data_hashes()
    unchanged = before == after
    code = int(code) if unchanged else 1
    (output / 'run.json').write_text(json.dumps({
        'finished': datetime.now(timezone.utc).isoformat(), 'platform': sys.platform,
        'exit_code': code, 'user_data_unchanged': unchanged,
        'changed_user_data_paths': sorted(key for key in before.keys() | after.keys()
                                         if before.get(key) != after.get(key)),
    }, indent=2), encoding='utf-8')
    print('USER_DATA_UNCHANGED:', unchanged, flush=True)
    return code


if __name__ == '__main__':
    raise SystemExit(run())
