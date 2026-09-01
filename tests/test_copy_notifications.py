import os
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5 import QtCore, QtWidgets

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
        self._show_status_signal = SimpleNamespace(emit=mock.Mock())
        self._hide_status_signal = SimpleNamespace(emit=mock.Mock())

    def has_tray(self):
        return True


def test_notification_setting_uses_the_tray_with_localized_copy_text():
    harness = _NotificationHarness(enabled=True)
    harness._show_copy_notification("ru")
    harness.tray_icon.showMessage.assert_called_once_with(
        "Click'n'Translate",
        main.TRANSLATION_RESULT_DIALOG_TEXT["ru"]["copied"],
        main.QSystemTrayIcon.Information,
        1800,
    )

    disabled = _NotificationHarness(enabled=False)
    disabled._show_copy_notification("en")
    disabled.tray_icon.showMessage.assert_not_called()

    disabled._show_copy_notification("en", force=True)
    disabled.tray_icon.showMessage.assert_called_once()


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
