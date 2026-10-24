"""Real graphics-proxy pointer and keyboard flows keep distinct focus feedback."""
import pytest
from PyQt5 import QtCore, QtWidgets, sip
from PyQt5.QtTest import QSignalSpy, QTest

from keyboard_navigation import focus_control, install_keyboard_navigation
from test_desktop_ux import app, window


def settle(app):
    for _ in range(5):
        app.processEvents()


def click(window, widget, app):
    controller = window._ui_scale_controller
    QTest.mouseClick(controller.view.viewport(), QtCore.Qt.LeftButton,
                     pos=controller.map_widget_to_view(widget))
    settle(app)


@pytest.fixture
def trace(app):
    class FocusTrace(QtCore.QObject):
        def __init__(self):
            super().__init__()
            self.events = []

        def eventFilter(self, widget, event):
            if event.type() == QtCore.QEvent.FocusIn and isinstance(widget, QtWidgets.QWidget):
                self.events.append((widget.objectName() or type(widget).__name__,
                                    widget.accessibleName(), int(event.reason())))
            return False
    recorder = FocusTrace()
    app.installEventFilter(recorder)
    yield recorder.events
    app.removeEventFilter(recorder)
    recorder.deleteLater()


def controls(window, picker):
    return [window.flag_button, *picker.buttons.values(), picker.previous_button,
            picker.next_button, picker.close_button]


def assert_pointer_feedback_only(window, picker, app, trace):
    marked = [control.accessibleName() or control.objectName()
              for control in controls(window, picker) if control.property('keyboardFocus')]
    ring = getattr(window.ui_root, '_keyboard_focus_ring', None)
    visible_ring = ring is not None and not sip.isdeleted(ring) and ring.isVisible()
    assert not marked and not visible_ring and not app._keyboard_navigation.keyboard and not picker.keyboard_mode, (marked, visible_ring, trace[-30:])


@pytest.mark.parametrize('locale', ['en', 'ru', 'ar'])
def test_mouse_open_has_selection_feedback_without_keyboard_frame(window, app, trace, locale):
    install_keyboard_navigation(app)
    window.set_interface_language(locale)
    settle(app)
    click(window, window.flag_button, app)
    picker = window._interface_language_picker
    assert picker is not None and picker.isVisible()
    assert window.flag_button.isChecked() and picker.buttons[locale].property('current')
    assert_pointer_feedback_only(window, picker, app, trace)


@pytest.mark.parametrize('locale', ['en', 'ru', 'ar'])
def test_mouse_choice_does_not_become_tab_navigation_during_live_relabel(window, app, trace, locale):
    install_keyboard_navigation(app)
    settle(app)
    click(window, window.flag_button, app)
    picker = window._interface_language_picker
    click(window, picker.buttons[locale], app)
    assert window._interface_language_picker is picker and picker.isVisible()
    assert window.current_interface_language == locale
    assert picker.buttons[locale].property('current')
    assert_pointer_feedback_only(window, picker, app, trace)


def test_mouse_page_arrows_preserve_pointer_mode_and_do_not_select(window, app, trace):
    install_keyboard_navigation(app)
    settle(app)
    initial = window.current_interface_language
    click(window, window.flag_button, app)
    picker = window._interface_language_picker
    click(window, picker.next_button, app)
    assert picker.pages.currentIndex() == 1 and window.current_interface_language == initial
    assert_pointer_feedback_only(window, picker, app, trace)
    click(window, picker.previous_button, app)
    assert picker.pages.currentIndex() == 0 and window.current_interface_language == initial
    assert_pointer_feedback_only(window, picker, app, trace)


def test_keyboard_enter_on_page_arrow_keeps_keyboard_feedback(window, app):
    install_keyboard_navigation(app)
    settle(app)
    click(window, window.flag_button, app)
    picker = window._interface_language_picker
    initial = window.current_interface_language
    focus_control(picker.next_button)
    QTest.keyClick(picker.next_button, QtCore.Qt.Key_Return)
    settle(app)
    assert picker.pages.currentIndex() == 1 and picker.keyboard_mode
    assert picker.buttons['hi'].hasFocus() and picker.buttons['hi'].property('keyboardFocus')
    assert window.current_interface_language == initial


def test_keyboard_arrows_take_over_after_mouse_paging(window, app, trace):
    settle(app)
    click(window, window.flag_button, app)
    picker = window._interface_language_picker
    initial = window.current_interface_language
    click(window, picker.next_button, app)
    assert_pointer_feedback_only(window, picker, app, trace)
    QTest.keyClick(picker.buttons['hi'], QtCore.Qt.Key_Right)
    settle(app)
    assert picker.keyboard_mode and picker.buttons['id'].hasFocus()
    assert picker.buttons['id'].property('keyboardFocus')
    assert window.current_interface_language == initial
    click(window, picker.previous_button, app)
    assert picker.pages.currentIndex() == 0 and window.current_interface_language == initial
    assert_pointer_feedback_only(window, picker, app, trace)


def test_switching_from_keyboard_to_mouse_removes_keyboard_feedback(window, app, trace):
    install_keyboard_navigation(app)
    settle(app)
    click(window, window.flag_button, app)
    picker = window._interface_language_picker
    QTest.keyClick(picker.focusWidget() or picker, QtCore.Qt.Key_Right)
    settle(app)
    click(window, picker.buttons['fr'], app)
    assert window.current_interface_language == 'fr'
    assert_pointer_feedback_only(window, picker, app, trace)


def test_mouse_focused_current_cell_has_no_extra_native_focus_pixels(window, app):
    settle(app)
    click(window, window.flag_button, app)
    picker = window._interface_language_picker
    selected = picker.buttons[window.current_interface_language]
    focused = selected.grab().toImage()
    selected.clearFocus()
    settle(app)
    unfocused = selected.grab().toImage()
    assert focused == unfocused


@pytest.mark.parametrize('page', [0, 1, 2, 3])
@pytest.mark.parametrize('locale', ['en', 'ar'])
def test_mouse_choice_after_keyboard_settings_navigation_keeps_mouse_feedback(window, app, trace, page, locale):
    window.show_settings()
    settings = window.settings_window
    settings._set_settings_page(page)
    settle(app)
    focus_control(settings.settings_page_tabs[page])
    click(window, window.flag_button, app)
    picker = window._interface_language_picker
    assert_pointer_feedback_only(window, picker, app, trace)
    click(window, picker.buttons[locale], app)
    assert window.settings_window is settings and settings.settings_pages.currentIndex() == page
    assert window.current_interface_language == locale
    assert_pointer_feedback_only(window, picker, app, trace)


def test_clicking_flag_again_closes_without_navigation_or_lost_draft(window, app):
    window.text_input.setPlainText('Draft before opening the language chooser')
    settle(app)
    original = window.main_text_section
    click(window, window.flag_button, app)
    click(window, window.flag_button, app)
    assert window._interface_language_picker is None and not window.flag_button.isChecked()
    assert window.main_text_section is original
    assert window.text_input.toPlainText() == 'Draft before opening the language chooser'


def test_clicking_blank_footer_dismisses_without_changing_language(window, app):
    settle(app)
    initial = window.current_interface_language
    click(window, window.flag_button, app)
    assert window._interface_language_picker is not None
    controller = window._ui_scale_controller
    footer = window.main_footer
    position = footer.mapTo(window.ui_root, QtCore.QPoint(3, footer.height()-3))
    view_point = controller.view.mapFromScene(window.ui_root.graphicsProxyWidget().mapToScene(QtCore.QPointF(position)))
    QTest.mouseClick(controller.view.viewport(), QtCore.Qt.LeftButton, pos=view_point)
    settle(app)
    assert window._interface_language_picker is None
    assert window.current_interface_language == initial


def test_outside_action_closes_picker_and_runs_once_after_keyboard_navigation(window, app):
    settle(app)
    click(window, window.flag_button, app)
    picker = window._interface_language_picker
    focus_control(picker.buttons[window.current_interface_language])
    theme_clicked = QSignalSpy(window.theme_button.clicked)
    initial_theme = window.current_theme
    click(window, window.theme_button, app)
    assert window._interface_language_picker is None
    assert len(theme_clicked) == 1 and window.current_theme != initial_theme
    assert not app._keyboard_navigation.keyboard
    assert not window.theme_button.property('keyboardFocus')


def test_connection_stem_is_part_of_open_picker_without_selecting_or_clicking_below(window, app, trace):
    from ui_scaling import widget_global_point
    settle(app)
    click(window, window.flag_button, app)
    picker = window._interface_language_picker
    connection = window._interface_language_connection
    flag = QtCore.QRect(window.flag_button.mapTo(window.ui_root, QtCore.QPoint()), window.flag_button.size())
    panel = QtCore.QRect(picker.mapTo(window.ui_root, QtCore.QPoint()), picker.size())
    overlap_left, overlap_right = max(flag.left(), panel.left()), min(flag.right(), panel.right())
    point = QtCore.QPoint((overlap_left+overlap_right)//2, (flag.bottom()+panel.top())//2)
    assert overlap_right > overlap_left and flag.bottom() < point.y() < panel.top()
    assert connection.contains_global(widget_global_point(window.ui_root, point))
    selected = QSignalSpy(picker.languageSelected)
    focus_control(picker.buttons[window.current_interface_language])
    QTest.keyClick(picker.focusWidget(), QtCore.Qt.Key_Right)
    assert picker.keyboard_mode
    controller = window._ui_scale_controller
    view_point = controller.view.mapFromScene(window.ui_root.graphicsProxyWidget().mapToScene(QtCore.QPointF(point)))
    QTest.mouseClick(controller.view.viewport(), QtCore.Qt.LeftButton, pos=view_point)
    settle(app)
    assert window._interface_language_picker is picker and picker.isVisible()
    assert len(selected) == 0 and window.flag_button.isChecked()
    assert_pointer_feedback_only(window, picker, app, trace)


def test_escape_after_mouse_open_restores_keyboard_focus_to_flag(window, app):
    settle(app)
    click(window, window.flag_button, app)
    picker = window._interface_language_picker
    assert not picker.keyboard_mode
    dismiss_modes = []
    picker.dismissed.connect(lambda: dismiss_modes.append(picker.keyboard_mode))
    QTest.keyClick(picker.focusWidget() or picker, QtCore.Qt.Key_Escape)
    settle(app)
    assert window._interface_language_picker is None
    assert dismiss_modes == [True]
    assert app._keyboard_navigation.keyboard and window.flag_button.hasFocus()
    ring = getattr(window.ui_root, '_keyboard_focus_ring', None)
    assert window.flag_button.property('keyboardFocus') or (ring is not None and ring.isVisible())


def test_keyboard_open_tab_arrows_enter_escape_have_visible_focus_and_keep_draft(window, app):
    install_keyboard_navigation(app)
    window.text_input.setPlainText('Keyboard draft')
    settle(app)
    focus_control(window.flag_button)
    QTest.keyClick(window.flag_button, QtCore.Qt.Key_Return)
    settle(app)
    picker = window._interface_language_picker
    assert picker is not None
    selected = picker.buttons[window.current_interface_language]
    assert selected.hasFocus()
    ring = getattr(window.ui_root, '_keyboard_focus_ring', None)
    assert selected.property('keyboardFocus') or (ring is not None and ring.isVisible())
    QTest.keyClick(selected, QtCore.Qt.Key_Home)
    QTest.keyClick(picker.buttons['en'], QtCore.Qt.Key_Right)
    assert picker.buttons['ru'].hasFocus()
    QTest.keyClick(picker.buttons['ru'], QtCore.Qt.Key_Return)
    settle(app)
    assert window.current_interface_language == 'ru' and picker.buttons['ru'].hasFocus()
    QTest.keyClick(picker.buttons['ru'], QtCore.Qt.Key_Tab)
    assert picker.isAncestorOf(picker.focusWidget())
    QTest.keyClick(picker.focusWidget(), QtCore.Qt.Key_Escape)
    settle(app)
    assert window._interface_language_picker is None and not window.flag_button.isChecked()
    assert window.text_input.toPlainText() == 'Keyboard draft'
