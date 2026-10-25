"""The result selector explains destinations and keeps three independent switches."""
import pytest
import main
from result_presentation_text import RESULT_PRESENTATION_TEXT
from settings_window import settings_text
from test_desktop_ux import app, window


@pytest.mark.parametrize('locale', tuple(main.INTERFACE_LANGUAGE_BY_CODE))
@pytest.mark.parametrize('dark', [True, False])
def test_result_menu_explains_checked_and_unchecked_destinations(window, app, locale, dark):
    window.set_interface_language(locale)
    if (window.current_theme != 'Светлая') != dark:
        window.toggle_theme()
    window.show_settings()
    settings = window.settings_window
    settings._set_settings_page(1)
    control = settings.result_window_control
    app.processEvents()
    copy = RESULT_PRESENTATION_TEXT[locale]
    assert settings.result_window_label.text() == settings_text(locale, 'result_window_label')
    assert control.model().item(0).text() == settings_text(locale, 'result_window_modes_header')
    note = control.model().item(control.count()-1)
    assert note.text() == settings_text(locale, 'result_window_footer')
    assert not note.isEnabled() and note.toolTip()
    assert set(copy) == set(RESULT_PRESENTATION_TEXT['en'])
    assert all(value.strip() for value in copy.values())
    for mode in main.RESULT_WINDOW_MODES:
        item = control._item(mode)
        assert item.toolTip() == settings_text(locale, 'result_window_mode_'+mode+'_tooltip')
        assert item.text() == settings_text(locale, 'result_window_row_'+mode)
    before = control.checked_modes()
    control._toggle_pressed(note.index())
    assert control.checked_modes() == before
    for scale in (80, 125, 200):
        window.set_ui_scale_percent(scale)
        control.showPopup()
        for _ in range(4): app.processEvents()
        view = control.view()
        for row in range(control.count()):
            index = control.model().index(row, 0)
            rectangle = view.visualRect(index)
            assert rectangle.height() > 0
            assert view.viewport().rect().contains(rectangle.adjusted(1, 0, -1, 0)), (locale, scale, row, rectangle)
        control.hidePopup()


def test_result_menu_choices_preserve_delivery_semantics(window, app):
    window.show_settings()
    settings = window.settings_window
    control = settings.result_window_control
    for mode in main.RESULT_WINDOW_MODES:
        control.set_mode_checked(mode, False)
        assert main.result_window_hidden_for(window.config, mode)
        control.set_mode_checked(mode, True)
        assert not main.result_window_hidden_for(window.config, mode)
