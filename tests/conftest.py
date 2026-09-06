"""Native Mac regressions must never read or overwrite the user's settings."""

import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def pytest_configure(config):
    if sys.platform != 'darwin':
        return
    import macos_desktop
    temporary = tempfile.TemporaryDirectory(prefix='cnt-pytest-macos-')
    original = macos_desktop.user_data_dir
    macos_desktop.user_data_dir = lambda: temporary.name
    # Argos imports create directories, too. Keep those in the same sandbox.
    variables = ('XDG_DATA_HOME', 'XDG_CACHE_HOME', 'XDG_CONFIG_HOME')
    previous = {name: os.environ.get(name) for name in variables}
    for name in variables:
        os.environ[name] = str(Path(temporary.name) / name.lower())
    config._cnt_macos_data = (temporary, original, previous)


def pytest_unconfigure(config):
    state = getattr(config, '_cnt_macos_data', None)
    if state is None:
        return
    import macos_desktop
    temporary, macos_desktop.user_data_dir, previous = state
    for name, value in previous.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
    temporary.cleanup()
