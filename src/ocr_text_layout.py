"""Reading order shared by the GUI and the isolated OCR worker."""

import math


def _bounds(box):
    try:
        xs = [float(point[0]) for point in box]
        ys = [float(point[1]) for point in box]
        if not xs or not all(math.isfinite(value) for value in xs + ys):
            return None
        return min(xs), min(ys), max(xs), max(ys)
    except (TypeError, ValueError, IndexError):
        return None


def ocr_lines(items):
    """Group boxes by line before ordering words from left to right.

    A one-pixel difference between the tops of word boxes is not a new line.
    Compare centres with a tolerance based on the smaller box's height so a
    tall box cannot pull together two separate lines of ordinary text.
    """
    positioned = [(item, _bounds(item[0])) for item in items]
    positioned.sort(key=lambda pair: (pair[1][1], pair[1][0]) if pair[1] else (math.inf, math.inf))
    lines = []
    for item, bounds in positioned:
        if bounds is None:
            lines.append((None, [(item, bounds)]))
            continue
        centre = (bounds[1] + bounds[3]) / 2
        height = max(1, bounds[3] - bounds[1])
        for anchor, line in reversed(lines):
            if anchor is None:
                continue
            anchor_centre = (anchor[1] + anchor[3]) / 2
            tolerance = .5 * min(height, max(1, anchor[3] - anchor[1]))
            if abs(centre - anchor_centre) <= tolerance:
                line.append((item, bounds))
                break
        else:
            lines.append((bounds, [(item, bounds)]))
    return [
        [item for item, bounds in sorted(line, key=lambda pair: pair[1][0] if pair[1] else 0)]
        for anchor, line in lines
    ]


def order_ocr_items(items):
    return [item for line in ocr_lines(items) for item in line]


def ocr_text_from_items(items):
    return '\n'.join(' '.join(item[1] for item in line) for line in ocr_lines(items)).strip()
