"""Archived v7 walk experiment; the application uses complete v5 poses."""
from functools import lru_cache
import math
from PyQt5 import QtCore, QtGui
from assistant_art import art_path

NAMES = ('body', 'blink', 'arm-near', 'arm-far', 'foot-near', 'foot-far')
BODY_WIDTH = {'pancake': 100., 'mochi': 94., 'momo': 90., 'orbit': 86.}
FOOT_WIDTH = {'pancake': 36., 'mochi': 33., 'momo': 33., 'orbit': 32.}
ARM_WIDTH = {'pancake': 24., 'mochi': 21., 'momo': 24., 'orbit': 20.}
CONTACT = .60


@lru_cache(maxsize=4)
def layers(mascot):
    result = {name: QtGui.QPixmap(art_path(f'{mascot}/walk-layers/{name}.png')) for name in NAMES}
    return result if all(not image.isNull() for image in result.values()) else None


def smooth(t):
    return t*t*(3-2*t)


def foot(phase, stride):
    """A contact foot moves backward at exactly the body's travel speed."""
    cycle = phase % 1
    reach = stride*CONTACT/2
    if cycle < CONTACT:
        x = reach-stride*cycle
        if cycle < .08:
            roll = -5*(1-smooth(cycle/.08))
        elif cycle > CONTACT-.10:
            roll = 7*smooth((cycle-CONTACT+.10)/.10)
        else:
            roll = 0.
        return x, 0., roll
    t = (cycle-CONTACT)/(1-CONTACT)
    tangent = -stride*(1-CONTACT)
    # Match the planted foot's velocity on takeoff and landing. Both legs use
    # this same path, half a cycle apart, in the forward/back direction.
    x = -reach+2*reach*smooth(t)+tangent*(2*t**3-3*t*t+t)
    return x, -9.5*math.sin(math.pi*t)**2, 7-12*smooth(t)


def draw_part(painter, pixmap, rect):
    painter.drawPixmap(rect, pixmap, QtCore.QRectF(pixmap.rect()))


def paint_walk(painter, mascot, phase, stride):
    images = layers(mascot)
    if not images:
        return False
    width = BODY_WIDTH[mascot]
    body = images['body']
    height = width*body.height()/body.width()
    bob = 1.5*math.sin(phase*math.tau)**2
    bottom = 113.5-bob
    ground = 120.

    def draw_foot(near):
        x, y, roll = foot(phase+(0 if near else .5), stride)
        # A small depth offset, not two separate left/right lanes. Each foot
        # crosses beneath the body and alternates ahead of the other.
        center = 64+(2 if near else -2)+x
        paw = images['foot-near' if near else 'foot-far']
        w = FOOT_WIDTH[mascot]*(1 if near else .91)
        h = w*paw.height()/paw.width()
        pivot = w*.34*(1 if roll > 0 else -1)
        painter.save()
        painter.translate(center+pivot, ground+y)
        painter.rotate(roll)
        draw_part(painter, paw, QtCore.QRectF(-w/2-pivot, -h, w, h))
        painter.restore()

    def draw_arm(near):
        arm = images['arm-near' if near else 'arm-far']
        w = ARM_WIDTH[mascot]*(1 if near else .80)
        h = w*arm.height()/arm.width()
        swing = math.cos(phase*math.tau)*17*(1 if near else -1)
        painter.save()
        painter.translate(64+width*(-.34 if near else .38), bottom-height*.36)
        painter.rotate(swing)
        draw_part(painter, arm, QtCore.QRectF(-w*.45, -h*.14, w, h))
        painter.restore()

    draw_arm(False)
    painter.save()
    painter.translate(64, bottom)
    painter.rotate(.7+.65*math.sin(phase*math.tau))
    draw_part(painter, body, QtCore.QRectF(-width/2, -height, width, height))
    painter.restore()
    # The rounded belly used to hide the far foot's entire airborne arc.
    # Keep both feet visible, with the smaller far foot behind the near one.
    draw_foot(False)
    draw_arm(True)
    draw_foot(True)
    return True
