import mode_coordinator


def setup_function():
    mode_coordinator._reset_for_tests()


def teardown_function():
    mode_coordinator._reset_for_tests()


def test_repeating_the_same_mode_stops_it_instead_of_starting_a_second_copy():
    stopped = []

    assert mode_coordinator.request_mode("game", lambda: stopped.append("game"))
    assert mode_coordinator.active_mode() == "game"
    assert not mode_coordinator.request_mode("game", lambda: stopped.append("new"))
    assert stopped == ["game"]
    assert mode_coordinator.active_mode() is None


def test_starting_a_different_mode_stops_the_previous_owner_first():
    stopped = []

    assert mode_coordinator.request_mode("capture:ocr", lambda: stopped.append("ocr"))
    assert mode_coordinator.request_mode("fullscreen", lambda: stopped.append("screen"))
    assert stopped == ["ocr"]
    assert mode_coordinator.active_mode() == "fullscreen"

    # A late closeEvent from the old mode cannot release the new owner.
    assert not mode_coordinator.release_mode("capture:ocr")
    assert mode_coordinator.active_mode() == "fullscreen"


def test_stop_active_mode_runs_cleanup_once_and_clears_the_owner():
    stopped = []
    mode_coordinator.request_mode("capture:copy", lambda: stopped.append("copy"))

    assert mode_coordinator.stop_active_mode() == "capture:copy"
    assert mode_coordinator.stop_active_mode() is None
    assert stopped == ["copy"]
    assert mode_coordinator.active_mode() is None
