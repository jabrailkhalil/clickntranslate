"""Text direction is independent of the app's interface language and alignment."""
import unicodedata
import re

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QTextOption


def text_direction(text):
    """Use the first strong character, as for a natural-language paragraph."""
    for char in str(text or ''):
        bidi = unicodedata.bidirectional(char)
        if bidi in ('R', 'AL'):
            return Qt.RightToLeft
        if bidi == 'L':
            return Qt.LeftToRight
    return Qt.LeftToRight


def ui_directional_text(text, locale):
    """Scope Arabic labels even in Qt styles that force the outer label LTR.

    This is display-only: catalogs, user text, translation requests and copied
    results retain their logical Unicode order. An embedding keeps trailing
    acronyms and punctuation at the end, without reversing the Latin letters.
    """
    if str(locale).split('-')[0] == 'ar' and text_direction(text) == Qt.RightToLeft:
        return '\u202b' + text + '\u202c'
    return text


def directional_text_flags(text):
    rtl = text_direction(text) == Qt.RightToLeft
    return Qt.AlignRight if rtl else Qt.AlignLeft


def text_option(text, alignment=None):
    option = QTextOption(alignment if alignment is not None else
                         directional_text_flags(text) | Qt.AlignVCenter)
    option.setTextDirection(text_direction(text))
    option.setWrapMode(QTextOption.NoWrap)
    return option


def single_line_text(text):
    """Retain the screen layer's single-line layout without modifying its data."""
    return re.sub(r'[\r\n\u2028\u2029]+', ' ', str(text or ''))
