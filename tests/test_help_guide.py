"""The guide has to describe the window the user is actually looking at.

Its Settings section named three of the seven check boxes, none of the buttons
and none of the drop-downs on the right, so the parts of the window a first-time
user has to click were the parts the guide did not mention.
"""

import os
import re
import sys
import unicodedata
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import main  # noqa: E402
from settings_window import settings_text  # noqa: E402

LANGUAGES = ("en", "ru", "es", "de", "fr", "zh")

# Every control in the settings window, by the key its label comes from.
CHECK_BOXES = (
    "autostart",
    "start_minimized",
    "copy_translated_text",
    "copy_history",
    "history",
    "keep_visible_on_ocr",
    "freeze_screen_on_ocr",
)
BUTTONS = (
    "clear_cache",
    "reset",
    "update",
    "ocr_language_packs",
    "copy_history_button",
    "translation_history_button",
    "hotkeys",
)


def _guide_text(lang):
    return "\n".join(
        item for _title, items in main.HELP_CONTENT[lang] for item in items
    )


def _normalise(value):
    """Compare on letters only: the guide writes labels without the trailing
    colon, and the window and the guide disagree about diacritics — the window
    says "Afficher fenêtre :" where the guide says "Afficher fenetre"."""
    stripped = "".join(
        char for char in unicodedata.normalize("NFKD", value.lower())
        if not unicodedata.combining(char)
    )
    return re.sub(r"[^0-9a-zЀ-ӿ一-鿿]+", "", stripped)


class GuideCoverageTest(unittest.TestCase):
    def test_every_check_box_is_explained(self):
        for lang in LANGUAGES:
            guide = _normalise(_guide_text(lang))
            for key in CHECK_BOXES:
                label = settings_text(lang, key)
                self.assertIn(_normalise(label), guide, (lang, key, label))

    def test_every_button_is_explained(self):
        for lang in LANGUAGES:
            guide = _normalise(_guide_text(lang))
            for key in BUTTONS:
                label = settings_text(lang, key)
                self.assertIn(_normalise(label), guide, (lang, key, label))

    def test_the_show_window_dropdown_is_explained(self):
        """It is new, it holds three switches, and nothing else in the window
        looks like it."""
        for lang in LANGUAGES:
            guide = _normalise(_guide_text(lang))
            # The label carries a colon in the window; the guide does not.
            label = settings_text(lang, "result_window_label")
            self.assertIn(_normalise(label), guide, (lang, label))
            for mode in main.RESULT_WINDOW_MODES:
                row = settings_text(lang, f"result_window_row_{mode}")
                # The guide describes the actions rather than quoting the rows,
                # so match on the distinctive part of each one.
                self.assertTrue(
                    any(_normalise(word) in guide
                        for word in row.split() if len(word) > 4),
                    (lang, mode, row),
                )
            replacement = settings_text(lang, "replace_selection_translate_label")
            self.assertIn(_normalise(replacement), guide, (lang, replacement))

    def test_unticked_does_not_read_as_no_translation(self):
        """The setting only chooses where the result goes, and the guide has to
        say so or it reads like a switch that turns translation off."""
        clues = {
            "en": ("clipboard",),
            "ru": ("буфер",),
            "es": ("portapapeles",),
            "de": ("zwischenablage",),
            "fr": ("presse",),
            "zh": ("剪贴板",),
        }
        for lang in LANGUAGES:
            guide = _guide_text(lang).lower()
            self.assertTrue(
                any(clue in guide for clue in clues[lang]), lang
            )

    def test_the_guide_renders_for_every_language(self):
        for lang in LANGUAGES:
            html = main.help_text(lang)
            self.assertIn("section-title", html)
            for title, _items in main.HELP_CONTENT[lang]:
                self.assertIn(title, html, (lang, title))
            # Unbalanced markup from a hand-edited string shows as raw tags.
            self.assertEqual(
                html.count("<span class='item-title'>"), html.count("</span>"), lang
            )

    def test_help_uses_a_real_light_palette(self):
        html = main.help_text("ru", "Светлая")

        self.assertIn("body { color: #2b2532", html)
        self.assertIn(".hero-title { color: #211b28", html)
        self.assertNotIn("body { color: #e8e0f7", html)

    def test_document_guide_covers_every_entry_point_and_partial_translation(self):
        fragment_clues = {
            "en": "fragment",
            "ru": "фрагмент",
            "es": "fragmento",
            "de": "abschnitt",
            "fr": "passage",
            "zh": "片段",
        }
        icon_clues = {
            "en": "icon",
            "ru": "значок",
            "es": "icono",
            "de": "symbol",
            "fr": "icône",
            "zh": "图标",
        }
        for lang in LANGUAGES:
            section = "\n".join(
                item
                for _title, items in main.DOCUMENT_HELP_CONTENT[lang]
                for item in items
            ).lower()
            self.assertIn(".docx", section, lang)
            self.assertIn("ctrl+o", section, lang)
            self.assertIn(fragment_clues[lang], section, lang)
            self.assertIn(icon_clues[lang], section, lang)

    def test_hotkey_guide_explains_hover_replace_and_rebinding(self):
        hover_clues = {
            "en": "hover",
            "ru": "наведите",
            "es": "ratón",
            "de": "zeigen",
            "fr": "survolez",
            "zh": "悬停",
        }
        for lang in LANGUAGES:
            faq = _guide_text(lang).lower()
            tour = "\n".join(
                body for _action, _title, body in main.guide_text(lang)["steps"]
            ).lower()
            self.assertIn(hover_clues[lang], faq, lang)
            self.assertIn("ctrl+alt+q", tour, lang)
            self.assertIn("ctrl+shift+q", tour, lang)
            self.assertIn("esc", faq, lang)


if __name__ == "__main__":
    unittest.main()
