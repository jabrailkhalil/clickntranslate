"""Regression tests keep user settings and the system clipboard untouched."""

import os
from pathlib import Path
import sys
import tempfile
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def isolated_clipboard(monkeypatch):
    """Exercise copying without replacing text while the user is working."""
    from PyQt5 import QtCore, QtGui, QtWidgets
    import pyperclip

    class MemoryClipboard(QtCore.QObject):
        dataChanged = QtCore.pyqtSignal()
        selectionChanged = QtCore.pyqtSignal()
        changed = QtCore.pyqtSignal(int)
        Clipboard, Selection, FindBuffer = 0, 1, 2

        def __init__(self):
            super().__init__()
            self._text = {}

        def text(self, mode=0):
            return self._text.get(mode, '')

        def setText(self, value, mode=0):
            self._text[mode] = str(value)
            self.changed.emit(mode)
            (self.selectionChanged if mode == self.Selection else self.dataChanged).emit()

        def clear(self, mode=0):
            self.setText('', mode)

        def supportsSelection(self):
            return True

        def mimeData(self, mode=0):
            data = QtCore.QMimeData()
            data.setText(self.text(mode))
            return data

        def setMimeData(self, data, mode=0):
            self.setText(data.text(), mode)

    clipboard = MemoryClipboard()
    monkeypatch.setattr(pyperclip, 'copy', clipboard.setText)
    monkeypatch.setattr(pyperclip, 'paste', clipboard.text)
    for application in (QtGui.QGuiApplication, QtWidgets.QApplication):
        monkeypatch.setattr(application, 'clipboard', staticmethod(lambda: clipboard))
    return clipboard


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
