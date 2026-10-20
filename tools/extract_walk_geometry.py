"""Extract scalable, frame-aligned geometry from the ten reference cels.

Only source pixel regions are classified and traced. No generated raster is
edited, and no pose, limb or timing is synthesized. Rendering materials belong
to the application, so the runtime geometry contains no source palette.
"""
from collections import defaultdict
from pathlib import Path
import hashlib
import json

import cv2
import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / 'docs/mascots/reference/original.gif'
DOCS = ROOT / 'docs/mascots/sources-v17/reference-geometry.json'
RUNTIME = ROOT / 'src/icons/desktop-assistant/orbit/walk-geometry.json'
CROP = (30, 43, 96, 109)
FOOT = ((175, 69, 61), (247, 85, 62), (64, 34, 34),
        (222, 74, 58), (120, 60, 58), (148, 61, 56))
EYE = ((22, 22, 29), (29, 20, 107), (207, 207, 218),
       (154, 156, 175), (24, 28, 139), (32, 45, 200), (247, 247, 249))
BODY_INK = (132, 15, 82)


def color_mask(pixels, colors):
    mask = np.zeros(pixels.shape[:2], dtype=bool)
    for color in colors:
        mask |= np.all(pixels[:, :, :3] == color, axis=2)
    return mask & (pixels[:, :, 3] > 0)


def components(mask):
    count, labels, stats, centers = cv2.connectedComponentsWithStats(mask.astype('uint8'), 8)
    return [(labels == index, stats[index].tolist(), centers[index].tolist())
            for index in range(1, count)]


def contours(mask):
    """Trace exact unit-cell edges; retain holes and remove only straight runs."""
    height, width = mask.shape
    outgoing = defaultdict(list)
    for y, x in zip(*np.nonzero(mask)):
        x, y = int(x), int(y)
        if y == 0 or not mask[y - 1, x]:
            outgoing[(x, y)].append((x + 1, y))
        if x + 1 == width or not mask[y, x + 1]:
            outgoing[(x + 1, y)].append((x + 1, y + 1))
        if y + 1 == height or not mask[y + 1, x]:
            outgoing[(x + 1, y + 1)].append((x, y + 1))
        if x == 0 or not mask[y, x - 1]:
            outgoing[(x, y + 1)].append((x, y))
    direction = {(1, 0): 0, (0, 1): 1, (-1, 0): 2, (0, -1): 3}
    rings = []
    while outgoing:
        start = min(outgoing)
        current, previous_direction = start, None
        points = []
        while True:
            points.append(current)
            options = outgoing[current]
            if previous_direction is None or len(options) == 1:
                following = options[0]
            else:
                # A right turn keeps diagonally touching pixel regions separate.
                preference = {1: 0, 0: 1, 3: 2, 2: 3}
                following = min(options, key=lambda end: preference[
                    (direction[(end[0] - current[0], end[1] - current[1])]
                     - previous_direction) % 4])
            options.remove(following)
            if not options:
                del outgoing[current]
            previous_direction = direction[(following[0] - current[0], following[1] - current[1])]
            current = following
            if current == start:
                break
        simple = []
        for index, point in enumerate(points):
            before, after = points[index - 1], points[(index + 1) % len(points)]
            cross = ((point[0] - before[0]) * (after[1] - point[1])
                     - (point[1] - before[1]) * (after[0] - point[0]))
            if cross:
                simple.append(list(point))
        rings.append(simple)
    return rings


def shape(mask):
    ys, xs = np.nonzero(mask)
    bounds = ([int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]
              if len(xs) else None)
    return {'contours': contours(mask), 'bounds': bounds, 'area_px': int(mask.sum())}


def component_shapes(mask):
    result = []
    for region, stats, center in components(mask):
        item = shape(region)
        item['center'] = center
        result.append(item)
    return sorted(result, key=lambda item: item['center'][0])


def extract():
    image = Image.open(REFERENCE)
    frames = []
    for index in range(image.n_frames):
        image.seek(index)
        pixels = np.asarray(image.convert('RGBA').crop(CROP))
        opaque = pixels[:, :, 3] > 0
        feet = color_mask(pixels, FOOT)
        body = opaque & ~feet
        eyes = color_mask(pixels, EYE)
        ink = color_mask(pixels, (BODY_INK,))
        mouth = np.zeros_like(ink)
        for region, stats, center in components(ink):
            x, y, width, height, area = stats
            if area == 2 and width == 1 and height == 2 and x >= 40 and 30 <= y <= 38:
                mouth |= region
        ink &= ~mouth
        interior = cv2.erode(body.astype('uint8'), np.ones((3, 3), dtype='uint8'),
                             borderType=cv2.BORDER_CONSTANT, borderValue=0).astype(bool)
        internal_ink = ink & interior
        near_ink = internal_ink.copy()
        near_ink[:, 42:] = False
        far_ink = internal_ink & ~near_ink
        cheek = color_mask(pixels, ((255, 91, 165), (222, 7, 104)))
        face_zone = cv2.dilate((eyes | cheek | mouth).astype('uint8'),
                               np.ones((3, 3), dtype='uint8')).astype(bool)
        body_mid = color_mask(pixels, ((249, 162, 203), (245, 131, 193))) & ~face_zone
        body_shade = color_mask(pixels, ((244, 108, 166), (234, 19, 132),
                                         (176, 17, 108))) & ~face_zone
        # An anchor from the top three outline rows follows the actual body bob.
        top = int(np.nonzero(body)[0].min())
        crown_x = np.nonzero(body[top:top + 3])[1]
        crown = [float(crown_x.mean()), top]
        frame = {
            'index': index, 'duration_ms': int(image.info.get('duration', 110)),
            'body': shape(body), 'feet': shape(feet),
            'body_ink': shape(ink), 'arm_ink': shape(internal_ink),
            'near_arm_ink': shape(near_ink), 'far_arm_ink': shape(far_ink),
            'eyes': shape(eyes), 'eye_components': component_shapes(eyes),
            'eye_highlight': shape(color_mask(pixels, ((247, 247, 249), (207, 207, 218)))),
            'mouth': shape(mouth),
            'foot_ink': shape(color_mask(pixels, ((64, 34, 34),))),
            'foot_light': shape(color_mask(pixels, ((247, 85, 62),))),
            'foot_mid': shape(color_mask(pixels, ((222, 74, 58),))),
            'foot_shadow': shape(color_mask(pixels, ((175, 69, 61), (120, 60, 58), (148, 61, 56)))),
            'body_mid': shape(body_mid), 'body_shade': shape(body_shade),
            'core_top_anchor': crown,
            'anchors': {'crown': crown,
                        'eye_centers': [eye['center'] for eye in component_shapes(eyes)],
                        'mouth_center': component_shapes(mouth)[0]['center'] if mouth.any() else None,
                        'ground_y': int(np.nonzero(feet)[0].max()) + 1},
        }
        frames.append(frame)
    geometry = {
        'schema_version': 1,
        'coordinates': {'width': 66, 'height': 66, 'unit': 'source_pixel',
                        'contour_rule': 'closed pixel-cell edge rings; odd-even fill; integer vertices',
                        'viewport': [-3, -6, 69, 66]},
        'frames': frames,
    }
    RUNTIME.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME.write_text(json.dumps(geometry, separators=(',', ':')) + '\n', encoding='utf-8')
    documented = dict(geometry)
    documented['extraction'] = {
        'source': 'docs/mascots/reference/original.gif',
        'sha256': hashlib.sha256(REFERENCE.read_bytes()).hexdigest(),
        'crop': list(CROP), 'source_size': list(image.size),
        'classification': {'foot_rgb': [list(color) for color in FOOT],
                           'eye_rgb': [list(color) for color in EYE],
                           'body_ink_rgb': list(BODY_INK),
                           'mouth_rule': 'isolated two-pixel vertical ink component at x>=40, y30..38',
                           'arm_ink_rule': 'body ink inside one-pixel eight-neighbor erosion of body; '
                                           'near arm x<42, far-arm division x>=42'},
        'method': 'Exact visible regions from each original cel; only collinear path vertices removed. '
                  'Body includes filled eye/mouth/cheek areas. Feet retain visible occlusion and seams. '
                  'No limb fitting, interpolation, registration or generated-raster edits.',
    }
    DOCS.write_text(json.dumps(documented, separators=(',', ':')) + '\n', encoding='utf-8')
    print(RUNTIME)
    print(DOCS)
    for frame in frames:
        print(f'{frame["index"]:02}: body={frame["body"]["bounds"]} feet={frame["feet"]["bounds"]} '
              f'arm_ink={frame["arm_ink"]["area_px"]} eyes={len(frame["eye_components"])} '
              f'mouth={frame["mouth"]["area_px"]} crown={frame["anchors"]["crown"]}')


if __name__ == '__main__':
    extract()
