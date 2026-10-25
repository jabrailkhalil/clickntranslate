"""Copy feedback at the OCR boundary, without touching the desktop clipboard."""

import os
import threading
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtTest import QTest

import main
import ocr
from styled_dialogs import CopyNotificationPopup


class _Receiver(QtWidgets.QWidget):
    _copy_notification_signal = QtCore.pyqtSignal(str)
    _show_copy_notification = main.DarkThemeApp._show_copy_notification

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.current_interface_language = config.get("interface_language", "en")
        self._copy_notice = CopyNotificationPopup()
        self._copy_notification_signal.connect(
            self._show_copy_notification, QtCore.Qt.QueuedConnection)
        from copy_feedback import register_copy_feedback
        register_copy_feedback(self)


@pytest.fixture
def receiver(monkeypatch):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    config = {"interface_language": "ar", "copy_history": False}
    monkeypatch.setattr(main, "get_cached_config", lambda: config)
    # Writing history is independent of notification delivery. No background
    # history writes, settings changes or actual platform clipboard are needed.
    monkeypatch.setattr(main.threading, "Thread", mock.Mock())
    widget = _Receiver(config)
    yield SimpleNamespace(widget=widget, config=config, app=app)
    widget._copy_notice.close()
    widget._copy_notice.deleteLater()
    widget.close()
    widget.deleteLater()
    app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    app.processEvents()


@pytest.mark.parametrize("enabled", [None, False, True])
def test_ocr_copy_delivers_localized_feedback_independently_of_history(
        receiver, isolated_clipboard, enabled):
    if enabled is not None:
        receiver.config["notifications"] = enabled
    owner = SimpleNamespace(mode="copy", close=mock.Mock())
    source = "  Recognized paragraph.\nSecond line.  "
    result = ocr.ScreenCaptureOverlay._handle_ocr_result_inner(owner, source)
    receiver.app.processEvents()

    assert result is True
    assert isolated_clipboard.text() == source
    owner.close.assert_called_once_with()
    assert receiver.widget._copy_notice.isVisible() is (enabled is not False)
    if enabled is not False:
        assert main.TRANSLATION_RESULT_DIALOG_TEXT["ar"]["copied"] in receiver.widget._copy_notice.text()


@pytest.mark.parametrize('failure', ['reported', 'exception'])
def test_copy_failure_does_not_announce_success(receiver, failure):
    receiver.config["notifications"] = True
    owner = SimpleNamespace(mode="copy", close=mock.Mock())
    with mock.patch.object(ocr.platform_support, "copy_text", return_value=False,
                           side_effect=RuntimeError('clipboard busy') if failure == 'exception' else None):
        result = ocr.ScreenCaptureOverlay._handle_ocr_result_inner(owner, "recognized text")
    receiver.app.processEvents()
    assert result is not True
    assert not receiver.widget._copy_notice.isVisible()
    main.threading.Thread.assert_not_called()
    owner.close.assert_not_called()


@pytest.mark.parametrize("source", ["", " \t\r\n"])
def test_empty_ocr_does_not_replace_clipboard_or_announce_success(receiver, isolated_clipboard, source):
    receiver.config["notifications"] = True
    isolated_clipboard.setText("existing clipboard")
    owner = SimpleNamespace(mode="copy", close=mock.Mock(), hide=mock.Mock(),
                            _persist_failed_ocr_artifacts=mock.Mock())
    with mock.patch.object(ocr, "QMessageBox") as message_class, \
            mock.patch.object(ocr, "get_cached_ocr_config", return_value=receiver.config):
        result = ocr.ScreenCaptureOverlay._handle_ocr_result_inner(owner, source)
    receiver.app.processEvents()
    assert result is not True
    assert isolated_clipboard.text() == "existing clipboard"
    assert not receiver.widget._copy_notice.isVisible()
    owner._persist_failed_ocr_artifacts.assert_called_once_with("empty_result")
    message_class.return_value.exec_.assert_called_once_with()


def test_worker_dispatch_queues_notice_on_the_gui_thread(monkeypatch):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    widget = _Receiver({"notifications": True, "interface_language": "de"})
    def forbidden_widget_scan():
        raise AssertionError('Workers must not enumerate GUI widgets')
    monkeypatch.setattr(QtWidgets.QApplication, 'topLevelWidgets', staticmethod(forbidden_widget_scan))
    # Create the worker before any fixture could replace threading.Thread.
    results = []
    worker = threading.Thread(target=lambda: results.append(main.notify_copy_completed(widget.config)))
    try:
        worker.start()
        worker.join(2)
        assert not worker.is_alive() and results == [True]
        # Signal delivery from this worker must await the GUI event loop.
        assert not widget._copy_notice.isVisible()
        app.processEvents()
        assert widget._copy_notice.isVisible()
        assert widget._copy_notice.thread() == app.thread()
        assert main.TRANSLATION_RESULT_DIALOG_TEXT["de"]["copied"] in widget._copy_notice.text()
    finally:
        widget._copy_notice.close()
        widget._copy_notice.deleteLater()
        widget.close()
        widget.deleteLater()


@pytest.mark.parametrize("language", tuple(main.TRANSLATION_RESULT_DIALOG_TEXT))
@pytest.mark.parametrize("dark", [False, True])
@pytest.mark.parametrize("dpi,bounds", [
    (96, (-1920, 0, 1920, 1080)),
    (144, (2560, -1440, 2560, 1440)),
    (192, (-2560, -1440, 2560, 1440)),
])
def test_notification_fits_cursor_monitor_and_localized_text(monkeypatch, language, dark, dpi, bounds):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    previous_theme = app.property("ui_theme")
    app.setProperty("ui_theme", "dark" if dark else "light")
    monitor = QtCore.QRect(*bounds)
    screen = SimpleNamespace(availableGeometry=lambda: monitor,
                             logicalDotsPerInch=lambda: dpi)
    monkeypatch.setattr(QtWidgets.QApplication, "screenAt", staticmethod(lambda _pos: screen))
    popup = CopyNotificationPopup()
    try:
        popup.show_message(main.TRANSLATION_RESULT_DIALOG_TEXT[language]["copied"])
        app.processEvents()
        assert popup.isVisible()
        assert monitor.adjusted(18, 18, -18, -18).contains(popup.geometry())
        assert popup.width() >= popup.sizeHint().width()
        assert popup.height() >= popup.sizeHint().height()
        assert popup.focusPolicy() == QtCore.Qt.NoFocus
        assert popup.testAttribute(QtCore.Qt.WA_ShowWithoutActivating)
        assert popup.testAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        # Paint the actual Qt window, including Arabic shaping and the shared
        # light/dark surface. This is deliberately not a desktop screenshot.
        image = popup.grab().toImage()
        assert not image.isNull()
        center = image.pixelColor(image.width() // 2, 2)
        assert center.alpha() > 0
        if language in {"ru", "ar", "de"} and dpi == 144:
            output = os.environ.get("CNT_QA_NOTIFICATION_RENDER_DIR")
            if output:
                os.makedirs(output, exist_ok=True)
                image.save(os.path.join(output, f"copy-{language}-{'dark' if dark else 'light'}.png"))
    finally:
        popup.close()
        popup.deleteLater()
        app.setProperty("ui_theme", previous_theme)


def test_no_monitor_safely_skips_feedback(monkeypatch):
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    popup = CopyNotificationPopup()
    monkeypatch.setattr(QtWidgets.QApplication, "screenAt", staticmethod(lambda _pos: None))
    monkeypatch.setattr(QtWidgets.QApplication, "primaryScreen", staticmethod(lambda: None))
    try:
        popup.show_message("Copied")
        assert not popup.isVisible()
        assert not popup._dismiss.isActive()
    finally:
        popup.deleteLater()


def test_manual_close_then_new_copy_reopens_notice():
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    popup = CopyNotificationPopup()
    try:
        popup.show_message("First", duration_ms=60)
        popup.close()
        assert not popup.isVisible()
        popup.show_message("Second", duration_ms=160)
        QTest.qWait(80)
        assert popup.isVisible() and "Second" in popup.text()
        QTest.qWait(100)
        assert not popup.isVisible()
    finally:
        popup.close()
        popup.deleteLater()


def test_disposed_native_receiver_does_not_receive_feedback():
    from copy_feedback import emit_copy_feedback
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    widget = _Receiver({'notifications': True})
    popup = widget._copy_notice
    widget.deleteLater()
    app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    try:
        assert emit_copy_feedback('en') is False
        assert emit_copy_feedback('en', failed=True) is False
    finally:
        popup.close()
        popup.deleteLater()


def test_a_new_registered_owner_survives_old_owner_disposal():
    from copy_feedback import emit_copy_feedback
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    previous = _Receiver({'notifications': True})
    current = _Receiver({'notifications': True})
    try:
        previous.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        assert emit_copy_feedback('ru') is True
        app.processEvents()
        assert current._copy_notice.isVisible()
        assert main.TRANSLATION_RESULT_DIALOG_TEXT['ru']['copied'] in current._copy_notice.text()
    finally:
        for popup in (previous._copy_notice, current._copy_notice):
            popup.close()
            popup.deleteLater()
        current.deleteLater()
