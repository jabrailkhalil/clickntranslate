"""Read selected text from the foreground Windows control via UI Automation."""

from __future__ import annotations

import logging
import sys
import threading

logger = logging.getLogger("clickntranslate.selection")
_com_client = None
_bootstrap_attempted = False


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
    client = _com_client
    if client is None:
        return ""  # A pool worker must never become comtypes' first importer.
    import ctypes
    api = ctypes.WinDLL('ole32')
    api.CoInitializeEx.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    api.CoInitializeEx.restype = ctypes.c_long
    api.CoUninitialize.argtypes = []
    api.CoUninitialize.restype = None
    initialized = int(api.CoInitializeEx(None, 0))  # COINIT_MULTITHREADED
    if initialized not in (0, 1):  # S_OK and S_FALSE each own one reference.
        return ""
    try:
        return _read_initialized_selection(client)
    finally:
        api.CoUninitialize()


def _read_initialized_selection(client):
    """Keep all COM values and handled exception frames inside the owned scope."""
    try:
        types = client.GetModule('UIAutomationCore.dll')
        automation = client.CreateObject(types.CUIAutomation, interface=types.IUIAutomation)
        element = automation.GetFocusedElement()
        if element is None:
            return ""
        unknown = element.GetCurrentPattern(10014)  # UIA_TextPatternId
        if unknown is None:
            return ""
        text_pattern = unknown.QueryInterface(types.IUIAutomationTextPattern)
        ranges = text_pattern.GetSelection()
        if ranges is not None and int(getattr(ranges, "Length", 0) or 0) > 0:
            parts = []
            for index in range(int(ranges.Length)):
                parts.append(str(ranges.GetElement(index).GetText(-1) or ""))
            return "".join(parts).strip()
    except Exception as error:
        # Logging a traceback would retain this frame's COM pointers beyond
        # CoUninitialize. Store only a plain diagnostic string in log records.
        logger.debug("TextPattern selection read failed (%s)", type(error).__name__)
    return ""
