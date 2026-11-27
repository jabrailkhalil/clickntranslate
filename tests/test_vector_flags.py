"""Flags retain source detail at proxy zoom and physical display densities."""
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest
from PyQt5 import QtCore, QtGui, QtSvg

from icon_rendering import paint_icon, ScalableIconLabel, load_icon
from languages import LANGUAGES, language_icon_path
from project_paths import resource_root
from test_desktop_ux import app


@pytest.mark.parametrize('language', LANGUAGES, ids=lambda language: language.code)
def test_every_language_has_a_self_contained_vector_flag(app, language):
    path = resource_root()/language_icon_path(language.code)
    assert path.suffix == '.svg' and path.is_file()
    document = ET.fromstring(path.read_bytes())
    assert document.attrib['viewBox'] == '0 0 90 80'
    assert all(node.tag.rsplit('}', 1)[-1] not in ('script', 'image', 'foreignObject', 'marker')
               for node in document.iter())
    assert QtSvg.QSvgRenderer(str(path)).isValid()
    image = load_icon(str(path)).pixmap(240, 240).toImage()
    assert image.width() >= 200 and image.height() >= 200
    assert image.pixelColor(0, 0).alpha() == 0
    assert any(image.pixelColor(x, y).alpha() > 200
               for x in range(40, 180, 20) for y in range(40, 180, 20))
    sources = json.loads((path.parent/'vector-sources.json').read_text())
    assert hashlib.sha256(path.read_bytes()).hexdigest() == sources['files'][path.stem]['bundled_sha256']
    assert 'Copyright (c) 2013 Panayiotis Lipiridis' in (path.parent/'LICENSE.txt').read_text()


def test_us_flag_renders_all_fifty_stars_not_just_an_empty_canton(app):
    image = load_icon(str(resource_root()/language_icon_path('en'))).pixmap(900, 800).toImage()
    stars = {(x, y) for y in range(115, 415) for x in range(75, 495)
             if min(image.pixelColor(x, y).red(), image.pixelColor(x, y).green(),
                    image.pixelColor(x, y).blue()) > 245}
    components = 0
    while stars:
        pending = [stars.pop()]
        touches_crop_edge = False
        while pending:
            x, y = pending.pop()
            touches_crop_edge |= x in (75, 494) or y in (115, 414)
            for neighbor in ((x+dx, y+dy) for dx in (-1,0,1) for dy in (-1,0,1) if dx or dy):
                if neighbor in stars:
                    stars.remove(neighbor)
                    pending.append(neighbor)
        # The rounded white frame can enter the crop at its top-left edge;
        # stars are the enclosed white components within the blue canton.
        components += not touches_crop_edge
    assert components == 50


class RecordingIcon(QtGui.QIconEngine):
    def __init__(self, sizes):
        super().__init__()
        self.sizes = sizes

    def clone(self):
        return RecordingIcon(self.sizes)

    def pixmap(self, size, mode, state):
        self.sizes.append(QtCore.QSize(size))
        pixels = QtGui.QPixmap(size)
        pixels.fill(QtCore.Qt.blue)
        return pixels


@pytest.mark.parametrize('zoom', [.8, 1, 1.37, 2, 3])
@pytest.mark.parametrize('dpr', [1, 1.25, 2, 3])
def test_icon_uses_actual_painter_density_once(app, zoom, dpr):
    sizes = []
    icon = QtGui.QIcon(RecordingIcon(sizes))
    image = QtGui.QImage(300, 300, QtGui.QImage.Format_ARGB32_Premultiplied)
    image.setDevicePixelRatio(dpr)
    image.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(image)
    painter.scale(zoom, zoom)
    paint_icon(painter, icon, QtCore.QRectF(0, 0, 20, 20))
    painter.end()
    expected = math.ceil(20*zoom*dpr)
    assert sizes[-1] == QtCore.QSize(expected, expected)
    assert image.pixelColor(min(expected//2, 299), min(expected//2, 299)) == QtGui.QColor('blue')


def test_interface_flag_label_keeps_the_vector_until_paint(app):
    sizes = []
    label = ScalableIconLabel(QtGui.QIcon(RecordingIcon(sizes)))
    label.setFixedSize(18, 18)
    image = QtGui.QImage(180, 180, QtGui.QImage.Format_ARGB32_Premultiplied)
    image.setDevicePixelRatio(2)
    image.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(image)
    painter.scale(3, 3)
    label.render(painter)
    painter.end()
    assert sizes[-1] == QtCore.QSize(108, 108)
    label.deleteLater()
