"""Shared mascot poses, reference-timed walking and application reactions.

Four walkers use ten complete poses with the original GIF's frame timing.
Jelly creeps by extending, then drawing its back forward. Artwork is cached.
"""
from functools import lru_cache
from bisect import bisect_right
from itertools import accumulate
from typing import NamedTuple
import math

from PyQt5 import QtCore, QtGui, sip

from assistant_art import art_path, mascot_id

TAU = math.tau
STRIDE = 30.
CONTACT = .66
BODY_STATES = ('neutral', 'happy', 'curious', 'thinking', 'surprised', 'sad', 'sleepy', 'blink')
SPECIAL_STATES = ('sleep', 'proud', 'work-a', 'work-b')
PARTS = ('foot-left', 'foot-right', 'arm-left', 'arm-right')
WIDTHS = {'pancake': 88., 'mochi': 78., 'bubu': 84., 'momo': 78., 'orbit': 76.}
# Extracted from the original GIF: 10 frames, 110 ms each. The old QMovie
# kept this cadence independently of sprite size and screen travel speed.
WALK_FRAME_NAMES = tuple(f'{index:02}' for index in range(10))
WALK_FRAME_DURATIONS = (110,) * 10
WALK_FRAME_ENDS = tuple(accumulate(WALK_FRAME_DURATIONS))


def walk_frame_index(phase):
    elapsed = (phase % 1) * WALK_FRAME_ENDS[-1]
    return min(len(WALK_FRAME_ENDS)-1, bisect_right(WALK_FRAME_ENDS, elapsed))


class Gait(NamedTuple):
    stride: float
    contact: float
    hip: float
    clearance: float
    rise: float
    sway: float
    pace: float


GAITS = {
    'pancake': Gait(STRIDE, CONTACT, 17., 6.5, 2.2, 1.3, .52),
    'mochi': Gait(32., .60, 17., 8.0, 2.8, 1.0, .62),
    'momo': Gait(28., .64, 16., 6.0, 2.2, 1.2, .55),
    'orbit': Gait(30., .65, 17., 6.5, 1.5, .65, .58),
}


def _ease(t):
    t = max(0., min(1., t))
    return t*t*(3-2*t)


def foot_pose(phase, leg=0, mascot='pancake'):
    """Return foot offset and contact flag in a 128-unit character canvas."""
    gait = GAITS.get(mascot, GAITS['pancake'])
    cycle = (phase + leg * .5) % 1
    # Separate hips: feet never swap sides or cross through one another.
    hip = -gait.hip if leg else gait.hip
    reach = gait.stride*gait.contact/2
    if cycle < gait.contact:
        return hip + reach - gait.stride*cycle, 0., True
    swing = (cycle - gait.contact) / (1 - gait.contact)
    # Hermite swing joins the planted foot's velocity at both ends. The old
    # straight return abruptly reversed direction at toe-off and touchdown.
    tangent = -gait.stride*(1-gait.contact)
    x = -reach + 2*reach*_ease(swing) + tangent*(2*swing**3-3*swing**2+swing)
    y = -gait.clearance * math.sin(math.pi*swing)**2
    return hip+x, y, False


def foot_roll(phase, leg=0, mascot='pancake'):
    gait = GAITS.get(mascot, GAITS['pancake'])
    cycle = (phase + leg*.5) % 1
    if cycle < .1:
        return -6*(1-_ease(cycle/.1))  # Heel takes the weight, then sole settles.
    if cycle < gait.contact-.1:
        return 0.
    if cycle < gait.contact:
        return 9*_ease((cycle-gait.contact+.1)/.1)  # Push off the toes.
    return 9-15*_ease((cycle-gait.contact)/(1-gait.contact))


def crawl_progress(phase):
    """Extend with the back planted, contract with the front planted."""
    cycle = math.floor(phase)
    fraction = phase - cycle
    half = 0 if fraction < .5 else 1
    t = (fraction * 2) % 1
    eased = t*t*(3-2*t)
    return cycle + (half + eased) / 2


class PetMotion:
    def __init__(self, mascot):
        self.mascot = mascot_id(mascot)
        self.time = 0.
        self.distance = 0.
        self.walk_time = 0.
        self.crawl_phase = 0.
        self.quiet = 0.
        self.status = 'idle'
        self.status_age = 0.
        self.reactions = True

    @property
    def phase(self):
        return self.walk_time / (WALK_FRAME_ENDS[-1]/1000) % 1

    def interact(self):
        self.quiet = 0.

    def set_activity(self, activity):
        self.status = activity if activity in ('busy', 'success', 'error') else 'idle'
        self.status_age = 0.
        self.interact()

    def action(self):
        if not self.reactions:
            return 'walk'
        if self.status == 'busy':
            return 'work'
        if self.status in ('success', 'error') and self.status_age < 3:
            return self.status
        # Idle walking stays walking. Other poses are selected explicitly or
        # triggered by translation activity, never by an inactivity timer.
        return 'walk'

    def advance(self, dt, speed, extent):
        dt = max(0., min(float(dt), .25))
        self.time += dt
        self.status_age += dt
        if self.status != 'busy':
            self.quiet += dt
        if self.action() != 'walk':
            return 0.
        self.walk_time += dt
        if self.mascot == 'bubu':
            before = crawl_progress(self.crawl_phase)
            stride = WIDTHS['bubu'] * .25 * extent / 128
            self.crawl_phase += max(0., speed) * .4 * dt / max(1., stride)
            return (crawl_progress(self.crawl_phase) - before) * stride
        return max(0., speed) * dt

    def moved(self, pixels, extent):
        self.distance += abs(pixels) * 128 / max(1., extent)


@lru_cache(maxsize=5)
def skin(mascot):
    mascot = mascot_id(mascot)
    names = (*BODY_STATES, *SPECIAL_STATES, *PARTS)
    return {name: QtGui.QPixmap(art_path(f'{mascot}/rig/{name}.png')) for name in names}


@lru_cache(maxsize=4)
def walking_frames(mascot):
    # Use a whole sequence; never mix old and new poses on missing resources.
    for folder in ('walk-reference-frames', 'walk-frames'):
        frames = tuple(QtGui.QPixmap(art_path(f'{mascot}/{folder}/{name}.png'))
                       for name in WALK_FRAME_NAMES)
        if all(not frame.isNull() for frame in frames):
            return frames
    return ()


@lru_cache(maxsize=5)
def leg_ink(mascot):
    paw = skin(mascot)['foot-left'].toImage()
    return paw.pixelColor(paw.width()//2, paw.height()//2)


def _draw(painter, pixmap, x, y, width, angle=0., scale_y=1., opacity=1.):
    if pixmap.isNull():
        return
    height = width * pixmap.height() / pixmap.width()
    painter.save()
    painter.translate(x, y)
    painter.rotate(angle)
    painter.scale(1, scale_y)
    painter.setOpacity(opacity)
    painter.drawPixmap(QtCore.QRectF(-width/2, -height/2, width, height), pixmap,
                       QtCore.QRectF(pixmap.rect()))
    painter.restore()


def _draw_foot(painter, pixmap, x, ground, width, angle):
    """Roll around a heel/toe on the floor, not around a floating ankle."""
    height = width * pixmap.height() / max(1, pixmap.width())
    pivot = width*.32*(1 if angle > 0 else -1)
    painter.save()
    painter.translate(x+pivot, ground)
    painter.rotate(angle)
    painter.drawPixmap(QtCore.QRectF(-width/2-pivot, -height, width, height),
                       pixmap, QtCore.QRectF(pixmap.rect()))
    painter.restore()


def paint_pet(painter, rect, mascot, *, phase=0., time=0., action='idle', facing=1,
              expression='neutral', crawl_phase=0.):
    """Draw complete walking poses, grounded jelly motion or static layers."""
    mascot = mascot_id(mascot)
    images = skin(mascot)
    painter.save()
    painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
    painter.translate(rect.center())
    scale = min(rect.width(), rect.height()) / 128
    painter.scale(scale * facing, scale)
    painter.translate(-64, -64)
    width = WIDTHS[mascot]
    if action == 'walk' and mascot != 'bubu':
        frames = walking_frames(mascot)
        if frames:
            frame = frames[walk_frame_index(phase)]
            painter.drawPixmap(QtCore.QRectF(0, 0, 128, 128), frame, QtCore.QRectF(frame.rect()))
            painter.restore()
            return
    if action in ('sleep', 'proud', 'work'):
        key = {'sleep': 'sleep', 'proud': 'proud', 'work': 'work-a'}[action]
        source = images[key]
        w = min(104., 104 * source.width() / max(1, source.height()))
        # Keep a solid silhouette: blending separately generated faces makes
        # double eyes/hands. Tiny continuous gestures animate one clean pose.
        breathing = 1 + .012 * math.sin(time * 2) if action in ('sleep', 'work') else 1.
        angle = .8 * math.sin(time * 2.4) if action == 'work' else 0.
        _draw(painter, source, 64, 76, w, scale_y=breathing, angle=angle)
        if action == 'work':
            painter.setPen(QtCore.Qt.NoPen)
            for dot in range(3):
                alpha = int(90 + 130 * (1 + math.sin(time*4-dot)) / 2)
                painter.setBrush(QtGui.QColor(170, 205, 235, alpha))
                painter.drawEllipse(QtCore.QPointF(56+8*dot, 14), 1.5, 1.5)
        painter.restore()
        return
    if action in ('success', 'wave'):
        expression = 'happy'
    elif action == 'error':
        expression = 'sad'
    elif action == 'curious':
        expression = 'curious'
    elif action == 'drag':
        expression = 'surprised'
    elif action == 'walk' and time % 4.1 > 3.94:
        expression = 'blink'
    source = images.get(expression, images['neutral'])
    neutral = images['neutral']
    body_height = width * neutral.height() / max(1, neutral.width())
    expression_scale_y = body_height / (width * source.height() / max(1, source.width()))
    bottom = 112.
    angle = 0.
    sy = 1.
    sx = 1.
    lift = 0.
    weight_shift = 0.
    moving = action == 'walk'
    if mascot == 'bubu':
        bottom = 120.
        fraction = crawl_phase % 1
        if moving:
            t = fraction*2 if fraction < .5 else (1-fraction)*2
            extension = t*t*(3-2*t)
            sx = .88 + .25*extension
            sy = 1 - (sx-1)*.5
        elif action in ('success', 'wave'):
            sy = 1 + .035 * math.sin(time * 4)
            sx = 1 / math.sqrt(sy)
        painter.save()
        painter.translate(64, bottom)
        painter.scale(sx, sy)
        _draw(painter, source, 0, -body_height/2, width, scale_y=expression_scale_y)
        painter.restore()
        painter.restore()
        return
    if moving:
        gait = GAITS[mascot]
        support = math.sin(phase*TAU)
        # Lowest at contact, highest above the supporting leg. Shift the body
        # toward that leg while the other passes, with a small forward lean.
        lift = gait.rise * support**2
        weight_shift = gait.sway * support
        angle = .6 + gait.sway*.6*support
        expression_scale_y *= 1 - .012*(1-support**2)
    elif action == 'success':
        lift = 6 * abs(math.sin(time * 5))
    elif action == 'error':
        angle = -5
    def draw_foot(leg):
        x, y, planted = foot_pose(phase, leg, mascot) if moving else ((-16 if leg else 16), 0, True)
        foot = images[PARTS[leg]]
        foot_width = (19 if mascot == 'pancake' else 18) - (1.5 if moving and leg else 0)
        roll = foot_roll(phase, leg, mascot) if moving else 0
        _draw_foot(painter, foot, 64+x, 120+y-lift*(not moving), foot_width, roll)
    if moving:
        # Short bending ankles join the body to the planted paw. Much of each
        # leg is hidden by the body; without it the far shoe could float apart.
        for leg in (1, 0):
            x, y, _ = foot_pose(phase, leg, mascot)
            foot = images[PARTS[leg]]
            foot_height = 18*foot.height()/max(1, foot.width())
            hip_x = 64+weight_shift+(-1 if leg else 1)*gait.hip*.7
            hip_y = bottom-4-lift
            ankle_x, ankle_y = 64+x, 120+y-foot_height*.55
            joint = QtGui.QPainterPath(QtCore.QPointF(hip_x, hip_y))
            joint.quadTo((hip_x+ankle_x)/2-1.5, (hip_y+ankle_y)/2-1., ankle_x, ankle_y)
            ink = leg_ink(mascot)
            painter.setPen(QtGui.QPen(ink.darker(145), 6, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap))
            painter.drawPath(joint)
            painter.setPen(QtGui.QPen(ink, 4, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap))
            painter.drawPath(joint)
    draw_foot(1)
    if not moving:
        draw_foot(0)
    arm_phase = math.cos(phase*TAU) if moving else 0
    arm_swing = 10 * arm_phase
    arm_y = bottom - body_height*.28 - lift
    _draw(painter, images['arm-left'], 64+weight_shift-width*.44+2*arm_phase,
          arm_y, 14, angle=arm_swing)
    _draw(painter, source, 64+weight_shift, bottom-body_height/2-lift, width,
          angle=angle, scale_y=expression_scale_y)
    if moving:
        # The near paw passes in front of the belly; drawing both behind the
        # body hid the lifted step and made the character seem to glide.
        draw_foot(0)
    wave = action in ('success', 'wave')
    _draw(painter, images['arm-right'], 64+weight_shift+width*.44-2*arm_phase,
          arm_y-(13 if wave else 0), 15,
          angle=(-45+8*math.sin(time*5) if wave else -arm_swing))
    painter.restore()


@lru_cache(maxsize=80)
def pose_pixmap(mascot, expression='neutral', special=''):
    result = QtGui.QPixmap(192, 192)
    result.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(result)
    paint_pet(painter, QtCore.QRectF(0, 0, 192, 192), mascot,
              expression=expression, action=special or 'idle')
    painter.end()
    return result


def notify_activity(owner, activity, source='main'):
    """Main-thread notifications; concurrent document jobs retain busy state."""
    if owner is None:
        return
    jobs = getattr(owner, '_companion_jobs', None)
    if jobs is None:
        jobs = owner._companion_jobs = set()
    if activity == 'busy':
        jobs.add(source)
    else:
        jobs.discard(source)
    state = 'busy' if jobs else activity
    owner._companion_activity = state
    helper = getattr(owner, '_desktop_assistant', None)
    if helper is not None:
        helper.anchor.motion.set_activity(state)
        helper.anchor.update()
    preview = getattr(owner, 'assistant_preview', None)
    if preview is not None and not sip.isdeleted(preview):
        preview.motion.set_activity(state)
        preview.button.update()
