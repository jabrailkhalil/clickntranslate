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


def _taskbar_above(window_id):
    """Inspect only overlapping shell taskbars, in native pixel coordinates."""
    pair = _windows_api()
    if pair is None:
        return False
    import ctypes
    from ctypes import wintypes
    api, _ = pair
    api.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
    api.GetWindow.restype = wintypes.HWND
    api.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    api.GetWindowRect.restype = wintypes.BOOL
    api.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    api.GetClassNameW.restype = ctypes.c_int
    api.IsWindowVisible.argtypes = [wintypes.HWND]
    api.IsWindowVisible.restype = wintypes.BOOL
    own = wintypes.RECT()
    if not api.GetWindowRect(window_id, ctypes.byref(own)):
        return False
    candidate = api.GetWindow(window_id, 3)  # GW_HWNDPREV: higher in Z order.
    visited = set()
    while candidate and candidate not in visited and len(visited) < 1024:
        visited.add(candidate)
        name = ctypes.create_unicode_buffer(128)
        api.GetClassNameW(candidate, name, len(name))
        if name.value in ('Shell_TrayWnd', 'Shell_SecondaryTrayWnd') and api.IsWindowVisible(candidate):
            rect = wintypes.RECT()
            if api.GetWindowRect(candidate, ctypes.byref(rect)) and (
                    rect.left < own.right and own.left < rect.right
                    and rect.top < own.bottom and own.top < rect.bottom):
                return True
        candidate = api.GetWindow(candidate, 3)
    return False


def synchronize_topmost(window_id, enabled, *, above_taskbar=False):
    """Repair drift, or an overlapping taskbar above a still-topmost companion.

    Ordinary topmost apps are never a reason to reorder an already correct
    window. The taskbar check runs only while the companion overlaps its strip.
    """
    current = native_topmost(window_id)
    if current is None:
        return False
    enabled = bool(enabled)
    if current == enabled and not (enabled and above_taskbar and _taskbar_above(window_id)):
        return True
    api, _ = _windows_api()
    # NOMOVE | NOSIZE | NOACTIVATE | NOOWNERZORDER. Never SHOWWINDOW:
    # an OCR capture may have hidden the companion deliberately.
    if not api.SetWindowPos(int(window_id), -1 if enabled else -2, 0, 0, 0, 0, 0x0213):
        return False
    return native_topmost(window_id) == enabled


def synchronize_no_activate(window_id, enabled):
    """Keep a mouse-operated palette from becoming the source of Ctrl+C.

    Qt 5's WindowDoesNotAcceptFocus does not consistently set this Windows
    extended style on a translucent tool window. Keep the native guarantee
    explicit, and remove it when the user invokes keyboard navigation.
    """
    pair = _windows_api()
    if pair is None or not window_id or not pair[0].IsWindow(int(window_id)):
        return False
    import ctypes
    from ctypes import wintypes
    api, get_style = pair
    style = get_style(int(window_id), -20)
    flag = 0x08000000  # WS_EX_NOACTIVATE.
    desired = style | flag if enabled else style & ~flag
    if style == desired:
        return True
    setter = getattr(api, 'SetWindowLongPtrW', None) or api.SetWindowLongW
    setter.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
    setter.restype = ctypes.c_ssize_t
    ctypes.set_last_error(0)
    previous = setter(int(window_id), -20, desired)
    if not previous and ctypes.get_last_error():
        return False
    # Apply cached frame styles without moving, raising, focusing or showing.
    if not api.SetWindowPos(int(window_id), 0, 0, 0, 0, 0, 0x0237):
        return False
    return bool(get_style(int(window_id), -20) & flag) == bool(enabled)
