import json
import os
import tempfile
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import main


def test_old_config_receives_all_new_default_hotkeys():
    old_config = {
        "theme": main.DEFAULT_CONFIG["theme"],
        "interface_language": "en",
        "copy_hotkey": "Ctrl+Alt+C",
        "translate_hotkey": "Ctrl+Alt+T",
    }

    migrated, missing = main.merge_config_defaults(old_config)

    assert migrated["fullscreen_translate_hotkey"] == "Ctrl+Alt+F"
    assert migrated["translate_selection_hotkey"] == main.DEFAULT_SELECTION_HOTKEY
    assert migrated["translate_replace_selection_hotkey"] == main.DEFAULT_REPLACE_SELECTION_HOTKEY
    assert migrated["game_translate_hotkey"] == main.DEFAULT_GAME_HOTKEY
    assert migrated["toggle_window_hotkey"] == main.DEFAULT_TOGGLE_WINDOW_HOTKEY
    assert "fullscreen_translate_hotkey" in missing
    assert "translate_selection_hotkey" in missing
    assert "translate_replace_selection_hotkey" in missing
    assert "game_translate_hotkey" in missing
    assert "toggle_window_hotkey" in missing


def test_old_shared_language_pairs_are_migrated_to_each_hotkey_mode():
    migrated, missing = main.merge_config_defaults({
        "main_translation_source_language": "de",
        "main_translation_target_language": "fr",
        "ocr_translate_source_language": "zh",
        "ocr_translate_target_language": "en",
    })

    assert migrated["selection_translate_source_language"] == "de"
    assert migrated["selection_translate_target_language"] == "fr"
    assert migrated["replace_selection_source_language"] == "de"
    assert migrated["replace_selection_target_language"] == "fr"
    assert migrated["fullscreen_translate_from"] == "zh"
    assert migrated["fullscreen_translate_to"] == "en"
    assert "selection_translate_source_language" in missing
    assert "replace_selection_source_language" in missing
    assert "fullscreen_translate_from" in missing


def test_old_default_is_removed_but_custom_values_are_preserved():
    migrated, _missing = main.merge_config_defaults({
        "toggle_window_hotkey": "Ctrl+Alt+M",
    })
    custom, _missing = main.merge_config_defaults({
        "toggle_window_hotkey": "Ctrl+Shift+Y",
    })

    assert migrated["toggle_window_hotkey"] == main.DEFAULT_TOGGLE_WINDOW_HOTKEY
    assert migrated["hotkey_defaults_revision"] == main.HOTKEY_DEFAULTS_REVISION
    assert custom["toggle_window_hotkey"] == "Ctrl+Shift+Y"


def test_revision_two_defaults_are_cleared_without_touching_custom_hotkeys():
    migrated, _missing = main.merge_config_defaults({
        "hotkey_defaults_revision": 2,
        "translate_selection_hotkey": "Ctrl+Alt+Q",
        "translate_replace_selection_hotkey": "Ctrl+Shift+Q",
        "game_translate_hotkey": "Ctrl+Shift+T",
        "toggle_window_hotkey": "Ctrl+Shift+Space",
    })
    custom, _missing = main.merge_config_defaults({
        "hotkey_defaults_revision": 2,
        "translate_selection_hotkey": "Ctrl+Shift+S",
        "translate_replace_selection_hotkey": "Ctrl+Shift+R",
        "game_translate_hotkey": "Ctrl+Shift+G",
        "toggle_window_hotkey": "Ctrl+Shift+W",
    })

    assert migrated["translate_selection_hotkey"] == main.DEFAULT_SELECTION_HOTKEY
    assert migrated["translate_replace_selection_hotkey"] == main.DEFAULT_REPLACE_SELECTION_HOTKEY
    assert migrated["game_translate_hotkey"] == main.DEFAULT_GAME_HOTKEY
    assert migrated["toggle_window_hotkey"] == main.DEFAULT_TOGGLE_WINDOW_HOTKEY
    assert custom["translate_selection_hotkey"] == "Ctrl+Shift+S"
    assert custom["translate_replace_selection_hotkey"] == "Ctrl+Shift+R"
    assert custom["game_translate_hotkey"] == "Ctrl+Shift+G"
    assert custom["toggle_window_hotkey"] == "Ctrl+Shift+W"


def test_intentionally_removed_hotkey_stays_empty():
    config = {
        "hotkey_defaults_revision": main.HOTKEY_DEFAULTS_REVISION,
        "fullscreen_translate_hotkey": "",
        "translate_selection_hotkey": "",
        "translate_replace_selection_hotkey": "",
        "game_translate_hotkey": "",
        "toggle_window_hotkey": "",
    }

    migrated, missing = main.merge_config_defaults(config)

    assert migrated["fullscreen_translate_hotkey"] == ""
    assert migrated["translate_selection_hotkey"] == ""
    assert migrated["translate_replace_selection_hotkey"] == ""
    assert migrated["game_translate_hotkey"] == ""
    assert migrated["toggle_window_hotkey"] == ""
    assert "fullscreen_translate_hotkey" not in missing
    assert "translate_selection_hotkey" not in missing
    assert "translate_replace_selection_hotkey" not in missing
    assert "game_translate_hotkey" not in missing
    assert "toggle_window_hotkey" not in missing


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
    assert dummy.config["translate_selection_hotkey"] == main.DEFAULT_SELECTION_HOTKEY
    assert dummy.config["translate_replace_selection_hotkey"] == main.DEFAULT_REPLACE_SELECTION_HOTKEY
    assert dummy.config["game_translate_hotkey"] == main.DEFAULT_GAME_HOTKEY
    assert dummy.config["toggle_window_hotkey"] == main.DEFAULT_TOGGLE_WINDOW_HOTKEY


def test_revision_three_gets_gaming_default_but_preserves_custom_or_current_empty():
    migrated, _ = main.merge_config_defaults({
        "hotkey_defaults_revision": 3,
        "game_translate_hotkey": "",
    })
    custom, _ = main.merge_config_defaults({
        "hotkey_defaults_revision": 3,
        "game_translate_hotkey": "Ctrl+Shift+G",
    })
    current_empty, _ = main.merge_config_defaults({
        "hotkey_defaults_revision": main.HOTKEY_DEFAULTS_REVISION,
        "game_translate_hotkey": "",
    })

    assert migrated["game_translate_hotkey"] == main.DEFAULT_GAME_HOTKEY
    assert custom["game_translate_hotkey"] == "Ctrl+Shift+G"
    assert current_empty["game_translate_hotkey"] == ""


def test_revision_four_receives_defaults_for_every_visible_action():
    migrated, _ = main.merge_config_defaults({
        "hotkey_defaults_revision": 4,
        "translate_selection_hotkey": "",
        "translate_replace_selection_hotkey": "",
        "game_translate_hotkey": "",
        "toggle_window_hotkey": "",
    })

    assert migrated["translate_selection_hotkey"] == main.DEFAULT_SELECTION_HOTKEY
    assert migrated["translate_replace_selection_hotkey"] == main.DEFAULT_REPLACE_SELECTION_HOTKEY
    assert migrated["game_translate_hotkey"] == main.DEFAULT_GAME_HOTKEY
    assert migrated["toggle_window_hotkey"] == main.DEFAULT_TOGGLE_WINDOW_HOTKEY


def test_window_toggle_preserves_tray_or_taskbar_destination():
    tray_window = SimpleNamespace(
        isVisible=lambda: True,
        windowState=lambda: main.Qt.WindowNoState,
        _window_hide_destination="tray",
        has_tray=lambda: True,
        hide=mock.Mock(),
        minimize_to_taskbar=mock.Mock(),
        show_window_from_tray=mock.Mock(),
    )
    main.DarkThemeApp.toggle_window_visibility(tray_window)
    tray_window.hide.assert_called_once_with()
    tray_window.minimize_to_taskbar.assert_not_called()

    taskbar_window = SimpleNamespace(
        isVisible=lambda: True,
        windowState=lambda: main.Qt.WindowNoState,
        _window_hide_destination="taskbar",
        has_tray=lambda: True,
        hide=mock.Mock(),
        minimize_to_taskbar=mock.Mock(),
        show_window_from_tray=mock.Mock(),
    )
    main.DarkThemeApp.toggle_window_visibility(taskbar_window)
    taskbar_window.minimize_to_taskbar.assert_called_once_with()

    hidden_window = SimpleNamespace(
        isVisible=lambda: False,
        windowState=lambda: main.Qt.WindowNoState,
        show_window_from_tray=mock.Mock(),
    )
    main.DarkThemeApp.toggle_window_visibility(hidden_window)
    hidden_window.show_window_from_tray.assert_called_once_with(force_show=True)
