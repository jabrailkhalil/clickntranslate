import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

import main  # noqa: E402
import mode_coordinator  # noqa: E402
import platform_support  # noqa: E402
import translater  # noqa: E402
from selection_quick_translate import (  # noqa: E402
    SelectionQuickTranslateController,
    DEBOUNCE_MS,
)
from PyQt5.QtWidgets import QApplication  # noqa: E402


class SelectionQuickTranslateLogicTest(unittest.TestCase):
    def test_automatic_mode_dedupes_identical_text(self):
        app = QApplication.instance() or QApplication([])
        owner = SimpleNamespace(
            config={"selection_quick_translate_enabled": True, "selection_quick_translate_mode": "automatic"},
            destroyed=SimpleNamespace(connect=lambda *_: None),
        )
        emitted = []
        with mock.patch("selection_quick_translate.is_foreign_foreground", return_value=True), \
                mock.patch("selection_quick_translate.read_selected_text", return_value="Hello there"), \
                mock.patch.object(mode_coordinator, "active_mode", return_value=None):
            controller = SelectionQuickTranslateController(owner)
            controller.translate_requested.connect(emitted.append)
            controller.configure(True, "automatic")
            controller._complete_probe()
            controller._complete_probe()
        self.assertEqual(emitted, ["Hello there"])
        controller.dispose()

    def test_mode_coordinator_blocks_probe(self):
        app = QApplication.instance() or QApplication([])
        owner = SimpleNamespace(
            config={},
            destroyed=SimpleNamespace(connect=lambda *_: None),
        )
        emitted = []
        with mock.patch("selection_quick_translate.is_foreign_foreground", return_value=True), \
                mock.patch("selection_quick_translate.read_selected_text", return_value="Hello") as reader, \
                mock.patch.object(mode_coordinator, "active_mode", return_value="ocr"):
            controller = SelectionQuickTranslateController(owner)
            controller.translate_requested.connect(emitted.append)
            controller.configure(True, "automatic")
            controller._complete_probe()
        reader.assert_not_called()
        self.assertEqual(emitted, [])
        controller.dispose()


class PreloadedSelectionTranslationTest(unittest.TestCase):
    def test_preloaded_text_skips_simulate_copy(self):
        harness = SimpleNamespace(
            config={"interface_language": "en", "restore_clipboard_after_selection": True},
            current_interface_language="en",
            _selected_text_translation_pair=lambda: ("auto", "ru"),
            _show_status_signal=SimpleNamespace(emit=lambda *_: None),
            _hide_status_signal=SimpleNamespace(emit=lambda: None),
            _show_selection_signal=SimpleNamespace(emit=lambda *_: None),
        )

        def fake_thread(target=None, daemon=None, **_kwargs):
            return SimpleNamespace(start=target)

        with mock.patch.multiple(platform_support, IS_LINUX=False, IS_WINDOWS=True, IS_MAC=False), \
                mock.patch.object(main.threading, "Thread", fake_thread), \
                mock.patch.object(main.time, "sleep", lambda _seconds: None), \
                mock.patch.object(main, "simulate_copy") as simulate_copy, \
                mock.patch.object(main, "save_translation_history"), \
                mock.patch.object(translater, "translate_text", return_value="Привет"):
            main.DarkThemeApp._launch_translate_selection(
                harness, replace_selection=False, preloaded_text="Hello"
            )
        simulate_copy.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
