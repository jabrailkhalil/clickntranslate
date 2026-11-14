"""Arabic sentences keep a trailing Latin acronym/name at the logical end."""
from types import SimpleNamespace
from unittest import mock

import pytest
from PyQt5 import QtCore, QtGui

import ocr
from settings_window import settings_text, SETTINGS_TEXT
from text_direction import text_option, text_direction, ui_directional_text
from test_desktop_ux import app


def paint(text, direction, font, *, option=None):
    image = QtGui.QImage(700, 48, QtGui.QImage.Format_ARGB32_Premultiplied)
    image.fill(QtCore.Qt.white)
    painter = QtGui.QPainter(image)
    painter.setFont(font)
    painter.setPen(QtCore.Qt.black)
    painter.setLayoutDirection(direction)
    if option is None:
        painter.drawText(QtCore.QRectF(0, 0, 700, 48), QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter | QtCore.Qt.TextSingleLine, text)
    else:
        painter.drawText(QtCore.QRectF(0, 0, 700, 48), text, option)
    painter.end()
    return image


@pytest.mark.parametrize('text,rtl', [
    ('على الأقل لقد حصلت على Stoneshard.', True),
    ('إبقاء النافذة ظاهرة أثناء OCR', True),
    ('تجميد الشاشة أثناء OCR', True),
    ('(123) هذا هو النص API', True),
    ('OCR text with a name', False),
    ('Перевод с API', False),
    ('12345', False),
])
def test_translation_direction_is_independent_of_the_ui(app, text, rtl):
    font = QtGui.QFont('Segoe UI', 14)
    assert text_direction(text) == (QtCore.Qt.RightToLeft if rtl else QtCore.Qt.LeftToRight)
    expected_direction = QtCore.Qt.RightToLeft if rtl else QtCore.Qt.LeftToRight
    # A native QTextOption is an independent reference for the expected layout.
    expected = QtGui.QImage(700, 48, QtGui.QImage.Format_ARGB32_Premultiplied)
    expected.fill(QtCore.Qt.white)
    painter = QtGui.QPainter(expected)
    painter.setFont(font)
    painter.setPen(QtCore.Qt.black)
    option = QtGui.QTextOption((QtCore.Qt.AlignRight if rtl else QtCore.Qt.AlignLeft) | QtCore.Qt.AlignVCenter)
    option.setTextDirection(expected_direction)
    option.setWrapMode(QtGui.QTextOption.NoWrap)
    painter.drawText(QtCore.QRectF(0, 0, 700, 48), text, option)
    painter.end()
    assert paint(text, QtCore.Qt.LeftToRight, font, option=text_option(text)) == paint(text, QtCore.Qt.RightToLeft, font, option=text_option(text))
    assert paint(text, QtCore.Qt.LeftToRight, font, option=text_option(text)) == expected


@pytest.mark.parametrize('key', ['keep_visible_on_ocr', 'freeze_screen_on_ocr', 'dim_screen_during_ocr'])
def test_arabic_checkbox_text_keeps_ocr_at_the_end_even_with_an_ltr_style(app, key):
    raw = SETTINGS_TEXT['ar'][key]
    rendered = settings_text('ar', key)
    assert rendered[1:-1] == raw  # Only display boundaries; no character reversal.
    font = QtGui.QFont('Segoe UI', 14)
    # Inspect the actual visual cursor positions in an explicitly LTR outer
    # label, as used by Qt's checkbox label painter. The Latin run must stay
    # LTR while appearing physically left of the Arabic sentence's first word.
    layout = QtGui.QTextLayout(rendered, font)
    option = QtGui.QTextOption()
    option.setTextDirection(QtCore.Qt.LeftToRight)
    layout.setTextOption(option)
    layout.beginLayout()
    line = layout.createLine()
    line.setLineWidth(700)
    layout.endLayout()
    latin = rendered.index('OCR')
    x = lambda index: line.cursorToX(index)[0]
    assert x(latin+1) < x(1)
    assert x(latin+1) < x(latin+2)
    assert abs(QtGui.QFontMetrics(font).horizontalAdvance(rendered)
               - QtGui.QFontMetrics(font).horizontalAdvance(raw)) <= 1
    assert settings_text('en', key) == SETTINGS_TEXT['en'][key]


def test_mixed_arabic_in_fullscreen_uses_translation_direction_not_app_direction(app):
    overlay = SimpleNamespace(width=lambda: 1000, height=lambda: 600)
    for text in ('على الأقل لقد حصلت على Stoneshard.', 'At least I have the Stoneshard.'):
        layout = ocr.FullScreenTranslateOverlay._translation_block_layout(
            overlay, QtCore.QRectF(100, 200, 780, 26), 'Original English line', text)
        assert bool(layout[3] & QtCore.Qt.AlignRight) == text.startswith('على')
        painter = mock.Mock()
        overlay._replacement_palette = lambda rect: (QtGui.QColor('white'), QtGui.QColor('black'))
        painter.fontMetrics.return_value.horizontalAdvance.return_value = 100
        ocr.FullScreenTranslateOverlay._paint_block(overlay, painter, QtCore.QRectF(100, 200, 780, 26), 'Original', text, layout=layout)
        options = painter.drawText.call_args.args[2]
        assert options.textDirection() == text_direction(text)


def test_ui_embedding_does_not_change_plain_latin_values_or_other_locales():
    assert ui_directional_text('OCR', 'ar') == 'OCR'
    assert ui_directional_text('API key', 'en') == 'API key'


def test_fullscreen_keeps_one_line_and_original_translation_data(app):
    original = 'على الأقل\nلقد حصلت على Stoneshard.'
    overlay = SimpleNamespace(width=lambda: 1000, height=lambda: 600,
                              _replacement_palette=lambda rect: (QtGui.QColor('white'), QtGui.QColor('black')))
    layout = ocr.FullScreenTranslateOverlay._translation_block_layout(
        overlay, QtCore.QRectF(100, 200, 780, 26), 'Original', original)
    painter = mock.Mock()
    painter.fontMetrics.return_value.horizontalAdvance.return_value = 100
    ocr.FullScreenTranslateOverlay._paint_block(overlay, painter, QtCore.QRectF(100, 200, 780, 26), 'Original', original, layout=layout)
    assert painter.drawText.call_args.args[1] == 'على الأقل لقد حصلت على Stoneshard.'
    assert '\n' in original
