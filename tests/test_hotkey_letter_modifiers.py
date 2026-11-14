"""Synthetic VkKeyScan mappings distinguish implicit Shift from AltGr modifiers."""
from types import SimpleNamespace
from unittest import mock

import pytest

import main


@pytest.mark.parametrize('shortcut,scan_value,expected_modifiers,key,uses_scan', [
    ('Ctrl+Ł', 0x064C, main.MOD_CONTROL | main.MOD_ALT, 0x4C, True),
    ('Alt+Ł', 0x064C, main.MOD_CONTROL | main.MOD_ALT, 0x4C, True),
    ('Ctrl+Alt+Ł', 0x064C, main.MOD_CONTROL | main.MOD_ALT, 0x4C, True),
    ('Shift+Ł', 0x074C, main.MOD_CONTROL | main.MOD_ALT | main.MOD_SHIFT, 0x4C, True),
    ('Ctrl+ł', 0x064C, main.MOD_CONTROL | main.MOD_ALT, 0x4C, True),
    ('Ctrl+É', 0x0145, main.MOD_CONTROL, 0x45, True),
    ('Ctrl+Shift+É', 0x0145, main.MOD_CONTROL | main.MOD_SHIFT, 0x45, True),
    ('Ctrl+É', -1, None, None, True),
    ('Ctrl+É', 0x01FF, None, None, True),
    ('Ctrl+Alt+Q', 0x0751, main.MOD_CONTROL | main.MOD_ALT, 0x51, False),
    ('Ctrl+A', 0x0741, main.MOD_CONTROL, 0x41, False),
])
def test_letter_labels_keep_required_control_alt_without_adding_case_shift(
        monkeypatch, shortcut, scan_value, expected_modifiers, key, uses_scan):
    scan = mock.Mock(return_value=scan_value)
    monkeypatch.setattr(main.platform_support, 'IS_MAC', False)
    monkeypatch.setattr(main.ctypes, 'windll',
                        SimpleNamespace(user32=SimpleNamespace(VkKeyScanW=scan)), raising=False)
    listener = main.HotkeyListenerThread(shortcut, lambda: None)
    assert listener.vk == key
    if key is not None:
        assert listener.modifiers == expected_modifiers | 0x4000
    assert scan.call_count == int(uses_scan)
