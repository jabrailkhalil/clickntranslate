"""Confirm the running application's version only after its GUI is ready."""

import logging
import os
import tempfile


def acknowledge_ready(arguments, version, package_root=None):
    argument = next((value for value in arguments if value.startswith('--update-ack=')), '')
    path = argument.partition('=')[2].strip()
    if not path:
        return False
    temporary = None
    try:
        if package_root is not None:
            from release_manifest import verify_manifest
            verify_manifest(package_root, version)
        parent = os.path.dirname(os.path.abspath(path))
        os.makedirs(parent, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=parent,
                                         prefix='.cnt-update-ack-', delete=False) as output:
            temporary = output.name
            output.write(version)
        # The updater must never observe an empty or partially written version.
        os.replace(temporary, path)
        return True
    except (OSError, ValueError):
        logging.getLogger(__name__).exception('Could not confirm updated application startup')
        return False
    finally:
        if temporary is not None and os.path.exists(temporary):
            try:
                os.unlink(temporary)
            except OSError:
                logging.getLogger(__name__).warning('Could not remove temporary startup acknowledgement')
