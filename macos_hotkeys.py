"""Register only the requested macOS shortcuts; no keyboard monitoring hook.

Carbon's application event target is serviced by Qt's Cocoa event loop. All
registration and cleanup must run on the GUI thread, not a Python worker.
"""

import ctypes as C
import logging
import threading


# Physical ANSI key positions, matching the layout-independent Windows hotkeys.
# Spell out the sparse portion instead of treating macOS codes as ASCII.
KEY_CODES = {"a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5,
                  "z": 6, "x": 7, "c": 8, "v": 9, "b": 11,
                  "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17,
                  "1": 18, "2": 19, "3": 20, "4": 21, "6": 22, "5": 23,
                  "=": 24, "9": 25, "7": 26, "-": 27, "8": 28, "0": 29,
                  "]": 30, "o": 31, "u": 32, "[": 33, "i": 34, "p": 35,
                  "return": 36, "l": 37, "j": 38, "'": 39, "k": 40,
                  ";": 41, "\\": 42, ",": 43, "/": 44, "n": 45, "m": 46,
                  ".": 47, "tab": 48, "space": 49, "`": 50, "backspace": 51,
                  "escape": 53, "home": 115, "pageup": 116, "delete": 117,
                  "end": 119, "pagedown": 121, "left": 123, "right": 124,
                  "down": 125, "up": 126}
KEY_CODES.update(dict(zip((f"f{i}" for i in range(1, 21)),
                         (122, 120, 99, 118, 96, 97, 98, 100, 101, 109,
                          103, 111, 105, 107, 113, 106, 64, 79, 80, 90))))
ALIASES = {"enter": "return", "esc": "escape", "del": "delete", "pgup": "pageup", "pgdn": "pagedown"}
# Config uses QKeySequence.PortableText. Qt maps Ctrl to Command and Meta to
# physical Control on macOS; keep registration identical to its shortcut editor.
MODIFIERS = {"ctrl": 256, "control": 256, "alt": 2048, "option": 2048,
             "shift": 512, "cmd": 256, "command": 256, "meta": 4096,
             "win": 4096, "super": 4096}
CYRILLIC = dict(zip("йцукенгшщзфывапролджэячсмитьбюхъ", "qwertyuiopasdfghjkl;'zxcvbnm,.[]"))


def parse_hotkey(text):
    modifiers, keys = 0, []
    for part in str(text).lower().split("+"):
        token = part.strip()
        if token in MODIFIERS:
            modifiers |= MODIFIERS[token]
            continue
        token = ALIASES.get(token, CYRILLIC.get(token, token))
        if token not in KEY_CODES:
            raise ValueError(f"Unsupported macOS shortcut key: {part}")
        keys.append(KEY_CODES[token])
    if len(keys) != 1 or not modifiers:
        raise ValueError("A global shortcut needs modifiers and one main key.")
    return modifiers, keys[0]


def _fourcc(text):
    return int.from_bytes(text.encode("ascii"), "big")


class _HotkeyID(C.Structure):
    _fields_ = [("signature", C.c_uint32), ("id", C.c_uint32)]


class _EventType(C.Structure):
    _fields_ = [("event_class", C.c_uint32), ("kind", C.c_uint32)]


class HotkeyRegistry:
    def __init__(self):
        self.library = C.CDLL("/System/Library/Frameworks/Carbon.framework/Carbon")
        self.callbacks, self.references, self.pressed = {}, {}, set()
        self._next_id = 0
        self.signature = _fourcc("CnTr")
        lib = self.library
        callback_type = C.CFUNCTYPE(C.c_int32, C.c_void_p, C.c_void_p, C.c_void_p)
        signatures = {
            "GetApplicationEventTarget": (C.c_void_p, []),
            "GetEventKind": (C.c_uint32, [C.c_void_p]),
            "InstallEventHandler": (C.c_int32, [C.c_void_p, callback_type, C.c_uint32, C.POINTER(_EventType), C.c_void_p, C.POINTER(C.c_void_p)]),
            "RegisterEventHotKey": (C.c_int32, [C.c_uint32, C.c_uint32, _HotkeyID, C.c_void_p, C.c_uint32, C.POINTER(C.c_void_p)]),
            "UnregisterEventHotKey": (C.c_int32, [C.c_void_p]),
            "GetEventParameter": (C.c_int32, [C.c_void_p, C.c_uint32, C.c_uint32, C.c_void_p, C.c_uint32, C.c_void_p, C.c_void_p]),
        }
        for name, (result, args) in signatures.items():
            function = getattr(lib, name)
            function.restype, function.argtypes = result, args
        self._callback = callback_type(self._handle_event)  # retain for Carbon
        types = (_EventType * 2)(_EventType(_fourcc("keyb"), 6), _EventType(_fourcc("keyb"), 7))
        self._handler = C.c_void_p()
        status = lib.InstallEventHandler(lib.GetApplicationEventTarget(), self._callback,
                                         2, types, None, C.byref(self._handler))
        if status:
            raise RuntimeError(f"macOS hotkey handler failed ({status}).")

    def _handle_event(self, _handler, event, _data):
        identity = _HotkeyID()
        status = self.library.GetEventParameter(event, _fourcc("----"), _fourcc("hkid"),
                                               None, C.sizeof(identity), None, C.byref(identity))
        if status or identity.signature != self.signature or identity.id not in self.callbacks:
            return -9874  # eventNotHandledErr
        if self.library.GetEventKind(event) == 7:
            self.pressed.discard(identity.id)
        elif identity.id not in self.pressed:
            self.pressed.add(identity.id)
            try:
                self.callbacks[identity.id]()
            except Exception:
                logging.exception("macOS shortcut callback failed")
        return 0

    def register(self, text, callback):
        if threading.current_thread() is not threading.main_thread():
            raise RuntimeError("macOS hotkeys must be registered on the GUI thread.")
        modifiers, key = parse_hotkey(text)
        self._next_id += 1
        identifier = self._next_id
        reference = C.c_void_p()
        status = self.library.RegisterEventHotKey(key, modifiers, _HotkeyID(self.signature, identifier),
                                                  self.library.GetApplicationEventTarget(), 0, C.byref(reference))
        if status:
            raise RuntimeError(f"Shortcut is unavailable: {text} (macOS {status}).")
        self.references[identifier], self.callbacks[identifier] = reference, callback
        return identifier

    def unregister(self, identifier):
        reference = self.references.pop(identifier, None)
        self.callbacks.pop(identifier, None)
        self.pressed.discard(identifier)
        if reference is not None:
            self.library.UnregisterEventHotKey(reference)


_registry = None


def registry():
    global _registry
    if _registry is None:
        _registry = HotkeyRegistry()
    return _registry
