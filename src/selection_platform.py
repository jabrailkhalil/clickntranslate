"""Read highlighted text from other applications without starting a translation."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess

import platform_support

logger = logging.getLogger("clickntranslate.selection")


def read_primary_selection(app=None):
    """Linux/X11 PRIMARY selection, or Qt selection when an app instance exists."""
    try:
        if app is None:
            from PyQt5.QtWidgets import QApplication

            app = QApplication.instance()
        if app is not None:
            clipboard = app.clipboard()
            text = clipboard.text(clipboard.Selection)
            if text and str(text).strip():
                return str(text).strip()
    except Exception:
        logger.debug("Qt PRIMARY selection read failed", exc_info=True)
    for command in (["xclip", "-o", "-selection", "primary"], ["xsel", "-p"]):
        if not shutil.which(command[0]):
            continue
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=3,
                env=platform_support.system_subprocess_env(),
            )
            if completed.returncode == 0 and completed.stdout.strip():
                return completed.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            continue
    return ""


def read_selected_text(*, allow_copy_fallback=False):
    """Best-effort selected text in the foreground application."""
    if platform_support.IS_LINUX:
        return read_primary_selection()
    if platform_support.IS_MAC:
        from macos_desktop import read_foreground_selected_text

        return read_foreground_selected_text()
    if platform_support.IS_WINDOWS:
        from windows_selection import read_windows_selected_text

        text = read_windows_selected_text()
        if text or not allow_copy_fallback:
            return text
        return _read_selection_via_copy()
    return ""


def _read_selection_via_copy():
    """Windows fallback: simulate copy and read clipboard (restores prior contents)."""
    try:
        import ctypes
        import time

        import pyperclip

        previous = str(pyperclip.paste() or "")
        platform_support.copy_text("")
        if platform_support.IS_WINDOWS:
            VK_CONTROL = 0x11
            VK_C = 0x43
            KEYEVENTF_KEYUP = 0x0002
            ctypes.windll.user32.keybd_event(VK_CONTROL, 0, 0, 0)
            ctypes.windll.user32.keybd_event(VK_C, 0, 0, 0)
            time.sleep(0.02)
            ctypes.windll.user32.keybd_event(VK_C, 0, KEYEVENTF_KEYUP, 0)
            ctypes.windll.user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.2)
        text = str(pyperclip.paste() or "").strip()
        if previous:
            platform_support.copy_text(previous)
        return text
    except Exception:
        logger.debug("Copy fallback selection read failed", exc_info=True)
        return ""


def is_foreign_foreground():
    """True when another application owns the foreground window."""
    if platform_support.IS_WINDOWS:
        import ctypes

        hwnd = int(ctypes.windll.user32.GetForegroundWindow())
        if not hwnd:
            return False
        pid = ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return int(pid.value) != os.getpid()
    if platform_support.IS_MAC:
        import AppKit

        app = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
        return app is not None and int(app.processIdentifier()) != os.getpid()
    return True
