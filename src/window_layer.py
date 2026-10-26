"""Repair Windows topmost state without activation or changing window geometry."""
from functools import lru_cache
import sys


@lru_cache(maxsize=1)
def _windows_api():
    if sys.platform != 'win32':
        return None
    import ctypes
    from ctypes import wintypes
    api = ctypes.WinDLL('user32', use_last_error=True)
    api.IsWindow.argtypes = [wintypes.HWND]
    api.IsWindow.restype = wintypes.BOOL
    get_style = getattr(api, 'GetWindowLongPtrW', api.GetWindowLongW)
    get_style.argtypes = [wintypes.HWND, ctypes.c_int]
    get_style.restype = ctypes.c_ssize_t
    api.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
    api.SetWindowPos.restype = wintypes.BOOL
    return api, get_style


def native_topmost(window_id):
    pair = _windows_api()
    if pair is None or not window_id or not pair[0].IsWindow(int(window_id)):
        return None
    return bool(pair[1](int(window_id), -20) & 0x00000008)  # GWL_EXSTYLE / WS_EX_TOPMOST


def synchronize_topmost(window_id, enabled):
    """Only repair drift. Repeated calls must not fight other topmost windows."""
    current = native_topmost(window_id)
    if current is None:
        return False
    enabled = bool(enabled)
    if current == enabled:
        return True
    api, _ = _windows_api()
    # NOMOVE | NOSIZE | NOACTIVATE | NOOWNERZORDER. Never SHOWWINDOW:
    # an OCR capture may have hidden the companion deliberately.
    if not api.SetWindowPos(int(window_id), -1 if enabled else -2, 0, 0, 0, 0, 0x0213):
        return False
    return native_topmost(window_id) == enabled
