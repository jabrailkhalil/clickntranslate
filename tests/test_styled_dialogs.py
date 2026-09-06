import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5 import QtCore, QtWidgets

import main
import ocr
import settings_window
from styled_dialogs import StyledMessageBox, install_qt_exception_guard

_APP = None


def _app():
    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return _APP


def test_message_box_uses_custom_chrome_and_status_icon():
    app = _app()
    box = StyledMessageBox()
    box.setWindowTitle("EasyOCR not found")
    box.setText("Install the neural OCR engine into the app folder?")
    box.setIcon(StyledMessageBox.Question)
    box.addButton("Install", StyledMessageBox.AcceptRole)
    box.addButton("Cancel", StyledMessageBox.RejectRole)
    assert box.windowFlags() & QtCore.Qt.FramelessWindowHint
    assert box.title_bar.title_label.text() == "EasyOCR not found"
    assert box.title_bar.height() == 42
    assert box.minimumWidth() >= 500
    assert not box._status_pixmap().isNull()
    assert "styledMessageTitleBar" in box.styleSheet()


def test_external_message_style_cannot_remove_shared_chrome():
    _app()
    box = StyledMessageBox()
    box.setStyleSheet("QMessageBox { background-color: #ffffff; }")

    assert box._dark is False
    assert "#efecf2" in box.styleSheet()
    assert "QFrame#styledMessageTitleBar" in box.styleSheet()


def test_theme_detection_accepts_settings_parent_attribute():
    _app()
    owner = QtWidgets.QWidget()
    owner.current_theme = "Light"
    settings_like_child = QtWidgets.QWidget(owner)
    settings_like_child.parent = owner

    box = StyledMessageBox(settings_like_child)

    assert box._dark is False


def test_message_box_centers_on_embedded_settings_in_global_coordinates():
    app = _app()
    main_window = QtWidgets.QWidget()
    # Center relative to logical screen coordinates, including 150% system DPI,
    # so edge clamping does not mask the coordinate-space check.
    main_window.setGeometry(120, 80, 700, 400)
    main_window.move(app.primaryScreen().availableGeometry().center() - main_window.rect().center())
    embedded_settings = QtWidgets.QWidget(main_window)
    embedded_settings.setGeometry(0, 40, 700, 350)
    main_window.show()
    embedded_settings.show()
    app.processEvents()

    box = StyledMessageBox(embedded_settings)
    box.resize(500, 210)
    box._center_on_owner()

    expected = embedded_settings.mapToGlobal(embedded_settings.rect().center())
    actual = box.frameGeometry().center()
    assert abs(actual.x() - expected.x()) <= 1
    assert abs(actual.y() - expected.y()) <= 1


def test_every_process_uses_the_shared_message_box():
    assert settings_window.QMessageBox is StyledMessageBox
    assert main.QMessageBox is StyledMessageBox
    assert ocr.QMessageBox is StyledMessageBox


def test_qt_exception_guard_is_idempotent():
    previous = __import__("sys").excepthook
    try:
        install_qt_exception_guard()
        installed = __import__("sys").excepthook
        install_qt_exception_guard()
        assert __import__("sys").excepthook is installed
        assert installed._clickntranslate_qt_guard is True
    finally:
        __import__("sys").excepthook = previous


def test_unchanged_stylesheet_does_not_repolish_child_widgets():
    from styled_dialogs import set_widget_stylesheet

    app = _app()

    class StyleEvents(QtCore.QObject):
        def __init__(self):
            super().__init__()
            self.count = 0

        def eventFilter(self, watched, event):
            if event.type() == QtCore.QEvent.StyleChange:
                self.count += 1
            return False

    owner = QtWidgets.QWidget()
    button = QtWidgets.QPushButton("Action", owner)
    events = StyleEvents()
    button.installEventFilter(events)
    try:
        dark = "QPushButton { color: #ffffff; background: #302938; }"
        light = "QPushButton { color: #302938; background: #ffffff; }"
        set_widget_stylesheet(owner, dark)
        app.processEvents()
        initial = events.count
        assert initial > 0
        for _ in range(5):
            set_widget_stylesheet(owner, dark)
        app.processEvents()
        assert events.count == initial
        set_widget_stylesheet(owner, light)
        app.processEvents()
        assert events.count > initial
    finally:
        owner.close()
        owner.deleteLater()


def test_document_window_uses_the_shared_frameless_chrome():
    app = _app()
    owner = QtWidgets.QWidget()
    owner.current_interface_language = "en"
    owner.current_theme = "Темная"
    owner.resize(700, 500)
    owner.show()

    dialog = main.DocumentTranslationDialog(owner)
    dialog.show()
    app.processEvents()

    assert dialog.windowFlags() & QtCore.Qt.FramelessWindowHint
    assert dialog.testAttribute(QtCore.Qt.WA_TranslucentBackground)
    assert dialog.window_frame.objectName() == "docWindowFrame"
    assert dialog.doc_minimize_button.objectName() == "docWindowButton"
    assert dialog.doc_close_button.objectName() == "docWindowClose"
    assert "QFrame#docWindowFrame" in dialog.styleSheet()
    # Target/provider already have dedicated controls below. A second metadata
    # sentence in the title bar was clipped and repeated both values.
    assert not hasattr(dialog, "metadata_label")
    assert not hasattr(dialog, "header_subtitle")

    dialog.close()
    owner.close()


def test_document_stop_keeps_finished_text_and_does_not_report_completion(monkeypatch):
    from types import SimpleNamespace
    import document_translation

    app = _app()
    owner = QtWidgets.QWidget()
    owner.current_interface_language = 'ru'
    owner.current_theme = 'Темная'
    dialog = main.DocumentTranslationDialog(owner)
    workers = []
    monkeypatch.setattr(main.threading, 'Thread', lambda target, **kwargs: SimpleNamespace(start=lambda: workers.append(target)))
    saved = []
    monkeypatch.setattr(main, 'save_translation_history', lambda *args: saved.append(args))
    received = {}

    def translate(text, source, target, **kwargs):
        received.update(kwargs)
        assert kwargs['cancel_event'].is_set()
        return 'Готовая часть. ', [document_translation.TranslationChunkResult(0, 'Finished part. ', 'Готовая часть. ')]

    monkeypatch.setattr(main, 'translate_document_text', translate)
    try:
        dialog.show()
        dialog._start_translation('Finished part. More text.')
        assert dialog.translation_running
        assert dialog.translate_file_button.isEnabled()
        assert dialog.translate_file_button.text() == 'Остановить'
        dialog.translate_file_button.click()
        assert not dialog.translate_file_button.isEnabled()
        assert dialog._translation_cancel_event.is_set()
        dialog.refresh_language('en')
        assert dialog.translate_file_button.text() == 'Stop'
        assert not dialog.translate_file_button.isEnabled()
        assert dialog.current_status == main.doc_text('en', 'canceling_translation')
        dialog.refresh_language('ru')
        workers[0]()
        app.processEvents()
        assert not dialog.translation_running
        assert dialog.translated_view.toPlainText() == 'Готовая часть. '
        assert dialog.current_status == 'Перевод остановлен'
        assert dialog.progress_bar.value() < 100
        assert dialog.save_button.isEnabled()
        assert dialog.translate_file_button.text() == main.doc_text('ru', 'translate_file')
        assert not saved
    finally:
        dialog.close()
        dialog.deleteLater()
        owner.close()


def test_closing_document_requests_cancellation(monkeypatch):
    import threading
    _app()
    owner = QtWidgets.QWidget()
    dialog = main.DocumentTranslationDialog(owner)
    try:
        dialog.translation_running = True
        dialog._translation_cancel_event = threading.Event()
        dialog.reject()
        assert dialog._translation_cancel_event.is_set()
    finally:
        dialog.translation_running = False
        dialog.close()
        dialog.deleteLater()
        owner.close()


def test_document_pane_borders_survive_theme_and_language_switches():
    app = _app()
    owner = QtWidgets.QWidget()
    owner.current_interface_language = "en"
    owner.current_theme = "Темная"

    dialog = main.DocumentTranslationDialog(owner)
    dialog.show()
    app.processEvents()

    for theme, language in (
        ("Темная", "ru"),
        ("Светлая", "de"),
        ("Темная", "fr"),
    ):
        dialog.refresh_theme(theme)
        dialog.refresh_language(language)
        app.processEvents()

        # Check the rendered, continuous border on both panels, including the
        # seam where independently rounded editor/header frames used to meet.
        for editor in (dialog.original_view, dialog.translated_view):
            pane = editor.parentWidget()
            image = pane.grab().toImage()
            dpr = image.devicePixelRatio()
            edge = [image.pixelColor(0, round(y * dpr)) for y in
                    (20, editor.y() - 1, editor.y(), pane.height() // 2)]
            assert all(color == edge[0] for color in edge)
            assert edge[0] != image.pixelColor(round(12 * dpr), round(pane.height() / 2 * dpr))
        left, right = dialog.document_splitter.widget(0), dialog.document_splitter.widget(1)
        assert right.x() - (left.x() + left.width()) >= 10

        margins = dialog.window_frame.layout().contentsMargins()
        assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (1, 1, 1, 1)

    dialog.close()
    owner.close()


def test_tooltips_render_in_the_current_theme_across_widgets_and_theme_switches():
    from PyQt5 import QtGui, QtTest
    from styled_dialogs import install_tooltip_style, _uses_dark_theme

    app = _app()
    old_style, old_theme = app.styleSheet(), app.property('ui_theme')
    old_palette = QtWidgets.QToolTip.palette()
    owner = QtWidgets.QWidget()
    layout = QtWidgets.QHBoxLayout(owner)
    buttons = [QtWidgets.QPushButton('First'), QtWidgets.QPushButton('Second')]
    for button in buttons:
        button.setStyleSheet('QPushButton { border: none; padding: 4px; }')
        layout.addWidget(button)
    owner.show()
    try:
        for theme in ('Темная', 'Светлая', 'Темная', 'Светлая'):
            app.setProperty('ui_theme', theme)
            install_tooltip_style(app)
            dark = theme == 'Темная'
            assert _uses_dark_theme() == dark
            for index, button in enumerate(buttons):
                app.processEvents()
                QtWidgets.QToolTip.showText(button.mapToGlobal(button.rect().center()),
                                          f'{theme}: Tooltip {index}', button)
                QtTest.QTest.qWait(30)
                tips = [w for w in app.topLevelWidgets()
                        if w.metaObject().className() == 'QTipLabel' and w.isVisible()]
                assert tips, (theme, index)
                tip = tips[0]
                image = tip.grab().toImage()
                lightness = image.pixelColor(image.width() // 2, round(4 * image.devicePixelRatio())).lightness()
                assert (lightness < 90 if dark else lightness > 210), (theme, index, lightness, tip.styleSheet())
                ink = QtWidgets.QToolTip.palette().color(QtGui.QPalette.ToolTipText).lightness()
                assert ink > 200 if dark else ink < 90
    finally:
        QtWidgets.QToolTip.hideText()
        QtTest.QTest.qWait(300)
        owner.close()
        app.setProperty('ui_theme', old_theme)
        app.setStyleSheet(old_style)
        QtWidgets.QToolTip.setPalette(old_palette)


def test_document_window_uses_saved_target_when_opened_from_settings(monkeypatch):
    app = _app()
    owner = QtWidgets.QWidget()
    owner.current_interface_language = "en"
    owner.current_theme = "РўРµРјРЅР°СЏ"
    monkeypatch.setattr(
        main,
        "get_cached_config",
        lambda: {"main_translation_target_language": "ru", "translator_engine": "Google"},
    )

    dialog = main.DocumentTranslationDialog(owner)
    app.processEvents()

    assert dialog.target_combo.currentText() == "Russian"

    dialog.close()
    owner.close()


def test_document_provider_list_groups_online_and_only_installed_offline(monkeypatch):
    app = _app()
    owner = QtWidgets.QWidget()
    owner.current_interface_language = "en"
    owner.current_theme = "Темная"
    monkeypatch.setattr(main.translater, "argos_installed_translation_pairs_fast", lambda: set())
    monkeypatch.setattr(main.translater, "hymt_installed", lambda: False)

    dialog = main.DocumentTranslationDialog(owner)
    app.processEvents()

    assert dialog.provider_combo.itemText(0).strip() == "Online"
    assert not dialog.provider_combo.model().item(0).isEnabled()
    assert dialog.provider_combo.findData("google") > 0
    assert dialog.provider_combo.findData("argos") == -1
    assert dialog.provider_combo.findData("hymt") == -1

    monkeypatch.setattr(
        main.translater,
        "argos_installed_translation_pairs_fast",
        lambda: {("en", "ru")},
    )
    dialog._populate_provider_combo("argos")
    offline_header = dialog.provider_combo.findText("  Offline")
    assert offline_header > 0
    assert not dialog.provider_combo.model().item(offline_header).isEnabled()
    assert dialog.provider_combo.currentData() == "argos"
    assert dialog.provider_combo.findData("hymt") == -1

    dialog.close()
    owner.close()


def test_document_source_language_is_explicit_for_every_provider(monkeypatch):
    app = _app()
    owner = QtWidgets.QWidget()
    owner.current_interface_language = "en"
    owner.current_theme = "Темная"
    monkeypatch.setattr(
        main.translater,
        "argos_installed_translation_pairs_fast",
        lambda: {("en", "ru")},
    )
    monkeypatch.setattr(main.translater, "hymt_installed", lambda: True)

    dialog = main.DocumentTranslationDialog(owner)
    app.processEvents()

    for engine in ("google", "mymemory", "lingva", "libretranslate", "hymt"):
        dialog._populate_provider_combo(engine)
        dialog._refresh_document_provider_languages()
        assert dialog.provider_combo.currentData() == engine
        assert dialog.source_combo.findData("auto") == -1, engine
        assert dialog.source_combo.currentData() in {
            language.code for language in main.APP_LANGUAGES
        }, engine

    dialog._populate_provider_combo("argos")
    dialog._refresh_document_provider_languages()
    assert dialog.provider_combo.currentData() == "argos"
    assert dialog.source_combo.findData("auto") == -1

    dialog.close()
    owner.close()


def test_document_language_arrow_swaps_source_and_target(monkeypatch):
    app = _app()
    owner = QtWidgets.QWidget()
    owner.current_interface_language = "en"
    owner.current_theme = "Темная"
    monkeypatch.setattr(
        main,
        "get_cached_config",
        lambda: {
            "main_translation_source_language": "en",
            "main_translation_target_language": "ru",
            "translator_engine": "Google",
        },
    )

    dialog = main.DocumentTranslationDialog(owner)
    app.processEvents()
    dialog.source_combo.setCurrentIndex(dialog.source_combo.findData("en"))
    dialog.target_combo.setCurrentIndex(dialog.target_combo.findData("ru"))

    dialog.language_arrow.click()

    assert dialog.source_combo.currentData() == "ru"
    assert dialog.target_combo.currentData() == "en"
    dialog.close()
    owner.close()


def test_faq_uses_custom_chrome_and_exposes_project_links():
    app = _app()

    class HelpOwner(QtWidgets.QWidget):
        current_interface_language = "en"
        current_theme = "Темная"

        def _complete_guide_step(self, _step):
            pass

        def _close_help_and_start_guide(self, dialog):
            dialog.accept()

    owner = HelpOwner()
    observed = {}

    def inspect_and_close():
        dialog = next(
            widget for widget in app.topLevelWidgets()
            if widget.objectName() == "helpDialogRoot"
        )
        observed["frameless"] = bool(dialog.windowFlags() & QtCore.Qt.FramelessWindowHint)
        help_text = dialog.findChild(QtWidgets.QTextEdit)
        observed["github_at_end"] = help_text.toHtml().rfind("github.com/jabrailkhalil/clickntranslate") > help_text.toHtml().rfind("section-title")
        observed["external_links"] = help_text.openExternalLinks()
        observed["telegram"] = dialog.findChild(QtWidgets.QPushButton, "helpTelegramButton") is not None
        observed["bug_report"] = dialog.findChild(QtWidgets.QPushButton, "helpBugReportButton") is not None
        guide = dialog.findChild(QtWidgets.QPushButton, "helpGuideButton")
        observed["guide_fits"] = (
            guide is not None
            and guide.width() >= guide.sizeHint().width()
        )
        observed["frame"] = dialog.findChild(QtWidgets.QFrame, "helpDialogFrame") is not None
        version = dialog.findChild(QtWidgets.QLabel, "helpVersionLabel")
        observed["version"] = version.text() if version is not None else ""
        dialog.accept()

    QtCore.QTimer.singleShot(0, inspect_and_close)
    main.DarkThemeApp.show_help_dialog(owner)

    assert observed == {
        "frameless": True,
        "github_at_end": True,
        "external_links": True,
        "telegram": True,
        "bug_report": True,
        "guide_fits": True,
        "frame": True,
        "version": f"Click'n'Translate · V{main.APP_VERSION}",
    }
    assert "background-color: transparent" in main._HELP_STYLE
    owner.close()
