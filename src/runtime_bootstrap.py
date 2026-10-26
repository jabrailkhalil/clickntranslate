"""Load the declared private MSVC runtime before native SDK extensions."""
import json
import os
from pathlib import Path
import sys

_HANDLES = []
_INFO = None


def activate():
    global _INFO
    if _INFO is not None:
        return _INFO
    if os.name != 'nt' or getattr(sys, 'frozen', False):
        _INFO = {}
        return _INFO
    root = Path(sys.executable).resolve().parent
    marker = root / 'COMPONENT.json'
    if not marker.is_file() or not (root / 'python312._pth').is_file():
        _INFO = {}
        return _INFO
    value = json.loads(marker.read_text(encoding='utf-8'))
    if value.get('component') not in ('ocr.rapidocr', 'translation.argos'):
        _INFO = {}
        return _INFO
    import ctypes
    _HANDLES.append(os.add_dll_directory(str(root)))
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    query = kernel.GetModuleFileNameW
    query.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint]
    query.restype = ctypes.c_uint
    loaded = {}
    for name in ('msvcp140.dll', 'msvcp140_1.dll', 'msvcp140_2.dll'):
        library = root / name
        if not library.is_file():
            raise RuntimeError('Private MSVC runtime is missing: ' + name)
        handle = ctypes.WinDLL(str(library))
        _HANDLES.append(handle)
        buffer = ctypes.create_unicode_buffer(32768)
        if not query(handle._handle, buffer, len(buffer)) or Path(buffer.value).resolve() != library.resolve():
            raise RuntimeError('An external MSVC runtime was loaded: ' + name)
        loaded[name] = 'bundled'
    _INFO = loaded
    return _INFO
