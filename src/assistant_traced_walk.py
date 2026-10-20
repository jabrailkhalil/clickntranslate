"""Orbit material painted on the ten original, fixed frame contours.

Geometry is discrete: no rig, interpolation, centering or limb transforms.
The authoring GIF is not loaded by the application.
"""
from functools import lru_cache
import json
from pathlib import Path

from PyQt5 import QtCore, QtGui
from assistant_art import art_path


@lru_cache(maxsize=1)
def geometry():
    return json.loads(Path(art_path('orbit/walk-geometry.json')).read_text(encoding='utf-8'))


@lru_cache(maxsize=256)
def region_path(index, name):
    path = QtGui.QPainterPath()
    path.setFillRule(QtCore.Qt.OddEvenFill)
    for ring in geometry()['frames'][index][name]['contours']:
        if not ring:
            continue
        path.moveTo(*ring[0])
        for point in ring[1:]:
            path.lineTo(*point)
        path.closeSubpath()
    return path


def paint_orbit_frame(painter, target, index, *, decorations=True):
    """Paint all visible contours in a single constant coordinate system."""
    index %= 10
    frame = geometry()['frames'][index]
    left, top, right, bottom = geometry()['coordinates']['viewport']
    painter.save()
    scale = min(target.width() / (right-left), target.height() / (bottom-top))
    painter.translate(target.center().x() - scale*(left+right)/2,
                      target.center().y() - scale*(top+bottom)/2)
    painter.scale(scale, scale)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    painter.setPen(QtCore.Qt.NoPen)
    cx, crown = frame['core_top_anchor']

    if decorations:
        # One fixed antenna attached to the measured crown; no independent bob.
        painter.setPen(QtGui.QPen(QtGui.QColor('#5e514c'), .7))
        painter.setBrush(QtGui.QColor('#eee6d7'))
        painter.drawRoundedRect(QtCore.QRectF(cx-1, crown-5.8, 2, 6.2), .8, .8)
        glow = QtGui.QRadialGradient(cx-.7, crown-7, 3.1)
        glow.setColorAt(0, QtGui.QColor('#e9ffff'))
        glow.setColorAt(.4, QtGui.QColor('#6eecf5'))
        glow.setColorAt(1, QtGui.QColor('#0b839e'))
        painter.setBrush(glow)
        painter.drawEllipse(QtCore.QRectF(cx-2.3, crown-9, 4.6, 4.6))
        painter.setPen(QtCore.Qt.NoPen)

    shoes = QtGui.QLinearGradient(0, 42, 0, 64)
    shoes.setColorAt(0, QtGui.QColor('#64dce2'))
    shoes.setColorAt(.45, QtGui.QColor('#1996aa'))
    shoes.setColorAt(1, QtGui.QColor('#174857'))
    painter.fillPath(region_path(index, 'feet'), shoes)
    painter.fillPath(region_path(index, 'foot_light'), QtGui.QColor('#28b1c4'))
    painter.fillPath(region_path(index, 'foot_mid'), QtGui.QColor('#177d93'))
    painter.fillPath(region_path(index, 'foot_shadow'), QtGui.QColor('#17546a'))
    painter.fillPath(region_path(index, 'foot_ink'), QtGui.QColor('#203b49'))

    shell = QtGui.QRadialGradient(cx-9, crown+8, 51)
    shell.setColorAt(0, QtGui.QColor('#fffef4'))
    shell.setColorAt(.55, QtGui.QColor('#f4e7cf'))
    shell.setColorAt(1, QtGui.QColor('#b7a9a3'))
    body = region_path(index, 'body')
    painter.fillPath(body, shell)
    painter.fillPath(region_path(index, 'body_mid'), QtGui.QColor(196, 178, 165, 92))
    painter.fillPath(region_path(index, 'body_shade'), QtGui.QColor(140, 117, 110, 96))

    if decorations:
        # Keep the measured eye positions and profile visibility, but give
        # Orbit its own short, rounded eyes rather than the tall source eyes.
        eye_rects = []
        for eye in frame['eye_components']:
            x0, y0, x1, y1 = eye['bounds']
            center_x, center_y = (x0+x1)/2, (y0+y1)/2 + .5
            width, height = (x1-x0)*.92, 7.6
            eye_rects.append(QtCore.QRectF(center_x-width/2, center_y-height/2,
                                           width, height))
        eye_bounds = QtCore.QRectF(eye_rects[0])
        for eye in eye_rects[1:]:
            eye_bounds = eye_bounds.united(eye)
        mouth_x = frame['anchors']['mouth_center'][0]
        mouth_y = eye_bounds.center().y() + 6.2
        visor = QtCore.QRectF(eye_bounds.left()-2.8, eye_bounds.top()-2.2,
                             max(eye_bounds.right()+2.2, mouth_x+1.8)
                             - (eye_bounds.left()-2.8),
                             mouth_y+2 - (eye_bounds.top()-2.2))
        painter.save()
        painter.setClipPath(body)
        screen = QtGui.QLinearGradient(visor.topLeft(), visor.bottomRight())
        screen.setColorAt(0, QtGui.QColor('#355367'))
        screen.setColorAt(1, QtGui.QColor('#102637'))
        painter.setBrush(screen)
        painter.drawRoundedRect(visor, 4, 4)
        for eye in eye_rects:
            glow = QtGui.QRadialGradient(eye.center().x()-.5, eye.top()+2,
                                        eye.height()*.9)
            glow.setColorAt(0, QtGui.QColor('#b8ffff'))
            glow.setColorAt(.5, QtGui.QColor('#54e6f4'))
            glow.setColorAt(1, QtGui.QColor('#0facca'))
            painter.setBrush(glow)
            painter.drawEllipse(eye)
            painter.setBrush(QtGui.QColor('#efffff'))
            highlight_width = min(1.4, eye.width()*.27)
            painter.drawEllipse(QtCore.QRectF(eye.center().x()-highlight_width*.8,
                                              eye.top()+1.2, highlight_width, 1.5))
        smile = QtGui.QPainterPath()
        smile.moveTo(mouth_x-1, mouth_y-.35)
        smile.quadTo(mouth_x, mouth_y+1, mouth_x+1, mouth_y-.35)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.setPen(QtGui.QPen(QtGui.QColor('#7beffc'), .8,
                                 QtCore.Qt.SolidLine, QtCore.Qt.RoundCap))
        painter.drawPath(smile)
        painter.setPen(QtCore.Qt.NoPen)
        painter.restore()

    # Source ink defines all arm connections and occlusion. No new outline
    # stroke can make a hidden hand or shoe larger than its original region.
    painter.fillPath(region_path(index, 'body_ink'), QtGui.QColor('#796356'))
    painter.restore()


@lru_cache(maxsize=20)
def orbit_frame(index, side=192):
    image = QtGui.QImage(side, side, QtGui.QImage.Format_ARGB32_Premultiplied)
    image.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(image)
    paint_orbit_frame(painter, QtCore.QRectF(0, 0, side, side), index)
    painter.end()
    return QtGui.QPixmap.fromImage(image)
