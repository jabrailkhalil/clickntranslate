"""Hindi remains readable without an OS language/font package or internet."""
from pathlib import Path

from PyQt5 import QtGui
import pytest

import main
from test_desktop_ux import app


@pytest.mark.parametrize('weight', ['Regular', 'Bold'])
def test_bundled_devanagari_font_shapes_hindi_without_missing_glyphs(app, weight):
    path = Path(main.resource_path(f'icons/fonts/NotoSansDevanagari-{weight}.ttf'))
    identifier = QtGui.QFontDatabase.addApplicationFont(str(path))
    assert identifier >= 0
    family = QtGui.QFontDatabase.applicationFontFamilies(identifier)[0]
    assert family == 'Noto Sans Devanagari'
    assert QtGui.QFontDatabase.Devanagari in QtGui.QFontDatabase().writingSystems(family)
    layout = QtGui.QTextLayout('हिन्दी अनुवाद की भाषा', QtGui.QFont(family, 14))
    layout.beginLayout()
    line = layout.createLine()
    line.setLineWidth(600)
    layout.endLayout()
    runs = layout.glyphRuns()
    assert runs
    assert all(0 not in run.glyphIndexes() for run in runs)


def test_bundled_script_font_has_redistribution_license():
    text = Path(main.resource_path('icons/fonts/NOTO-DEVANAGARI-LICENSE.txt')).read_text(encoding='utf-8')
    assert 'SIL OPEN FONT LICENSE' in text
