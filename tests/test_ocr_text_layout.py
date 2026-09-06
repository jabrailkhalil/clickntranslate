import os
from pathlib import Path
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
import ocr
import ocr_worker
from ocr_text_layout import ocr_text_from_items


def box(left, top, right, bottom):
    return [[left, top], [right, top], [right, bottom], [left, bottom]]


@pytest.mark.parametrize('module', [ocr, ocr_worker])
@pytest.mark.parametrize('parser', ['_parse_rapidocr_output', '_parse_easyocr_output'])
def test_split_words_keep_reading_order_despite_slight_vertical_offsets(module, parser):
    # Coordinates reproduce the second line of a real DejaVu Sans OCR probe.
    output = [
        [box(183, 86, 653, 124), 'translation test 12345', .99],
        [box(30, 87, 179, 128), 'Screen', .99],
        [box(140, 36, 265, 74), 'world', .99],
        [box(32, 37, 139, 72), 'Hello', .99],
    ]
    items = getattr(module, parser)(output)
    assert [item[1] for item in items] == ['Hello', 'world', 'Screen', 'translation test 12345']
    assert ocr_text_from_items(items) == 'Hello world\nScreen translation test 12345'
    assert ocr_worker._result_for_items('sample', items, 10)['text'] == 'Hello world\nScreen translation test 12345'


def test_adjacent_lines_and_missing_boxes_stay_separate():
    items = [
        (box(0, 20, 100, 35), 'Second', .9),
        (box(0, 0, 100, 15), 'First', .9),
        (None, 'Unpositioned', .9),
    ]
    assert ocr_text_from_items(items) == 'First\nSecond\nUnpositioned'
    assert ocr_text_from_items([]) == ''


def test_large_drop_cap_does_not_merge_two_lines():
    items = [
        (box(25, 0, 100, 15), 'first', .9),
        (box(25, 20, 100, 35), 'second', .9),
        (box(0, 0, 20, 35), 'T', .9),
    ]
    assert 'first second' not in ocr_text_from_items(items)
