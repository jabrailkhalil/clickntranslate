import pytest

import main
from settings_window import (
    SETTINGS_EXPORT_FORMAT,
    SETTINGS_EXPORT_SCHEMA,
    settings_export_payload,
    validated_import_settings,
)


def test_settings_export_is_versioned_and_json_safe():
    payload = settings_export_payload({
        "interface_language": "ru",
        "result_window_hidden_modes": ("area",),
    })

    assert payload["format"] == SETTINGS_EXPORT_FORMAT
    assert payload["schema"] == SETTINGS_EXPORT_SCHEMA
    assert payload["settings"]["interface_language"] == "ru"
    assert payload["settings"]["result_window_hidden_modes"] == ["area"]


def test_import_accepts_known_type_safe_values_and_ignores_unknown_ones():
    payload = settings_export_payload({
        "interface_language": "de",
        "theme": "Светлая",
        "autostart": True,
        "ocr_dim_strength": 70,
        "unknown_future_option": "ignored",
    })

    imported = validated_import_settings(payload, main.DEFAULT_CONFIG)

    assert imported == {
        "interface_language": "de",
        "theme": "Светлая",
        "autostart": True,
        "ocr_dim_strength": 70,
    }


def test_import_clamps_numeric_controls_to_their_ui_ranges():
    payload = settings_export_payload({
        "ocr_dim_strength": 900,
        "game_capture_interval_ms": 1,
        "game_overlay_opacity": -20,
        "game_text_similarity": 4.0,
    })

    imported = validated_import_settings(payload, main.DEFAULT_CONFIG)

    assert imported["ocr_dim_strength"] == 80
    assert imported["game_capture_interval_ms"] == 450
    assert imported["game_overlay_opacity"] == 45
    assert imported["game_text_similarity"] == 1.0


@pytest.mark.parametrize(
    "payload",
    (
        None,
        {},
        {"format": SETTINGS_EXPORT_FORMAT, "schema": 999, "settings": {}},
        {"format": SETTINGS_EXPORT_FORMAT, "schema": 1, "settings": []},
        {"format": SETTINGS_EXPORT_FORMAT, "schema": 1, "settings": {"autostart": "yes"}},
    ),
)
def test_import_rejects_foreign_empty_or_type_unsafe_documents(payload):
    with pytest.raises(ValueError):
        validated_import_settings(payload, main.DEFAULT_CONFIG)
