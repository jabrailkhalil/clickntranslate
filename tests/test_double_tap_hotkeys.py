import pytest

from double_tap_hotkeys import _TapState, canonical_double_tap


@pytest.mark.parametrize('value,expected', [('shift, shift', 'Shift, Shift'), ('F8, F8', 'F8, F8'),
    ('Ctrl+X', None), ('Shift, Ctrl', None), ('Shift', None), ('F8,F8,F8', None)])
def test_parse_only_two_identical_bare_keys(value, expected):
    assert canonical_double_tap(value) == expected


def test_two_short_taps_fire_once_with_left_and_right_modifiers():
    state = _TapState()
    outputs = [state.feed(key, down, time, 1, {0x10}) for key, down, time in
               [(0xA0, True, 0), (0xA0, False, .05), (0xA1, True, .2), (0xA1, False, .25)]]
    assert outputs == [None, None, None, 0x10]
    assert state.previous is None and not state.down


@pytest.mark.parametrize('interruption', ['repeat', 'hold', 'other_key', 'other_window', 'injected', 'timeout'])
def test_non_gestures_never_trigger(interruption):
    state = _TapState()
    state.feed(0xA0, True, 0, 1, {0x10})
    state.feed(0xA0, False, .05, 1, {0x10})
    if interruption == 'other_key':
        state.feed(65, True, .1, 1, {0x10})
        state.feed(65, False, .15, 1, {0x10})
    if interruption == 'injected':
        state.feed(65, True, .1, 1, {0x10}, injected=True)
    foreground = 2 if interruption == 'other_window' else 1
    start = 1 if interruption == 'timeout' else .2
    state.feed(0xA0, True, start, foreground, {0x10})
    if interruption == 'repeat':
        state.feed(0xA0, True, start+.02, foreground, {0x10})
    released = start + (.4 if interruption == 'hold' else .05)
    assert state.feed(0xA0, False, released, foreground, {0x10}) is None
