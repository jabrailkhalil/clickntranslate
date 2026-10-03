"""Pancake walk study: stable artwork following closed reference trajectories.

This is opt-in in the Python comparison tool, not the production renderer.
Coordinates below are landmarks in the 114 x 105 local reference GIF.
Visible shoe centres were measured from its colour regions; occluded shoes,
body centres and arm attachments were annotated by eye. They are not an
automatic or exact reconstruction of the source animation.
V10 adapts the near shoe path and projected proportions from the preferred
drawn v8 poses, while keeping the periodic interpolation introduced in v9.
V11 rounds the acceleration changes in those same paths with a periodic
cubic B-spline. V9 and V10 remain available for visual comparison.
V12 attaches the near arm to one shoulder and swings it as a constant-length
limb; the shoulder follows the torso's turn instead of an independent path.
Its torso keeps more width in profile and both shoes are ten percent larger.
V13 adds a soft ground shadow to the same motion and proportions.
V14 uses rounder limb artwork and continuous partial occlusion by the belly.
V15 restores the earlier shoes and limits occlusion to the backward step.
"""
from functools import lru_cache
import math

from PyQt5 import QtCore, QtGui
from assistant_art import art_path

CYCLE_SECONDS = 1.1
KEY_COUNT = 10

# Every curve is periodic, including its tangent at the 9 -> 0 boundary.
# A shoe keeps its identity throughout the cycle, even when hidden by the body.
BODY_X = (63., 63.5, 63., 62., 63., 63., 62., 62., 62., 62.)
BODY_Y = (79.5, 78.5, 76.5, 74.5, 75.5, 77.5, 75., 76., 75., 76.)
YAW = (0., .06, .45, 1., .60, .08, -.10, -.16, -.16, -.06)
NEAR_X = (61.9, 54.8, 51.1, 43.5, 43., 53.4, 55.8, 63.1, 74.3, 72.3)
# The short torso needs a lower forward toe angle and lift than the round
# source character. Contact phases and horizontal paths are preserved.
NEAR_ROLL = (0., 9., 25., 55., 66., 12., 0., -18., -36., 0.)
NEAR_LIFT = (0., 0., 0., 0., 0., 3.5, 4.5, 6., 5., 0.)
NEAR_WIDTH = (26., 25., 25., 23., 22., 26., 27., 27., 25., 26.)
FAR_X = (65., 77.3, 79.2, 84., 79.6, 75.3, 65.7, 53.8, 51.7, 49.)
FAR_ROLL = (-28., -8., -22., -30., 0., 0., 3., 7., 30., 48.)
FAR_LIFT = (8., 5., 6., 7., 0., 0., 0., 0., 0., 0.)
ARM_ROOT_X = (50., 52., 57., 62., 58., 49., 47., 46., 44., 48.)
ARM_ROOT_Y = (78., 75., 72., 68., 72., 76., 72., 73., 72., 75.)
ARM_PALM_X = (46.5, 51., 61., 67., 63., 46., 42., 40., 38., 44.)
ARM_PALM_Y = (88., 87., 86., 79., 83., 88., 87., 87., 82., 88.)
FAR_ARM_X = (80., 79., 80., 79., 80., 83., 87., 88., 89., 87.)
FAR_ARM_Y = (87., 84., 79., 77., 83., 88., 86., 83., 81., 88.)

# Measured from the downward hanging arm: positive angles swing backward.
# The arm leads while the near foot is behind, and trails during its forward
# swing. Unlike the older palm/root tracks this cannot lengthen or slide it.
NEAR_ARM_SWING = (10., -2., -30., -58., -38., 8., 28., 43., 42., 20.)
NEAR_SHOE_DEPTH = (.68, .52, .28, .12, .18, .62, .82, .94, .95, .84)
CLASSIC_SHOE_DEPTH = (.99, .99, .97, .04, .08, .97, .99, .99, .99, .99)
VOLUME_NEAR_DEPTH = (.48, .50, .53, .67, .68, .57, .54, .54, .54, .47)
VOLUME_FAR_DEPTH = (.58, .54, .52, .54, .47, .47, .49, .51, .54, .59)
VOLUME_NEAR_ROLL = (0., 8., 28., 30., 70., -10., -7., -24., -32., -3.)

# V10 keeps the closed curves, but restores the stronger shoe silhouettes and
# body response of the drawn poses. Values describe projection/weight transfer,
# not a new independently drawn foot on each frame. V9 remains selectable.
LIVELY = {
    # Adapted from the preferred v8 shoe centres. Keep a backward-moving
    # contact foot across 9 -> 0 -> 1, instead of v8's near-identical 0 and 1.
    'near_x': (62., 58., 53.85, 50.45, 46.5, 58.9, 61.3, 72., 74.1, 71.1),
    'near_roll': (0., 8., 28., 30., 70., -10., -7., -26., -38., -3.),
    'near_width': (24.5, 24., 25., 17.5, 17.5, 24., 26.5, 27., 27., 26.),
    'near_depth': (.39, .42, .47, .65, .65, .54, .50, .55, .57, .39),
    'near_lift': (0., 0., 0., 0., 0., 2., 6., 5., 4., 0.),
    'far_roll': (-32., -10., -27., -39., -3., 0., 4., 10., 33., 54.),
    'far_width': (22., 23., 24., 25., 25., 24., 23., 22., 21., 20.),
    'far_depth': (.55, .50, .46, .49, .38, .39, .41, .43, .47, .55),
    'far_lift': (9., 7., 8., 6., 0., 0., 0., 0., 0., 0.),
    'squash': (.975, 1., 1.025, 1.035, 1., .975, 1., 1.025, 1.025, .98),
    'lean': (0., -1., -2.5, -3., -1., 0., 1., 2.5, 2., 1.),
    'arm_width': (23., 24., 25., 27., 26., 23., 24., 26., 27., 24.),
    'arm_height': (26., 26., 25., 22., 24., 27., 27., 25., 23., 26.),
}


def sample(values, phase):
    """Periodic monotone cubic Hermite interpolation, without pose overshoot.

    Tangents are shared by the two adjacent intervals. The same rule is used
    across the loop seam, rather than easing each frame separately to a stop.
    """
    position = (phase % 1.) * len(values)
    index = math.floor(position)
    t = position - index
    count = len(values)

    def tangent(i):
        previous = values[i % count] - values[(i-1) % count]
        following = values[(i+1) % count] - values[i % count]
        if previous * following <= 0.:
            return 0.
        return 2. * previous * following / (previous + following)

    start, end = values[index], values[(index+1) % count]
    return ((2*t**3-3*t*t+1)*start + (t**3-2*t*t+t)*tangent(index)
            + (-2*t**3+3*t*t)*end + (t**3-t*t)*tangent(index+1))


@lru_cache(maxsize=64)
def smooth_controls(values):
    """Two control points per source pose retain the lively step's shape.

    The denser old trajectory limits damping of the extremes and narrows the
    smoothing window to roughly one third of a pose, with no new independent
    pose drawings.
    """
    count = len(values)*2
    return tuple(sample(values, index/count) for index in range(count))


def smooth_sample(values, phase):
    """Periodic cubic B-spline: continuous position, velocity and acceleration."""
    controls = smooth_controls(values)
    position = (phase % 1.)*len(controls)
    index = math.floor(position)
    t = position-index
    weights = ((1-t)**3, 3*t**3-6*t*t+4, -3*t**3+3*t*t+3*t+1, t**3)
    return sum(controls[(index+offset-1) % len(controls)]*weight
               for offset, weight in enumerate(weights))/6.


def swing_gate(phase, near):
    """Round takeoff/landing while preserving the original planted intervals.

    Smoothing a lift curve alone would lift both feet during weight transfer.
    This C2 envelope leaves the stance exactly at zero without a hard clamp.
    """
    start = .4 if near else .9
    elapsed = (phase-start) % 1.
    if elapsed >= .5:
        return 0.

    def ramp(t):
        if t >= 1.:
            return 1.
        return t*t*t*(10.+t*(-15.+6.*t))

    return ramp(elapsed/.075)*ramp((.5-elapsed)/.075)


@lru_cache(maxsize=4)
def artwork(volume=False, classic_shoes=False):
    images = {name: QtGui.QPixmap(art_path(f'pancake/cycle-layers/{name}.png'))
              for name in ('body', 'face', 'arm-near', 'arm-far')}
    images.update({name: QtGui.QPixmap(art_path(f'pancake/walk-layers/{name}.png'))
                   for name in ('foot-near', 'foot-far')})
    if volume:
        images.update({name: QtGui.QPixmap(art_path(f'pancake/volume-layers/{name}.png'))
                       for name in (('arm-near', 'arm-far') if classic_shoes else
                                    ('foot-near', 'foot-far', 'arm-near', 'arm-far'))})
    return images


@lru_cache(maxsize=8)
def sole_outline(name, volume=False, classic_shoes=False):
    """Convex outline of the actual foot alpha, in centred texture units."""
    image = artwork(volume, classic_shoes)[name].toImage().convertToFormat(QtGui.QImage.Format_RGBA8888)
    width, height = image.width(), image.height()
    alpha = image.constBits().asstring(image.byteCount())
    stride = image.bytesPerLine()
    points = []
    for y in range(height):
        occupied = [x for x in range(width) if alpha[y*stride+x*4+3] >= 128]
        if occupied:
            for x in (occupied[0], occupied[-1]):
                points.append(((x+.5)/width-.5, (y+.5)/height-.5))
    points = sorted(set(points))

    def cross(o, a, b):
        return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])

    lower, upper = [], []
    for point in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    for point in reversed(points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return tuple(lower[:-1]+upper[:-1])


def paint_pancake(painter, rect, phase, facing=1, landmarks=False, version='v15'):
    """Render the existing layered artwork into a stable 128-unit canvas."""
    classic_shoes = version == 'v15'
    volume = version in ('v14', 'v15')
    images = artwork(volume, classic_shoes)
    if any(image.isNull() for image in images.values()):
        return False
    painter.save()
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
    painter.translate(rect.x(), rect.y())
    painter.scale(rect.width()/128., rect.height()/128.)
    if facing < 0:
        painter.translate(128., 0.)
        painter.scale(-1., 1.)

    anchored = version in ('v12', 'v13', 'v14', 'v15')
    softened = version in ('v11', 'v12', 'v13', 'v14', 'v15')
    lively = version in ('v10', 'v11', 'v12', 'v13', 'v14', 'v15')
    curve = smooth_sample if softened else sample
    bx, by = curve(BODY_X, phase), curve(BODY_Y, phase)
    center_x = 64. + (bx-63.)*2.
    # Slightly raise the torso to sit on the larger v12 shoes.
    center_y = (75.7 if classic_shoes else 75. if volume else 76.5 if anchored else 78. if lively else 83.) + (by-79.5)*2.
    yaw = curve(YAW, phase)
    squash = curve(LIVELY['squash'], phase) if lively else 1.
    lean = curve(LIVELY['lean'], phase) if lively else 0.
    body_angle = -1.8*yaw + lean
    torso = QtGui.QTransform()
    torso.translate(center_x, center_y)
    torso.rotate(body_angle)

    if version in ('v13', 'v14', 'v15'):
        def shadow_ellipse(x, radius_x, radius_y, opacity, y=120.8):
            # Paint on the ground before every body part. The elliptical
            # gradient fades to transparent and fits inside the sprite canvas.
            painter.save()
            painter.translate(x, y)
            painter.scale(radius_x, radius_y)
            gradient = QtGui.QRadialGradient(0., 0., 1.)
            for position, strength in ((0., 1.), (.38, .80), (.72, .28), (1., 0.)):
                color = (3, 2, 5) if volume else (12, 9, 17)
                gradient.setColorAt(position, QtGui.QColor(*color, round(opacity*strength)))
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(gradient)
            painter.drawEllipse(QtCore.QRectF(-1., -1., 2., 2.))
            painter.restore()

        # Higher torso: a slightly wider and fainter shadow. Keep it subtle so
        # the soft outline does not pulse conspicuously with each step.
        rise = (79.5-by)*2.
        shadow_ellipse(center_x+1., (50. if volume else 47.)+rise*.15,
                       (5.2 if volume else 4.4)+rise*.06,
                       (168. if volume else 76.)-rise*1.4,
                       122.2 if volume else 120.8)
        for near_shoe in (False, True):
            side = 'near' if near_shoe else 'far'
            near_path = NEAR_X if classic_shoes else LIVELY['near_x']
            shoe_x = curve(near_path if near_shoe else FAR_X, phase)
            rolls = VOLUME_NEAR_ROLL if volume and not classic_shoes and near_shoe else LIVELY[f'{side}_roll']
            shoe_angle = math.radians(curve(rolls, phase))
            shoe_lift = curve(LIVELY[f'{side}_lift'], phase)*swing_gate(phase, near_shoe)
            # Contact darkens locally beneath a planted shoe; a lifted shoe's
            # smaller shadow fades smoothly rather than switching off.
            radius_x = 7.+11.*math.cos(shoe_angle)**2+shoe_lift*.15
            shadow_ellipse(64.+(shoe_x-63.)*2., radius_x, 2.+shoe_lift*.08,
                           (145. if volume else 78.)*math.exp(-shoe_lift*.30),
                           121.3 if volume else 120.8)

    def body_point(x, y):
        # Keep the pancake's shorter torso; feet retain the source ground plane.
        if lively:
            point = torso.map(QtCore.QPointF((x-bx)*2., (y-by)*1.6*squash))
            return point.x(), point.y()
        return (center_x+(x-bx)*2., center_y+(y-by)*1.42)

    def part(name, x, y, width, height=None, angle=0., target=None):
        target = painter if target is None else target
        image = images[name]
        if height is None:
            height = width*image.height()/image.width()
        target.save()
        target.translate(x, y)
        target.rotate(angle)
        target.drawPixmap(QtCore.QRectF(-width/2., -height/2., width, height),
                           image, QtCore.QRectF(image.rect()))
        target.restore()

    def shoe(near, target=None):
        if lively:
            side = 'near' if near else 'far'
            near_path = NEAR_X if classic_shoes else LIVELY['near_x']
            sx = curve(near_path if near else FAR_X, phase)
            angle = curve(LIVELY[f'{side}_roll'], phase)
            width = curve(LIVELY[f'{side}_width'], phase)*1.80
            height = width*curve(LIVELY[f'{side}_depth'], phase)
            lift = curve(LIVELY[f'{side}_lift'], phase)
            if softened:
                lift *= swing_gate(phase, near)
            if volume and not classic_shoes:
                height = width*curve(VOLUME_NEAR_DEPTH if near else VOLUME_FAR_DEPTH, phase)
                if near:
                    angle = curve(VOLUME_NEAR_ROLL, phase)
        else:
            sx = sample(NEAR_X if near else FAR_X, phase)
            angle = sample(NEAR_ROLL if near else FAR_ROLL, phase)
            width = sample(NEAR_WIDTH, phase)*1.80 if near else 42.
            height = width*.43
            lift = sample(NEAR_LIFT if near else FAR_LIFT, phase)
        name = 'foot-near' if near else 'foot-far'
        if anchored:
            width *= 1.14 if classic_shoes else 1.22 if volume else 1.10
            height *= 1.21 if classic_shoes else 1.22 if volume else 1.10
        # The actual sole is the support point, including during toe-off.
        # Construct the centre from clearance, without clamping a moving foot.
        radians = math.radians(angle)
        supports = tuple(x*width*math.sin(radians)+y*height*math.cos(radians)
                         for x, y in sole_outline(name, volume, classic_shoes))
        bottom = max(supports)
        if softened:
            # A hard max switches between sole vertices as the shoe rotates.
            # Smooth that switch with a conservative support estimate: its
            # subpixel clearance keeps the painted sole above the floor.
            temperature = .12
            bottom += temperature*math.log(sum(math.exp((value-bottom)/temperature)
                                               for value in supports))
        cx, cy = 64.+(sx-63.)*2., 120.-bottom-lift
        part(name, cx, cy, width, height, angle, target)
        return cx, cy

    # The far limbs stay behind the torso for the whole cycle. They emerge at
    # the silhouette naturally; there is no visibility toggle or layer swap.
    if volume:
        far_shoulder = torso.map(QtCore.QPointF(33.-4.*yaw, 1.))
        painter.save()
        painter.translate(far_shoulder.x(), far_shoulder.y())
        painter.rotate(-curve(NEAR_ARM_SWING, phase)+body_angle)
        painter.drawPixmap(QtCore.QRectF(-11., -3., 22., 25.),
                           images['arm-far'], QtCore.QRectF(images['arm-far'].rect()))
        painter.restore()
    else:
        far_arm_x, far_arm_y = body_point(curve(FAR_ARM_X, phase), curve(FAR_ARM_Y, phase))
        part('arm-far', far_arm_x, far_arm_y, 18.,
             angle=-18.-yaw*12.+(body_angle if lively else 0.))
    far = shoe(False)
    body = images['body']
    turn_narrowing = .025 if anchored else .10 if lively else .045
    body_width = 96.*(1.-turn_narrowing*yaw)/math.sqrt(squash)
    body_height = 79.*squash if lively else 96.*body.height()/body.width()
    def draw_body(target):
        target.save()
        target.translate(center_x, center_y)
        target.shear(.035*yaw, 0.)
        target.rotate(body_angle)
        target.drawPixmap(QtCore.QRectF(-body_width/2, -body_height/2, body_width, body_height),
                       body, QtCore.QRectF(body.rect()))
        target.restore()

    draw_body(painter)

    # Turn the same facial features, rather than replacing the entire head.
    # Its smaller projected width gives a gentle three-quarter/profile change.
    if lively:
        face_center = torso.map(QtCore.QPointF(20.+yaw*5.5, 0.))
        part('face', face_center.x(), face_center.y(), 48.*(1.-.36*yaw), 25., body_angle)
    else:
        part('face', center_x+21.+yaw*9., center_y+4., 48.*(1.-.28*yaw), 23.)

    arm = images['arm-near']
    if anchored:
        # One anatomical attachment, projected with the same torso yaw. The
        # shoulder stays at the side and at one height relative to the torso.
        # The original measured tracks migrated up and across the whole belly.
        shoulder = torso.map(QtCore.QPointF(-28.+12.*yaw, 0.))
        root = shoulder.x(), shoulder.y()
        arm_width, arm_height = (27.5, 28.5) if volume else (25., 26.)
        target_angle = 90.+curve(NEAR_ARM_SWING, phase)+body_angle
    else:
        root = body_point(curve(ARM_ROOT_X, phase), curve(ARM_ROOT_Y, phase))
        palm = body_point(curve(ARM_PALM_X, phase), curve(ARM_PALM_Y, phase))
        dx, dy = palm[0]-root[0], palm[1]-root[1]
        arm_width = curve(LIVELY['arm_width'], phase) if lively else 23.
        arm_height = curve(LIVELY['arm_height'], phase) if lively else arm_width*arm.height()/arm.width()
        target_angle = math.degrees(math.atan2(dy, dx))
    local_dx, local_dy = (0., .53*arm_height) if volume else (-.28*arm_width, .61*arm_height)
    angle = target_angle-math.degrees(math.atan2(local_dy, local_dx))
    painter.save()
    painter.translate(root[0], root[1])
    painter.rotate(angle)
    painter.drawPixmap(QtCore.QRectF(-arm_width*(.5 if volume else .73),
                                    -arm_height*(.12 if volume else .06), arm_width, arm_height),
                       arm, QtCore.QRectF(arm.rect()))
    painter.restore()
    if volume:
        # A body-shaped depth mask hides the near shoe's attachment under the
        # belly. The contour recedes as the foot swings forward. Each visible
        # shoe pixel is painted once, avoiding a seam at the torso's outline.
        front = QtGui.QImage(384, 384, QtGui.QImage.Format_ARGB32_Premultiplied)
        front.fill(QtCore.Qt.transparent)
        layer = QtGui.QPainter(front)
        layer.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.SmoothPixmapTransform)
        layer.scale(3., 3.)
        near = shoe(True, layer)
        mask = QtGui.QImage(front.size(), front.format())
        mask.fill(QtCore.Qt.transparent)
        mask_painter = QtGui.QPainter(mask)
        mask_painter.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.SmoothPixmapTransform)
        mask_painter.scale(3., 3.)
        mask_painter.translate(center_x, center_y)
        mask_painter.shear(.035*yaw, 0.)
        mask_painter.rotate(body_angle)
        depth = curve(CLASSIC_SHOE_DEPTH if classic_shoes else NEAR_SHOE_DEPTH, phase)
        radius = math.sqrt(1.-depth*depth)
        if classic_shoes:
            radius *= 1.30
        contour = QtGui.QPainterPath()
        contour.addEllipse(QtCore.QRectF(-body_width*.5*radius, -body_height*.44*radius,
                                         body_width*radius, body_height*.88*radius))
        mask_painter.setClipPath(contour)
        mask_painter.drawPixmap(QtCore.QRectF(-body_width/2, -body_height/2, body_width, body_height),
                               body, QtCore.QRectF(body.rect()))
        mask_painter.end()
        layer.setCompositionMode(QtGui.QPainter.CompositionMode_DestinationOut)
        layer.drawImage(QtCore.QRectF(0., 0., 128., 128.), mask)
        layer.end()
        painter.drawImage(QtCore.QRectF(0., 0., 128., 128.), front)
    else:
        near = shoe(True)
    if landmarks:
        painter.setPen(QtGui.QPen(QtGui.QColor('#66fff0'), .7))
        painter.setBrush(QtCore.Qt.NoBrush)
        for x, y in ((center_x, center_y), root, near, far):
            painter.drawEllipse(QtCore.QPointF(x, y), 2., 2.)
    painter.restore()
    return True
