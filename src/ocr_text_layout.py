"""Reading order shared by the GUI and the isolated OCR worker."""

import math
import unicodedata


def is_rtl_text(text):
    directions = [unicodedata.bidirectional(c) for c in text]
    return sum(d in {'R', 'AL'} for d in directions) > directions.count('L')


def inline_reading_order(items, *, position, text):
    """Order word boxes without reversing characters or Latin runs in RTL."""
    ordered = sorted(items, key=position)
    if not is_rtl_text(' '.join(str(text(item)) for item in ordered)):
        return ordered
    groups = []
    latin_run = []
    for item in ordered:
        directions = {unicodedata.bidirectional(c) for c in str(text(item))}
        if not directions.intersection({'R', 'AL'}) and directions.intersection({'L', 'EN', 'AN'}):
            latin_run.append(item)
        else:
            if latin_run:
                groups.append(latin_run)
                latin_run = []
            groups.append([item])
    if latin_run:
        groups.append(latin_run)
    return [item for group in reversed(groups) for item in group]


def windows_line_text(line):
    """WinRT can return Arabic words in visual left-to-right order."""
    words = list(getattr(line, 'words', ()) or ())
    if not words:
        return str(getattr(line, 'text', '') or '')
    if is_rtl_text(' '.join(str(word.text) for word in words)):
        words = inline_reading_order(words, position=lambda word: float(word.bounding_rect.x),
                                     text=lambda word: word.text)
    return ' '.join(str(word.text) for word in words if str(word.text).strip())


def _bounds(box):
    try:
        xs = [float(point[0]) for point in box]
        ys = [float(point[1]) for point in box]
        if not xs or not all(math.isfinite(value) for value in xs + ys):
            return None
        return min(xs), min(ys), max(xs), max(ys)
    except (TypeError, ValueError, IndexError):
        return None


def ocr_visual_lines(items):
    """Group boxes by baseline, retaining their visual left-to-right order.

    A one-pixel difference between the tops of word boxes is not a new line.
    Compare centres with a tolerance based on the smaller box's height so a
    tall box cannot pull together two separate lines of ordinary text.
    """
    positioned = [(item, _bounds(item[0])) for item in items]
    positioned.sort(key=lambda pair: (pair[1][1], pair[1][0]) if pair[1] else (math.inf, math.inf))
    lines = []
    active = []
    for item, bounds in positioned:
        if bounds is None:
            lines.append((None, [(item, bounds)]))
            continue
        centre = (bounds[1] + bounds[3]) / 2
        height = max(1, bounds[3] - bounds[1])
        # A baseline cannot overlap a box entirely below it. Keep completed
        # lines out of the search instead of revisiting every previous row.
        active = [(anchor, line) for anchor, line in active if anchor[3] >= bounds[1]]
        for anchor, line in reversed(active):
            anchor_centre = (anchor[1] + anchor[3]) / 2
            tolerance = .5 * min(height, max(1, anchor[3] - anchor[1]))
            if abs(centre - anchor_centre) <= tolerance:
                line.append((item, bounds))
                break
        else:
            line = [(item, bounds)]
            lines.append((bounds, line))
            active.append((bounds, line))
    return [[item for item, bounds in sorted(line, key=lambda pair: pair[1][0] if pair[1] else 0)]
            for _anchor, line in lines]


def ocr_lines(items):
    """Join visual word boxes in their logical reading direction."""
    result = []
    for line in ocr_visual_lines(items):
        ordered = inline_reading_order(line,
            position=lambda item: (_bounds(item[0]) or (0,))[0],
            text=lambda item: item[1])
        result.append(ordered)
    return result


def order_ocr_items(items):
    return [item for line in ocr_lines(items) for item in line]


def ocr_text_from_items(items, *, join_paragraphs=False):
    if join_paragraphs:
        from ocr_paragraphs import boxes_from_items, paragraph_text
        return paragraph_text(boxes_from_items(items))
    return '\n'.join(' '.join(item[1] for item in line) for line in ocr_lines(items)).strip()
