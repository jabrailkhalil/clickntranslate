from live_translation import LiveTextState, live_frame_changed


def line(text, x=10, y=20):
    return (x, y, 180, 24, text)


def test_typewriter_text_waits_for_stability_but_has_a_deadline():
    state = LiveTextState()
    state.observe([line('Open')], 0)
    assert not state.pending(0)
    state.observe([line('Open the')], .2)
    assert not state.pending(.2)
    state.observe([line('Open the gate')], .4)
    state.observe([line('Open the gate')], .6)
    assert state.pending(.6) == ['Open the gate']
    state.observe([line('Open the gate before')], 1.3)
    assert state.pending(1.3) == ['Open the gate before']


def test_scrolling_and_duplicate_labels_reuse_translation_at_current_positions():
    state = LiveTextState()
    state.observe([line('Settings')], 0)
    state.remember([('Settings', 'Настройки')])
    state.observe([line('Settings', y=100), line('Settings', x=500)], 1)
    assert state.pending(1) == []
    assert state.blocks() == [(*line('Settings', y=100), 'Настройки'),
                              (*line('Settings', x=500), 'Настройки')]


def test_late_response_cannot_reappear_over_a_new_scene():
    state = LiveTextState()
    state.observe([line('Old dialogue')], 0)
    state.observe([line('New dialogue')], 1)
    state.remember([('Old dialogue', 'Старый диалог')])
    assert not state.blocks()
    state.observe([line('New dialogue')], 1.2)
    assert state.pending(1.2) == ['New dialogue']
    state.observe([], 2)
    state.remember([('New dialogue', 'Новый диалог')])
    assert not state.blocks()


def test_ocr_pixel_jitter_is_stable_but_real_movement_updates_coordinates():
    state = LiveTextState()
    state.observe([line('Settings')], 0)
    state.remember([('Settings', 'Настройки')])
    state.observe([line('Settings', x=11, y=21)], .3)
    assert state.blocks()[0][:4] == line('Settings')[:4]
    state.observe([line('Settings', x=17, y=45)], .6)
    assert state.blocks()[0][:4] == line('Settings', x=17, y=45)[:4]


def test_numbers_and_negation_are_never_fuzzy_matched():
    state = LiveTextState(stable_after=0)
    state.remember([('You have 100 coins', 'У вас 100 монет'), ('Do open the gate', 'Открой ворота')])
    lines = [line('You have 101 coins'), line('Do not open the gate', y=70)]
    state.observe(lines, 0)
    state.observe(lines, .2)
    assert state.pending(.2) == ['You have 101 coins', 'Do not open the gate']
    assert not state.blocks()


def test_cache_is_bounded_and_does_not_cross_sessions():
    state = LiveTextState(max_entries=2, max_chars=20)
    state.remember([('one', 'один'), ('two', 'два'), ('three', 'три')])
    state.observe([line('one'), line('two'), line('three')], 0)
    assert len(state.blocks()) == 2
    state.remember([('unreasonably large source', 'result')])
    assert state._cache_chars <= 20
    another_provider = LiveTextState()
    another_provider.observe([line('two')], 0)
    assert another_provider.blocks() == []


def test_small_changed_label_is_detected_on_a_large_unchanged_screen():
    before = [20] * (192 * 108)
    after = before.copy()
    after[1500:1503] = [110, 70, 140]
    assert live_frame_changed(before, after)
    assert not live_frame_changed(before, before.copy())
    assert not live_frame_changed(before, [21] * len(before))
