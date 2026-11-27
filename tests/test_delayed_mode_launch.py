"""Delayed capture hotkeys obey the newest user command without desktop I/O."""
from types import SimpleNamespace
from unittest import mock

import pytest

import game_mode
import main
import mode_coordinator
import ocr


@pytest.fixture
def launches(monkeypatch):
    mode_coordinator._reset_for_tests()
    pending, started, stopped = [], [], []

    def start(name):
        if mode_coordinator.request_mode(name, lambda: stopped.append(name)):
            started.append(name)

    monkeypatch.setattr(main.QTimer, "singleShot", lambda delay, callback: pending.append(callback))
    monkeypatch.setattr(ocr, "run_screen_capture", lambda mode: start("capture:" + mode))
    monkeypatch.setattr(ocr, "run_fullscreen_translate", lambda: start("fullscreen"))
    monkeypatch.setattr(game_mode, "toggle_game_mode", lambda: start("game"))
    monkeypatch.setattr(game_mode, "game_mode_active", lambda: mode_coordinator.active_mode() == "game")
    owner = SimpleNamespace(config={"keep_visible_on_ocr": True}, current_interface_language="en",
                            _ensure_capture_permission=lambda: True, hide=mock.Mock())
    yield owner, pending, started, stopped
    mode_coordinator._reset_for_tests()


@pytest.mark.parametrize("old", ["launch_fullscreen_translate", "launch_game_translate"])
@pytest.mark.parametrize("new", ["launch_copy", "launch_translate", "launch_ocr"])
def test_new_area_command_cannot_be_replaced_by_an_older_delayed_hotkey(launches, old, new):
    owner, pending, started, stopped = launches
    main.DarkThemeApp.__dict__[old](owner)
    main.DarkThemeApp.__dict__[new](owner)
    current = mode_coordinator.active_mode()
    pending.pop(0)()
    assert mode_coordinator.active_mode() == current
    assert started == [current]
    assert stopped == []


@pytest.mark.parametrize("method", ["launch_fullscreen_translate", "launch_game_translate"])
def test_repeating_a_pending_hotkey_cancels_it(launches, method):
    owner, pending, started, _ = launches
    main.DarkThemeApp.__dict__[method](owner)
    main.DarkThemeApp.__dict__[method](owner)
    for callback in pending:
        callback()
    assert mode_coordinator.active_mode() is None
    assert started == []


@pytest.mark.parametrize("order", [("launch_fullscreen_translate", "launch_game_translate", "game"),
                                   ("launch_game_translate", "launch_fullscreen_translate", "fullscreen")])
def test_only_the_latest_of_two_delayed_modes_starts(launches, order):
    owner, pending, started, _ = launches
    first, second, expected = order
    main.DarkThemeApp.__dict__[first](owner)
    main.DarkThemeApp.__dict__[second](owner)
    for callback in pending:
        callback()
    assert mode_coordinator.active_mode() == expected
    assert started == [expected]


def test_stop_cancels_pending_capture_even_when_no_mode_has_started(launches):
    owner, pending, started, _ = launches
    main.DarkThemeApp.launch_fullscreen_translate(owner)
    mode_coordinator.stop_active_mode()
    pending.pop(0)()
    assert started == []


def test_active_mode_still_toggles_off_after_the_delay(launches):
    owner, pending, started, stopped = launches
    main.DarkThemeApp.launch_fullscreen_translate(owner)
    pending.pop(0)()
    main.DarkThemeApp.launch_fullscreen_translate(owner)
    pending.pop(0)()
    assert mode_coordinator.active_mode() is None
    assert started == ["fullscreen"] and stopped == ["fullscreen"]
