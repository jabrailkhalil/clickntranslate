"""The guide has to point at something unmistakably.

A soft glow behind a small button on a dark window reads as styling, not as
"click this". Everything except the target going dark cannot be misread.
"""

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PyQt5.QtCore import QRect, Qt  # noqa: E402
from PyQt5.QtWidgets import QApplication, QPushButton, QWidget  # noqa: E402

import main  # noqa: E402

TARGET = QRect(150, 80, 120, 32)


class GuideSpotlightTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.host = QWidget()
        self.host.resize(400, 200)
        self.host.setStyleSheet("background:#121212;")
        self.button = QPushButton("Target", self.host)
        self.button.setGeometry(TARGET)
        self.host.show()
        self.app.processEvents()

    def tearDown(self):
        self.host.close()
        self.app.processEvents()

    def _shot(self, spotlight):
        for _ in range(3):
            self.app.processEvents()
        return self.host.grab().toImage()

    @staticmethod
    def _luma(image, x, y):
        colour = image.pixel(x, y)
        return ((colour >> 16) & 0xFF) + ((colour >> 8) & 0xFF) + (colour & 0xFF)

    def test_everything_but_the_target_is_dimmed(self):
        spotlight = main.GuideSpotlight(self.host)
        plain = self._shot(None)
        spotlight.spotlight(TARGET)
        dimmed = self._shot(spotlight)

        corner = (20, 20)
        self.assertLess(
            self._luma(dimmed, *corner), self._luma(plain, *corner),
            "the rest of the window should go darker",
        )
        inside = (TARGET.center().x(), TARGET.center().y())
        self.assertEqual(
            self._luma(dimmed, *inside), self._luma(plain, *inside),
            "the control itself must not be dimmed",
        )

    def test_a_ring_is_drawn_around_the_target(self):
        spotlight = main.GuideSpotlight(self.host)
        spotlight.spotlight(TARGET)
        image = self._shot(spotlight)

        edge = TARGET.left() - spotlight.PADDING
        band = [image.pixel(x, TARGET.center().y()) for x in range(edge - 4, edge + 4)]
        # The accent is a light violet: blue high, and blue above red.
        self.assertTrue(
            any((c & 0xFF) > 0x90 and (c & 0xFF) > ((c >> 16) & 0xFF) for c in band),
            [hex(c & 0xFFFFFF) for c in band],
        )

    def test_the_control_underneath_stays_clickable(self):
        spotlight = main.GuideSpotlight(self.host)
        spotlight.spotlight(TARGET)
        self.assertTrue(spotlight.testAttribute(Qt.WA_TransparentForMouseEvents))
        # It covers the window, so without that attribute nothing could be
        # clicked and the guide could never advance.
        self.assertEqual(spotlight.size(), self.host.size())

    def test_clearing_removes_it(self):
        spotlight = main.GuideSpotlight(self.host)
        spotlight.spotlight(TARGET)
        self.assertTrue(spotlight.isVisible())
        spotlight.clear()
        self.assertFalse(spotlight.isVisible())

        after = self._shot(None)
        corner = (20, 20)
        self.host.repaint()
        self.assertGreater(self._luma(after, *corner), 0)

    def test_it_follows_the_target_between_steps(self):
        spotlight = main.GuideSpotlight(self.host)
        spotlight.spotlight(TARGET)
        first = self._shot(spotlight)
        second_target = QRect(20, 20, 90, 30)
        spotlight.spotlight(second_target)
        second = self._shot(spotlight)

        moved = (second_target.center().x(), second_target.center().y())
        self.assertGreater(
            self._luma(second, *moved), self._luma(first, *moved),
            "the new target should be the bright one now",
        )


class ResultWindowDefaultTest(unittest.TestCase):
    """Out of the box every action shows the window; turning one off is the
    user's move, not the default."""

    def test_a_fresh_config_hides_nothing(self):
        merged, _missing = main.merge_config_defaults({})
        self.assertEqual(main.result_window_hidden_modes(merged), ())
        for mode in main.RESULT_WINDOW_MODES:
            self.assertFalse(main.result_window_hidden_for(merged, mode), mode)

    def test_the_shipped_default_is_empty(self):
        self.assertEqual(main.DEFAULT_CONFIG["result_window_hidden_modes"], ())

    def test_an_upgraded_config_keeps_showing_everything(self):
        """A config written before the setting existed must not start hiding
        windows when the key is added."""
        old = {"interface_language": "en", "theme": "Темная"}
        merged, _missing = main.merge_config_defaults(old)
        self.assertEqual(main.result_window_hidden_modes(merged), ())


if __name__ == "__main__":
    unittest.main()
