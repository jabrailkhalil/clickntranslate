"""Verify real Screenshot portal delivery and clipboard on a Wayland desktop.

The companion qa_linux_wayland.sh supplies a private headless Sway desktop with
known backgrounds. Never accept a successful fallback helper as a portal pass.
This probe writes a synthetic string into the test desktop's clipboard.
"""

import argparse
import json
from pathlib import Path
import subprocess
import sys
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtTest import QTest

import linux_capture
import platform_support


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--background', action='append', default=[], metavar='SCREEN=#RRGGBB')
    options = parser.parse_args()
    options.output.mkdir(parents=True, exist_ok=True)
    expected = dict(item.split('=', 1) for item in options.background)
    app = QtWidgets.QApplication([])
    if not platform_support.IS_LINUX or not app.platformName().startswith('wayland'):
        raise SystemExit('Run on Linux with QT_QPA_PLATFORM=wayland and a Wayland compositor.')
    QtCore.QCoreApplication.setApplicationName('ClicknTranslateWaylandQA')
    app.setDesktopFileName(platform_support.APP_ID)
    QTest.qWait(1500)
    report = {'platform': app.platformName(), 'screens': [], 'failures': []}

    def check(name, condition):
        report[name] = bool(condition)
        if not condition:
            report['failures'].append(name)

    try:
        check('portal_available', linux_capture.portal_available())
        portal_path = Path(linux_capture.capture_with_portal())
        try:
            check('direct_portal_image', portal_path.is_file() and portal_path.stat().st_size > 0)
        finally:
            portal_path.unlink(missing_ok=True)
        for index, screen in enumerate(app.screens()):
            with mock.patch.object(linux_capture, 'capture_with_helper',
                                   side_effect=AssertionError('Portal failed; helper fallback is forbidden in this probe')):
                pixmap = linux_capture.grab_screen(screen)
            bounds = screen.geometry()
            image = pixmap.toImage()
            item = {'name': screen.name(), 'bounds': bounds.getRect(),
                    'qt_dpr': screen.devicePixelRatio(),
                    'image_size': [pixmap.width(), pixmap.height()]}
            report['screens'].append(item)
            check(f'screen_{index}_image', not pixmap.isNull())
            ratio = pixmap.width() / max(1, bounds.width())
            item['image_dpr'] = pixmap.devicePixelRatioF()
            check(f'screen_{index}_logical_coordinates', abs(pixmap.devicePixelRatioF() - ratio) < .01)
            check(f'screen_{index}_proportions', abs(pixmap.height() - bounds.height() * ratio) <= 1)
            if screen.name() in expected:
                colors = [image.pixelColor(int(image.width() * x), int(image.height() * y)).name()
                          for x in (0.1, 0.5, 0.9) for y in (0.1, 0.5, 0.9)]
                item['sampled_colors'] = colors
                check(f'screen_{index}_background', all(color == expected[screen.name()] for color in colors))
            pixmap.save(str(options.output / f'screen-{index}.png'))
        if expected:
            check('expected_screens', set(expected) == {screen.name() for screen in app.screens()})
        sample = 'Linux Wayland QA: Привет 世界'
        check('clipboard_write', platform_support.copy_text(sample))
        pasted = subprocess.check_output(['wl-paste', '--no-newline'], timeout=5).decode('utf-8')
        check('clipboard_roundtrip', pasted == sample)
    except Exception as error:
        report['failures'].append(f'{type(error).__name__}: {error}')
    report['passed'] = not report['failures']
    (options.output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report), flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(run())
