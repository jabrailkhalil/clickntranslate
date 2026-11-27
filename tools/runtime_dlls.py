"""Audit Windows runtime imports without relying on the build machine's DLLs."""
from pathlib import Path

SYSTEM = set('''advapi32 avrt bcrypt cabinet cfgmgr32 combase comctl32 comdlg32 crypt32
dbghelp dnsapi dwmapi dxgi d3d11 d3d12 d3dcompiler_47 gdi32 imagehlp imm32 iphlpapi kernel32 mf
mfplat mfreadwrite mfuuid mpr msi msvcrt netapi32 ntdll ole32 oleaut32 opengl32
powrprof propsys psapi rpcrt4 secur32 setupapi shell32 shlwapi user32 userenv usp10
version winhttp wininet winmm winspool wintrust wldap32 ws2_32 wtsapi32 ucrtbase'''.split())


def audit(runtime, entry_point='python.exe'):
    import pefile
    runtime = Path(runtime)
    binaries = sorted([*runtime.rglob('*.dll'), *runtime.rglob('*.pyd'), runtime / entry_point])
    paths = {path.name.lower():path for path in binaries}
    exports = {}
    imports = []
    for path in binaries:
        # CTranslate2 exports over 13k symbols; pefile's default 8192 cap
        # silently omits valid exports and would report a false ABI mismatch.
        binary = pefile.PE(str(path), fast_load=True, max_symbol_exports=65536)
        try:
            binary.parse_data_directories(directories=[0, 1])
            exports[path.name.lower()] = {item.name for item in getattr(
                getattr(binary, 'DIRECTORY_ENTRY_EXPORT', None), 'symbols', ()) if item.name}
            for entry in getattr(binary, 'DIRECTORY_ENTRY_IMPORT', ()):
                name = entry.dll.decode('ascii').lower()
                if name not in paths and name.removesuffix('.dll') not in SYSTEM and not name.startswith(('api-ms-win-', 'ext-ms-win-')):
                    raise RuntimeError('Runtime relies on an unbundled library: ' + name)
                imports.append((path.relative_to(runtime).as_posix(), name,
                                [item.name for item in entry.imports if item.name]))
        finally:
            binary.close()
    for source, name, symbols in imports:
        if name in exports:
            missing = set(symbols) - exports[name]
            if missing:
                raise RuntimeError(f'Bundled {name} lacks required exports for {source}: {len(missing)}')
    return {'binary_count':len(binaries),
            'required_system_libraries':sorted({name for _,name,_ in imports if name not in paths}),
            'unresolved_private_libraries':[]}
