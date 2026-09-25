from types import SimpleNamespace
from unittest import mock

import pytest
from PyQt5 import QtCore, QtWidgets

import macos_desktop
import macos_permissions as permissions


@pytest.fixture
def app():
    instance = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield instance
    for window in instance.topLevelWidgets():
        if isinstance(window, (Owner, permissions.MacPermissionsDialog)):
            window.close()
            window.deleteLater()
    instance.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    instance.processEvents()


@pytest.fixture
def grants(monkeypatch):
    states = {'screen': False, 'accessibility': False}
    monkeypatch.setattr(macos_desktop, 'permission_granted', lambda kind: states[kind])
    return states


class Owner(QtWidgets.QWidget):
    def __init__(self, language='ru', theme='Светлая'):
        super().__init__()
        self.current_interface_language = language
        self.current_theme = theme
        self.guide_checks = 0

    def _maybe_start_first_run_guide(self):
        self.guide_checks += 1


@pytest.mark.parametrize('language', list(permissions.TEXT))
@pytest.mark.parametrize('theme', ['Светлая', 'Темная'])
def test_guide_fits_and_does_not_request_access_without_a_click(app, grants, monkeypatch, language, theme):
    request = mock.Mock()
    monkeypatch.setattr(macos_desktop, 'request_permission', request)
    owner = Owner(language, theme)
    dialog = permissions.MacPermissionsDialog(owner, language)
    dialog.show()
    app.processEvents()
    assert dialog.isVisible()
    scroll = dialog.findChild(QtWidgets.QScrollArea, 'permissionScroll')
    assert scroll is not None
    assert scroll.verticalScrollBarPolicy() == QtCore.Qt.ScrollBarAsNeeded
    assert scroll.horizontalScrollBarPolicy() == QtCore.Qt.ScrollBarAlwaysOff
    for button in dialog.findChildren(QtWidgets.QPushButton):
        assert button.isVisible()
        assert dialog.rect().contains(QtCore.QRect(button.mapTo(dialog, QtCore.QPoint()), button.size()))
        assert button.fontMetrics().horizontalAdvance(button.text()) <= button.width()
    request.assert_not_called()
    dialog.buttons['screen'].click()
    request.assert_called_once_with('screen')
    assert dialog.isVisible()
    grants['screen'] = grants['accessibility'] = True
    dialog.refresh()
    assert all(not button.isEnabled() for button in dialog.buttons.values())
    assert dialog.continue_button.text() == permissions.TEXT[language][8]
    dialog.accept()
    assert not dialog.timer.isActive()
    owner.close()


def test_startup_shows_once_per_session_and_defers_when_hidden(app, grants, monkeypatch):
    monkeypatch.setattr(permissions.platform_support, 'IS_MAC', True)
    owner = Owner()
    assert permissions.maybe_show_permissions(owner) is False
    owner.show()
    assert permissions.maybe_show_permissions(owner) is True
    dialog = owner._macos_permissions_dialog
    assert permissions.maybe_show_permissions(owner) is True
    assert owner._macos_permissions_dialog is dialog
    dialog.reject()
    app.processEvents()
    assert permissions.maybe_show_permissions(owner) is False
    assert owner._macos_permissions_dialog is None
    owner.close()


def test_granted_permissions_skip_the_startup_guide(app, grants, monkeypatch):
    monkeypatch.setattr(permissions.platform_support, 'IS_MAC', True)
    grants.update(screen=True, accessibility=True)
    owner = Owner()
    owner.show()
    assert permissions.maybe_show_permissions(owner) is False
    assert getattr(owner, '_macos_permissions_dialog', None) is None
    owner.close()


def test_other_platforms_never_probe_permissions(app, monkeypatch):
    monkeypatch.setattr(permissions.platform_support, 'IS_MAC', False)
    probe = mock.Mock(side_effect=AssertionError('unexpected Mac probe'))
    monkeypatch.setattr(macos_desktop, 'permission_granted', probe)
    owner = Owner()
    owner.show()
    assert permissions.maybe_show_permissions(owner) is False
    probe.assert_not_called()
    owner.close()


def test_opening_settings_failure_stays_recoverable(app, grants, monkeypatch):
    monkeypatch.setattr(macos_desktop, 'request_permission', mock.Mock(side_effect=OSError('test')))
    dialog = permissions.MacPermissionsDialog(language='ru')
    dialog.show()
    dialog.buttons['accessibility'].click()
    assert dialog.error_label.isVisible()
    assert dialog.buttons['accessibility'].isEnabled()
    dialog.reject()


@pytest.mark.parametrize('kind', ['screen', 'accessibility'])
def test_request_uses_os_prompt_for_current_process_and_correct_pane(grants, monkeypatch, kind):
    import sys
    screen_prompt, accessibility_prompt = mock.Mock(), mock.Mock()
    monkeypatch.setitem(sys.modules, 'Quartz', SimpleNamespace(CGRequestScreenCaptureAccess=screen_prompt))
    monkeypatch.setitem(sys.modules, 'ApplicationServices', SimpleNamespace(
        AXIsProcessTrustedWithOptions=accessibility_prompt, kAXTrustedCheckOptionPrompt='prompt'))
    opened = mock.Mock()
    native_app = mock.Mock()
    monkeypatch.setitem(sys.modules, 'AppKit', SimpleNamespace(
        NSApplication=SimpleNamespace(sharedApplication=lambda: native_app)))
    monkeypatch.setattr(macos_desktop.subprocess, 'Popen', opened)
    assert macos_desktop.request_permission(kind) is False
    if kind == 'screen':
        screen_prompt.assert_called_once_with()
        accessibility_prompt.assert_not_called()
    else:
        accessibility_prompt.assert_called_once_with({'prompt': True})
        screen_prompt.assert_not_called()
    pane = 'Privacy_ScreenCapture' if kind == 'screen' else 'Privacy_Accessibility'
    assert opened.call_args.args[0][-1].endswith('?' + pane)
    native_app.hide_.assert_called_once_with(None)
    grants[kind] = True
    opened.reset_mock()
    native_app.hide_.reset_mock()
    assert macos_desktop.request_permission(kind) is True
    opened.assert_not_called()
    native_app.hide_.assert_not_called()


def test_request_rejects_unknown_permission():
    with pytest.raises(ValueError):
        macos_desktop.request_permission('unknown')


def test_startup_checks_permissions_even_after_tutorial_was_completed(app, grants, monkeypatch):
    import main
    monkeypatch.setattr(main.platform_support, 'IS_MAC', True)
    monkeypatch.setattr(main, 'LAYOUT_EDITOR_MODE', False)
    owner = Owner()
    owner.config = {'first_run_guide_completed': True, 'first_run_guide_pending': False}
    owner.show()
    main.DarkThemeApp._maybe_start_first_run_guide(owner)
    assert owner._macos_permissions_dialog.isVisible()
    owner._macos_permissions_dialog.reject()
    owner.close()
