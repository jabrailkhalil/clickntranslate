"""Editable settings values with the same horizontal arrows as interface scale."""
from PyQt5 import QtCore, QtWidgets

from classic_style import classic_palette
from number_controls import StepperFrame, _NumberEdit


class _DecimalBox(QtWidgets.QDoubleSpinBox):
    def __init__(self, decimals):
        super().__init__()
        self.setLineEdit(_NumberEdit(self))
        self.setDecimals(decimals)
        self.setKeyboardTracking(False)
        self.setCorrectionMode(QtWidgets.QAbstractSpinBox.CorrectToPreviousValue)
        self.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setLayoutDirection(QtCore.Qt.LeftToRight)

    def _localized_text(self, text):
        # These bounded settings never need thousands separators. Accept either
        # keyboard decimal key even when Windows uses a different locale from
        # the application, while letting Qt handle local digits and formatting.
        prefix, suffix = self.prefix(), self.suffix()
        start = len(prefix) if prefix and text.startswith(prefix) else 0
        end = len(text) - len(suffix) if suffix and text.endswith(suffix) else len(text)
        number = text[start:end]
        decimal = self.locale().decimalPoint()
        if decimal not in number:
            for alternative in ('.', ','):
                if alternative != decimal and number.count(alternative) == 1:
                    number = number.replace(alternative, decimal)
                    break
        return text[:start] + number + text[end:]

    def validate(self, text, position):
        return super().validate(self._localized_text(text), position)

    def valueFromText(self, text):
        return super().valueFromText(self._localized_text(text))

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            # Do not save a partially typed value when the user cancels editing.
            self.lineEdit().setText(self.prefix() + self.textFromValue(self.value()) + self.suffix())
            self.lineEdit().deselect()
            event.accept()
            return
        super().keyPressEvent(event)

    def wheelEvent(self, event):
        if not self.hasFocus() and not self.lineEdit().hasFocus():
            event.ignore()
            return
        super().wheelEvent(event)


class NumericStepper(StepperFrame):
    """QDoubleSpinBox API in the existing scale control's compact frame.

    Values commit on Enter, a step, or leaving the editor, rather than on every
    keystroke. Decimals=0 gives percentage/integer controls; decimal precision
    and a suffix make intervals explicit without converting display strings.
    """
    valueChanged = QtCore.pyqtSignal(float)
    editingFinished = QtCore.pyqtSignal()

    def __init__(self, parent=None, *, dark=True, font_size=14, decimals=0):
        super().__init__(_DecimalBox(decimals), parent, dark=dark, font_size=font_size)
        self.decrease.clicked.connect(lambda: self.stepBy(-1))
        self.increase.clicked.connect(lambda: self.stepBy(1))
        self.editor.valueChanged.connect(self._value_changed)
        self.editor.editingFinished.connect(self.editingFinished)
        self._sync_steps()

    def set_theme(self, dark, *, inset=True):
        super().set_theme(dark, inset=inset)
        colors = classic_palette(dark)
        self.setStyleSheet(self.styleSheet() + f'''
            QDoubleSpinBox {{ color:{colors['text']}; background:transparent; border:0;
                padding:0; margin:0; min-height:0; font-size:{self._editor_font_size}px; font-weight:400; }}
            QDoubleSpinBox:disabled {{ color:{colors['muted']}; }}
        ''')

    def _sync_steps(self):
        self.decrease.setEnabled(self.value() > self.minimum())
        self.increase.setEnabled(self.value() < self.maximum())

    def _value_changed(self, value):
        self._sync_steps()
        self.valueChanged.emit(value)

    def setRange(self, minimum, maximum):
        self.editor.setRange(minimum, maximum)
        self._sync_steps()

    def setMinimum(self, value):
        self.editor.setMinimum(value)
        self._sync_steps()

    def setMaximum(self, value):
        self.editor.setMaximum(value)
        self._sync_steps()

    def minimum(self):
        return self.editor.minimum()

    def maximum(self):
        return self.editor.maximum()

    def setValue(self, value):
        self.editor.setValue(value)
        self._sync_steps()

    def value(self):
        return self.editor.value()

    def setSingleStep(self, value):
        self.editor.setSingleStep(value)

    def singleStep(self):
        return self.editor.singleStep()

    def setDecimals(self, value):
        self.editor.setDecimals(value)
        self._sync_steps()

    def decimals(self):
        return self.editor.decimals()

    def setSuffix(self, value):
        self.editor.setSuffix(value)

    def suffix(self):
        return self.editor.suffix()

    def setPrefix(self, value):
        self.editor.setPrefix(value)

    def prefix(self):
        return self.editor.prefix()

    def setKeyboardTracking(self, enabled):
        self.editor.setKeyboardTracking(enabled)

    def lineEdit(self):
        return self.editor.lineEdit()

    def stepBy(self, steps):
        self.editor.stepBy(steps)
        self._sync_steps()

    def stepUp(self):
        self.stepBy(1)

    def stepDown(self):
        self.stepBy(-1)

    def setAccessibleName(self, name):
        super().setAccessibleName(name)
        self.editor.setAccessibleName(name)
        self.decrease.setAccessibleName(name + ' −')
        self.increase.setAccessibleName(name + ' +')
