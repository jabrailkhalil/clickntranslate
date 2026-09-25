"""Apply portable engines without losing a working installation or its models."""

import logging
import os
from pathlib import Path
import shutil
import tempfile


def install_directory(source, destination, validate, preserve=(), check_cancel=None):
    """Stage on the destination volume, validate, and roll back failed installs.

    Only app-owned directories are passed here. Preserved files supplement the
    new distribution; files shipped by the new version take precedence.
    """
    destination = Path(destination).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f'.{destination.name}-install-', dir=destination.parent))
    candidate = staging / 'candidate'
    backup = staging / 'backup'
    applied = False
    keep_backup = False
    try:
        if check_cancel:
            check_cancel()
        # A cross-volume copy can fail halfway. Complete it before moving the
        # currently installed engine out of the way.
        shutil.move(os.fspath(source), candidate)
        for relative in preserve:
            old_root = destination / relative
            new_root = candidate / relative
            if old_root.is_dir():
                for old_file in old_root.rglob('*'):
                    if old_file.is_file():
                        target = new_root / old_file.relative_to(old_root)
                        if not target.exists():
                            target.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(old_file, target)
        if check_cancel:
            check_cancel()
        if destination.exists():
            destination.rename(backup)
        candidate.rename(destination)
        applied = True
        validate(os.fspath(destination))
        if check_cancel:
            check_cancel()
    except Exception as error:
        try:
            if applied and destination.exists():
                shutil.rmtree(destination)
            if backup.exists():
                backup.rename(destination)
        except OSError as rollback_error:
            keep_backup = True
            raise RuntimeError(
                f'{error}\nCould not restore the previous engine: {rollback_error}. '
                f'Recovery files were preserved in {staging}'
            ) from error
        raise
    finally:
        if not keep_backup:
            try:
                shutil.rmtree(staging)
            except OSError:
                logging.getLogger(__name__).warning('Could not remove installation staging folder %s', staging)
