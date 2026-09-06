import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import layout_editor  # noqa: E402


class LayoutEditorDraftTest(unittest.TestCase):
    def test_invalid_draft_is_bounded_and_keeps_every_hotkey_once(self):
        draft = layout_editor.normalized_layout({
            "main": {
                "hotkey_order": ["copy", "copy", "unknown", None],
                "hotkey_horizontal_spacing": 999,
                "engine_status_width": 20,
            },
            "settings": {"actions_footer_gap": -50},
            "widgets": {
                "main": {
                    "translate_button": {
                        "x": -20,
                        "y": 900,
                        "w": 9999,
                        "h": 1,
                        "text": "Новая надпись",
                    }
                }
            },
            "editor": {"snap_enabled": False, "grid_size": 100},
        })
        order = [key for key in draft["main"]["hotkey_order"] if key]
        self.assertEqual(set(order), set(layout_editor.HOTKEY_KEYS))
        self.assertEqual(len(order), len(layout_editor.HOTKEY_KEYS))
        self.assertEqual(draft["main"]["hotkey_horizontal_spacing"], 40)
        self.assertEqual(draft["main"]["engine_status_width"], 480)
        self.assertEqual(draft["settings"]["actions_footer_gap"], 4)
        self.assertEqual(
            draft["widgets"]["main"]["translate_button"],
            {
                "x": 0,
                "y": 399,
                "w": 700,
                "h": 1,
                "text": "Новая надпись",
            },
        )
        self.assertFalse(draft["editor"]["snap_enabled"])
        self.assertEqual(draft["editor"]["grid_size"], 32)

    def test_save_and_load_round_trip_uses_only_the_draft_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "layout.json"
            values = layout_editor.normalized_layout()
            values["main"]["engine_status_width"] = 605
            values["settings"]["actions_footer_gap"] = 23
            saved = layout_editor.save_layout_draft(values, path)
            loaded = layout_editor.load_layout_draft(path)
            self.assertEqual(loaded, saved)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), saved)

    def test_missing_draft_uses_current_application_defaults(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "missing.json"
            self.assertEqual(
                layout_editor.load_layout_draft(path),
                layout_editor.normalized_layout(),
            )


if __name__ == "__main__":
    unittest.main()
