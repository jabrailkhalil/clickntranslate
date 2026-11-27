"""The permission list, toolbar gate and settings exchange agree on each mode."""
import copy
from unittest import mock

import pytest
from PyQt5 import QtCore
from PyQt5.QtTest import QTest

import main
from capture_regions import memory_control_modes
from test_desktop_ux import app, window
from test_capture_region_memory import capture
from test_translation_area_preference import memory_context


def test_hidden_control_cannot_enable_or_save_an_area(memory_context):
    c = memory_context
    c.config['capture_area_memory_modes'] = []
    c.config['remember_translate_area'] = True
    c.config['last_translate_area'] = copy.deepcopy(c.area)
    c.save()
    value = c.create('translate')
    assert value._preview_rect is None
    assert not value.memory_panel.isVisible()
    assert not value.repeat_area_button.isVisible()
    before = copy.deepcopy(c.config)
    value.remember_area_checkbox.setChecked(True)
    assert not value.remember_area_checkbox.isChecked()
    assert c.config == before
    value._accept_capture_region(QtCore.QRect(50, 300, 220, 80))
    assert c.config == before
    assert c.captures == [QtCore.QRect(50, 300, 220, 80)]


def test_keyboard_can_toggle_modes_and_escape_without_extra_saves(memory_context, app):
    c = memory_context
    c.control.showPopup()
    app.processEvents()
    QTest.keyClick(c.control.view(), QtCore.Qt.Key_Home)
    QTest.keyClick(c.control.view(), QtCore.Qt.Key_Space)
    assert c.config['remember_translate_area'] is True
    count = c.save.call_count
    QTest.keyClick(c.control.view(), QtCore.Qt.Key_Escape)
    assert not c.control.view().isVisible()
    assert c.save.call_count == count


def test_context_switch_migrates_legacy_permissions_before_disabling_memory(memory_context):
    c = memory_context
    assert c.config['capture_area_memory_modes'] is None
    value = c.create('copy')
    assert value.remember_area_checkbox.isChecked()
    value.remember_area_checkbox.click()
    assert c.config['capture_area_memory_modes'] == ['copy']
    assert c.config['remember_copy_area'] is False
    assert c.config['last_copy_area'] is None
    value.close()
    value = c.create('copy')
    assert value.remember_area_checkbox.isVisible()
    assert not value.remember_area_checkbox.isChecked()
    assert value._preview_rect is None


def test_failed_save_restores_modes_flags_and_saved_areas(memory_context):
    c = memory_context
    before = copy.deepcopy(c.config)
    raw = c.path.read_bytes()
    with mock.patch.object(c.window, 'save_config', side_effect=OSError('read only')), \
            mock.patch('settings_window.QMessageBox.warning') as warning:
        c.control.toggle_mode('copy')
    warning.assert_called_once()
    assert c.config == before
    assert c.path.read_bytes() == raw
    assert c.control.checked_modes() == ('copy',)


@pytest.mark.parametrize('config,expected', [
    ({}, ()), ({'remember_translate_area': True}, ('translate',)),
    ({'remember_copy_area': True}, ('copy',)),
    ({'capture_area_memory_modes': [], 'remember_translate_area': True}, ()),
    ({'capture_area_memory_modes': ['copy','unknown','copy']}, ('copy',)),
])
def test_migration_preserves_old_opt_ins_and_explicit_modes_take_priority(config, expected):
    assert memory_control_modes(config) == expected


@pytest.mark.parametrize('selection', [None, [], ['translate'], ['copy'], ['translate','copy']])
def test_mode_permissions_round_trip_through_settings_export(selection):
    from settings_window import settings_export_payload, validated_import_settings
    settings = {'capture_area_memory_modes': selection}
    assert validated_import_settings(settings_export_payload(settings), main.DEFAULT_CONFIG) == settings


@pytest.mark.parametrize('invalid', [['fullscreen'], [True], 'copy', {}])
def test_invalid_imported_modes_do_not_enable_extra_controls(invalid):
    from settings_window import settings_export_payload, validated_import_settings
    payload = settings_export_payload({'theme': 'Темная', 'capture_area_memory_modes': invalid})
    assert validated_import_settings(payload, main.DEFAULT_CONFIG) == {'theme': 'Темная'}
