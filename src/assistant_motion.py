"""Shared whole-frame companion playback and application activity state."""
from functools import lru_cache
import sys
from PyQt5 import QtCore, QtGui, sip
from assistant_art import mascot_id
from assistant_sprites import atlas, frame_index, paint_sprite, ROWS, STATIONARY_STATES

WALK_FRAME_DURATIONS = ROWS['running-right'][1]
WALK_FRAME_NAMES = tuple(f'{index:02}' for index in range(len(WALK_FRAME_DURATIONS)))
IDLE_REST_SECONDS = 10.


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
        self.play('waving')

    def play(self, state):
        if state not in STATIONARY_STATES or self.status in ('busy', 'waiting'):
            return False
        if self.status in ('success', 'error'):
            self.status, self.status_age = 'idle', 0.
        self.gesture = {'waving': 'wave', 'jumping': 'success', 'running': 'work',
                        'failed': 'error'}.get(state, state)
        self.gesture_age = 0.
        self.interact()
        return True

    @property
    def gesture_duration(self):
        state = {'wave': 'waving', 'success': 'jumping', 'work': 'running',
                 'error': 'failed'}.get(self.gesture, self.gesture)
        return sum(ROWS.get(state, ROWS['idle'])[1]) / 1000

    def action(self, locomotion=False):
        if self.reactions:
            if self.status == 'busy':
                return 'work'
            if self.status == 'waiting':
                return 'waiting'
        if self.gesture and self.gesture_age < self.gesture_duration:
            return self.gesture
        if self.reactions:
            if self.status == 'error' and self.status_age < 3:
                return 'error'
            if self.status == 'success' and self.status_age < 3:
                return 'success' if self.status_age < .84 else 'review'
        return 'waiting' if getattr(self, 'menu_open', False) else 'idle'

    def seconds(self, action):
        if self.gesture == action and self.gesture_age < self.gesture_duration:
            return self.gesture_age
        if action in ('work', 'waiting', 'error', 'success'):
            return self.status_age
        if action == 'review' and self.status == 'success':
            return max(0., self.status_age - .84)
        if action == 'idle':
            # Hold the clean resting pose between natural, single-cycle idle
            # movements. Explicit clicks and translation reactions keep their
            # native timing instead of being slowed down with the idle loop.
            cycle = sum(ROWS['idle'][1]) / 1000
            elapsed = self.time % (IDLE_REST_SECONDS + cycle)
            return max(0., elapsed - IDLE_REST_SECONDS)
        return self.time

    def advance(self, dt, speed=0., extent=0., locomotion=False):
        dt = max(0., min(float(dt), .25))
        self.time += dt
        self.status_age += dt
        self.gesture_age += dt
        if self.status in ('success', 'error') and self.status_age >= 3:
            self.status = 'idle'
        if self.status != 'busy':
            self.quiet += dt
        return 0.

    def moved(self, pixels, extent):
        pass  # Compatibility for saved preview tools; companions never travel.


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
        state = 'idle'
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
        if helper.menu is not None:
            helper.menu.set_activity(state)
    preview = getattr(owner, 'assistant_preview', None)
    if preview is not None and not sip.isdeleted(preview):
        preview.set_activity(state)
        preview._sync_animation()
        for button in preview.buttons.values():
            button.update()
    stage = _settings_stage(owner)
    if stage is not None:
        stage.set_activity(state)


def _settings_stage(owner):
    settings = getattr(owner, 'settings_window', None) or getattr(owner, '_cached_settings_window', None)
    page = getattr(settings, 'settings_assistant_page', None)
    stage = getattr(page, 'mascot_preview', None)
    return stage if stage is not None and not sip.isdeleted(stage) else None


def play_reaction(owner, state, *, anchor=None, preview=None):
    """Explicit one-cycle reaction shared by the two stationary companions."""
    helper = getattr(owner, '_desktop_assistant', None)
    anchor = anchor if anchor is not None else getattr(helper, 'anchor', None)
    if anchor is not None:
        anchor.motion.play(state)
        anchor._sync_motion()
        anchor.update()
    preview = preview if preview is not None else getattr(owner, 'assistant_preview', None)
    if preview is not None and not sip.isdeleted(preview):
        preview.react(state)
    stage = _settings_stage(owner)
    if stage is not None:
        stage.react(state)


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
