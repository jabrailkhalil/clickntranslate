"""The text and shortcut panels share one header/body visual hierarchy."""
import pytest
from PyQt5.QtCore import QPoint, QRect

from test_desktop_ux import app, window


@pytest.mark.parametrize('theme', ['Темная', 'Светлая'])
@pytest.mark.parametrize('percent', [100, 150, 200])
def test_text_panel_matches_shortcut_surfaces_without_inner_card_edges(window, app, theme, percent):
    window.current_theme = theme
    window.apply_theme()
    window.set_ui_scale_percent(percent)
    for _ in range(5):
        app.processEvents()
    image = window.ui_root.grab().toImage()
    ratio = image.devicePixelRatio()

    def color(widget, x, y):
        point = widget.mapTo(window.ui_root, QPoint(x, y))
        return image.pixelColor(round(point.x() * ratio), round(point.y() * ratio)).name()

    upper, lower = window.main_text_section, window.main_shortcut_section
    composer, shortcuts = window.main_composer, window.main_hotkey_area
    assert upper.x() == lower.x() and upper.width() == lower.width()
    assert color(upper, 4, 25) == color(lower, 4, 25)
    surface = '#121116' if theme == 'Темная' else '#f8f5fb'
    assert color(composer, 3, 20) == color(shortcuts, 3, 12) == surface
    # The toolbar and editors are not independently outlined cards. Both
    # panes sit directly on the common lower surface, including their edges.
    # Sample the inner-facing edges; the outside edges share the outer
    # panel's antialiased stroke at fractional device-pixel ratios.
    assert color(window.main_input_pane, window.main_input_pane.width() - 1, 20) == surface
    assert color(window.main_result_pane, 0, 20) == surface
    # Both panels have the same uninterrupted full-width horizontal seam.
    for x in (10, composer.width() // 2, composer.width() - 10):
        assert color(composer, x, 0) == color(shortcuts, x, 0)
        assert color(composer, x, 0) != surface
    for widget in (window.translate_button, window.main_result_copy_button,
                   window.main_result_expand_button):
        bounds = QRect(widget.mapTo(composer, QPoint()), widget.size())
        assert composer.rect().contains(bounds)
    assert upper.geometry().bottom() < lower.geometry().top()
