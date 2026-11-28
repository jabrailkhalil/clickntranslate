"""Language mutations and engine maintenance are separate, visible actions."""
from pathlib import Path
from unittest import mock

import pytest
from PyQt5 import QtCore, QtWidgets

from engine_center import MAINTENANCE, MAINTENANCE_KEYS, text
from settings_window import OcrLanguageManagerDialog
from test_language_package_manager import _AppParent, _ManagerOwner


@pytest.fixture
def center():
    app = QtWidgets.QApplication.instance()
    parent = _AppParent()
    owner = _ManagerOwner(parent)
    owner.easyocr_status = (True, '')
    with mock.patch.object(OcrLanguageManagerDialog, '_start_runtime_probe'), \
         mock.patch.object(OcrLanguageManagerDialog, '_start_argos_catalog_refresh'):
        dialog = OcrLanguageManagerDialog(owner)
        dialog._initial_probe_timer.stop()
        dialog._initial_catalog_timer.stop()
    yield dialog, owner, parent
    dialog.close()
    owner.deleteLater()
    parent.deleteLater()
    app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def _rows():
    return [dict(code=code, name=name, package=code + '.traineddata', status=status,
                 checked=installed, selectable=not installed)
            for code, name, status, installed in [('en', 'English', 'Installed', True),
                                                  ('fr', 'French', 'Missing', False)]]


@pytest.mark.parametrize('direction', [QtCore.Qt.LeftToRight, QtCore.Qt.RightToLeft])
def test_keyboard_focus_tracks_the_active_engine_section(center, direction, monkeypatch):
    from PyQt5.QtTest import QTest
    from keyboard_navigation import focus_control, install_keyboard_navigation
    from package_presentation import text as package_text

    dialog, _, parent = center
    parent.config = {'translator_engine': 'google', 'ocr_engine': 'Windows'}
    app = QtWidgets.QApplication.instance()
    monkeypatch.setattr('provider_secrets.get_key', lambda *_: '')
    install_keyboard_navigation(app)
    dialog.setLayoutDirection(direction)
    dialog.show()
    app.processEvents()
    bar = dialog.tabs.tabBar()
    forward = QtCore.Qt.Key_Left if direction == QtCore.Qt.RightToLeft else QtCore.Qt.Key_Right
    focus_control(bar)
    for index in range(dialog.tabs.count()):
        if index:
            QTest.keyClick(bar, forward)
            app.processEvents()
        assert bar.currentIndex() == index
        assert bar.hasFocus()
        selected = bar.tabRect(index)
        selected.moveTopLeft(bar.mapTo(dialog, selected.topLeft()))
        assert dialog._keyboard_focus_ring.isVisible()
        assert dialog._keyboard_focus_ring.geometry() == selected.adjusted(3, 3, -3, -3)
        if index < 2:
            picker = dialog._engine_selectors[index]
            assert picker.accessibleName() == package_text(dialog.lang, 'engine')
            assert any(label.buddy() is picker for label in dialog.findChildren(QtWidgets.QLabel))
    QTest.mouseClick(bar, QtCore.Qt.LeftButton, pos=bar.tabRect(0).center())
    assert not dialog._keyboard_focus_ring.isVisible()


def test_withdrawn_engine_clears_stale_download_sizes_and_keeps_local_removal(center, monkeypatch):
    from package_presentation import text as package_text
    from test_package_presentation import platform_size_catalog

    dialog, _, _ = center
    monkeypatch.setattr('settings_window.managed_install_supported', lambda: True)
    table = dialog.easyocr_table
    dialog._set_language_rows(table, _rows())
    available = dict(platform_size_catalog(), revision=1)
    dialog._on_package_sizes_ready(available)
    mark = table.item(1, 0)
    mark.setCheckState(QtCore.Qt.Checked)
    buttons = {b.property('packageAction'): b for b in table._package_action_buttons}
    assert buttons['install'].isEnabled()
    assert 'MB' in buttons['install'].text()
    table.selectRow(0)
    dialog._on_package_sizes_ready(dict(available, revision=2, bundles=[]))
    assert not buttons['install'].isEnabled()
    assert 'MB' not in buttons['install'].text()
    assert not table._pending_package_codes
    assert mark.checkState() == QtCore.Qt.Unchecked
    assert not mark.flags() & QtCore.Qt.ItemIsEnabled
    assert table.item(1, 4).text() == '—'
    assert buttons['remove'].isEnabled()
    assert table.item(0, 3).text() == 'Installed'
    dialog._set_engine_missing_state(table, True, 'EasyOCR')
    missing_install = table._package_missing_install_button
    assert not missing_install.isEnabled()
    assert 'MB' not in missing_install.text()
    assert package_text(dialog.lang, 'unavailable') in table._package_missing_body.text()
    dialog._set_package_actions_busy(True)
    dialog._on_package_sizes_ready(dict(available, revision=3))
    assert not missing_install.isEnabled()
    dialog._set_package_actions_busy(False)
    assert missing_install.isEnabled()
    assert mark.flags() & QtCore.Qt.ItemIsEnabled
    assert mark.checkState() == QtCore.Qt.Unchecked
    assert 'MB' in table.item(1, 4).text()
    assert package_text(dialog.lang, 'unavailable') not in table._package_missing_body.text()


def test_unmanaged_language_installer_stays_available_without_a_signed_bundle(center, monkeypatch):
    dialog, _, _ = center
    monkeypatch.setattr('settings_window.managed_install_supported', lambda: False)
    table = dialog.easyocr_table
    dialog._set_language_rows(table, _rows())
    dialog._on_package_sizes_ready(dict(bundles=[], artifacts={}, revision=1))
    mark = table.item(1, 0)
    mark.setCheckState(QtCore.Qt.Checked)
    button = next(b for b in table._package_action_buttons if b.property('packageAction') == 'install')
    assert button.isEnabled()
    assert dialog._selected_codes(table) == ['fr']


def test_size_feedback_distinguishes_unreachable_metadata_from_a_withdrawn_engine(center, monkeypatch):
    from test_package_presentation import platform_size_catalog

    dialog, _, _ = center
    monkeypatch.setattr('settings_window.managed_install_supported', lambda: True)
    table = dialog.easyocr_table
    label = table._package_size_label
    offline_error = 'The catalog is offline <test> & retry'
    dialog._on_package_sizes_ready(offline_error)
    assert 'catalog' in label.text().lower()
    assert '&lt;test&gt;' in label.toolTip()
    assert '&lt;test&gt;' in table._package_missing_body.toolTip()
    assert table._package_missing_install_button.isEnabled()
    if dialog.windows_table is not None:
        assert 'catalog' not in dialog.windows_table._package_size_label.text().lower()
    valid = dict(platform_size_catalog(), revision=1)
    dialog._on_package_sizes_ready(valid)
    assert 'MB' in label.text() and 'catalog' not in label.text().lower()
    dialog._on_package_sizes_ready(offline_error)
    assert 'MB' in label.text() and 'last' in label.text().lower()
    dialog._on_package_sizes_ready(valid)
    assert 'last' not in label.text().lower() and '&lt;test&gt;' not in label.toolTip()


def test_argos_pair_failure_does_not_mark_other_engines_metadata_as_offline(center, monkeypatch, tmp_path):
    from component_catalog import ComponentError
    from test_package_presentation import platform_size_catalog

    dialog, _, _ = center
    monkeypatch.setenv('CLICKNTRANSLATE_COMPONENTS_DIR', str(tmp_path))
    monkeypatch.setattr('settings_window.managed_install_supported', lambda: True)
    with (mock.patch.object(dialog, '_refresh_catalog', return_value=dict(platform_size_catalog(), revision=1)),
          mock.patch('component_argos.catalog_rows', side_effect=ComponentError('no_compatible_update')),
          mock.patch('translater.argos_package_catalog', return_value=[])):
        dialog._load_argos_catalog_worker(refresh=True)
    assert dialog._argos_catalog_error
    assert not dialog._package_sizes_error
    assert 'MB' in dialog.easyocr_table._package_size_label.text()


def test_language_buttons_require_the_matching_selection(center):
    dialog, _, _ = center
    table = dialog.easyocr_table
    dialog._set_language_rows(table, _rows())
    buttons = {button.property('packageAction'): button for button in table._package_action_buttons}
    assert set(buttons) == {'install', 'remove'}
    assert not any(button.isEnabled() for button in buttons.values())
    table.item(1, 0).setCheckState(QtCore.Qt.Checked)
    assert buttons['install'].isEnabled()
    table.selectRow(1)
    assert not buttons['remove'].isEnabled(), 'checked missing packages cannot be removed'
    table.selectRow(0)
    assert buttons['remove'].isEnabled()
    table.clearSelection()
    assert not buttons['remove'].isEnabled()
    dialog._set_language_rows(table, _rows()[:1])
    assert buttons['install'].isEnabled(), 'a search keeps pending downloads'
    assert all(button.toolTip().strip() for button in buttons.values())


@pytest.mark.parametrize('direction', [QtCore.Qt.LeftToRight, QtCore.Qt.RightToLeft])
def test_installed_checkmark_can_receive_row_selection_without_requesting_a_download(center, direction):
    dialog, _, _ = center
    table = dialog.easyocr_table
    dialog.setLayoutDirection(direction)
    dialog._set_language_rows(table, _rows())
    mark = table.item(0, 0)
    assert mark.flags() & QtCore.Qt.ItemIsSelectable
    assert mark.flags() & QtCore.Qt.ItemIsEnabled
    assert not mark.flags() & QtCore.Qt.ItemIsUserCheckable
    table.selectRow(0)
    dialog._on_package_row_clicked(table, 0, 1)
    assert mark.checkState() == QtCore.Qt.Checked
    assert dialog._highlighted_installed_codes(table) == ['en']
    assert dialog._selected_codes(table) == []
    assert not table._pending_package_codes


@pytest.mark.parametrize(('row', 'query', 'expected'), [
    (0, 'French', []),
    (1, 'German', ['en->de']),
])
def test_argos_filter_only_keeps_highlights_for_the_same_installed_direction(center, row, query, expected):
    dialog, _, _ = center
    table = dialog.argos_table
    dialog._argos_catalog = [
        dict(source_code='en', target_code=target, installed=True)
        for target in ('ru', 'de', 'fr')
    ]
    dialog._populate_argos_table(table)
    table.selectRow(row)
    previous_code = table.item(row, 0).data(QtCore.Qt.UserRole)
    assert dialog._highlighted_installed_codes(table) == [previous_code]
    table._package_filter_edit.setText(query)
    remove = next(b for b in table._package_action_buttons if b.property('packageAction') == 'remove')
    assert dialog._highlighted_installed_codes(table) == expected
    assert remove.isEnabled() == bool(expected)
    assert table.currentRow() == (0 if expected else -1)


def test_argos_download_caption_includes_checked_pairs_hidden_by_the_search(center):
    from package_presentation import PackageSizes
    dialog, _, _ = center
    table = dialog.argos_table
    files = {
        'en__ru': [dict(sha256='russian', destination='models/russian.argosmodel')],
        'en__de': [dict(sha256='german', destination='models/german.argosmodel')],
    }
    catalog = dict(
        artifacts={name: dict(size=size) for name, size in
                   [('runtime', 5000000), ('german', 7000000), ('russian', 11000000)]},
        bundles=[dict(id='argos', component='translation.argos', channel='stable', revision=1,
                      os='windows', arch='x86_64', contract=3, min_os='10', app='>=1.8.2,<2',
                      files=[dict(sha256='runtime', destination='bin/argos')],
                      languages=list(files), language_files=files)])
    dialog._package_sizes = PackageSizes(catalog, target=dict(os='windows', arch='x86_64', os_version='10'))
    dialog._argos_catalog = [dict(source_code='en', target_code=code, available=True) for code in ('ru', 'de')]
    with mock.patch('component_runtime.managed_runtime', return_value=object()):
        dialog._populate_argos_table(table)
        for row in range(table.rowCount()):
            table.item(row, 0).setCheckState(QtCore.Qt.Checked)
        install = next(b for b in table._package_action_buttons if b.property('packageAction') == 'install')
        assert '18.0 MB' in install.text()
        for query in ('German', 'no matching language'):
            table._package_filter_edit.setText(query)
            assert install.isEnabled()
            assert set(dialog._selected_codes(table)) == {'en->ru', 'en->de'}
            assert '18.0 MB' in install.text()
            assert '18.0 MB' in table._package_size_label.text()


def test_catalog_refresh_keeps_user_choice_after_following_argos_install_link(center):
    dialog, _, _ = center
    table = dialog.argos_table
    dialog.focus_translation_engine('argos', 'en', 'ru')
    dialog._argos_catalog = [dict(source_code='en', target_code=target, installed=True)
                             for target in ('ru', 'de')]
    dialog._on_argos_catalog_ready('')
    assert dialog._highlighted_codes(table) == ['en->ru']
    table.selectRow(1)
    dialog._on_argos_catalog_ready('')
    assert dialog._highlighted_codes(table) == ['en->de']


def test_rtl_argos_link_and_mouse_click_act_on_the_visible_language_pair(center, tmp_path):
    from PyQt5.QtTest import QTest
    dialog, _, _ = center
    table = dialog.argos_table
    app = QtWidgets.QApplication.instance()
    dialog.setLayoutDirection(QtCore.Qt.RightToLeft)
    dialog._argos_catalog = [dict(source_code='en', target_code=t, installed=True) for t in ('ru', 'de', 'fr')]
    # Following an install link selects the row even before the first window paint.
    dialog.focus_translation_engine('argos', 'en', 'de')
    dialog._on_argos_catalog_ready('')
    dialog.show()
    app.processEvents()
    assert table.isVisible() and dialog._highlighted_installed_codes(table) == ['en->de']
    target = next(table.item(i, 1) for i in range(table.rowCount())
                  if table.item(i, 0).data(QtCore.Qt.UserRole) == 'en->fr')
    rect = table.visualItemRect(target)
    assert table.viewport().rect().contains(rect.center())
    QTest.mouseClick(table.viewport(), QtCore.Qt.LeftButton, pos=rect.center())
    assert dialog._highlighted_installed_codes(table) == ['en->fr']
    assert not dialog._selected_codes(table)
    assert dialog.grab().save(str(tmp_path / 'argos-rtl-selection.png'))


def test_a_runtime_refresh_during_the_current_probe_runs_once_more(center):
    dialog, _, _ = center
    with (mock.patch('settings_window.threading.Thread') as thread,
          mock.patch.object(dialog, '_start_argos_catalog_refresh')):
        dialog._start_runtime_probe()
        dialog._on_runtime_probe_ready({'windows_tags': ['en-US'], 'windows_ready_codes': ['en']})
        dialog.refresh_catalog()
        dialog.refresh_catalog()
        assert thread.call_count == 1
        dialog._on_runtime_probe_ready({'rapidocr': (False, 'old result'), 'complete': True})
        assert thread.call_count == 2 and dialog._runtime_probe_active
        dialog._on_runtime_probe_ready({'windows_tags': ['fr-FR'], 'windows_ready_codes': ['fr']})
        dialog._on_runtime_probe_ready({'rapidocr': (True, ''), 'complete': True})
        assert dialog._windows_tags_cache == ['fr-FR'] and dialog._rapidocr_status_cache == (True, '')
        assert not dialog._runtime_probe_active


def test_an_argos_download_catalog_refresh_is_not_lost_behind_a_local_refresh(center):
    dialog, _, _ = center
    with mock.patch('settings_window.threading.Thread') as thread:
        dialog._start_argos_catalog_refresh(False)
        for fetch in (False, True, False):
            dialog._start_argos_catalog_refresh(fetch)
        assert thread.call_count == 1
        dialog._on_argos_catalog_ready('')
        assert thread.call_count == 2 and thread.call_args.kwargs['args'] == (True,)
        assert dialog._argos_catalog_request_active
        dialog._on_argos_catalog_ready('')
        assert not dialog._argos_catalog_loading


@pytest.mark.parametrize('engine_probe', [True, False])
def test_engine_center_can_retry_when_the_os_rejects_a_probe_thread(center, engine_probe):
    dialog, _, _ = center
    dialog._argos_catalog = [dict(source_code='en', target_code='ru', installed=True)]
    start = dialog._start_runtime_probe if engine_probe else lambda: dialog._start_argos_catalog_refresh(True)
    with mock.patch('settings_window.threading.Thread', side_effect=RuntimeError('no worker available')):
        start()
    assert not dialog._runtime_probe_active and not dialog._argos_catalog_request_active
    if engine_probe:
        assert dialog._status_checking() == text('en', 'unchecked')
        assert 'no worker available' in dialog.task_status_label.toolTip()
    else:
        assert dialog._argos_catalog_error and dialog._argos_catalog[0]['installed']
    with mock.patch('settings_window.threading.Thread') as thread:
        start()
        thread.return_value.start.assert_called_once()


def test_failed_receipt_lookup_does_not_strand_the_rest_of_the_engine_inventory():
    from types import SimpleNamespace
    owner = SimpleNamespace(_easyocr_runtime_installed=lambda: True, _rapidocr_runtime_status=lambda: (True, ''))
    probe = SimpleNamespace(owner=owner, _engine_states_ready=mock.Mock(), _emit_runtime_probe_payload=mock.Mock(),
                            _available_windows_tags=lambda: [], _windows_ocr_capability_catalog=lambda: {})
    with mock.patch('engine_center.installed_states', side_effect=RuntimeError('storage path unavailable')):
        OcrLanguageManagerDialog._runtime_probe_worker(probe)
    probe._emit_runtime_probe_payload.assert_any_call({'rapidocr': (True, ''), 'complete': True})


def test_unreadable_argos_catalog_preserves_the_last_known_directions(center, monkeypatch):
    import settings_window
    dialog, _, _ = center
    directions = [dict(source_code='en', target_code='ru', installed=True)]
    dialog._argos_catalog = directions.copy()
    monkeypatch.setattr(settings_window, 'managed_install_supported', lambda: False)
    with mock.patch('translater.argos_package_catalog', side_effect=OSError('unavailable test catalog')):
        dialog._load_argos_catalog_worker(True)
    assert dialog._argos_catalog == directions and dialog._argos_catalog_error
    dialog._on_argos_catalog_ready('', [])
    assert dialog._argos_catalog == [] and not dialog._argos_catalog_error


def test_refreshing_packages_discards_the_previous_update_offer(center):
    dialog, _, _ = center
    table = dialog.easyocr_table
    button = next(b for b in table._package_engine_actions if b.property('packageAction') == 'update')
    install = mock.Mock()
    plan = dict(current=False, installed='1', available='2', size=7000000)
    dialog._on_update_plan_ready('easyocr', plan)
    with (mock.patch.object(dialog, '_start_runtime_probe'),
          mock.patch.object(dialog, '_start_argos_catalog_refresh'),
          mock.patch('settings_window.threading.Thread') as thread):
        dialog.refresh_catalog()
        assert button.text() == text('en', 'check_updates')
        assert 'Available: 2' not in table._package_size_label.text()
        dialog._request_update_check(table, button, install)
        thread.assert_called_once()
        install.assert_not_called()


def test_old_update_check_cannot_replace_a_more_recent_request(center, tmp_path, monkeypatch):
    dialog, _, _ = center
    table = dialog.easyocr_table
    button = next(b for b in table._package_engine_actions if b.property('packageAction') == 'update')
    monkeypatch.setenv('CLICKNTRANSLATE_COMPONENTS_DIR', str(tmp_path))
    catalog = dict(schema=1, revision=1, artifacts={}, bundles=[])
    old = dict(current=False, installed='1', available='2', size=10)
    new = dict(current=False, installed='1', available='3', size=20)
    with (mock.patch.object(dialog, '_start_runtime_probe'),
          mock.patch.object(dialog, '_start_argos_catalog_refresh'),
          mock.patch('settings_window.threading.Thread') as thread,
          mock.patch('component_catalog.trusted_catalog', return_value=catalog),
          mock.patch('engine_center.compare_update', side_effect=(old, new))):
        install = mock.Mock()
        dialog._request_update_check(table, button, install)
        old_request = thread.call_args.kwargs
        dialog.refresh_catalog()
        dialog._request_update_check(table, button, install)
        assert thread.call_count == 2
        new_request = thread.call_args.kwargs
        old_request['target'](*old_request['args'])
        assert button.property('packageUpdateChecking') and not button.isEnabled()
        assert button.property('packageUpdatePlan') is None
        new_request['target'](*new_request['args'])
        assert button.property('packageUpdatePlan')['available'] == '3'
        assert button.isEnabled()
        install.assert_not_called()


def test_newer_signed_catalog_retires_old_offers_and_never_rolls_sizes_back(center):
    dialog, _, _ = center
    table = dialog.easyocr_table
    button = next(b for b in table._package_engine_actions if b.property('packageAction') == 'update')
    first = dict(schema=1, revision=4, artifacts={}, bundles=[])
    second = dict(first, revision=5)
    offer = dict(current=False, installed='1', available='2', size=10, catalog_revision=4)
    dialog._on_package_sizes_ready(first)
    dialog._on_update_plan_ready('easyocr', offer)
    assert button.property('packageUpdatePlan')
    dialog._on_package_sizes_ready(second)
    dialog._on_package_sizes_ready(first)
    dialog._on_update_plan_ready('easyocr', offer)
    assert dialog._package_sizes.catalog['revision'] == 5
    assert not button.property('packageUpdatePlan')
    assert button.text() == text('en', 'check_updates')


def test_engine_maintenance_is_only_in_current_engine_menu_and_respects_busy_state(center):
    dialog, _, _ = center
    table = dialog.easyocr_table
    dialog._set_engine_missing_state(table, False)
    dialog.ocr_tabs.setCurrentWidget(table.parentWidget())
    dialog._populate_engine_menu(dialog.ocr_tabs)
    menu = dialog.ocr_tabs._tools_menu
    maintenance = table._package_engine_actions
    remove = table._package_remove_engine_button
    assert maintenance and remove in menu.actions()
    assert all(isinstance(action, QtWidgets.QAction) for action in maintenance)
    assert all(action in menu.actions() for action in maintenance)
    assert dialog.refresh_btn in menu.actions()
    assert dialog.findChildren(QtWidgets.QPushButton, 'languagePackageEngineRemove') == []
    dialog._install_in_progress = True
    dialog._set_package_actions_busy(True)
    assert not any(action.isEnabled() for action in [*maintenance, remove, dialog.refresh_btn])
    dialog._install_in_progress = False
    dialog._set_package_actions_busy(False)
    assert all(action.isEnabled() for action in [*maintenance, remove, dialog.refresh_btn])
    dialog._set_engine_missing_state(table, True)
    dialog._populate_engine_menu(dialog.ocr_tabs)
    assert menu.actions() == [dialog.refresh_btn], 'no stale actions from the previous engine'


@pytest.mark.parametrize('locale', tuple(MAINTENANCE))
@pytest.mark.parametrize('dark', (True, False))
def test_center_footer_and_maintenance_menu_render_without_overlap(center, locale, dark):
    from classic_style import classic_palette
    dialog, owner, parent = center
    # Construct in the requested locale, as normal opening does. No desktop UI.
    parent.current_interface_language = locale
    parent.current_theme = 'Темная' if dark else 'Светлая'
    dialog.close()
    with mock.patch.object(OcrLanguageManagerDialog, '_start_runtime_probe'), \
         mock.patch.object(OcrLanguageManagerDialog, '_start_argos_catalog_refresh'):
        rendered = OcrLanguageManagerDialog(owner)
        rendered._initial_probe_timer.stop()
        rendered._initial_catalog_timer.stop()
    try:
        app = QtWidgets.QApplication.instance()
        rendered._easyocr_status_cache = (True, '')
        rendered.ocr_tabs.setCurrentWidget(rendered.easyocr_table.parentWidget())
        rendered.show()
        app.processEvents()
        footer = [rendered.download_access_btn, rendered.close_btn]
        for button in footer:
            rect = QtCore.QRect(button.mapTo(rendered, QtCore.QPoint()), button.size())
            assert rendered.rect().contains(rect)
            assert button.width() >= button.minimumSizeHint().width()
        assert not footer[0].geometry().intersects(footer[1].geometry())
        for inner in (rendered.ocr_tabs, rendered.translation_tabs):
            rendered._populate_engine_menu(inner)
            menu = inner._tools_menu
            menu.ensurePolished()
            menu.resize(menu.sizeHint())
            menu.show()
            app.processEvents()
            for action in menu.actions():
                if not action.isSeparator() and action.isVisible():
                    assert menu.rect().contains(menu.actionGeometry(action))
            assert not menu.grab().isNull()
            menu.hide()
        image = rendered.grab().toImage()
        border = classic_palette(dark)['border']
        for point in ((0, 0), (image.width()-1, 0), (0, image.height()-1),
                      (image.width()-1, image.height()-1), (0, image.height()//2),
                      (image.width()-1, image.height()//2)):
            assert image.pixelColor(*point).name() == border
        # A former footer position must be cleared instead of painting twice.
        expected = classic_palette(dark)['background']
        x = rendered.content_widget.x() + 4
        for y in range(rendered.height() - 85, rendered.height() - 5):
            assert image.pixelColor(x, y).name() == expected
        output = Path('.tmp/engine-center-20261029')
        output.mkdir(parents=True, exist_ok=True)
        assert image.save(str(output / f'{locale}-{"dark" if dark else "light"}.png'))
        rendered._show_task_status('Preparing language packages: ' + 'Download details ' * 40, 45)
        rendered.task_show_button.show()
        app.processEvents()
        footer = [rendered.task_status_label, rendered.task_show_button,
                  rendered.download_access_btn, rendered.close_btn]
        rects = [QtCore.QRect(widget.mapTo(rendered, QtCore.QPoint()), widget.size()) for widget in footer]
        assert all(rendered.rect().contains(rect) for rect in rects)
        assert all(not rect.intersects(other) for i, rect in enumerate(rects) for other in rects[i+1:])
        assert rendered.task_status_label.toolTip().strip()
        assert not rendered.grab().isNull()
    finally:
        rendered.close()
        rendered.deleteLater()


def test_maintenance_copy_is_complete_for_every_interface_language():
    for locale, values in MAINTENANCE.items():
        assert len(values) == len(MAINTENANCE_KEYS)
        assert all(text(locale, key).strip() for key in MAINTENANCE_KEYS)


@pytest.mark.parametrize('percent', (80, 100, 125, 150, 200))
def test_engine_transitions_at_each_scale_keep_footer_and_children_inside(center, percent):
    from window_appearance import DialogAppearance
    dialog, _, _ = center
    app = QtWidgets.QApplication.instance()
    appearance = DialogAppearance(app, percent=percent, theme='Темная')
    try:
        with mock.patch.object(appearance, 'available_geometry',
                               return_value=QtCore.QRect(0, 0, 3840, 2160)):
            dialog.show()
            app.processEvents()
            appearance.apply(dialog)
            expected = dialog.size()
            for tabs in (dialog.ocr_tabs, dialog.translation_tabs):
                dialog.tabs.setCurrentWidget(tabs.parentWidget())
                for index in range(tabs.count()):
                    tabs.setCurrentIndex(index)
                    app.processEvents()
                    appearance.apply(dialog)
                    app.processEvents()
                    assert dialog.size() == expected
                    widgets = [dialog.download_access_btn, dialog.close_btn, tabs._activate_button,
                               tabs._tools_button]
                    table = dialog._active_engine_table()
                    if table is not None:
                        widgets += [table, table._package_missing_frame,
                                    table._package_missing_install_button, *table._package_action_buttons]
                    visible = [widget for widget in widgets if widget.isVisible()]
                    rects = [QtCore.QRect(widget.mapTo(dialog, QtCore.QPoint()), widget.size())
                             for widget in visible]
                    assert all(dialog.rect().contains(rect) for rect in rects)
                    for button in visible:
                        if isinstance(button, QtWidgets.QPushButton):
                            assert button.width() >= button.minimumSizeHint().width(), (
                                percent, tabs.tabText(index), button.objectName(), button.text(),
                                button.width(), button.minimumSizeHint().width())
                    # Nested missing-state frame/button intentionally overlap;
                    # sibling action controls may never overlap each other.
                    buttons = [widget for widget in visible if isinstance(widget, QtWidgets.QAbstractButton)]
                    for i, button in enumerate(buttons):
                        rect = QtCore.QRect(button.mapTo(dialog, QtCore.QPoint()), button.size())
                        assert all(not rect.intersects(QtCore.QRect(other.mapTo(dialog, QtCore.QPoint()), other.size()))
                                   for other in buttons[i+1:])
            output = Path('.tmp/engine-center-20261029')
            output.mkdir(parents=True, exist_ok=True)
            assert dialog.grab().save(str(output / f'scale-{percent}.png'))
    finally:
        app.removeEventFilter(appearance)
        appearance.deleteLater()
