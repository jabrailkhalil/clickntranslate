"""Live locale changes survive later styling of the same Dynamic controls."""
import unicodedata

import pytest
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtTest import QTest

import main
from capture_regions import text as region_text
from dynamic_templates import text as dynamic_text
from settings_categories import DYNAMIC_COMPACT
from test_desktop_ux import app, window


def _plain(text):
    return ' '.join(''.join(character for character in text
                            if unicodedata.category(character) != 'Cf').split())


def _settle(app):
    for _ in range(4):
        app.processEvents()
    QTest.qWait(20)
    app.processEvents()


def _assert_dynamic_labels(settings, locale):
    controls = (settings.game_pause_inactive_checkbox, settings.game_manual_output_checkbox,
                settings.game_toolbar_checkbox, settings.game_remember_template_checkbox)
    labels = (DYNAMIC_COMPACT[locale][2], dynamic_text(locale, 'manual_output'),
              DYNAMIC_COMPACT[locale][3], region_text(locale, 'dynamic_remember'))
    for control, label in zip(controls, labels):
        assert _plain(control.text()) == _plain(label)
        assert _plain(control.accessibleName()) == _plain(label)
        option = QtWidgets.QStyleOptionButton()
        control.initStyleOption(option)
        contents = control.style().subElementRect(QtWidgets.QStyle.SE_CheckBoxContents, option, control)
        align = QtCore.Qt.AlignRight if locale == 'ar' else QtCore.Qt.AlignLeft
        ink = control.fontMetrics().boundingRect(contents, align | QtCore.Qt.AlignVCenter, control.text())
        assert contents.contains(ink), (locale, control.text(), contents, ink)
        assert control.parentWidget().contentsRect().contains(control.geometry())


@pytest.mark.parametrize('locale', tuple(main.INTERFACE_LANGUAGE_BY_CODE))
def test_dynamic_labels_remain_localized_after_theme_scale_and_reopening(window, app, tmp_path, locale):
    assert app.platformName().split(':')[0] == 'offscreen', 'Never open desktop QA windows'
    window.set_interface_language('en')
    preferences = dict(game_pause_when_inactive=False, game_manual_output=True,
                       game_show_toolbar=False, game_remember_template=True)
    window.config.update(preferences)
    window.show_settings()
    settings = window.settings_window
    settings._set_settings_page(2)
    pages = settings.settings_pages
    flags = (settings.game_pause_inactive_checkbox, settings.game_manual_output_checkbox,
             settings.game_toolbar_checkbox, settings.game_remember_template_checkbox)
    window.set_interface_language(locale)
    _settle(app)
    _assert_dynamic_labels(settings, locale)

    for percent in (137, 80):
        window.set_ui_scale_percent(percent)
        for _ in range(2):
            window.toggle_theme()
            _settle(app)
            if percent == 137 and locale in ('ru', 'ar', 'hi'):
                assert window.grab().save(str(tmp_path / f'dynamic-{locale}-{window.current_theme}.png'))
            assert settings.settings_pages is pages
            assert settings.settings_pages.currentIndex() == 2
            _assert_dynamic_labels(settings, locale)
            assert [control.isChecked() for control in flags] == list(preferences.values())
            assert all(window.config[key] == value for key, value in preferences.items())

    window.show_main_screen()
    window.show_settings()
    settings._set_settings_page(2)
    _settle(app)
    _assert_dynamic_labels(settings, locale)
    assert all(window.config[key] == value for key, value in preferences.items())
    # Retranslation must not reconnect the setting's persistence signal.
    window.save_config.reset_mock()
    settings.game_manual_output_checkbox.click()
    assert window.config['game_manual_output'] is False
    window.save_config.assert_called_once_with()
