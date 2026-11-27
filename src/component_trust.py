"""Portable root-cache publication for the pinned python-tuf 6 client."""
from pathlib import Path

from tuf.ngclient import Updater


class PortableUpdater(Updater):
    def _update_root_symlink(self):
        # TUF has already authenticated this exact version and retained its
        # signed envelope in root_history. Only the convenience alias changes:
        # publish complete bytes atomically without requiring symlink rights.
        version = self._trusted_set.root.version
        root = Path(self._dir, 'root_history', f'{version}.root.json')
        self._persist_metadata('root', root.read_bytes())
