"""Saved-area identity and malformed records use synthetic monitors exclusively."""
import copy
from types import SimpleNamespace
from unittest import mock

import pytest
from PyQt5 import QtCore, QtGui, QtWidgets

import capture_regions as regions
import main
import ocr
import settings_window as sw


@pytest.fixture(autouse=True)
def synthetic_monitors_only(monkeypatch):
    assert QtWidgets.QApplication.platformName().split(':')[0] == 'offscreen'

    def blocked(*_args, **_kwargs):
        raise AssertionError('This audit must not inspect an actual screen or cursor')

    monkeypatch.setattr(QtGui.QCursor, 'pos', staticmethod(blocked))
    for name in ('screens', 'primaryScreen', 'screenAt'):
        monkeypatch.setattr(QtWidgets.QApplication, name, staticmethod(blocked))


def monitor(*, metadata=None, bounds=(-1600, -100, 1600, 900), dpi=96):
    value = SimpleNamespace(name=lambda: 'same-port', geometry=lambda: QtCore.QRect(*bounds),
                            logicalDotsPerInch=lambda: dpi)
    for key, text in (metadata or {}).items():
        setattr(value, key, lambda text=text: text)
    return value


def saved_area(screen):
    return regions.encode_area(QtCore.QRect(-1500, 100, 300, 120), screen)


def restore(area, screen):
    hint = SimpleNamespace(value='')
    hint.setText = lambda value: setattr(hint, 'value', value)
    value = SimpleNamespace(mode='translate', _area_memory_available=True,
                            _active_screen=screen, _preview_rect='stale',
                            geometry=lambda: screen.geometry(), memory_hint=hint,
                            _memory_locale='en', _update_memory_actions=mock.Mock())
    ocr.ScreenCaptureOverlay._restore_area(value, {'remember_translate_area': True, 'last_translate_area': area})
    value._update_memory_actions.assert_called_once_with()
    return value


@pytest.mark.parametrize('field', ['serialNumber', 'manufacturer', 'model'])
@pytest.mark.parametrize('missing', ['absent-method', 'empty-value'])
def test_saved_hardware_identity_cannot_disappear_before_preview_restore(field, missing):
    saved = saved_area(monitor(metadata={field: 'known-hardware'}))
    before = copy.deepcopy(saved)
    current = monitor(metadata={} if missing == 'absent-method' else {field: ''})
    assert regions.resolve_area(saved, current) is None
    preview = restore(saved, current)
    assert preview._preview_rect is None
    assert preview.memory_hint.value == regions.text('en', 'unavailable')
    assert saved == before


@pytest.mark.parametrize('field', ['serialNumber', 'manufacturer', 'model'])
def test_same_hardware_repositions_relative_area_but_changes_cannot_match(field):
    saved = saved_area(monitor(metadata={field: 'known-hardware'}))
    moved = monitor(metadata={field: 'known-hardware'}, bounds=(900, -200, 1600, 900))
    assert regions.resolve_area(saved, moved) == QtCore.QRect(1000, 0, 300, 120)
    preview = restore(saved, moved)
    assert preview._preview_rect == QtCore.QRect(100, 200, 300, 120)
    assert preview.memory_hint.value == regions.text('en', 'ready')
    assert regions.resolve_area(saved, monitor(metadata={field: 'other-hardware'})) is None
    assert regions.resolve_area(saved, monitor(metadata={field: 'known-hardware'}, dpi=144)) is None


@pytest.mark.parametrize('new_field', [None, 'serialNumber', 'manufacturer', 'model'],
                         ids=['no-metadata-on-either-side', 'new-serial', 'new-manufacturer', 'new-model'])
def test_legacy_identity_without_optional_metadata_keeps_the_existing_match_policy(new_field):
    saved = saved_area(monitor())
    metadata = {} if new_field is None else {new_field: 'newly-known-hardware'}
    current = monitor(metadata=metadata, bounds=(900, -200, 1600, 900))
    expected = QtCore.QRect(1000, 0, 300, 120) if new_field is None else None
    assert regions.resolve_area(saved, current) == expected
    # More current metadata was already a mismatch before this fix; a legacy
    # record is not silently upgraded to trust a newly identified monitor.


@pytest.mark.parametrize('dpi', [10 ** 309, -(10 ** 309), 10 ** 500],
                         ids=['positive-overflow', 'negative-overflow', 'larger-overflow'])
def test_extreme_saved_dpi_does_not_abort_restore_or_other_imported_settings(dpi):
    screen = monitor()
    saved = saved_area(screen)
    saved['screen']['dpi'] = dpi
    before = copy.deepcopy(saved)
    assert regions.validated_area(saved) is None
    assert regions.resolve_area(saved, screen) is None
    preview = restore(saved, screen)
    assert preview._preview_rect is None
    assert preview.memory_hint.value == regions.text('en', 'unavailable')
    payload = sw.settings_export_payload({'theme': 'Темная', 'last_translate_area': saved})
    assert sw.validated_import_settings(payload, main.DEFAULT_CONFIG) == {'theme': 'Темная'}
    assert saved == before


@pytest.mark.parametrize('dpi', [None, float('nan'), float('inf'), float('-inf'), True, 0, -10, 10000, '96'])
def test_other_malformed_saved_dpi_stays_unavailable(dpi):
    saved = saved_area(monitor())
    saved['screen']['dpi'] = dpi
    assert regions.validated_area(saved) is None


@pytest.mark.parametrize('dpi', [72, 96, 96.25, 144, 192])
def test_ordinary_integer_and_fractional_dpi_keep_their_coordinates(dpi):
    current = monitor(dpi=dpi)
    saved = saved_area(current)
    assert regions.validated_area(saved) == saved
    assert regions.resolve_area(saved, current) == QtCore.QRect(-1500, 100, 300, 120)


@pytest.mark.parametrize('mode', ['translate', 'copy'])
def test_disabled_memory_does_not_read_an_unusable_saved_record_or_screen(monkeypatch, mode):
    monkeypatch.setattr(regions, 'resolve_area', mock.Mock(side_effect=AssertionError('disabled area was read')))
    value = SimpleNamespace(mode=mode, _area_memory_available=False, _preview_rect='stale',
                            _active_screen=object(), _update_memory_actions=mock.Mock())
    enabled, area = regions.memory_keys(mode)
    ocr.ScreenCaptureOverlay._restore_area(value, {enabled: True, area: {'screen': {'dpi': 10 ** 500}}})
    assert value._preview_rect is None
    regions.resolve_area.assert_not_called()
    value._update_memory_actions.assert_called_once_with()


@pytest.mark.parametrize('change', ['moved', 'dpi', 'removed', 'deleted-screen'])
def test_preview_confirmation_rejects_changed_topology_without_capturing(monkeypatch, change):
    original = monitor()
    old_bounds = original.geometry()
    identity = regions.screen_identity(original)
    current = original
    if change == 'moved':
        current = monitor(bounds=(900, -200, 1600, 900))
    elif change == 'dpi':
        current = monitor(dpi=144)
    elif change == 'deleted-screen':
        current = monitor()
        current.name = mock.Mock(side_effect=RuntimeError('synthetic deleted QScreen'))
    screens = [] if change == 'removed' else [current]
    monkeypatch.setattr(ocr.QApplication, 'screens', staticmethod(lambda: screens))
    value = SimpleNamespace(_ocr_in_progress=False, _region_gesture=None,
                            _preview_rect=QtCore.QRect(100, 200, 300, 120),
                            _active_screen=current, _preview_screen_identity=identity,
                            lang_combo=None, target_lang_combo=None,
                            geometry=lambda: QtCore.QRect(old_bounds),
                            memory_hint=SimpleNamespace(setText=mock.Mock()), _memory_locale='en',
                            _update_memory_actions=mock.Mock(), update=mock.Mock(),
                            _accept_capture_region=mock.Mock())
    ocr.ScreenCaptureOverlay._repeat_area(value)
    assert value._preview_rect is None
    value._accept_capture_region.assert_not_called()
    value.memory_hint.setText.assert_called_once_with(regions.text('en', 'unavailable'))
