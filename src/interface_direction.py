"""Mirror interface layouts without changing the reading order of user text."""
from PyQt5 import QtCore, QtWidgets


def interface_direction(locale):
    return QtCore.Qt.RightToLeft if str(locale).lower().split('-')[0] == 'ar' else QtCore.Qt.LeftToRight


def apply_interface_direction(locale, root=None, *, application=False):
    direction = interface_direction(locale)
    app = QtWidgets.QApplication.instance()
    if application and app is not None and app.layoutDirection() != direction:
        app.setLayoutDirection(direction)
    if isinstance(root, QtWidgets.QWidget):
        root.setLayoutDirection(direction)
