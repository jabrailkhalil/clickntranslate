import os
import threading
import time
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5 import QtCore
from PyQt5.QtWidgets import QApplication

import main
import ocr


class _CallbackReceiver(QtCore.QObject):
    def __init__(self):
        super().__init__()
        self.callbacks = []

    @QtCore.pyqtSlot(object)
    def receive(self, callback):
        self.callbacks.append((callback, QtCore.QThread.currentThread()))


class TestStartupOcrPreparation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_startup_keeps_models_and_unused_overlays_unloaded(self):
        receiver = _CallbackReceiver()
        main.hotkey_dispatcher.triggered.connect(receiver.receive)
        try:
            with mock.patch.object(ocr, "warm_up") as warm_up, \
                    mock.patch.object(
                        main,
                        "get_cached_config",
                        return_value={
                            "ocr_engine": "Windows",
                            "translator_engine": "Google",
                            "last_ocr_language": "en",
                        },
                    ):
                worker = threading.Thread(
                    target=main._warm_up_ocr_after_window_is_visible,
                    name="StartupWarmupRegressionTest",
                )
                worker.start()
                worker.join(timeout=3)
                self.assertFalse(worker.is_alive())
                warm_up.assert_not_called()
            self.app.processEvents()
            self.assertEqual(receiver.callbacks, [])
        finally:
            main.hotkey_dispatcher.triggered.disconnect(receiver.receive)

    def test_gui_preparation_refuses_wrong_thread_even_if_called_directly(self):
        calls = []
        worker = threading.Thread(
            target=lambda: calls.append(main._prepare_ocr_overlays_on_gui_thread()),
            name="InvalidGuiPreparationRegressionTest",
        )
        with mock.patch.object(ocr, "prepare_overlay") as prepare:
            worker.start()
            worker.join(timeout=3)

        self.assertFalse(worker.is_alive())
        self.assertEqual(calls, [None])
        prepare.assert_not_called()


if __name__ == "__main__":
    unittest.main()
