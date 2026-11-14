"""Strict UIA interfaces and per-thread apartments; never import or call real COM."""
import builtins
import ctypes
from pathlib import Path
import sys
import threading
from types import ModuleType, SimpleNamespace
from unittest import mock

import pytest

import platform_support
import selection_platform
import selection_quick_translate as quick
import windows_selection as selection


CHANGED_MODE = 0x80010106
E_FAIL = 0x80004005


class IUIAutomation:
    pass


class IUIAutomationTextPattern:
    pass


class CUIAutomation:
    pass


class NativeCall:
    def __init__(self, callback):
        self.callback = callback

    def __call__(self, *args):
        return self.callback(*args)


class COMValue:
    def __init__(self, state, label):
        self.state, self.label, self.alive = state, label, False
        state.require_mta()
        self.owner = threading.get_ident()
        state.live[self.owner] = state.live.get(self.owner, 0) + 1
        self.alive = True

    def __del__(self):
        if self.alive:
            self.state.live[self.owner] -= 1
            self.state.events.append(('release', self.owner, self.label))


class Automation(COMValue):
    def GetFocusedElement(self):
        self.state.fail('element')
        return None if self.state.empty == 'element' else Element(self.state, 'element')


class Element(COMValue):
    def GetCurrentPattern(self, pattern_id):
        assert pattern_id == 10014
        self.state.fail('pattern')
        return None if self.state.empty == 'pattern' else Unknown(self.state, 'IUnknown')


class Unknown(COMValue):
    def QueryInterface(self, interface):
        assert interface is IUIAutomationTextPattern
        self.state.queries.append(interface)
        self.state.fail('qi')
        return Pattern(self.state, 'text-pattern')


class Pattern(COMValue):
    def GetSelection(self):
        self.state.fail('selection')
        return None if self.state.empty == 'ranges' else Ranges(self.state, 'ranges')


class Ranges(COMValue):
    @property
    def Length(self):
        return 0 if self.state.empty == 'count' else 2

    def GetElement(self, index):
        self.state.fail('range')
        value = TextRange(self.state, 'text-range')
        value.index = index
        return value


class TextRange(COMValue):
    def GetText(self, limit):
        assert limit == -1
        self.state.fail('text')
        return (' Native ', 'selection ')[self.index]


class Scenario:
    def __init__(self):
        self.local = threading.local()
        self.events, self.live, self.queries, self.interfaces, self.modules = [], {}, [], [], []
        self.exits = []
        self.first_import, self.import_error, self.fail_at, self.empty, self.init_failure = False, False, None, None, None
        self.api = SimpleNamespace(CoInitializeEx=NativeCall(self.initialize),
                                   CoUninitialize=NativeCall(self.uninitialize))
        self.seed('none')

    def seed(self, kind):
        self.local.kind = kind
        self.local.refs = 1 if kind in ('mta', 'sta', 'mainsta') else 0
        self.local.implicit = kind == 'implicit'

    def initialize(self, reserved, flags):
        assert reserved is None and flags == 0
        result = self.init_failure
        if result is None:
            result = (E_FAIL if self.local.kind == 'unknown' else CHANGED_MODE
                      if self.local.kind in ('sta', 'mainsta', 'neutral') else int(self.local.refs > 0))
        self.events.append(('init', threading.get_ident(), result))
        if result in (0, 1):
            self.local.kind = 'mta'
            self.local.refs += 1
        return result

    def uninitialize(self):
        owner = threading.get_ident()
        self.events.append(('uninit', owner, self.live.get(owner, 0)))
        assert self.live.get(owner, 0) == 0, 'COM values or exception tracebacks outlived their initialized scope'
        assert self.local.refs > 0, 'Uninitialized a parent or never-initialized apartment'
        self.local.refs -= 1
        if not self.local.refs:
            self.local.kind = 'implicit' if self.local.implicit else 'none'

    def import_client(self):
        self.events.append(('import', threading.get_ident(), self.first_import))
        if self.first_import:
            self.first_import = False
            if self.local.kind == 'mta':
                raise OSError(CHANGED_MODE, 'synthetic comtypes auto-STA conflict')
            self.local.kind, self.local.refs = 'sta', self.local.refs + 1
            self.events.append(('auto-init', threading.get_ident(), 0))
            self.exits.append(threading.get_ident())
        if self.import_error:
            raise ImportError('synthetic comtypes import failure')

    def require_mta(self):
        assert self.local.kind == 'mta' and self.local.refs > 0, 'UIA called without explicit MTA ownership'

    def fail(self, point):
        if self.fail_at == point:
            self.events.append(('failed', threading.get_ident(), point))
            raise RuntimeError('synthetic provider failure at ' + point)

    def create(self, _progid, **kwargs):
        self.require_mta()
        self.interfaces.append(kwargs.get('interface'))
        self.fail('create')
        return Automation(self, 'automation')

    def typelib(self, name):
        self.require_mta()
        self.modules.append(name)
        self.fail('typelib')
        return SimpleNamespace(CUIAutomation=CUIAutomation, IUIAutomation=IUIAutomation,
                               IUIAutomationTextPattern=IUIAutomationTextPattern)


@pytest.fixture
def scenario(monkeypatch):
    state = Scenario()
    package, client = ModuleType('comtypes'), ModuleType('comtypes.client')
    package.__path__ = []
    package.client = client
    client.CreateObject, client.GetModule = state.create, state.typelib
    client.gen_dir = object()  # The adapter must preserve upstream cache policy.
    monkeypatch.setitem(sys.modules, 'comtypes', package)
    monkeypatch.setitem(sys.modules, 'comtypes.client', client)
    monkeypatch.setattr(selection, '_com_client', client, raising=False)
    monkeypatch.setattr(selection, '_bootstrap_attempted', True, raising=False)
    original_import = builtins.__import__

    def import_module(name, *args, **kwargs):
        if name == 'comtypes.client':
            monkeypatch.setitem(sys.modules, 'comtypes', package)
            monkeypatch.setitem(sys.modules, 'comtypes.client', client)
            state.import_client()
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', import_module)
    original_dll = getattr(ctypes, 'WinDLL', None)

    def library(name, *args, **kwargs):
        if str(name).lower().rsplit('/', 1)[-1] in ('ole32', 'ole32.dll'):
            return state.api
        assert original_dll is not None
        return original_dll(name, *args, **kwargs)

    monkeypatch.setattr(ctypes, 'WinDLL', library, raising=False)
    monkeypatch.setattr(platform_support, 'IS_WINDOWS', True)
    monkeypatch.setattr(platform_support, 'IS_MAC', False)
    monkeypatch.setattr(platform_support, 'IS_LINUX', False)
    state.client = client
    def unprepare():
        monkeypatch.setattr(selection, '_com_client', None, raising=False)
        monkeypatch.setattr(selection, '_bootstrap_attempted', False, raising=False)
        monkeypatch.delitem(sys.modules, 'comtypes', raising=False)
        monkeypatch.delitem(sys.modules, 'comtypes.client', raising=False)
    state.unprepare = unprepare
    return state


@pytest.mark.parametrize('kind', ['none', 'implicit', 'mta'])
def test_uia_read_owns_only_its_calling_thread_initializations(scenario, kind):
    state = scenario
    state.seed(kind)
    cache_policy = state.client.gen_dir
    assert selection.read_windows_selected_text() == 'Native selection'
    assert state.local.refs == int(kind == 'mta')
    assert state.queries == [IUIAutomationTextPattern]
    assert state.interfaces == [IUIAutomation]
    assert state.modules == ['UIAutomationCore.dll']
    assert state.client.gen_dir is cache_policy
    assert len([event for event in state.events if event[0] == 'init']) == 1
    assert len([event for event in state.events if event[0] == 'uninit']) == 1


@pytest.mark.parametrize('kind', ['sta', 'mainsta', 'neutral', 'unknown'])
def test_incompatible_or_unknown_parent_apartment_is_not_changed(scenario, kind):
    scenario.seed(kind)
    refs = scenario.local.refs
    assert selection.read_windows_selected_text() == ''
    assert scenario.local.kind == kind and scenario.local.refs == refs
    assert not any(event[0] == 'uninit' for event in scenario.events)
    assert not scenario.interfaces


@pytest.mark.parametrize('failure', [CHANGED_MODE, E_FAIL])
def test_failed_explicit_initialization_never_uninitializes_or_reads_uia(scenario, failure):
    scenario.init_failure = failure
    assert selection.read_windows_selected_text() == ''
    assert [event[0] for event in scenario.events] == ['init']
    assert scenario.local.refs == 0 and not scenario.interfaces


@pytest.mark.parametrize('point', ['typelib', 'create', 'element', 'pattern', 'qi', 'selection', 'range', 'text'])
def test_provider_failures_release_every_pointer_before_owned_uninitialize(scenario, caplog, point):
    scenario.seed('mta')
    scenario.fail_at = point
    caplog.set_level('DEBUG', logger='clickntranslate.selection')
    assert selection.read_windows_selected_text() == ''
    assert any(event[0] == 'failed' and event[2] == point for event in scenario.events)
    assert scenario.events[-1][0] == 'uninit' and scenario.events[-1][2] == 0
    assert scenario.local.refs == 1
    assert all(record.exc_info is None for record in caplog.records)


@pytest.mark.parametrize('empty', ['element', 'pattern', 'ranges', 'count'])
def test_empty_uia_result_still_balances_owned_initialization(scenario, empty):
    scenario.empty = empty
    assert selection.read_windows_selected_text() == ''
    assert scenario.events[-1][0] == 'uninit'
    assert scenario.local.refs == 0


def test_main_bootstrap_and_library_shutdown_stay_on_the_original_thread(scenario):
    scenario.unprepare()
    scenario.seed('sta')
    scenario.first_import = True
    assert selection.prepare_windows_selection()
    assert scenario.local.refs == 2 and not scenario.modules and not scenario.interfaces
    assert selection.prepare_windows_selection()
    assert scenario.local.refs == 2 and len(scenario.exits) == 1
    results = []
    def read_on_worker():
        scenario.seed('none')
        results.append(selection.read_windows_selected_text())
        assert scenario.local.refs == 0
    worker = threading.Thread(target=read_on_worker)
    worker.start()
    worker.join(2)
    assert not worker.is_alive() and results == ['Native selection']
    assert scenario.local.refs == 2
    # This is the library-owned atexit cleanup, on its original import thread.
    assert scenario.exits.pop() == threading.get_ident()
    scenario.uninitialize()
    assert scenario.local.refs == 1


def test_bootstrap_failure_never_uninitializes_an_existing_mta(scenario):
    scenario.unprepare()
    scenario.seed('mta')
    scenario.first_import = True
    assert not selection.prepare_windows_selection()
    assert scenario.local.kind == 'mta' and scenario.local.refs == 1
    assert not any(event[0] == 'uninit' for event in scenario.events)


def test_failed_client_import_leaves_library_main_apartment_for_its_own_shutdown(scenario):
    scenario.unprepare()
    scenario.seed('sta')
    scenario.first_import, scenario.import_error = True, True
    assert not selection.prepare_windows_selection()
    assert scenario.local.refs == 2
    assert not any(event[0] == 'uninit' for event in scenario.events)
    assert scenario.exits.pop() == threading.get_ident()
    scenario.uninitialize()
    assert scenario.local.refs == 1


def test_worker_cannot_be_the_first_comtypes_importer(scenario):
    scenario.unprepare()
    outcomes = []
    worker = threading.Thread(target=lambda: outcomes.append(selection.read_windows_selected_text()))
    worker.start()
    worker.join(2)
    assert not worker.is_alive() and outcomes == ['']
    assert not scenario.events and not scenario.interfaces


def test_worker_cannot_prepare_the_global_client_or_its_main_apartment(scenario):
    scenario.unprepare()
    outcomes = []
    worker = threading.Thread(target=lambda: outcomes.append(selection.prepare_windows_selection()))
    worker.start()
    worker.join(2)
    assert not worker.is_alive() and outcomes == [False]
    assert selection._com_client is None and not scenario.events


def test_imported_client_of_unknown_thread_ownership_is_not_adopted(scenario, monkeypatch):
    monkeypatch.setattr(selection, '_com_client', None)
    monkeypatch.setattr(selection, '_bootstrap_attempted', False)
    assert not selection.prepare_windows_selection()
    assert not scenario.events and selection._com_client is None


def test_failed_first_bootstrap_cannot_adopt_a_later_foreign_import(scenario, monkeypatch):
    scenario.unprepare()
    scenario.import_error = True
    assert not selection.prepare_windows_selection()
    foreign = ModuleType('comtypes')
    foreign.__path__ = []
    foreign.client = ModuleType('comtypes.client')
    monkeypatch.setitem(sys.modules, 'comtypes', foreign)
    monkeypatch.setitem(sys.modules, 'comtypes.client', foreign.client)
    previous_import = builtins.__import__
    def import_foreign(name, *args, **kwargs):
        return foreign if name == 'comtypes.client' else previous_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', import_foreign)
    assert not selection.prepare_windows_selection()
    assert selection._com_client is None
    assert scenario.local.refs == 0


@pytest.mark.parametrize('enabled', [False, True])
def test_quick_feature_prepares_backend_only_when_enabled_without_disabling_fallback(monkeypatch, enabled):
    prepare = mock.Mock(return_value=False)
    monkeypatch.setattr(selection, 'prepare_windows_selection', prepare, raising=False)
    monkeypatch.setattr(platform_support, 'IS_WINDOWS', True)
    controller = SimpleNamespace(_cancel_probe=mock.Mock(), _revision=0,
        _dismiss_selection=mock.Mock(), clear_auto_dedupe=mock.Mock(), set_active=mock.Mock())
    quick.SelectionQuickTranslateController.configure(controller, enabled, 'automatic')
    assert prepare.call_count == int(enabled)
    controller.set_active.assert_called_once_with(enabled)


def test_cached_import_initializes_each_actual_python_worker_independently(scenario):
    barrier = threading.Barrier(2)
    results, errors = [], []

    def work():
        try:
            scenario.seed('none')
            barrier.wait(2)
            results.append(selection.read_windows_selected_text())
            assert scenario.local.refs == 0
        except BaseException as error:
            errors.append(error)

    workers = [threading.Thread(target=work) for _ in range(2)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(3)
    assert all(not worker.is_alive() for worker in workers) and not errors
    assert results == ['Native selection', 'Native selection']
    initialized = [event[1] for event in scenario.events if event[0] == 'init']
    released = [event[1] for event in scenario.events if event[0] == 'uninit']
    assert len(set(initialized)) == 2 and sorted(initialized) == sorted(released)


def test_successful_typed_uia_read_skips_the_copy_fallback(scenario, monkeypatch):
    fallback = mock.Mock(return_value='Copied fallback')
    monkeypatch.setattr(selection_platform, '_read_selection_via_copy', fallback)
    assert selection_platform.read_selected_text(allow_copy_fallback=True) == 'Native selection'
    fallback.assert_not_called()


def test_windows_dependency_and_packager_explicitly_include_the_existing_uia_backend():
    root = Path(__file__).resolve().parents[1]
    assert 'comtypes==1.4.17' in (root / 'tools/requirements/windows.txt').read_text(encoding='utf-8')
    assert "collect_submodules('comtypes')" in (root / 'tools/packaging/ClicknTranslate.spec').read_text(encoding='utf-8')
    for name in ('linux.txt', 'macos.txt'):
        assert 'comtypes' not in (root / 'tools/requirements' / name).read_text(encoding='utf-8').lower()
