"""Shared whole-frame companion playback and application activity state."""
from functools import lru_cache
import sys
from PyQt5 import QtCore, QtGui, sip
from assistant_art import mascot_id
from assistant_sprites import atlas, frame_index, paint_sprite, ROWS

WALK_FRAME_DURATIONS = ROWS['running-right'][1]
WALK_FRAME_NAMES = tuple(f'{index:02}' for index in range(len(WALK_FRAME_DURATIONS)))


def walk_frame_index(phase):
    return frame_index(WALK_FRAME_DURATIONS, (phase % 1) * sum(WALK_FRAME_DURATIONS) / 1000)


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
        self.gesture = ''
        self.gesture_age = 0.

    @property
    def phase(self):
        return self.walk_time / (sum(WALK_FRAME_DURATIONS) / 1000) % 1

    def interact(self):
        self.quiet = 0.

    def set_activity(self, activity):
        self.status = activity if activity in ('busy', 'waiting', 'success', 'error') else 'idle'
        self.status_age = 0.
        self.gesture = ''
        self.interact()

    def greet(self):
        if self.status not in ('busy', 'waiting'):
            self.gesture, self.gesture_age = 'wave', 0.

    def action(self, locomotion=True):
        if self.reactions:
            if self.status == 'busy':
                return 'work'
            if self.status == 'waiting':
                return 'waiting'
            if self.status == 'error' and self.status_age < 3:
                return 'error'
            if self.status == 'success' and self.status_age < 3:
                return 'success' if self.status_age < .84 else 'review'
            if self.gesture == 'wave' and self.gesture_age < .7:
                return 'wave'
            if self.quiet >= 45:
                return 'sleep'
            if 6 <= self.quiet < 6.7:
                return 'wave'
            if 8 <= self.quiet < 8.8:
                return 'curious'
        return 'walk' if locomotion else 'idle'

    def seconds(self, action):
        if action in ('work', 'waiting', 'error', 'success'):
            return self.status_age
        if action == 'review' and self.status == 'success':
            return max(0., self.status_age - .84)
        if action == 'wave':
            return self.gesture_age if self.gesture == 'wave' and self.gesture_age < .7 else self.quiet - 6
        if action == 'sleep':
            return max(0., self.quiet - 45)
        if action == 'curious':
            return max(0., self.quiet - 8)
        return self.walk_time if action == 'walk' else self.time

    def advance(self, dt, speed, extent, locomotion=True):
        dt = max(0., min(float(dt), .25))
        self.time += dt
        self.status_age += dt
        self.gesture_age += dt
        if self.status in ('success', 'error') and self.status_age >= 3:
            self.status = 'idle'
        if self.status != 'busy':
            self.quiet += dt
        if self.action(locomotion) != 'walk':
            return 0.
        self.walk_time += dt
        return max(0., speed) * dt

    def moved(self, pixels, extent):
        self.distance += abs(pixels) * 128 / max(1., extent)


def skin(mascot):
    """Shared decoded artwork used by both companion views."""
    return atlas(mascot)


@lru_cache(maxsize=6)
def walking_frames(mascot):
    artwork = atlas(mascot)
    return tuple(artwork.pixmap.copy(artwork.source('running-right', index=i)[1])
                 for i in range(len(WALK_FRAME_NAMES)))


def paint_pet(painter, rect, mascot, *, phase=0., time=0., action='idle', facing=1,
              expression='neutral', crawl_phase=0., gaze=None, state_time=None):
    state = {'work': 'running', 'success': 'jumping', 'error': 'failed',
             'wave': 'waving', 'drag': 'waiting', 'curious': 'waiting',
             'proud': 'review'}.get(action, action)
    seconds = time if state_time is None else state_time
    if action == 'walk':
        seconds = phase * sum(WALK_FRAME_DURATIONS) / 1000
    if expression != 'neutral' and action == 'idle' and gaze is None:
        pixmap = atlas(mascot).pose(expression)
        size = QtCore.QSizeF(pixmap.size()).scaled(rect.size(), QtCore.Qt.KeepAspectRatio)
        target = QtCore.QRectF(rect.center().x() - size.width()/2,
                             rect.bottom() - size.height(), size.width(), size.height())
        painter.save()
        painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
        painter.drawPixmap(target, pixmap, QtCore.QRectF(pixmap.rect()))
        painter.restore()
        return
    paint_sprite(painter, rect, mascot, state, seconds, facing=facing, gaze=gaze)


@lru_cache(maxsize=96)
def pose_pixmap(mascot, expression='neutral', special=''):
    return atlas(mascot).pose(expression, special)


def notify_activity(owner, activity, source='main'):
    """Main-thread notifications; concurrent jobs retain the working state."""
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
        helper.anchor._sync_motion()
        helper.anchor.update()
    preview = getattr(owner, 'assistant_preview', None)
    if preview is not None and not sip.isdeleted(preview):
        preview.motion.set_activity(state)
        preview._sync_animation()
        preview.button.update()


def notify_current_activity(activity, source, *, only_if_busy=False):
    """Optional GUI-thread activity bridge for capture and live overlays."""
    app = QtGui.QGuiApplication.instance()
    if app is None or QtCore.QThread.currentThread() != app.thread():
        return
    for name in ('main', '__main__'):
        owner = getattr(sys.modules.get(name), '_main_window_ref', None)
        if owner is None or sip.isdeleted(owner):
            continue
        if only_if_busy and source not in getattr(owner, '_companion_jobs', ()):
            return
        notify_activity(owner, activity, source)
        return
