"""Reading order is translation/scale invariant; malformed bounds keep text."""
from collections import Counter
import math

import pytest

import ocr_paragraphs
import ocr_text_layout


TRANSFORMS = [(1, -1920, 0), (.37, 155, -80), (.81, -320, -240),
              (1.03, 1000, 400), (1.37, -2000, 500), (2.5, 0, 0)]


@pytest.mark.parametrize('words', [
    ['First', 'Second', 'Third', 'Fourth'],
    ['الأولى', 'الثانية', 'الثالثة', 'الرابعة'],
    ['第一段', '第二段', '第三段', '第四段'],
])
@pytest.mark.parametrize('scale,dx,dy', TRANSFORMS)
def test_paragraph_reading_order_is_invariant_under_capture_scale_and_origin(words, scale, dx, dy):
    rows = [(10, 10, 80, 16, words[0]), (10, 30, 82, 16, words[1]),
            (200, 10, 80, 16, words[2]), (200, 30, 82, 16, words[3])]
    baseline = ocr_paragraphs.paragraph_blocks(rows)
    changed = [(x * scale + dx, y * scale + dy, w * scale, h * scale, text)
               for x, y, w, h, text in rows]
    actual = ocr_paragraphs.paragraph_blocks(changed)
    assert [row[4] for row in actual] == [row[4] for row in baseline]
    text = ocr_paragraphs.paragraph_text(changed)
    # CJK line reflow intentionally has no spaces between words. Check the
    # fragments and Unicode characters rather than whitespace tokenization.
    assert all(text.count(word) == 1 for word in words)
    assert Counter(char for char in text if not char.isspace()) == Counter(''.join(words))
    for expected, got in zip(baseline, actual):
        transformed = (expected[0] * scale + dx, expected[1] * scale + dy,
                       expected[2] * scale, expected[3] * scale)
        assert all(math.isclose(left, right, rel_tol=1e-10, abs_tol=1e-9)
                   for left, right in zip(transformed, got[:4]))


@pytest.mark.parametrize('coordinate', range(4), ids=['x', 'y', 'width', 'height'])
def test_unrepresentable_row_coordinate_retains_text_as_an_unpositioned_block(coordinate):
    bounds = [10, 10, 80, 16]
    bounds[coordinate] = 10 ** 1000
    rows = [(0, 0, 20, 10, 'Known'), (*bounds, 'Unknown')]
    assert [row[4] for row in ocr_paragraphs.paragraph_blocks(rows)] == ['Known']
    assert ocr_paragraphs.paragraph_text(rows) == 'Known\n\nUnknown'


@pytest.mark.parametrize('point', range(4))
def test_unrepresentable_sdk_box_does_not_drop_the_recognized_text(point):
    box = [[10, 10], [90, 10], [90, 26], [10, 26]]
    box[point][0] = 10 ** 1000
    items = [(box, 'Unknown', .99)]
    assert ocr_paragraphs.boxes_from_items(items) == [(None, None, None, None, 'Unknown')]
    assert ocr_text_layout.ocr_text_from_items(items, join_paragraphs=False) == 'Unknown'
    assert ocr_text_layout.ocr_text_from_items(items, join_paragraphs=True) == 'Unknown'
