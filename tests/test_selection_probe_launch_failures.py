"""Selection activity recovers from worker admission failures without OS input."""
from types import SimpleNamespace

import pytest
from PyQt5 import QtCore, QtWidgets

import mode_coordinator
import platform_support
import selection_quick_translate as quick


@pytest.fixture
def selection_probe(monkeypatch):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    assert app.platformName().split(':')[0] == 'offscreen'
    # Disable native pollers before the controller can construct or start one.
    monkeypatch.setattr(quick.SelectionQuickTranslateController, '_start_monitor', lambda _self: None)
    monkeypatch.setattr(platform_support, 'IS_WINDOWS', True)
    monkeypatch.setattr(platform_support, 'IS_MAC', False)
    monkeypatch.setattr(platform_support, 'IS_LINUX', False)
    monkeypatch.setattr(quick, 'is_foreign_foreground', lambda: True)
    monkeypatch.setattr(mode_coordinator, 'active_mode', lambda: None)
    monkeypatch.setattr(quick.QtGui.QCursor, 'pos', staticmethod(lambda: QtCore.QPoint()))
    state = SimpleNamespace(target=101, tasks=[], emitted=[], presented=[])
    monkeypatch.setattr(quick, 'foreground_token', lambda: state.target)
    monkeypatch.setattr(quick, 'read_selected_text', lambda **_kwargs: f'Selection {state.target}')
    pool = SimpleNamespace(start=state.tasks.append)
    monkeypatch.setattr(quick.QtCore.QThreadPool, 'globalInstance', staticmethod(lambda: pool))
    owner = QtCore.QObject()
    controller = quick.SelectionQuickTranslateController(owner)
    monkeypatch.setattr(controller._button, 'show_near',
                        lambda _anchor: state.presented.append(controller._pending_text))
    controller.translate_requested.connect(state.emitted.append)
    state.controller, state.pool = controller, pool
    try:
        yield state
    finally:
        controller.dispose()
        owner.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        app.processEvents()


@pytest.mark.parametrize('mode', ['automatic', 'button'])
@pytest.mark.parametrize('stage', ['construct', 'start'])
@pytest.mark.parametrize('error_type', [OSError, RuntimeError])
def test_refused_probe_is_contained_and_the_next_selection_can_retry(selection_probe, monkeypatch, mode, stage, error_type):
    state = selection_probe
    controller = state.controller
    controller.configure(True, mode)
    with monkeypatch.context() as fault:
        def refuse(*_args, **_kwargs):
            raise error_type('injected selection worker admission failure')
        if stage == 'construct':
            fault.setattr(quick, '_SelectionProbe', refuse)
        else:
            fault.setattr(state.pool, 'start', refuse)
        controller._complete_probe()
    assert controller._inflight is None
    assert not controller._probe_again and not controller._queued_click
    assert not state.emitted and not state.presented
    controller._complete_probe()
    assert controller._inflight is state.tasks[-1]
    state.tasks[-1].run()
    assert controller._inflight is None
    if mode == 'automatic':
        assert state.emitted == ['Selection 101']
    else:
        assert state.presented == ['Selection 101']
        assert controller._pending_text == 'Selection 101'
        assert controller._pending_target == 101


def test_button_selection_can_reappear_after_a_failed_refresh(selection_probe, monkeypatch):
    state = selection_probe
    controller = state.controller
    controller.configure(True, 'button')
    controller._complete_probe()
    state.tasks[-1].run()
    assert state.presented == ['Selection 101']
    with monkeypatch.context() as fault:
        fault.setattr(state.pool, 'start', lambda _task: (_ for _ in ()).throw(OSError('no worker slot')))
        controller._complete_probe()
    assert not controller._pending_text
    controller._complete_probe()
    state.tasks[-1].run()
    assert state.presented == ['Selection 101', 'Selection 101']
    assert controller._pending_text == 'Selection 101'


def test_changed_target_discards_canceled_probe_and_delivers_only_the_current_selection(selection_probe):
    state = selection_probe
    controller = state.controller
    controller.configure(True, 'automatic')
    controller._complete_probe()
    first = state.tasks[-1]
    state.target = 202
    controller._schedule_probe()
    controller._complete_probe()
    first.run()
    assert state.emitted == []
    controller._debounce.stop()
    controller._complete_probe()
    current = state.tasks[-1]
    assert current is not first
    current.run()
    assert state.emitted == ['Selection 202']
    assert controller._inflight is None


def test_disposing_a_pending_probe_discards_its_result_and_queued_rerun(selection_probe):
    state = selection_probe
    controller = state.controller
    controller.configure(True, 'automatic')
    controller._complete_probe()
    first = state.tasks[-1]
    controller._complete_probe()
    controller.dispose()
    first.run()
    assert not state.emitted and not state.presented
    assert len(state.tasks) == 1
    assert controller._inflight is None
