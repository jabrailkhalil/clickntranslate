"""Native paired-output capture test on a generated two-color fixture only."""

from contextlib import ExitStack
import json
import os
from pathlib import Path
import sys
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.argv[0] = str(ROOT/'main.py')
if sys.platform != 'win32' or os.environ.get('QT_QPA_PLATFORM') == 'offscreen':
    raise SystemExit('Native Windows Qt is required')

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtTest import QSignalSpy, QTest
import game_mode
import dynamic_workspace as workspace
from dynamic_templates import TemplateStore, decode_rect
import ocr


def run():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    screen = app.primaryScreen()
    available = screen.availableGeometry()
    folder = ROOT/'.tmp/dynamic-output-20260912/native'
    folder.mkdir(parents=True, exist_ok=True)
    fixture = QtWidgets.QWidget(None, QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)
    fixture.setGeometry(available.x()+30, available.y()+150, 650, 320)
    fixture.setStyleSheet('background:#263555')
    label = QtWidgets.QLabel('SOURCE TEXT', fixture)
    label.setAlignment(QtCore.Qt.AlignCenter)
    label.setStyleSheet('background:#14644d; color:white; font:18px "Arial"')
    label.setGeometry(20, 50, 240, 90)
    fixture.show()
    fixture.raise_()
    QTest.qWait(160)
    origin = fixture.geometry().topLeft()
    source = label.geometry().translated(origin)
    output = QtCore.QRect(320, 70, 280, 110).translated(origin)
    def capture(rect):
        local = rect.translated(-screen.geometry().topLeft())
        return ocr.grab_screen_pixmap(screen, *local.getRect()).toImage()
    source_image, output_image = capture(source), capture(output)
    config = {'theme':'Темная', 'interface_language':'ru', 'ocr_engine':'Windows', 'translator_engine':'Google',
              'history':False, 'game_pause_when_inactive':False, 'game_show_original_text':True}
    try:
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(ocr, 'get_cached_ocr_config', return_value=config))
            stack.enter_context(mock.patch.object(game_mode.GameTranslationOverlay, '_start_scanning'))
            stack.enter_context(mock.patch.object(game_mode.GameTranslationOverlay, '_start_ocr'))
            store = TemplateStore(folder/'templates.json')
            stack.enter_context(mock.patch.object(workspace, 'TemplateStore', return_value=store))
            worker = ocr.create_position_ocr_worker(source_image, 'en', 'Windows')
            assert worker is not None
            result = QSignalSpy(worker.result_ready)
            worker.start()
            if not result:
                assert result.wait(10000)
            assert worker.wait(3000)
            assert 'SOURCE TEXT' in ' '.join(item[4] for item in result[0][0])
            worker.deleteLater()
            overlay = workspace.PairedTranslationOverlay(source, 'en', 'ru', output_region=output, style={'opacity':0})
            try:
                assert overlay._capture_excluded and overlay.controls._capture_excluded
                overlay._process_frame(source_image)
                overlay._apply_translation(0, 'SOURCE TEXT', 'Только перевод в выбранном месте', '')
                QTest.qWait(120)
                assert overlay.geometry() == output and overlay.region == source
                assert overlay._output_frame == output_image, 'Output background must come from output, not source'
                assert overlay.original_label.isHidden() and overlay.status_label.isHidden()
                with mock.patch.object(overlay, 'setWindowOpacity', side_effect=AssertionError('Overlay blink')):
                    for _ in range(3):
                        assert overlay._grab_region().toImage() == source_image
                        assert capture(output) == output_image, 'Visible translated text entered capture'
                overlay.grab().save(str(folder/'output.png'))
                overlay.controls.gear.click()
                overlay.controls.font_size.setValue(26)
                overlay.controls.opacity.setValue(65)
                overlay.controls.locked.setChecked(False)
                QTest.qWait(80)
                overlay.controls.grab().save(str(folder/'settings.png'))
                assert overlay.controls._capture_excluded
                assert overlay._grab_region().toImage() == source_image
                for button, delta in ((overlay.controls.move_button, QtCore.QPoint(10, 5)),
                                      (overlay.controls.resize_button, QtCore.QPoint(20, 10))):
                    destination = button.mapToGlobal(button.rect().center())+delta
                    QTest.mousePress(button, QtCore.Qt.LeftButton, pos=button.rect().center())
                    QTest.mouseRelease(button, QtCore.Qt.LeftButton, pos=button.mapFromGlobal(destination))
                output.translate(10, 5)
                output.setSize(output.size()+QtCore.QSize(20, 10))
                assert overlay.output_rect == output and overlay.region == source
                overlay.controls.template_name.setText('Native fixture')
                overlay.controls.save_button.click()
                saved = TemplateStore(store.path).load()[0]
                assert decode_rect(saved['pairs'][0]['source'], app.screens()) == source
                assert decode_rect(saved['pairs'][0]['output'], app.screens()) == output
                assert saved['pairs'][0]['style'] == {'font_size':26, 'opacity':65, 'locked':False}
                report = {'passed':True, 'density':source_image.width()/source.width(), 'source':source.getRect(),
                          'output':output.getRect(), 'frames':3, 'template_roundtrip':True, 'native_ocr':True}
                (folder/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
                print(json.dumps(report))
            finally:
                overlay.close()
                app.processEvents()
    finally:
        fixture.close()
        app.processEvents()


if __name__ == '__main__':
    run()
