"""Read selected text from the foreground Windows control via UI Automation."""

from __future__ import annotations

import logging
import sys
import threading
import time
from dataclasses import dataclass

logger = logging.getLogger("clickntranslate.selection")
_com_client = None
_bootstrap_attempted = False


def _modifiers_down():
    import ctypes
    state = ctypes.windll.user32.GetAsyncKeyState
    state.argtypes = [ctypes.c_int]
    state.restype = ctypes.c_short
    return any(state(key) & 0x8000 for key in (0x11, 0x12, 0x10, 0x5b, 0x5c))


def wait_for_modifier_release():
    """Wait for Ctrl, Alt, Shift and Windows keys without modifying the user's input."""
    deadline = time.monotonic() + 1.5
    try:
        while _modifiers_down():
            if time.monotonic() >= deadline:
                return False
            time.sleep(.02)
        return True
    except (AttributeError, OSError):
        return False


def _discard_provider_error_frames(error):
    """Break provider exception cycles before releasing the owned apartment."""
    kind = type(error).__name__
    pending, seen = [error], set()
    while pending:
        item = pending.pop()
        if id(item) in seen:
            continue
        seen.add(id(item))
        pending.extend(value for value in (item.__context__, item.__cause__) if value is not None)
        item.__traceback__ = item.__context__ = item.__cause__ = None
    return kind


@dataclass(frozen=True)
class WindowsEditTarget:
    """Plain identity only: no COM pointer may outlive its MTA apartment."""
    window: int
    process_id: int
    runtime_id: tuple[int, ...]


def _foreground_process(expected_window):
    """Resolve the expected foreground HWND without truncating 64-bit handles."""
    import ctypes
    from ctypes import wintypes
    api = ctypes.WinDLL('user32', use_last_error=True)
    api.GetForegroundWindow.argtypes = []
    api.GetForegroundWindow.restype = wintypes.HWND
    api.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    api.GetWindowThreadProcessId.restype = wintypes.DWORD
    if not expected_window or int(api.GetForegroundWindow() or 0) != expected_window:
        return 0
    process = wintypes.DWORD()
    if not api.GetWindowThreadProcessId(expected_window, ctypes.byref(process)):
        return 0
    return int(process.value)


def read_windows_edit_target(expected_window):
    """Prove focus, identity and writability before any replacement shortcut.

    A selected spreadsheet cell, button, password field or unknown provider is
    not an editor. Unavailable UIA fails closed rather than trying Ctrl+A/C/V.
    """
    try:
        process = _foreground_process(expected_window)
        if process:
            return _in_mta(_read_initialized_edit_target, None, expected_window, process)
    except Exception as error:
        logger.debug("Editable target unavailable (%s)", type(error).__name__)
    return None


def prepare_windows_selection():
    """Import on main so comtypes' automatic STA and atexit share one thread."""
    global _com_client, _bootstrap_attempted
    if _com_client is not None:
        return True
    if threading.current_thread() is not threading.main_thread():
        return False
    if _bootstrap_attempted or 'comtypes' in sys.modules:
        # Failed preparation or an unknown earlier importer cannot be adopted.
        return False
    _bootstrap_attempted = True
    try:
        import comtypes.client
        _com_client = comtypes.client
        return True
    except Exception as error:
        logger.debug("UI Automation preparation unavailable (%s)", type(error).__name__)
        return False


def read_windows_selected_text():
    try:
        return _read_via_comtypes()
    except ImportError:
        logger.debug("UI Automation unavailable (comtypes not installed)")
    except Exception as error:
        logger.debug("UI Automation selection read failed (%s)", type(error).__name__)
    return ""


def _read_via_comtypes():
    return _in_mta(_read_initialized_selection, "")


def _in_mta(reader, empty, *args):
    client = _com_client
    if client is None:
        return empty  # A pool worker must never become comtypes' first importer.
    import ctypes
    api = ctypes.WinDLL('ole32')
    api.CoInitializeEx.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    api.CoInitializeEx.restype = ctypes.c_long
    api.CoUninitialize.argtypes = []
    api.CoUninitialize.restype = None
    initialized = int(api.CoInitializeEx(None, 0))  # COINIT_MULTITHREADED
    if initialized not in (0, 1):  # S_OK and S_FALSE each own one reference.
        return empty
    try:
        return reader(client, *args)
    finally:
        api.CoUninitialize()


def _read_initialized_selection(client):
    """Keep all COM values and handled exception frames inside the owned scope."""
    try:
        types = client.GetModule('UIAutomationCore.dll')
        automation = client.CreateObject(types.CUIAutomation, interface=types.IUIAutomation)
        element = automation.GetFocusedElement()
        if element is None or element.CurrentIsPassword:
            return ""
        unknown = element.GetCurrentPattern(10014)  # UIA_TextPatternId
        if not unknown:
            return ""
        text_pattern = unknown.QueryInterface(types.IUIAutomationTextPattern)
        ranges = text_pattern.GetSelection()
        if ranges and int(getattr(ranges, "Length", 0) or 0) > 0:
            parts = []
            for index in range(int(ranges.Length)):
                text_range = ranges.GetElement(index)
                # A caret is a degenerate range, not a text selection. Never
                # substitute the element's Name/Value (e.g. an Excel cell).
                if text_range.CompareEndpoints(0, text_range, 1) != 0:
                    parts.append(str(text_range.GetText(-1) or ""))
            if not automation.CompareElements(element, automation.GetFocusedElement()):
                return ""
            return "".join(parts).strip()
    except Exception as error:
        # Logging a traceback would retain this frame's COM pointers beyond
        # CoUninitialize. Store only a plain diagnostic string in log records.
        logger.debug("TextPattern selection read failed (%s)", _discard_provider_error_frames(error))
    return ""


def _is_writable(element, types):
    try:
        unknown = element.GetCurrentPattern(10002)  # UIA_ValuePatternId
    except Exception as error:
        # Only a genuinely unsupported pattern permits the Text-only path.
        # Access errors/disconnected providers must not authorize editing.
        if getattr(error, 'hresult', 0) & 0xffffffff != 0x80040204:  # UIA_E_NOTSUPPORTED
            raise
        _discard_provider_error_frames(error)
        unknown = None
    if unknown:
        value = unknown.QueryInterface(types.IUIAutomationValuePattern)
        readonly = value.CurrentIsReadOnly
    else:
        unknown = element.GetCurrentPattern(10014)  # UIA_TextPatternId
        if not unknown:
            return False
        text = unknown.QueryInterface(types.IUIAutomationTextPattern)
        readonly = text.DocumentRange.GetAttributeValue(40015)  # UIA_IsReadOnlyAttributeId
    # Mixed/not-supported attribute sentinels are COM objects, not evidence
    # that a document or input field can be edited.
    return type(readonly) in (bool, int) and readonly == 0


def _read_initialized_edit_target(client, expected_window, process):
    try:
        types = client.GetModule('UIAutomationCore.dll')
        automation = client.CreateObject(types.CUIAutomation, interface=types.IUIAutomation)
        element = automation.GetFocusedElement()
        if (element is None or element.CurrentIsPassword
                or not element.CurrentIsEnabled or not element.CurrentHasKeyboardFocus
                or int(element.CurrentProcessId) != process
                or int(element.CurrentControlType) not in (50003, 50004, 50030)
                or not _is_writable(element, types)):
            return None
        if int(element.CurrentControlType) == 50030 and not element.GetCurrentPattern(10032):
            # A document can expose IsReadOnly=False as a default attribute
            # without actually accepting input. Require the TextEdit pattern
            # as additional evidence before treating a document as an editor.
            return None
        runtime_id = tuple(int(part) for part in element.GetRuntimeId())
        if (not runtime_id
                or not automation.CompareElements(element, automation.GetFocusedElement())
                or _foreground_process(expected_window) != process):
            return None
        return WindowsEditTarget(int(expected_window), process, runtime_id)
    except Exception as error:
        # As in the selection reader, keep handled COM exception frames here
        # so no pointer/traceback survives CoUninitialize in the caller.
        logger.debug("Editable target read failed (%s)", _discard_provider_error_frames(error))
    return None
