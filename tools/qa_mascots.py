"""Render mascot settings and art using isolated configuration and no hotkeys."""
from contextlib import ExitStack
from pathlib import Path
from unittest import mock
import os
import sys
import tempfile


def run():
    root = Path(__file__).resolve().parents[1]
    sys.path[:0] = [str(root), str(root / 'src'), str(root / 'tests')]
    sys.argv[0] = str(root / 'main.py')
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    from PyQt5 import QtCore, QtGui, QtWidgets
    import portable_paths
    from qt_layout_test_support import ensure_layout_fonts
    from ui_scaling import MainWindowScaleController
    from assistant_art import MASCOTS, companion_art

    output = root / '.tmp/mascot-qa'
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='cnt-mascot-qa-') as sandbox, ExitStack() as stack:
        stack.enter_context(mock.patch.object(portable_paths, 'portable_base_dir', return_value=sandbox))
        import main
        config = dict(main.DEFAULT_CONFIG, interface_language='ru', desktop_assistant_enabled=True)
        for patch in (
            mock.patch.object(main, 'LAYOUT_EDITOR_MODE', True),
            mock.patch.object(main, 'get_cached_config', return_value=config),
            mock.patch.object(main.DarkThemeApp, 'save_config'),
            mock.patch.object(main.DarkThemeApp, 'sync_autostart_state', return_value=False),
            mock.patch.object(MainWindowScaleController, 'available_geometry',
                              return_value=QtCore.QRect(0, 0, 2560, 1440)),
        ):
            stack.enter_context(patch)
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        ensure_layout_fonts(app)
        window = main.DarkThemeApp()
        window.current_interface_language = 'ru'
        window.config['interface_language'] = 'ru'
        window.show()
        try:
            for theme, suffix in (('Темная', 'dark'), ('Светлая', 'light')):
                window.current_theme = theme
                window.config['theme'] = theme
                window.apply_theme()
                window.show_assistant_settings()
                page = window.settings_window.settings_assistant_page
                for mascot in MASCOTS:
                    page.choose_mascot(mascot)
                    for pose in ('portrait', 'walking'):
                        page.choose_appearance(pose)
                        window.set_ui_scale_percent(100)
                        for _ in range(6):
                            app.processEvents()
                        window.grab().save(str(output / f'{mascot}-{pose}-{suffix}.png'))
                page.mascot_combo.showPopup()
                app.processEvents()
                page.mascot_combo.view().window().grab().save(str(output / f'character-dropdown-{suffix}.png'))
                page.mascot_combo.hidePopup()
                canvas = QtGui.QImage(1000, 360, QtGui.QImage.Format_ARGB32)
                canvas.fill(QtGui.QColor('#202028' if suffix == 'dark' else '#f4f4f8'))
                painter = QtGui.QPainter(canvas)
                painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
                painter.setPen(QtGui.QColor('white' if suffix == 'dark' else '#292937'))
                font = painter.font()
                font.setPixelSize(18)
                painter.setFont(font)
                for index, mascot in enumerate(MASCOTS):
                    pixmap = companion_art('portrait', mascot=mascot)
                    painter.drawPixmap(QtCore.QRect(index * 200 + 4, 24, 192, 192), pixmap)
                    painter.drawText(QtCore.QRect(index * 200, 222, 200, 30), QtCore.Qt.AlignCenter, mascot.title())
                    painter.drawPixmap(QtCore.QRect(index * 200 + 56, 260, 88, 88), pixmap)
                painter.end()
                canvas.save(str(output / f'characters-{suffix}.png'))
            print(f'Rendered 20 settings views, two dropdowns and two character sheets in {output}.')
        finally:
            window.force_quit = True
            window.close()
            window.deleteLater()
            app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
            app.processEvents()


if __name__ == '__main__':
    run()
