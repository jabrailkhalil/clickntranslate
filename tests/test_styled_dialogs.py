import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5 import QtCore, QtWidgets

import main
import ocr
import settings_window
from styled_dialogs import StyledMessageBox, install_qt_exception_guard

_APP = None


def _app():
    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return _APP


def test_message_box_uses_custom_chrome_and_status_icon():
    app = _app()
    box = StyledMessageBox()
    box.setWindowTitle("EasyOCR not found")
    box.setText("Install the neural OCR engine into the app folder?")
    box.setIcon(StyledMessageBox.Question)
    box.addButton("Install", StyledMessageBox.AcceptRole)
    box.addButton("Cancel", StyledMessageBox.RejectRole)
    assert box.windowFlags() & QtCore.Qt.FramelessWindowHint
    assert box.title_bar.title_label.text() == "EasyOCR not found"
    assert box.title_bar.height() == 42
    assert box.minimumWidth() >= 500
    assert not box._status_pixmap().isNull()
    assert "styledMessageTitleBar" in box.styleSheet()


def test_external_message_style_cannot_remove_shared_chrome():
    _app()
    box = StyledMessageBox()
    box.setStyleSheet("QMessageBox { background-color: #ffffff; }")

    assert box._dark is False
    assert "#f8f8fb" in box.styleSheet()
    assert "QFrame#styledMessageTitleBar" in box.styleSheet()


def test_theme_detection_accepts_settings_parent_attribute():
    _app()
    owner = QtWidgets.QWidget()
    owner.current_theme = "Light"
    settings_like_child = QtWidgets.QWidget(owner)
    settings_like_child.parent = owner

    box = StyledMessageBox(settings_like_child)

    assert box._dark is False


def test_message_box_centers_on_embedded_settings_in_global_coordinates():
    app = _app()
    main_window = QtWidgets.QWidget()
    # Keep the fixture far enough from the 800x600 offscreen screen edges so
    # the dialog's safety clamping does not mask the coordinate-space check.
    main_window.setGeometry(120, 80, 700, 400)
    embedded_settings = QtWidgets.QWidget(main_window)
    embedded_settings.setGeometry(0, 40, 700, 350)
    main_window.show()
    embedded_settings.show()
    app.processEvents()

    box = StyledMessageBox(embedded_settings)
    box.resize(500, 210)
    box._center_on_owner()

    expected = embedded_settings.mapToGlobal(embedded_settings.rect().center())
    actual = box.frameGeometry().center()
    assert abs(actual.x() - expected.x()) <= 1
    assert abs(actual.y() - expected.y()) <= 1


def test_every_process_uses_the_shared_message_box():
    assert settings_window.QMessageBox is StyledMessageBox
    assert main.QMessageBox is StyledMessageBox
    assert ocr.QMessageBox is StyledMessageBox


def test_qt_exception_guard_is_idempotent():
    previous = __import__("sys").excepthook
    try:
        install_qt_exception_guard()
        installed = __import__("sys").excepthook
        install_qt_exception_guard()
        assert __import__("sys").excepthook is installed
        assert installed._clickntranslate_qt_guard is True
    finally:
        __import__("sys").excepthook = previous
