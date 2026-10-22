"""An update must reach GUI readiness without waiting for a Welcome click."""
from unittest import mock
import pytest
from PyQt5.QtWidgets import QApplication
import main


@pytest.mark.parametrize('argument', ['--show-after-update', '--update-ack=/tmp/ready'])
def test_restart_skips_welcome_without_changing_the_users_preference(monkeypatch, argument):
    app = QApplication.instance() or QApplication([])
    load = main.DarkThemeApp.load_config

    def config(owner):
        load(owner)
        owner.config['show_update_info'] = True
        for key in tuple(owner.config):
            if key.endswith('_hotkey'):
                owner.config[key] = ''

    monkeypatch.setattr(main.sys, 'argv', [main.sys.argv[0], argument])
    monkeypatch.setattr(main, 'LAYOUT_EDITOR_MODE', False)
    monkeypatch.setattr(main.DarkThemeApp, 'load_config', config)
    with mock.patch.object(main, 'WelcomeDialog') as welcome, \
         mock.patch.object(main.DarkThemeApp, 'create_tray_icon'), \
         mock.patch.object(main.DarkThemeApp, '_sync_desktop_assistant'), \
         mock.patch.object(main.DarkThemeApp, '_sync_selection_quick_translate'), \
         mock.patch.object(main.DarkThemeApp, 'sync_autostart_state', return_value=False):
        owner = main.DarkThemeApp()
        try:
            welcome.assert_not_called()
            assert owner.config['show_update_info'] is True
            owner.show()
            app.processEvents()
            assert owner.isVisible() and owner.central_widget.isVisible()
        finally:
            owner.force_quit = True
            owner.close()
            owner.deleteLater()
            app.processEvents()
