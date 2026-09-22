"""Use the desktop's real GLib parser to launch a harmless temporary program."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

import linux_desktop


@pytest.fixture(scope='module')
def gio_python():
    if sys.platform != 'linux':
        pytest.skip('Native freedesktop launcher parser is Linux-only')
    interpreter = '/usr/bin/python3'
    if not Path(interpreter).is_file():
        pytest.skip('Install system python3 and python3-gi for native desktop launcher checks')
    probe = subprocess.run([interpreter, '-c', 'from gi.repository import Gio; assert Gio.DesktopAppInfo'], capture_output=True, timeout=8)
    if probe.returncode:
        pytest.skip('Install python3-gi for native desktop launcher checks')
    return interpreter


@pytest.mark.parametrize('name', ['plain', 'with spaces', 'with"quote', 'with$dollar', 'with`tick',
                                  'with\\backslash', 'with%f-percent', 'with\nnewline', "with'apostrophe", 'with(parentheses)', 'with=equals'])
def test_launcher_preserves_special_characters_in_executable_path(gio_python, tmp_path, name):
    program = tmp_path / name / 'fixture'
    program.parent.mkdir()
    record = tmp_path / 'received.json'
    program.write_text('#!/usr/bin/python3\nimport json, os, sys\n'
                       'target = os.environ["CNT_QA_RECORD"]\n'
                       'with open(target + ".tmp", "w") as f: json.dump(sys.argv, f)\n'
                       'os.replace(target + ".tmp", target)\n', encoding='utf-8')
    program.chmod(0o755)
    desktop = tmp_path / 'fixture.desktop'
    desktop.write_text(linux_desktop.desktop_entry_text(str(program)), encoding='utf-8')
    driver = '''
import json, pathlib, sys, time
from gi.repository import Gio
desktop, record = sys.argv[1:]
application = Gio.DesktopAppInfo.new_from_filename(desktop)
assert application is not None, 'GLib rejected the desktop entry'
context = Gio.AppLaunchContext()
context.setenv('CNT_QA_RECORD', record)
assert application.launch([], context)
deadline = time.monotonic() + 4
while not pathlib.Path(record).exists() and time.monotonic() < deadline:
    time.sleep(.02)
assert pathlib.Path(record).exists(), 'The desktop entry did not launch its executable'
'''
    launched = subprocess.run([gio_python, '-c', driver, str(desktop), str(record)], capture_output=True, text=True, timeout=8)
    assert launched.returncode == 0, launched.stderr
    assert json.loads(record.read_text()) == [str(program)]


def test_source_checkout_launcher_uses_python_without_executable_bit(gio_python, tmp_path):
    program = tmp_path / 'main.py'
    program.write_text('print("source launcher")\n')
    text = linux_desktop.desktop_entry_text(str(program))
    assert 'Exec=' + sys.executable + ' ' + str(program) in text
    desktop = tmp_path / 'source.desktop'
    desktop.write_text(text)
    probe = subprocess.run([gio_python, '-c',
        'from gi.repository import Gio; import sys; app = Gio.DesktopAppInfo.new_from_filename(sys.argv[1]); assert app.launch([], None)',
        str(desktop)], capture_output=True, text=True, timeout=8)
    assert probe.returncode == 0, probe.stderr
    assert 'source launcher' in probe.stdout
