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

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtTest import QTest

import linux_capture
import platform_support


WALLPAPER_SIZE = (256, 160)
MARKER_RECTS = ((41, 94, 22, 14), (180, 35, 16, 23), (96, 59, 17, 13))
WALLPAPERS = {
    'HEADLESS-1': ('#14644d', ('#ec742c', '#f9c741', '#7d97e8')),
    'HEADLESS-2': ('#263555', ('#f9c741', '#7d97e8', '#ec742c')),
}


def write_wallpapers(folder):
    for name, (background, colors) in WALLPAPERS.items():
        image = QtGui.QImage(*WALLPAPER_SIZE, QtGui.QImage.Format_RGB32)
        image.fill(QtGui.QColor(background))
        painter = QtGui.QPainter(image)
        for rect, color in zip(MARKER_RECTS, colors):
            painter.fillRect(QtCore.QRect(*rect), QtGui.QColor(color))
        painter.end()
        if not image.save(str(folder / (name + '.png'))):
            raise OSError(f'Could not generate wallpaper for {name}')


def check_marker_regions(screen, full, check, item):
    import ocr

    background, colors = WALLPAPERS[screen.name()]
    scale_x = screen.geometry().width() / WALLPAPER_SIZE[0]
    scale_y = screen.geometry().height() / WALLPAPER_SIZE[1]
    item['markers'] = []
    for index, ((x, y, width, height), color) in enumerate(zip(MARKER_RECTS, colors)):
        marker = QtCore.QRect(round(x * scale_x), round(y * scale_y),
                              round(width * scale_x), round(height * scale_y))
        area = marker.adjusted(-5, -5, 5, 5)
        # Exercise both paths used by the selection overlay. Its live path asks
        # the portal for a fresh frame, while its frozen path reuses the old one.
        with mock.patch.object(linux_capture, 'capture_with_helper', side_effect=AssertionError('Expected a portal grab')):
            live = ocr.grab_screen_pixmap(screen, *area.getRect())
        frozen = ocr.crop_frozen_pixmap(full, area)
        live_image, frozen_image = live.toImage(), frozen.toImage()
        key = f'{screen.name()}_marker_{index}'
        ratio = full.devicePixelRatioF()
        check(key + '_size', live_image.size() == QtCore.QSize(round(area.width() * ratio), round(area.height() * ratio)))
        check(key + '_live_and_frozen', live_image == frozen_image)
        if live_image.isNull():
            continue
        # Sample immediately inside and outside all four edges. Testing one
        # center point would accept a shifted, oversized or mirrored rectangle.
        center_x, center_y = area.width() // 2, area.height() // 2
        samples = [(2, center_y, background), (8, center_y, color),
                   (area.width() - 9, center_y, color), (area.width() - 3, center_y, background),
                   (center_x, 2, background), (center_x, 8, color),
                   (center_x, area.height() - 9, color), (center_x, area.height() - 3, background)]
        observed = [live_image.pixelColor(round(px * ratio), round(py * ratio)).name() for px, py, _ in samples]
        check(key + '_edges', observed == [expected for _, _, expected in samples])
        item['markers'].append({'area': area.getRect(), 'color': color, 'edge_samples': observed})


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--background', action='append', default=[], metavar='SCREEN=#RRGGBB')
    parser.add_argument('--write-wallpapers', action='store_true', help='Create the synthetic Sway fixtures and exit')
    parser.add_argument('--check-markers', action='store_true', help='Check OCR selection against the synthetic fixtures')
    options = parser.parse_args()
    options.output.mkdir(parents=True, exist_ok=True)
    if options.write_wallpapers:
        write_wallpapers(options.output)
        return 0
    expected = dict(item.split('=', 1) for item in options.background)
    if options.check_markers:
        expected.update({name: colors[0] for name, colors in WALLPAPERS.items()})
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
            if options.check_markers and screen.name() in WALLPAPERS:
                check_marker_regions(screen, pixmap, check, item)
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
