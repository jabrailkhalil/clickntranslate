"""Compact value controls with bounded arrows and a centered value."""
from PyQt5 import QtCore, QtGui, QtWidgets

from ui_scaling import ScaleArrowButton


class _NumberEdit(QtWidgets.QLineEdit):
    def focusOutEvent(self, event):
        self._select_after_click = False
        super().focusOutEvent(event)
        self.deselect()

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self._select_after_click = event.reason() == QtCore.Qt.MouseFocusReason
        self.selectAll()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if getattr(self, '_select_after_click', False):
            self._select_after_click = False
            self.selectAll()

    def keyPressEvent(self, event):
        self._select_after_click = False
        super().keyPressEvent(event)


class _NumberBox(QtWidgets.QSpinBox):
    def __init__(self):
        super().__init__()
        self.setLineEdit(_NumberEdit(self))
        self.setKeyboardTracking(False)
        self.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.setAlignment(QtCore.Qt.AlignCenter)

    def _digits(self, value):
        value = value.strip()
        if self.suffix() and value.endswith(self.suffix()):
            value = value[:-len(self.suffix())].strip()
        return value

    def validate(self, value, position):
        digits = self._digits(value)
        state = QtGui.QValidator.Intermediate
        if digits:
            if not digits.isdecimal() or len(digits) > len(str(self.maximum())):
                state = QtGui.QValidator.Invalid
            elif self.minimum() <= int(digits) <= self.maximum():
                state = QtGui.QValidator.Acceptable
        return state, value, position

    def valueFromText(self, value):
        digits = self._digits(value)
        number = int(digits) if digits.isdecimal() else self.value()
        return max(self.minimum(), min(self.maximum(), number))

    def fixup(self, value):
        return str(self.valueFromText(value)) + self.suffix()


class StepperFrame(QtWidgets.QFrame):
    """Shared chrome; the owner retains its existing commit/scale behavior."""
    def __init__(self, editor, parent=None, *, dark=True, font_size=15):
        super().__init__(parent)
        self.setProperty('numberStepper', True)
        self._editor_font_size = int(font_size)
        self.editor = editor
        self.decrease = ScaleArrowButton(self)
        self.increase = ScaleArrowButton(self)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(0)
        for button, glyph in ((self.decrease, '‹'), (self.increase, '›')):
            button.setText(glyph)
            button.setFixedWidth(28)
            button.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Expanding)
            button.setCursor(QtCore.Qt.PointingHandCursor)
            button.setFocusPolicy(QtCore.Qt.StrongFocus)
            button.setAutoRepeat(False)
        editor.setMinimumWidth(0)
        editor.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Expanding)
        layout.addWidget(self.decrease)
        layout.addWidget(editor, 1)
        layout.addWidget(self.increase)
        self.setFocusProxy(editor)
        self.set_theme(dark)

    def set_theme(self, dark):
        from button_styles import button_qss
        background, border, ink = (('#17181d', '#3d3948', '#f4f6fb') if dark
                                   else ('#e9e4ed', '#d7cde7', '#202124'))
        self.setStyleSheet(f'''
            QFrame[numberStepper="true"] {{ background:{background}; border:1px solid {border};
                border-radius:7px; margin:1px 3px; }}
            QLineEdit, QSpinBox {{ color:{ink}; background:transparent; border:0;
                padding:0; margin:0; min-height:0; font-size:{self._editor_font_size}px; font-weight:400; }}
            QLineEdit:disabled, QSpinBox:disabled {{ color:{'#7d7487' if dark else '#958b9f'}; }}
        ''' + button_qss(dark, 'quiet', 'QToolButton', icon=True, radius=4) + '''
            QToolButton { padding:0; margin:0; min-width:0; min-height:0; font-size:15px; }
            QToolButton:disabled { background:transparent; border-color:transparent; }
        ''')


class ChoiceStepper(StepperFrame):
    """Named choices with the same bounded arrows as the numeric controls."""
    valueChanged = QtCore.pyqtSignal(str)

    def __init__(self, choices, parent=None, *, dark=True, font_size=15):
        self._choices = tuple(choices)
        if not self._choices:
            raise ValueError('ChoiceStepper needs at least one choice')
        self._index = 0
        editor = QtWidgets.QLineEdit()
        editor.setReadOnly(True)
        editor.setAlignment(QtCore.Qt.AlignCenter)
        editor.setFocusPolicy(QtCore.Qt.NoFocus)
        editor.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        super().__init__(editor, parent, dark=dark, font_size=font_size)
        self.decrease.clicked.connect(lambda: self.stepBy(-1))
        self.increase.clicked.connect(lambda: self.stepBy(1))
        for control in (self, self.decrease, self.increase):
            control.installEventFilter(self)
        self._sync_choice()

    def value(self):
        return self._choices[self._index][0]

    def setValue(self, value):
        index = tuple(key for key, _label in self._choices).index(value)
        if index != self._index:
            self._index = index
            self._sync_choice()
            self.valueChanged.emit(self.value())

    def stepBy(self, direction):
        index = max(0, min(len(self._choices) - 1, self._index + direction))
        self.setValue(self._choices[index][0])

    def _sync_choice(self):
        self.editor.setText(self._choices[self._index][1])
        self.decrease.setEnabled(self._index > 0)
        self.increase.setEnabled(self._index < len(self._choices) - 1)

    def eventFilter(self, watched, event):
        if event.type() == QtCore.QEvent.KeyPress and event.modifiers() == QtCore.Qt.NoModifier:
            key = event.key()
            if key in (QtCore.Qt.Key_Left, QtCore.Qt.Key_Down, QtCore.Qt.Key_Right, QtCore.Qt.Key_Up):
                self.stepBy(-1 if key in (QtCore.Qt.Key_Left, QtCore.Qt.Key_Down) else 1)
            elif key in (QtCore.Qt.Key_Home, QtCore.Qt.Key_End):
                self.setValue(self._choices[0 if key == QtCore.Qt.Key_Home else -1][0])
            else:
                return super().eventFilter(watched, event)
            event.accept()
            return True
        return super().eventFilter(watched, event)


class NumberStepper(StepperFrame):
    valueChanged = QtCore.pyqtSignal(int)

    def __init__(self, parent=None, *, dark=True):
        super().__init__(_NumberBox(), parent, dark=dark)
        self.decrease.clicked.connect(lambda: self.editor.stepBy(-1))
        self.increase.clicked.connect(lambda: self.editor.stepBy(1))
        self.editor.valueChanged.connect(self._value_changed)
        self._sync_steps()

    def _sync_steps(self):
        self.decrease.setEnabled(self.value() > self.minimum())
        self.increase.setEnabled(self.value() < self.maximum())

    def _value_changed(self, value):
        self._sync_steps()
        self.valueChanged.emit(value)

    def setRange(self, minimum, maximum):
        self.editor.setRange(minimum, maximum)
        self._sync_steps()

    def setValue(self, value):
        self.editor.setValue(value)
        self._sync_steps()

    def value(self):
        return self.editor.value()

    def minimum(self):
        return self.editor.minimum()

    def maximum(self):
        return self.editor.maximum()

    def setSuffix(self, suffix):
        self.editor.setSuffix(suffix)

    def setKeyboardTracking(self, enabled):
        self.editor.setKeyboardTracking(enabled)

    def lineEdit(self):
        return self.editor.lineEdit()

    def setAccessibleName(self, name):
        super().setAccessibleName(name)
        self.editor.setAccessibleName(name)
        self.decrease.setAccessibleName(name + ' −1')
        self.increase.setAccessibleName(name + ' +1')
