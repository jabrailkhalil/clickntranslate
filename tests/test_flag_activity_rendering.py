"""Render the real flag widgets and waiting header, without desktop windows."""
import os
from pathlib import Path
import threading

import pytest
from PyQt5 import QtCore, QtGui

from icon_rendering import paint_icon, load_icon
from languages import LANGUAGES, language_icon_path
from project_paths import resource_root
from settings_sections import PAGE_DYNAMIC
from test_desktop_ux import app, window
from test_ui_operations import wait_until
from ui_operations import operation_for


def output_dir(tmp_path):
    directory = Path(os.environ.get('CNT_VISUAL_QA_DIR', str(tmp_path)))
    directory.mkdir(parents=True, exist_ok=True)
    return directory


@pytest.mark.parametrize('dark', [True, False])
def test_all_flag_drawings_remain_framed_at_six_times_logical_density(app, tmp_path, dark):
    columns, cell = 9, 180
    image = QtGui.QImage(columns*cell, ((len(LANGUAGES)+columns-1)//columns)*cell,
                        QtGui.QImage.Format_ARGB32_Premultiplied)
    image.fill(QtGui.QColor('#17171c' if dark else '#f5f1f8'))
    painter = QtGui.QPainter(image)
    painter.scale(6, 6)
    for index, language in enumerate(LANGUAGES):
        x, y = (index % columns)*30, (index//columns)*30
        icon = load_icon(str(resource_root()/language_icon_path(language.code)))
        paint_icon(painter, icon, QtCore.QRectF(x+5, y+2, 20, 20))
        painter.setPen(QtGui.QColor('white' if dark else 'black'))
        font = QtGui.QFont('Segoe UI')
        font.setPixelSize(3)
        painter.setFont(font)
        painter.drawText(QtCore.QRectF(x, y+23, 30, 5), QtCore.Qt.AlignCenter, language.code.upper())
    painter.end()
    assert image.save(str(output_dir(tmp_path)/f'all-flags-6x-{"dark" if dark else "light"}.png'))
    # Distinct national stripes survive the high-density paint (not just an
    # empty white frame with a valid SVG container).
    for code in ('ru', 'id', 'en', 'hi', 'ar'):
        index = next(i for i, language in enumerate(LANGUAGES) if language.code == code)
        x, y = (index % columns)*cell, (index//columns)*cell
        colors = {image.pixelColor(x+offset_x, y+offset_y).name()
                  for offset_x in range(55, 125, 10) for offset_y in range(30, 110, 8)}
        assert len(colors-{'#17171c', '#f5f1f8'}) >= 2, code


@pytest.mark.parametrize('locale,theme,scale', [('en', 'Темная', 137), ('ar', 'Светлая', 200)])
def test_real_header_feedback_and_language_grid_fit_the_scaled_application(window, app, tmp_path, locale, theme, scale):
    window.set_interface_language(locale)
    if window.current_theme != theme:
        window.toggle_theme()
    window.set_ui_scale_percent(scale)
    window.show_settings()
    window.settings_window._set_settings_page(PAGE_DYNAMIC)
    window.show_interface_language_menu()
    app.processEvents()
    directory = output_dir(tmp_path)
    assert window.grab().save(str(directory/f'language-grid-{locale}-{scale}.png'))
    window._close_interface_language_picker()
    release = threading.Event()
    operation = operation_for(window)
    operation.DELAY_MS = 0
    try:
        operation.start('import', work=lambda: release.wait(3))
        wait_until(app, lambda: operation._indicator is not None and operation._indicator.isVisible())
        indicator = operation._indicator
        assert indicator.parentWidget().rect().contains(indicator.geometry())
        assert indicator.parentWidget() is window
        from ui_scaling import widget_global_rect
        for name in ('flag_button', 'theme_button', 'settings_button', 'close_button'):
            button_rect = widget_global_rect(getattr(window, name))
            button_rect.translate(-window.mapToGlobal(QtCore.QPoint()))
            assert not indicator.geometry().intersects(button_rect)
        assert window.grab().save(str(directory/f'waiting-header-{locale}-{scale}.png'))
    finally:
        release.set()
        wait_until(app, lambda: not operation.active)
