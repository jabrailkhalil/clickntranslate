"""Unmodified companion artwork, decoded once and fitted by Qt at render time."""
from functools import lru_cache
from pathlib import Path
import sys

from PyQt5 import QtCore, QtGui


APPEARANCES = ('orb', 'portrait', 'star', 'sleep_icon', 'walking', 'custom')
STATIC_FILES = {'orb': 'purple-orb.png', 'portrait': 'kirby-stand.png', 'star': 'kirby-star.png', 'sleep_icon': 'kirby-sleep.png'}


def art_path(name):
    return str(Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent)) / 'icons/desktop-assistant' / name)


@lru_cache(maxsize=12)
def _read_pixmap(path, modified=0):
    reader = QtGui.QImageReader(path)
    reader.setAutoTransform(True)
    size = reader.size()
    if not size.isValid() or size.width() > 8192 or size.height() > 8192 or size.width() * size.height() > 32_000_000:
        return QtGui.QPixmap()
    reader.setScaledSize(size.scaled(512, 512, QtCore.Qt.KeepAspectRatio))
    return QtGui.QPixmap.fromImage(reader.read())


def companion_art(appearance, custom_image=''):
    if appearance == 'walking':
        # Match the runtime sprite's visible silhouette in the picker, without
        # modifying the GIF resource or showing a different 3D character.
        pixmap = _read_pixmap(art_path('kirby.gif'))
        if not pixmap.isNull():
            return pixmap.copy(QtGui.QRegion(pixmap.mask()).boundingRect())
    if appearance == 'custom':
        try:
            path = Path(custom_image)
            stat = path.stat()
            if stat.st_size <= 10_000_000:
                pixmap = _read_pixmap(str(path), stat.st_mtime_ns)
                if not pixmap.isNull():
                    return pixmap
        except (OSError, ValueError):
            pass
    filename = STATIC_FILES.get(appearance, 'purple-orb.png')
    return _read_pixmap(art_path(filename))
