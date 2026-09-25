"""Repository locations, separate from installed application and user data paths."""
from pathlib import Path
import sys


def source_root() -> Path:
    return Path(__file__).resolve().parent


def repository_root() -> Path:
    return source_root().parent


def resource_root() -> Path:
    return Path(sys._MEIPASS) if hasattr(sys, '_MEIPASS') else source_root()


def source_entry() -> Path:
    return repository_root() / 'main.py'
