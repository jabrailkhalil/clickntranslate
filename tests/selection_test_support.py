"""A confirmed editor for selection tests unrelated to the UIA provider itself."""
from unittest import mock

import pytest

import main
import windows_selection


@pytest.fixture
def editable_editor(monkeypatch):
    target = windows_selection.WindowsEditTarget(42, 77, (42, 1, 8))
    reader = mock.Mock(return_value=target)
    monkeypatch.setattr(main, '_windows_edit_target', reader)
    monkeypatch.setattr(main, '_windows_foreground_window', lambda: 42)
    monkeypatch.setattr(windows_selection, 'prepare_windows_selection', lambda: True)
    return reader
