"""Classify ClicknTranslate release attachments for downloads and in-app updates."""
import re


_VERSION = r'v?(?P<version>\d+(?:\.\d+){1,3}(?:-(?:alpha|beta|rc)\.?\d*)?(?:\+[a-z0-9.]+)?)'
_CPU = r'(?P<cpu>arm64|aarch64|x86[_-]64|amd64|x64|x86|armv7|universal)'
_ANDROID_CPU = r'(?P<cpu>arm64-v8a|armeabi-v7a|arm64|armv7|x86_64|x64|x86|universal)'
_PREFIX = r'click[-_]?n[-_]?translate[-_]'
_FORMATS = (
    ('Windows', 'Setup', rf'{_VERSION}-windows-{_CPU}-(?:installer|setup)\.exe'),
    ('Windows', 'Setup', rf'setup-{_VERSION}-(?P<cpu>win64|win32)\.exe'),
    ('Windows', 'MSIX', rf'{_VERSION}-(?:store-|windows-)?{_CPU}\.msix'),
    ('Windows', 'Portable ZIP', rf'{_VERSION}-windows-(?:portable-)?{_CPU}\.zip'),
    ('Windows', 'Portable ZIP', rf'{_VERSION}-windows-{_CPU}-portable\.zip'),
    ('Windows', 'Portable ZIP', rf'{_VERSION}-(?P<cpu>win64|win32)\.zip'),
    ('macOS', 'DMG', rf'{_VERSION}-macos-{_CPU}\.dmg'),
    ('macOS', 'App ZIP', rf'{_VERSION}-macos-{_CPU}\.zip'),
    ('Linux', 'AppImage', rf'{_VERSION}-linux-{_CPU}\.appimage'),
    ('Linux', 'tar.gz', rf'{_VERSION}-linux-{_CPU}\.tar\.gz'),
    ('Android', 'APK', rf'(?:android-)?{_VERSION}(?:-{_ANDROID_CPU})?\.apk'),
    ('Android', 'APK', rf'android-{_ANDROID_CPU}-{_VERSION}\.apk'),
)
_ARCHITECTURES = {
    'universal': 'Universal', 'arm64': 'ARM64', 'aarch64': 'ARM64', 'arm64-v8a': 'ARM64',
    'armeabi-v7a': 'ARMv7', 'armv7': 'ARMv7', 'x86_64': 'x64', 'x86-64': 'x64',
    'amd64': 'x64', 'win64': 'x64', 'win32': 'x86',
}
_HISTORIC_WINDOWS = {
    'clickntranslate-windows.zip': ('1.0.0',),
    'clickntranslate.zip': ('1.1', '1.2'),
}


def release_distribution(name, tag=None, *, allow_unversioned=False):
    """Return (OS, package format, architecture) for an application binary."""
    filename = name.lower()
    version = tag.lower().removeprefix('v') if tag else None
    if filename in _HISTORIC_WINDOWS:
        if version in _HISTORIC_WINDOWS[filename] or (allow_unversioned and version is None):
            return 'Windows', 'Portable ZIP', ''
        return None
    for platform, kind, pattern in _FORMATS:
        match = re.fullmatch(_PREFIX + pattern, filename)
        if match is not None:
            if version and version != match['version']:
                return None
            arch = match['cpu'] or ''
            return platform, kind, _ARCHITECTURES.get(arch, arch)
    if allow_unversioned:
        # Private update feeds can omit the version from the Windows ZIP name.
        match = re.fullmatch(_PREFIX + rf'windows-(?:portable-)?{_CPU}\.zip', filename)
        if match:
            arch = match['cpu']
            return 'Windows', 'Portable ZIP', _ARCHITECTURES.get(arch, arch)
    return None
