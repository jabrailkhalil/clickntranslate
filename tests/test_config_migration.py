import json
import os
import tempfile
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import main


def test_old_config_receives_both_new_default_hotkeys():
    old_config = {
        "theme": main.DEFAULT_CONFIG["theme"],
        "interface_language": "en",
        "copy_hotkey": "Ctrl+Alt+C",
        "translate_hotkey": "Ctrl+Alt+T",
    }

    migrated, missing = main.merge_config_defaults(old_config)

    assert migrated["fullscreen_translate_hotkey"] == "Ctrl+Alt+F"
    assert migrated["translate_selection_hotkey"] == "Ctrl+Alt+Q"
    assert "fullscreen_translate_hotkey" in missing
    assert "translate_selection_hotkey" in missing


def test_intentionally_removed_hotkey_stays_empty():
    config = {
        "fullscreen_translate_hotkey": "",
        "translate_selection_hotkey": "",
    }

    migrated, missing = main.merge_config_defaults(config)

    assert migrated["fullscreen_translate_hotkey"] == ""
    assert migrated["translate_selection_hotkey"] == ""
    assert "fullscreen_translate_hotkey" not in missing
    assert "translate_selection_hotkey" not in missing


def test_app_load_persists_migrated_defaults():
    old_config = {
        "theme": main.DEFAULT_CONFIG["theme"],
        "interface_language": "en",
        "autostart": False,
        "translation_mode": "English",
        "start_minimized": False,
        "copy_hotkey": "Ctrl+Alt+C",
        "translate_hotkey": "Ctrl+Alt+T",
    }
    with tempfile.TemporaryDirectory(prefix="cnt_config_migration_") as temp_dir:
        config_path = os.path.join(temp_dir, "config.json")
        with open(config_path, "w", encoding="utf-8") as stream:
            json.dump(old_config, stream)

        saved = []
        dummy = SimpleNamespace()
        dummy.sync_autostart_state = lambda repair_stale=True: False
        dummy.save_config = lambda: saved.append(dict(dummy.config))

        with mock.patch.object(main, "get_data_file", return_value=config_path):
            main.DarkThemeApp.load_config(dummy)

    assert saved
    assert dummy.config["fullscreen_translate_hotkey"] == "Ctrl+Alt+F"
    assert dummy.config["translate_selection_hotkey"] == "Ctrl+Alt+Q"
