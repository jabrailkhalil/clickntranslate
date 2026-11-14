"""Inspect a QA-owned native child, without requiring administrator access."""
import ctypes
from ctypes import wintypes
from pathlib import Path


def private_modules(process, runtime):
    runtime=Path(runtime).resolve()
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    enum=kernel.K32EnumProcessModules
    enum.argtypes=[wintypes.HANDLE,ctypes.POINTER(ctypes.c_void_p),wintypes.DWORD,
                   ctypes.POINTER(wintypes.DWORD)]
    enum.restype=wintypes.BOOL
    filename=kernel.K32GetModuleFileNameExW
    filename.argtypes=[wintypes.HANDLE,ctypes.c_void_p,wintypes.LPWSTR,wintypes.DWORD]
    filename.restype=wintypes.DWORD
    modules=(ctypes.c_void_p*1024)();needed=wintypes.DWORD()
    if not enum(int(process._handle),modules,ctypes.sizeof(modules),ctypes.byref(needed)):
        return {}  # loader is still initializing; the QA caller polls briefly
    if needed.value>ctypes.sizeof(modules):raise RuntimeError('Native module list was truncated')
    expected={path.name.casefold() for path in runtime.rglob('*.dll')}
    result={}
    for module in modules[:needed.value//ctypes.sizeof(ctypes.c_void_p)]:
        name=ctypes.create_unicode_buffer(32768)
        if not filename(int(process._handle),module,name,len(name)):continue
        path=Path(name.value).resolve()
        if path.name.casefold() in expected:
            if not path.is_relative_to(runtime):
                raise RuntimeError('Native child used an external private dependency: '+path.name)
            result[path.name.casefold()]='bundled'
    return result
