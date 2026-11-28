"""Portable, app-owned companion image gallery; never delete source files."""
import hashlib
import os
from pathlib import Path
import tempfile

EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}


def _filesystem_path(path):
    path = Path(path)
    if os.name == 'nt':
        absolute = os.path.abspath(path)
        # A portable install can live in a deep directory even when the
        # Windows machine has not enabled long paths in its registry.
        if not absolute.startswith('\\\\?\\') and len(absolute.encode('utf-16-le', 'surrogatepass')) >= 248 * 2:
            return Path('\\\\?\\UNC\\' + absolute[2:] if absolute.startswith('\\\\') else '\\\\?\\' + absolute)
    return path


def gallery_dir():
    from portable_paths import portable_base_dir
    return _filesystem_path(Path(portable_base_dir()) / 'data' / 'companion-images')


def _in_gallery(path):
    try:
        return _filesystem_path(path.parent).samefile(gallery_dir())
    except FileNotFoundError:
        return False


def image_reference(filename):
    path = Path(filename)
    if _in_gallery(path):
        return 'data/companion-images/' + path.name
    return str(filename)


def resolve_image(filename):
    if filename == '':
        return ''
    path = Path(filename)
    if not path.is_absolute() and len(path.parts) == 3 and path.parts[:2] == ('data', 'companion-images'):
        path = gallery_dir() / path.name
    return str(_filesystem_path(path))


def images():
    root = gallery_dir()
    if not root.is_dir():
        return []
    entries = (_filesystem_path(entry) for entry in root.iterdir())
    return sorted((p for p in entries if p.is_file() and not p.is_symlink()
                   and p.suffix.lower() in EXTENSIONS), key=lambda p: p.name.casefold())


def import_image(filename):
    from assistant_art import load_custom_art, MAX_IMAGE_BYTES
    source = _filesystem_path(filename)
    load_custom_art(str(source))
    # Enforce the bound on the actual read too (the file may have changed).
    with source.open('rb') as stream:
        content = stream.read(MAX_IMAGE_BYTES + 1)
    if len(content) > MAX_IMAGE_BYTES:
        raise ValueError('Image exceeds the companion image size limit')
    root = gallery_dir()
    root.mkdir(parents=True, exist_ok=True)
    # Retain the user's filename for a readable selector, deduplicate content.
    digest = hashlib.sha256(content).hexdigest()
    existing = next((p for p in images() if p.name.startswith(digest + '-')), None)
    if existing is not None:
        return str(existing)
    suffix = source.suffix.lower()
    # The SHA prefix is part of the 255-byte component limit on portable
    # filesystems. CJK characters and emoji can each take several bytes.
    name_budget = 255 - len((digest + '-' + suffix).encode('utf-8'))
    stem = source.stem[:100].encode('utf-8')[:name_budget].decode('utf-8', errors='ignore')
    destination = _filesystem_path(root / (digest + '-' + stem + suffix))
    fd, staging = tempfile.mkstemp(prefix='.image-', dir=root)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
        # Decode the copied bytes before publishing, including a racing writer.
        load_custom_art(staging)
        os.replace(staging, destination)
    finally:
        Path(staging).unlink(missing_ok=True)
    return str(destination)


def display_name(filename):
    name = Path(filename).name
    return name[65:] if len(name) > 65 and name[64] == '-' else name


def remove_image(filename):
    path = Path(resolve_image(filename))
    # Legacy paths outside the library are references, never deletion targets.
    if not path.is_symlink() and _in_gallery(path):
        path.unlink(missing_ok=True)
    from assistant_art import _read_custom_pixmap
    _read_custom_pixmap.cache_clear()
