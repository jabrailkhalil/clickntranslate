import os
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtTest import QTest
from styled_dialogs import CopyNotificationPopup

import main


_APP = None


def _app():
    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return _APP


class _Receiver(QtWidgets.QWidget):
    _copy_notification_signal = QtCore.pyqtSignal(str)


class _NotificationHarness:
    _show_copy_notification = main.DarkThemeApp._show_copy_notification

    def __init__(self, enabled=True):
        self.config = {"notifications": enabled}
        self.current_interface_language = "en"
        self.tray_icon = mock.Mock()
        self._copy_notice = CopyNotificationPopup()
        self._show_status_signal = SimpleNamespace(emit=mock.Mock())
        self._hide_status_signal = SimpleNamespace(emit=mock.Mock())

    def has_tray(self):
        return True


def test_notification_is_visible_even_when_a_tray_exists():
    _app()
    harness = _NotificationHarness(enabled=True)
    disabled = _NotificationHarness(enabled=False)
    try:
        harness._show_copy_notification("ru")
        assert harness._copy_notice.isVisible()
        assert main.TRANSLATION_RESULT_DIALOG_TEXT['ru']['copied'] in harness._copy_notice.text()
        assert harness._copy_notice.screen().availableGeometry().contains(harness._copy_notice.geometry())
        assert harness._copy_notice.testAttribute(QtCore.Qt.WA_ShowWithoutActivating)
        harness.tray_icon.showMessage.assert_not_called()
        disabled._show_copy_notification("en")
        assert not disabled._copy_notice.isVisible()
        disabled._show_copy_notification("en", force=True)
        assert disabled._copy_notice.isVisible()
    finally:
        harness._copy_notice.close()
        disabled._copy_notice.close()


def test_repeated_copy_extends_notice_instead_of_old_timeout_hiding_it():
    _app()
    popup = CopyNotificationPopup()
    try:
        popup.show_message('First', duration_ms=80)
        QTest.qWait(50)
        popup.show_message('Second', duration_ms=160)
        QTest.qWait(60)
        assert popup.isVisible() and 'Second' in popup.text()
        QTest.qWait(140)
        assert not popup.isVisible()
    finally:
        popup.close()


def test_copy_notification_dispatch_is_opt_in_and_thread_safe_signal_based():
    app = _app()
    receiver = _Receiver()
    received = []
    receiver._copy_notification_signal.connect(received.append)
    try:
        with mock.patch.object(
            main,
            "get_cached_config",
            return_value={"notifications": True, "interface_language": "de"},
        ):
            assert main.notify_copy_completed() is True
        app.processEvents()
        assert received == ["de"]

        received.clear()
        assert main.notify_copy_completed({"notifications": False}) is False
        assert received == []
    finally:
        receiver.close()


def test_every_recorded_copy_runs_the_optional_notification_hook():
    fake_thread = mock.Mock()
    with mock.patch.object(main, "notify_copy_completed") as notify, \
            mock.patch.object(
                main.threading, "Thread", return_value=fake_thread
            ) as thread_class:
        main.save_copy_history("copied text")

    notify.assert_called_once_with()
    thread_class.assert_called_once_with(
        target=main._save_copy_history_sync,
        args=("copied text",),
        daemon=True,
    )
    fake_thread.start.assert_called_once_with()
