"""Portable, app-owned companion image gallery; never delete source files."""
import hashlib
import os
from pathlib import Path
import tempfile

EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}


def gallery_dir():
    from portable_paths import portable_base_dir
    return Path(portable_base_dir()) / 'data' / 'companion-images'


def image_reference(filename):
    path = Path(filename)
    if path.parent.resolve() == gallery_dir().resolve():
        return 'data/companion-images/' + path.name
    return str(filename)


def resolve_image(filename):
    path = Path(filename)
    if not path.is_absolute() and len(path.parts) == 3 and path.parts[:2] == ('data', 'companion-images'):
        return str(gallery_dir() / path.name)
    return str(filename)


def images():
    root = gallery_dir()
    if not root.is_dir():
        return []
    return sorted((p for p in root.iterdir() if p.is_file() and not p.is_symlink()
                   and p.suffix.lower() in EXTENSIONS), key=lambda p: p.name.casefold())


def import_image(filename):
    from assistant_art import load_custom_art, MAX_IMAGE_BYTES
    source = Path(filename)
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
    destination = root / (digest + '-' + source.stem[:100] + source.suffix.lower())
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
    if not path.is_symlink() and path.parent.resolve() == gallery_dir().resolve():
        path.unlink(missing_ok=True)
    from assistant_art import _read_custom_pixmap
    _read_custom_pixmap.cache_clear()
