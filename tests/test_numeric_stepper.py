"""Real numeric editing, range and pointer behavior for replacement settings controls."""
import pytest
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtTest import QTest

from classic_style import classic_palette
from numeric_stepper import NumericStepper
from test_desktop_ux import app


@pytest.fixture
def field(app):
    owner = QtWidgets.QWidget()
    owner.resize(300, 100)
    control = NumericStepper(owner, decimals=2)
    control.setRange(.45, 10)
    control.setSingleStep(.05)
    control.setSuffix(' s')
    control.setValue(.8)
    control.setGeometry(5, 5, 180, 28)
    owner.show()
    app.processEvents()
    yield control
    owner.close()
    owner.deleteLater()


def _type(field, text):
    editor = field.lineEdit()
    editor.setFocus()
    editor.selectAll()
    QTest.keyClicks(editor, text)
    return editor


def test_decimal_draft_only_commits_on_enter(field):
    changed = []
    field.valueChanged.connect(changed.append)
    editor = _type(field, '1.25')
    assert field.value() == .8
    assert changed == []
    QTest.keyClick(editor, QtCore.Qt.Key_Return)
    assert field.value() == 1.25
    assert changed == [1.25]
    assert field.suffix() == ' s'


def test_cancel_and_invalid_intermediate_do_not_save(field):
    changed = []
    field.valueChanged.connect(changed.append)
    editor = _type(field, '1.25')
    QTest.keyClick(editor, QtCore.Qt.Key_Escape)
    assert field.value() == .8
    assert changed == []
    assert editor.text() == field.editor.textFromValue(.8) + ' s'
    editor = _type(field, '')
    QTest.keyClick(editor, QtCore.Qt.Key_Backspace)
    QTest.keyClick(editor, QtCore.Qt.Key_Return)
    assert field.value() == .8
    assert changed == []


def test_arrow_limits_and_keyboard_steps(field):
    field.setValue(.45)
    assert not field.decrease.isEnabled()
    QTest.mouseClick(field.increase, QtCore.Qt.LeftButton)
    assert field.value() == .5
    field.editor.setFocus()
    QTest.keyClick(field.editor, QtCore.Qt.Key_Up)
    assert field.value() == .55
    field.setValue(10)
    assert not field.increase.isEnabled()
    field.stepDown()
    assert field.value() == 9.95
    field.setValue(100)
    assert field.value() == 10


def test_arrow_commits_typed_draft_before_applying_step(field):
    _type(field, '1.25')
    QTest.mouseClick(field.increase, QtCore.Qt.LeftButton)
    assert field.value() == 1.3


def test_lower_bound_intermediate_never_emits_a_setting_value(field):
    changed = []
    field.valueChanged.connect(changed.append)
    editor = field.lineEdit()
    editor.setFocus()
    editor.setText(field.editor.textFromValue(.44) + field.suffix())
    QTest.keyClick(editor, QtCore.Qt.Key_Return)
    assert field.value() == .8
    assert changed == []
    assert editor.text() == field.editor.textFromValue(.8) + field.suffix()


def test_decimal_comma_commits_when_system_locale_uses_point(field):
    field.editor.setLocale(QtCore.QLocale('en_US'))
    editor = _type(field, '1,25')
    QTest.keyClick(editor, QtCore.Qt.Key_Return)
    assert field.value() == 1.25


def test_wheel_ignores_inactive_field(field, app):
    field.editor.clearFocus()
    field.lineEdit().clearFocus()
    app.processEvents()
    event = QtGui.QWheelEvent(QtCore.QPointF(20, 10), QtCore.QPointF(20, 10),
                             QtCore.QPoint(), QtCore.QPoint(0, 120), QtCore.Qt.NoButton,
                             QtCore.Qt.NoModifier, QtCore.Qt.NoScrollPhase, False)
    field.editor.wheelEvent(event)
    assert field.value() == .8
    assert not event.isAccepted()


@pytest.mark.parametrize('locale', ['en_US', 'de_DE', 'ar_SA'])
def test_numeric_locale_and_rtl_units_do_not_reverse_arrows(field, locale):
    field.parentWidget().setLayoutDirection(QtCore.Qt.RightToLeft)
    # The surrounding page may be RTL; numeric arrows intentionally stay LTR.
    assert field.layoutDirection() == QtCore.Qt.LeftToRight
    field.editor.setLocale(QtCore.QLocale(locale))
    field.setValue(1.25)
    text = field.editor.textFromValue(2.5)
    editor = _type(field, '')
    editor.setText(text + field.suffix())
    QTest.keyClick(editor, QtCore.Qt.Key_Return)
    assert field.value() == 2.5
    assert field.decrease.geometry().left() < field.increase.geometry().left()


@pytest.mark.parametrize('dark', [True, False])
def test_theme_and_integer_percent_variant(field, dark):
    field.set_theme(dark)
    field.setDecimals(0)
    field.setRange(45, 100)
    field.setSingleStep(1)
    field.setSuffix('%')
    field.setValue(88)
    assert field.lineEdit().text() == '88%'
    assert field.singleStep() == 1
    assert classic_palette(dark)['field'] in field.styleSheet()
    assert 'QDoubleSpinBox' in field.styleSheet()
    field.setAccessibleName('Background opacity')
    assert field.editor.accessibleName() == 'Background opacity'
