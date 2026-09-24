"""Optional Windows double-tap shortcuts; one event-driven, non-blocking hook.

Only key codes and the current two-tap state are retained, never typed text.
The hook exists only while at least one double-tap shortcut is registered.
Native API contracts: https://learn.microsoft.com/windows/win32/winmsg/lowlevelkeyboardproc
"""
import logging
import sys
import threading
import time


TAP_INTERVAL = .45
MAX_HOLD = .30
_KEYS = {'Shift': 0x10, 'Ctrl': 0x11, 'Alt': 0x12,
         'Space': 0x20, 'Tab': 0x09, 'Backspace': 0x08, 'Enter': 0x0D,
         'Insert': 0x2D, 'Delete': 0x2E, 'Home': 0x24, 'End': 0x23,
         'PgUp': 0x21, 'PgDown': 0x22, 'Up': 0x26, 'Down': 0x28,
         'Left': 0x25, 'Right': 0x27, 'Pause': 0x13}
_KEYS.update({f'F{i}': 0x6F + i for i in range(1, 25)})
_KEYS.update({chr(i): i for i in (*range(48, 58), *range(65, 91))})
_NAMES = {name.casefold(): name for name in _KEYS}
_NAMES.update({'control': 'Ctrl', 'return': 'Enter', 'del': 'Delete', 'ins': 'Insert'})


def parse_double_tap(text):
    """Return (canonical key name, VK) only for two identical bare keys."""
    parts = str(text or '').split(',')
    if len(parts) != 2:
        return None
    names = [_NAMES.get(part.strip().casefold()) for part in parts]
    if names[0] is None or names[0] != names[1]:
        return None
    return names[0], _KEYS[names[0]]


def canonical_double_tap(text):
    parsed = parse_double_tap(text)
    return f'{parsed[0]}, {parsed[0]}' if parsed else None


def _normalized_vk(vk):
    return {0xA0: 0x10, 0xA1: 0x10, 0xA2: 0x11, 0xA3: 0x11,
            0xA4: 0x12, 0xA5: 0x12}.get(vk, vk)


class _TapState:
    def __init__(self):
        self.down = set()
        self.candidate = None
        self.previous = None

    def feed(self, key, pressed, now, foreground, watched, injected=False):
        if injected:
            self.candidate = self.previous = None
            return None
        vk = _normalized_vk(key)
        if pressed:
            if key in self.down:  # Auto-repeat and long holds are not taps.
                self.candidate = self.previous = None
                return None
            clean = not self.down and vk in watched
            self.down.add(key)
            self.candidate = (key, now, foreground) if clean else None
            if not clean or (self.previous and self.previous[0] != vk):
                self.previous = None
            return None
        self.down.discard(key)
        candidate = self.candidate
        self.candidate = None
        if (not candidate or candidate[0] != key or self.down
                or now - candidate[1] > MAX_HOLD or candidate[2] != foreground):
            self.previous = None
            return None
        previous = self.previous
        if (previous and previous[0] == vk and previous[2] == foreground
                and now - previous[1] <= TAP_INTERVAL):
            self.previous = None
            return vk
        self.previous = (vk, now, foreground)
        return None


class _HookThread(threading.Thread):
    def __init__(self):
        super().__init__(name='double-tap-shortcuts', daemon=True)
        self.targets = ()
        self.ready = threading.Event()
        self.cancelled = threading.Event()
        self.error = None
        self.thread_id = None
        self.user32 = None

    def stop(self):
        self.cancelled.set()
        if self.thread_id and self.user32:
            self.user32.PostThreadMessageW(self.thread_id, 0x0012, 0, 0)

    def run(self):
        import ctypes
        from ctypes import wintypes
        hook = None
        try:
            user = ctypes.WinDLL('user32', use_last_error=True)
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            self.user32 = user
            callback_type = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int,
                                               ctypes.c_size_t, ctypes.c_ssize_t)
            class KeyEvent(ctypes.Structure):
                _fields_ = [('vkCode', wintypes.DWORD), ('scanCode', wintypes.DWORD),
                            ('flags', wintypes.DWORD), ('time', wintypes.DWORD),
                            ('extraInfo', ctypes.c_size_t)]
            user.SetWindowsHookExW.argtypes = [ctypes.c_int, callback_type, wintypes.HINSTANCE, wintypes.DWORD]
            user.SetWindowsHookExW.restype = wintypes.HANDLE
            user.CallNextHookEx.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_size_t, ctypes.c_ssize_t]
            user.CallNextHookEx.restype = ctypes.c_ssize_t
            user.UnhookWindowsHookEx.argtypes = [wintypes.HANDLE]
            user.UnhookWindowsHookEx.restype = wintypes.BOOL
            user.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
            user.GetMessageW.restype = wintypes.BOOL
            user.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT]
            user.PeekMessageW.restype = wintypes.BOOL
            user.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, ctypes.c_size_t, ctypes.c_ssize_t]
            user.PostThreadMessageW.restype = wintypes.BOOL
            user.GetForegroundWindow.restype = wintypes.HWND
            user.GetAsyncKeyState.argtypes = [ctypes.c_int]
            user.GetAsyncKeyState.restype = ctypes.c_short
            kernel.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
            kernel.GetModuleHandleW.restype = wintypes.HMODULE
            kernel.GetCurrentThreadId.restype = wintypes.DWORD
            state = _TapState()
            # A one-time snapshot outside the callback avoids treating a key
            # held during registration as a fresh standalone tap.
            state.down = {vk for vk in range(8, 255) if vk not in (0x10, 0x11, 0x12)
                          and user.GetAsyncKeyState(vk) & 0x8000}

            @callback_type
            def callback(code, message, address):
                if code == 0 and message in (0x100, 0x101, 0x104, 0x105) and not self.cancelled.is_set():
                    try:
                        event = ctypes.cast(address, ctypes.POINTER(KeyEvent)).contents
                        targets = self.targets
                        fired = state.feed(event.vkCode, message in (0x100, 0x104),
                                           time.monotonic(), user.GetForegroundWindow(),
                                           {item[1] for item in targets}, bool(event.flags & 0x12))
                        if fired is not None:
                            for _, vk, dispatch in targets:
                                if vk == fired:
                                    dispatch()  # Queue a Qt signal only; no GUI work here.
                    except Exception:
                        state.candidate = state.previous = None
                # Never consume keys: OS shortcuts and normal typing continue.
                return user.CallNextHookEx(None, code, message, address)

            msg = wintypes.MSG()
            user.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)
            self.thread_id = kernel.GetCurrentThreadId()
            hook = user.SetWindowsHookExW(13, callback, kernel.GetModuleHandleW(None), 0)
            if not hook:
                raise ctypes.WinError(ctypes.get_last_error())
            self.ready.set()
            while not self.cancelled.is_set():
                result = user.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if result <= 0:
                    break
        except Exception as error:
            self.error = error
            logging.exception('Could not install double-tap shortcuts')
        finally:
            if hook:
                self.user32.UnhookWindowsHookEx(hook)
            self.ready.set()


class _Registry:
    def __init__(self):
        self._worker = None
        self._lock = threading.RLock()

    def register(self, text, callback):
        parsed = parse_double_tap(text)
        if sys.platform != 'win32' or parsed is None:
            raise ValueError('Double-tap shortcuts require Windows and two identical keys')
        with self._lock:
            worker = self._worker
            if worker is None or not worker.is_alive():
                worker = self._worker = _HookThread()
            if any(vk == parsed[1] for _, vk, _ in worker.targets):
                raise ValueError('Double-tap shortcut already registered')
            token = object()
            worker.targets = (*worker.targets, (token, parsed[1], callback))
            if worker.ident is None:
                worker.start()
            if not worker.ready.wait(2) or worker.error or not worker.is_alive():
                worker.stop()
                worker.join(timeout=2)
                self._worker = None
                raise RuntimeError('Could not register double-tap shortcut') from worker.error
            return token

    def unregister(self, token):
        with self._lock:
            worker = self._worker
            if worker is None:
                return
            worker.targets = tuple(item for item in worker.targets if item[0] is not token)
            if not worker.targets:
                worker.stop()
                worker.join(timeout=2)
                self._worker = None


_registry = _Registry()


def registry():
    return _registry
