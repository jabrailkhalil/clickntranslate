"""Check the native process exit, beyond a successful in-process assertion."""

import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.skipif(sys.platform != 'darwin' or os.environ.get('QT_QPA_PLATFORM') == 'offscreen',
                    reason='Requires the native Cocoa application lifecycle')
@pytest.mark.parametrize('cycle', range(3))
def test_quit_returns_from_event_loop_and_disposes_cocoa_without_crashing(cycle):
    script = r'''
import tempfile
from unittest import mock
import macos_desktop
temporary = tempfile.TemporaryDirectory(prefix='cnt-quit-test-')
macos_desktop.user_data_dir = lambda: temporary.name
import main
from PyQt5 import QtCore, sip
main.LAYOUT_EDITOR_MODE = True
app = main._ensure_startup_application()
with mock.patch.object(main.DarkThemeApp, 'sync_autostart_state', return_value=False):
    window = main.DarkThemeApp()
window.show()
window.show_settings()
dialogs = []
for index in range(8):
    dialog = main.TranslationResultDialog(window, 'Result', auto_copy=False,
                source_text='Source', source_lang='en', target_lang='ru')
    dialog.show()
    dialogs.append(dialog)
QtCore.QTimer.singleShot(20, window.exit_app)
assert app.exec_() == 0
main.dispose_native_application(app)
assert sip.isdeleted(app)
assert all(sip.isdeleted(dialog) for dialog in dialogs)
assert sip.isdeleted(window)
print('Clean event loop return and Cocoa disposal')
'''
    result = subprocess.run([sys.executable, '-X', 'faulthandler', '-c', script],
                cwd=Path(__file__).resolve().parents[1], capture_output=True,
                text=True, timeout=30, env=dict(os.environ, QT_QPA_PLATFORM='cocoa'))
    assert result.returncode == 0, result.stderr
    assert 'Clean event loop return and Cocoa disposal' in result.stdout
