import threading
import time
from types import SimpleNamespace
from unittest import mock
from pathlib import Path

import pytest
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtTest import QTest

import main
import image_input
from image_input import ImageImportController, ImageInputTextEdit
from test_desktop_ux import app, window


def photo():
    image = QtGui.QImage(200, 100, QtGui.QImage.Format_RGB32)
    image.fill(QtCore.Qt.white)
    return image


def finish(app, predicate):
    deadline = time.monotonic() + 3
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.005)
    assert predicate()


def test_clipboard_image_becomes_a_photo_request_and_text_stays_text(app):
    editor = ImageInputTextEdit()
    received = []
    editor.image_requested.connect(received.append)
    mime = QtCore.QMimeData()
    mime.setImageData(photo())
    editor.insertFromMimeData(mime)
    assert len(received) == 1 and received[0].size() == QtCore.QSize(200, 100)
    assert editor.toPlainText() == ''
    mime = QtCore.QMimeData()
    mime.setText('normal pasted text')
    editor.insertFromMimeData(mime)
    assert editor.toPlainText() == 'normal pasted text'
    editor.deleteLater()


def test_ctrl_v_pastes_image_without_touching_system_clipboard(app,isolated_clipboard):
    editor=ImageInputTextEdit()
    received=[]
    editor.image_requested.connect(received.append)
    mime=QtCore.QMimeData();mime.setImageData(photo())
    isolated_clipboard.setMimeData(mime)
    editor.show();editor.setFocus()
    QTest.keyClick(editor,QtCore.Qt.Key_V,QtCore.Qt.ControlModifier)
    assert len(received)==1 and received[0].size()==photo().size()
    assert isolated_clipboard.mimeData() is mime
    editor.close();editor.deleteLater()


@pytest.mark.parametrize('extension', sorted(main.SUPPORTED_EXTENSIONS | image_input.EXTENSIONS))
def test_ctrl_v_routes_each_supported_file_instead_of_pasting_its_url(app, isolated_clipboard, tmp_path, extension):
    editor = ImageInputTextEdit()
    images, documents = [], []
    editor.image_requested.connect(images.append)
    editor.file_requested.connect(documents.append)
    path = str(tmp_path/('copied file'+extension.upper()))
    mime = QtCore.QMimeData()
    mime.setUrls([QtCore.QUrl.fromLocalFile(path)])
    isolated_clipboard.setMimeData(mime)
    editor.show()
    editor.setFocus()
    QTest.keyClick(editor, QtCore.Qt.Key_V, QtCore.Qt.ControlModifier)
    expected = ([Path(path)], []) if extension in image_input.EXTENSIONS else ([], [Path(path)])
    assert ([Path(value) for value in images], [Path(value) for value in documents]) == expected
    assert editor.toPlainText() == '' and isolated_clipboard.mimeData() is mime
    editor.close()
    editor.deleteLater()


def test_paste_file_does_not_require_an_image_handler_and_read_only_editors_ignore_it(app, isolated_clipboard, tmp_path):
    editor = ImageInputTextEdit()
    received = []
    editor.file_requested.connect(received.append)
    path = str(tmp_path/'a.txt')
    mime = QtCore.QMimeData()
    mime.setUrls([QtCore.QUrl.fromLocalFile(path)])
    isolated_clipboard.setMimeData(mime)
    editor.setReadOnly(True)
    QTest.keyClick(editor, QtCore.Qt.Key_V, QtCore.Qt.ControlModifier)
    assert not received
    editor.setReadOnly(False)
    QTest.keyClick(editor, QtCore.Qt.Key_V, QtCore.Qt.ControlModifier)
    assert [Path(value) for value in received] == [Path(path)]
    editor.deleteLater()


def test_browse_routes_documents_and_images_and_keeps_cancel_available(window, tmp_path):
    for extension in ('.txt', '.pdf', '.docx', '.PNG'):
        path = str(tmp_path/('picked'+extension))
        with (mock.patch.object(main.QFileDialog, 'getOpenFileName', return_value=(path, '')) as choose,
              mock.patch.object(window, '_import_main_image') as image,
              mock.patch.object(window, 'open_document_translation') as document):
            window.main_image_button.click()
            filters = choose.call_args.args[-1].split(';;')
            assert '*.png' in filters[0] and '*.pdf' in filters[0] and '*.docx' in filters[0]
            assert ('*.png' in filters[1]) and ('*.docx' in filters[2])
            if extension == '.PNG':
                image.assert_called_once_with(path)
                document.assert_not_called()
            else:
                document.assert_called_once_with(path)
                image.assert_not_called()
    with mock.patch.object(main.QFileDialog, 'getOpenFileName', return_value=('', '')):
        window._choose_main_attachment()
    window._image_importer.busy = True
    with (mock.patch.object(window._image_importer, 'cancel') as cancel,
          mock.patch.object(main.QFileDialog, 'getOpenFileName') as choose):
        window._choose_main_attachment()
        cancel.assert_called_once_with()
        choose.assert_not_called()
    window._image_importer.busy = False


def test_result_window_browse_and_paste_files_use_the_document_workspace(window, app, tmp_path, isolated_clipboard):
    dialog = main.TranslationResultDialog(window, '', auto_copy=False, lang='ru')
    path = str(tmp_path/'book.pdf')
    mime = QtCore.QMimeData()
    mime.setUrls([QtCore.QUrl.fromLocalFile(path)])
    isolated_clipboard.setMimeData(mime)
    try:
        with mock.patch.object(window, 'open_document_translation') as document:
            QTest.keyClick(dialog.source_edit, QtCore.Qt.Key_V, QtCore.Qt.ControlModifier)
            document.assert_called_once_with(mime.urls()[0].toLocalFile())
        with (mock.patch.object(main.QFileDialog, 'getOpenFileName', return_value=(path, '')),
              mock.patch.object(window, 'open_document_translation') as document):
            dialog.image_button.click()
            document.assert_called_once_with(path)
        dialog.refresh_language('ar')
        dialog.refresh_theme('Светлая')
        assert dialog.image_button.text() == image_input.attachment_text('ar', 'browse')
    finally:
        dialog.reject()


def test_main_canvas_accepts_pasted_files_without_an_editor_focus(window, app, tmp_path, isolated_clipboard):
    mime = QtCore.QMimeData()
    mime.setUrls([QtCore.QUrl.fromLocalFile(str(tmp_path/'file.pdf'))])
    isolated_clipboard.setMimeData(mime)
    with mock.patch.object(window, 'open_document_translation') as opened:
        QTest.keyClick(window.ui_root, QtCore.Qt.Key_V, QtCore.Qt.ControlModifier)
        opened.assert_called_once_with(mime.urls()[0].toLocalFile())
        opened.reset_mock()
        window.show_interface_language_menu()
        QTest.keyClick(window.ui_root, QtCore.Qt.Key_V, QtCore.Qt.ControlModifier)
        opened.assert_not_called()
        window._close_interface_language_picker()
        window.show_settings()
        QTest.keyClick(window.ui_root, QtCore.Qt.Key_V, QtCore.Qt.ControlModifier)
        opened.assert_not_called()


def test_drag_hover_does_not_copy_full_resolution_pixels(app):
    editor=ImageInputTextEdit()
    mime=QtCore.QMimeData();mime.setImageData(photo())
    with mock.patch.object(image_input,'image_from_mime',side_effect=AssertionError('eager copy')):
        assert editor.canInsertFromMimeData(mime)
    editor.deleteLater()


def test_image_drop_and_file_clipboard_are_supported(app, tmp_path):
    editor = ImageInputTextEdit()
    received = []
    editor.image_requested.connect(received.append)
    path = tmp_path/'photo.png'
    assert photo().save(str(path))
    mime = QtCore.QMimeData()
    mime.setUrls([QtCore.QUrl.fromLocalFile(str(path))])
    assert Path(image_input.image_from_mime(mime)) == path
    event = QtGui.QDropEvent(QtCore.QPointF(5, 5), QtCore.Qt.CopyAction, mime,
                            QtCore.Qt.LeftButton, QtCore.Qt.NoModifier)
    editor.dropEvent(event)
    assert len(received) == 1 and Path(received[0]) == path and event.isAccepted()
    editor.deleteLater()


def test_document_drop_keeps_the_existing_document_translator(window,app,tmp_path):
    path=tmp_path/'document.txt';path.write_text('document contents')
    mime=QtCore.QMimeData();mime.setUrls([QtCore.QUrl.fromLocalFile(str(path))])
    received=[]
    # The actual main input must have a document handler, so it never pastes
    # a local file URL in place of opening the existing document translator.
    assert window.text_input.receivers(window.text_input.file_requested)==1
    editor=ImageInputTextEdit();editor.file_requested.connect(received.append)
    event=QtGui.QDropEvent(QtCore.QPointF(5,5),QtCore.Qt.CopyAction,mime,QtCore.Qt.LeftButton,QtCore.Qt.NoModifier)
    editor.dropEvent(event)
    assert len(received)==1 and Path(received[0])==path and event.isAccepted()
    assert editor.toPlainText()==''
    editor.deleteLater()


def test_loading_file_and_corrupt_input(app, tmp_path):
    path = tmp_path/'photo.png'
    photo().save(str(path))
    assert image_input.load_image(path).size() == photo().size()
    path.write_bytes(b'not an image')
    with pytest.raises(ValueError, match='invalid'):
        image_input.load_image(path)


def test_huge_file_is_rejected_before_decoding(app, tmp_path):
    with mock.patch.object(image_input.os.path, 'getsize', return_value=image_input.MAX_BYTES+1):
        with pytest.raises(ValueError, match='large'):
            image_input.load_image(tmp_path/'large.png')


def test_exif_orientation_is_applied(app, tmp_path):
    from PIL import Image
    picture = Image.new('RGB', (120, 60), 'white')
    exif = picture.getexif()
    exif[274] = 6
    path = tmp_path/'rotated.jpg'
    picture.save(path, exif=exif)
    assert image_input.load_image(path).size() == QtCore.QSize(60, 120)


@pytest.mark.parametrize('join,expected', [(False, 'first line\nsecond line'), (True, 'first line second line')])
def test_local_ocr_uses_selected_engine_language_and_paragraph_option(app, join, expected):
    rows = [(0, 0, 140, 20, 'first line'), (0, 25, 140, 20, 'second line')]
    class FakeWorker(QtCore.QObject):
        result_ready = QtCore.pyqtSignal(object)
        def run(self):
            self.result_ready.emit(rows)
    with mock.patch('ocr.create_position_ocr_worker', return_value=FakeWorker()) as factory:
        text, translated = image_input.recognize_image(photo(), {'ocr_engine':'Tesseract', 'ocr_join_paragraphs':join}, 'en', 'ar', lambda:False)
    assert factory.call_args.args[1:] == ('en', 'Tesseract')
    assert text == expected and translated is None


def test_windows_photo_with_auto_source_uses_installed_ocr_languages(app):
    worker=SimpleNamespace(engine='windows',bitmap=object())
    with (mock.patch('ocr.create_position_ocr_worker',return_value=worker),
          mock.patch('ocr._recognize_with_windows_auto',return_value='detected text') as recognize):
        assert image_input.recognize_image(photo(),{'ocr_engine':'Windows','ocr_join_paragraphs':True},'auto','ar',lambda:False)==('detected text',None)
    assert recognize.call_args.args==(worker.bitmap,)
    assert recognize.call_args.kwargs['join_paragraphs'] is True


def test_vision_one_request_keeps_translation_and_does_not_use_local_ocr(app):
    from api_providers import VISION_ENGINES
    engine = next(name for name, code in VISION_ENGINES.items() if code == 'openai')
    config = {'ocr_engine':engine, 'api_profiles':{'openai':{'direct':True}}}
    with (mock.patch('api_providers.recognize', return_value=SimpleNamespace(source='book text', translation='نص الكتاب')) as recognize,
          mock.patch('ocr.create_position_ocr_worker') as local):
        assert image_input.recognize_image(photo(), config, 'en', 'ar', lambda:False) == ('book text', 'نص الكتاب')
    assert recognize.call_args.args[0] == 'openai'
    assert recognize.call_args.args[2:5] == ('en', 'ar', config)
    local.assert_not_called()


@pytest.mark.parametrize('join', [False, True])
def test_vision_ocr_only_import_reflows_before_main_window_translation(app, join):
    import json
    import api_providers as api
    from test_ocr_paragraphs import REPORTED_LINES
    engine = next(name for name, code in api.VISION_ENGINES.items() if code == 'openai')
    source = '\n'.join(REPORTED_LINES) + '\n\nSecond paragraph.'
    config = {'ocr_engine': engine, 'ocr_join_paragraphs': join,
              'api_providers': {'openai': {'url': api.BY_KEY['openai'].url,
                  'model': 'test-model', 'vision': True, 'direct': False}}}
    with (mock.patch.object(api, 'credential', return_value='test-secret'),
          mock.patch.object(api, '_text_response', return_value=json.dumps({
              'source': source, 'translation': None})),
          mock.patch('ocr.create_position_ocr_worker') as local):
        text, translated = image_input.recognize_image(photo(), config, 'en', 'ar', lambda: False)
    expected = ' '.join(REPORTED_LINES) + '\n\nSecond paragraph.' if join else source
    assert text == expected and translated is None
    local.assert_not_called()


def test_vision_errors_use_localized_safe_feedback(app):
    from api_providers import VISION_ENGINES,ProviderError
    engine=next(name for name,code in VISION_ENGINES.items() if code=='openai')
    with mock.patch('api_providers.recognize',side_effect=ProviderError('API key rejected: private-test-value')):
        with pytest.raises(RuntimeError) as error:
            image_input.recognize_image(photo(),{'ocr_engine':engine,'interface_language':'ar'},'en','ar',lambda:False)
    assert 'private-test-value' not in str(error.value)
    assert 'API' in str(error.value) and 'رُفض' in str(error.value)


def test_image_work_runs_off_gui_thread_and_returns_on_gui_thread(app):
    controller = ImageImportController(app)
    received, threads = [], []
    def recognize(*args):
        threads.append(threading.current_thread())
        return 'recognized', None
    controller.ready.connect(lambda *value: received.append((value, threading.current_thread())))
    with mock.patch.object(image_input, 'recognize_image', side_effect=recognize):
        assert controller.start(photo(), {}, 'en', 'ar')
        finish(app, lambda:bool(received))
    assert threads[0] != threading.current_thread()
    assert received[0] == (('recognized', None), threading.current_thread())
    assert not controller.busy
    controller.deleteLater()


def test_cancelled_ocr_cannot_overwrite_a_new_draft(app):
    controller = ImageImportController(app)
    started, release, stopped = threading.Event(), threading.Event(), threading.Event()
    received = []
    controller.ready.connect(lambda *value:received.append(value))
    def recognize(*args):
        started.set()
        release.wait(2)
        stopped.set()
        return 'stale text', None
    with mock.patch.object(image_input, 'recognize_image', side_effect=recognize):
        assert controller.start(photo(), {}, 'en', 'ar')
        assert started.wait(1)
        assert not controller.start(photo(), {}, 'en', 'ar')
        controller.cancel()
        release.set()
        assert stopped.wait(1)
        app.processEvents()
    assert not received and not controller.busy
    controller.deleteLater()


@pytest.mark.parametrize('result,error', [(('',None),'empty'), (ValueError('large'),'large'), (ValueError('invalid'),'invalid')])
def test_empty_or_invalid_image_has_an_actionable_error(app,result,error):
    controller = ImageImportController(app)
    received = []
    controller.failed.connect(received.append)
    options = {'side_effect':result} if isinstance(result,Exception) else {'return_value':result}
    with mock.patch.object(image_input,'recognize_image',**options):
        controller.start(photo(),{},'en','ar')
        finish(app,lambda:bool(received))
    assert received == [error] and not controller.busy
    controller.deleteLater()


def test_main_photo_fills_input_and_uses_existing_translation_flow(window,app):
    window.source_lang.setCurrentText(main.language_display_name('en',window.current_interface_language))
    window.target_lang.setCurrentText(main.language_display_name('ar',window.current_interface_language))
    with (mock.patch.object(image_input,'recognize_image',return_value=('the book',None)),
          mock.patch.object(window,'translate_input_text') as translate):
        window._import_main_image(photo())
        finish(app,lambda:translate.called)
    assert window.text_input.toPlainText() == 'the book'
    assert not window.text_input.isReadOnly()


def test_result_photo_paste_uses_current_pair_without_an_extra_window(window,app):
    dialog = main.TranslationResultDialog(window,'',auto_copy=False,lang='ru',source_lang='en',target_lang='ar')
    with (mock.patch.object(image_input,'recognize_image',return_value=('book','كتاب')),
          mock.patch('translater.translate_text') as translator):
        mime=QtCore.QMimeData();mime.setImageData(photo())
        dialog.source_edit.insertFromMimeData(mime)
        finish(app,lambda:dialog.text_edit.toPlainText()=='كتاب')
    assert dialog.source_edit.toPlainText()=='book'
    translator.assert_not_called()
    assert QtGui.QKeySequence(QtGui.QKeySequence.Paste).toString(QtGui.QKeySequence.NativeText) in image_input.image_text('ar','hint')
    dialog.reject()


def test_dropdown_arrow_points_the_same_way_in_rtl_and_ltr(app):
    from button_styles import paint_down_arrow
    pictures=[]
    for direction in (QtCore.Qt.LeftToRight,QtCore.Qt.RightToLeft):
        picture=QtGui.QImage(32,32,QtGui.QImage.Format_ARGB32)
        picture.fill(QtCore.Qt.transparent)
        painter=QtGui.QPainter(picture)
        painter.setLayoutDirection(direction)
        paint_down_arrow(painter,QtCore.QRectF(0,0,32,32),app.font(),QtGui.QColor('white'))
        painter.end()
        pictures.append(picture)
    assert pictures[0]==pictures[1]


def test_numeric_arrows_are_not_mirrored_as_arabic_punctuation(app):
    from ui_scaling import ScaleArrowButton
    pictures=[]
    button=ScaleArrowButton()
    button.setText('›');button.resize(30,30)
    button.setFocusPolicy(QtCore.Qt.NoFocus)
    button.setStyleSheet('QToolButton {background:#17181d; color:white; border:0; font-size:15px;}')
    for direction in (QtCore.Qt.LeftToRight,QtCore.Qt.RightToLeft):
        button.setLayoutDirection(direction)
        pictures.append(button.grab().toImage())
    assert pictures[0]==pictures[1]
    button.deleteLater()


def test_arabic_interface_and_result_status_switch_back_cleanly(window,app):
    from number_controls import StepperFrame
    window.set_interface_language('ar')
    assert window.layoutDirection()==app.layoutDirection()==QtCore.Qt.RightToLeft
    assert main.INTERFACE_LANGUAGE_BY_CODE['ar']['name']=='العربية'
    window.show_settings()
    assert window.settings_window.layoutDirection()==QtCore.Qt.RightToLeft
    stepper=window.settings_window.ui_scale_field
    assert isinstance(stepper,StepperFrame) and stepper.layoutDirection()==QtCore.Qt.LeftToRight
    dialog=main.TranslationResultDialog(window,'النتيجة',auto_copy=False,lang='en',source_text='source',source_lang='en',target_lang='ar')
    dialog.source_edit.setPlainText('edited source')
    assert dialog.status_label.text()=='Source text edited — click Translate'
    dialog.refresh_language('ru')
    assert dialog.status_label.text()=='Исходный текст изменён — нажмите «Перевести»'
    dialog.refresh_language('ar')
    assert dialog.layoutDirection()==QtCore.Qt.RightToLeft
    assert 'Translate' not in dialog.status_label.text()
    assert dialog.source_edit.toPlainText()=='edited source'
    window.set_interface_language('en')
    assert app.layoutDirection()==window.layoutDirection()==QtCore.Qt.LeftToRight
    dialog.reject()
