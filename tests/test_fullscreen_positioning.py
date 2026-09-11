"""Fullscreen replacements keep OCR coordinates, including scaled captures."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from types import SimpleNamespace
from unittest import mock

import pytest
from PyQt5 import QtCore, QtWidgets
import ocr
import translater
from qt_layout_test_support import ensure_layout_fonts


@pytest.fixture(scope='module', autouse=True)
def application():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    ensure_layout_fonts(app)
    yield app


@pytest.mark.parametrize('scale_x,scale_y', [(1, 1), (1.25, 1.25), (1.5, 1.5), (2, 2), (2, 1.5)])
def test_translations_keep_separate_screen_positions(scale_x, scale_y, monkeypatch):
    signal = mock.Mock()
    overlay = SimpleNamespace(_ocr_scale_x=scale_x, _ocr_scale_y=scale_y,
                              _translation_run_id=3, _translation_result_ready=signal)
    lines = [(40, 80, 120, 24, 'One'), (430, 80, 120, 24, 'Two'), (430, 380, 120, 24, 'Three')]
    pixels = [(x * scale_x, y * scale_y, w * scale_x, h * scale_y, text) for x, y, w, h, text in lines]
    translate = mock.Mock(side_effect=lambda text, *a, **kw: text.replace('One', 'Один').replace('Two', 'Два').replace('Three', 'Три'))
    monkeypatch.setattr(translater, 'translate_text', translate)
    monkeypatch.setattr(ocr, 'get_cached_ocr_config', lambda: {'translator_engine': 'Lingva'})
    ocr.FullScreenTranslateOverlay._translate_all(overlay, 3, pixels, 'en', 'ru')
    run_id, blocks, error = signal.emit.call_args.args
    assert run_id == 3 and not error
    assert [value[2] for value in blocks] == ['Один', 'Два', 'Три']
    assert [value[0].getRect() for value in blocks] == [tuple(row[:4]) for row in lines]
    assert translate.call_args.kwargs['engine'] == 'Lingva'
    assert not translate.call_args.kwargs['cancel_callback']()
    overlay._translation_run_id += 1
    assert translate.call_args.kwargs['cancel_callback']()


@pytest.mark.parametrize('rect', [(-300, 60, 100, 20), (850, 60, 100, 20),
                                 (100, 550, 100, 20), (100, -60, 100, 20),
                                 (float('nan'), 60, 100, 20), (20, 60, 0, 20)])
def test_invalid_ocr_boxes_never_become_text_at_top_left(rect):
    overlay = SimpleNamespace(width=lambda: 800, height=lambda: 500)
    layout = ocr.FullScreenTranslateOverlay._translation_block_layout(
        overlay, QtCore.QRectF(*rect), 'Original', 'Translation')
    assert layout[0].isEmpty()
    painter = mock.Mock()
    ocr.FullScreenTranslateOverlay._paint_block(overlay, painter, QtCore.QRectF(*rect),
                                               'Original', 'Translation', layout=layout)
    painter.drawText.assert_not_called()
    painter.drawRect.assert_not_called()


def test_malformed_ocr_coordinates_are_excluded_before_translation():
    assert ocr._group_screen_ocr_lines([
        (float('nan'), 20, 20, 20, 'invalid'),
        (20, float('inf'), 20, 20, 'invalid'),
        (20, 40, -10, 20, 'invalid'),
        (200, 80, 120, 24, 'Visible'),
    ]) == [(200, 80, 120, 24, 'Visible')]


@pytest.mark.parametrize('angle,expected', [(0, (80, 40, 30, 10)),
                                          (None, (80, 40, 30, 10)),
                                          (90, (100, 30, 10, 30)),
                                          (-90, (90, 40, 10, 30))])
def test_windows_deskewed_boxes_return_to_original_image(angle, expected):
    word = SimpleNamespace(text='Word', bounding_rect=SimpleNamespace(x=80, y=40, width=30, height=10))
    result = SimpleNamespace(text_angle=angle, lines=[SimpleNamespace(words=[word])])
    lines = ocr._windows_ocr_lines_in_image(result, 200, 100)
    assert lines[0][:4] == pytest.approx(expected)
    assert lines[0][4] == 'Word'
