"""Companion artwork, decoded once and fitted by Qt at render time."""
from functools import lru_cache
from pathlib import Path
import sys

from PyQt5 import QtCore, QtGui


MASCOTS = ('pancake', 'mochi', 'bubu', 'momo', 'orbit')
DEFAULT_MASCOT = MASCOTS[0]
APPEARANCES = ('portrait', 'happy', 'curious', 'thinking', 'surprised', 'sad',
               'sleep_alt', 'sleep_icon', 'star', 'hero', 'working', 'walking', 'custom')
EXPRESSIONS = {'portrait': 'neutral', 'happy': 'happy', 'curious': 'curious',
               'thinking': 'thinking', 'surprised': 'surprised', 'sad': 'sad',
               'sleep_alt': 'sleepy'}
SPECIAL_POSES = {'sleep_icon': 'sleep', 'star': 'proud', 'hero': 'success', 'working': 'work'}
MAX_IMAGE_BYTES = 10_000_000
MAX_IMAGE_SIDE = 8192


class ImageLoadError(ValueError):
    def __init__(self, reason, **details):
        super().__init__(reason)
        self.reason = reason
        self.details = details


def art_path(name):
    return str(Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent)) / 'icons/desktop-assistant' / name)


def mascot_id(value):
    return value if value in MASCOTS else DEFAULT_MASCOT


def walking_art_path(mascot=DEFAULT_MASCOT):
    return art_path(f'{mascot_id(mascot)}/walk.gif')


def _decode_pixmap(path):
    reader = QtGui.QImageReader(path)
    reader.setAutoTransform(True)
    if not reader.canRead():
        raise ImageLoadError('image_decode', detail=reader.errorString())
    size = reader.size()
    if not size.isValid():
        raise ImageLoadError('image_decode', detail=reader.errorString())
    if size.width() > MAX_IMAGE_SIDE or size.height() > MAX_IMAGE_SIDE:
        raise ImageLoadError('image_dimensions', width=size.width(), height=size.height(), limit=MAX_IMAGE_SIDE)
    # JPEG supports reduced-resolution decoding. Allow large photos without
    # expanding every source pixel into the desktop companion's image cache.
    scaled_jpeg = (bytes(reader.format()).lower() in (b'jpeg', b'jpg')
                   and reader.supportsOption(QtGui.QImageIOHandler.ScaledSize))
    pixel_limit = 64_000_000 if scaled_jpeg else 32_000_000
    pixels = size.width() * size.height()
    if pixels > pixel_limit:
        raise ImageLoadError('image_pixels', pixels=pixels/1_000_000, limit=pixel_limit/1_000_000)
    if max(size.width(), size.height()) > 512:
        reader.setScaledSize(size.scaled(512, 512, QtCore.Qt.KeepAspectRatio))
    image = reader.read()
    if image.isNull():
        raise ImageLoadError('image_decode', detail=reader.errorString())
    return QtGui.QPixmap.fromImage(image)


@lru_cache(maxsize=36)
def _read_pixmap(path, modified=0):
    return _decode_pixmap(path)


@lru_cache(maxsize=1)
def _read_custom_pixmap(path, modified):
    # Selecting another image releases the previous custom thumbnail cache.
    return _decode_pixmap(path)


def load_custom_art(filename):
    path = Path(filename)
    try:
        stat = path.stat()
        if not path.is_file():
            raise ImageLoadError('image_missing')
    except FileNotFoundError as error:
        raise ImageLoadError('image_missing') from error
    except OSError as error:
        raise ImageLoadError('image_unreadable', detail=str(error)) from error
    if stat.st_size > MAX_IMAGE_BYTES:
        raise ImageLoadError('image_too_large', size=stat.st_size/1_000_000, limit=MAX_IMAGE_BYTES/1_000_000)
    return _read_custom_pixmap(str(path), stat.st_mtime_ns)


def companion_art(appearance, custom_image='', mascot=DEFAULT_MASCOT):
    if appearance == 'custom':
        try:
            return load_custom_art(custom_image)
        except (OSError, ValueError):
            pass
    from assistant_motion import pose_pixmap
    if appearance == 'walking':
        return pose_pixmap(mascot_id(mascot), special='walk')
    return pose_pixmap(mascot_id(mascot), EXPRESSIONS.get(appearance, 'neutral'),
                       SPECIAL_POSES.get(appearance, ''))
