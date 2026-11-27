"""A multi-line label starts beside its indicator, in either reading direction."""
from pathlib import Path
import sys

import pytest
from PyQt5 import QtCore, QtGui, QtWidgets

from styled_dialogs import AccentControlStyle
from test_desktop_ux import app


@pytest.mark.parametrize('dark', [True, False])
@pytest.mark.parametrize('rtl', [False, True])
@pytest.mark.parametrize('lines', [1, 2, 3])
def test_indicator_aligns_with_first_line_without_changing_single_line_rows(app, dark, rtl, lines):
    style = AccentControlStyle(dark)
    checkbox = QtWidgets.QCheckBox('\n'.join(
        ['Проверять обновления', 'при запуске приложения', 'автоматически'][:lines]
        if not rtl else ['التحقق من التحديثات', 'عند تشغيل التطبيق', 'تلقائيًا'][:lines]))
    checkbox.setStyle(style)
    checkbox.setLayoutDirection(QtCore.Qt.RightToLeft if rtl else QtCore.Qt.LeftToRight)
    font = checkbox.font()
    font.setPixelSize(16)
    checkbox.setFont(font)
    checkbox.setChecked(True)
    checkbox.resize(340, 28 + (lines-1)*checkbox.fontMetrics().lineSpacing())
    checkbox.show()
    app.processEvents()
    try:
        option = QtWidgets.QStyleOptionButton()
        checkbox.initStyleOption(option)
        indicator = checkbox.style().subElementRect(QtWidgets.QStyle.SE_CheckBoxIndicator, option, checkbox)
        contents = checkbox.style().subElementRect(QtWidgets.QStyle.SE_CheckBoxContents, option, checkbox)
        text = option.fontMetrics.boundingRect(contents,
            QtCore.Qt.AlignLeading | QtCore.Qt.AlignVCenter | QtCore.Qt.TextShowMnemonic, checkbox.text())
        first_center = text.top() + option.fontMetrics.lineSpacing()/2
        assert abs(indicator.center().y() - first_center) <= 2, (lines, rtl, indicator, text)
        assert checkbox.rect().contains(indicator)
        image = checkbox.grab()
        if lines == 2:
            image.save(str(Path(sys.argv[0]).parent / f'multiline-check-{rtl}-{dark}.png'))
    finally:
        checkbox.close()
        checkbox.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
