"""Run the application's adapter with an approved component's private Python.

Source-mode bridge only: embedded CPython's ._pth does not include the supplied
script directory. Add our own application source directory, never a user path
from the request. Installed component bytes and model paths remain unchanged.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ocr_worker import main

if __name__ == '__main__':
    raise SystemExit(main())
