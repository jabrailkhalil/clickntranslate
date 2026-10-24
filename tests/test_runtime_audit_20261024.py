"""Private OCR content is persisted only with diagnostic opt-in.

These checks use fake engine results and temporary fixtures.  No engine is
started, no external service is contacted, and no real clipboard is touched.
"""
from types import SimpleNamespace
from unittest import mock
import threading
import time
import asyncio
import logging

import pytest
from PyQt5 import QtCore
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

import ocr


PRIVATE_TEXT = "private OCR fixture: confidential message\nsecond line"


@pytest.mark.parametrize("value", [None, "", PRIVATE_TEXT, "سري باللغة العربية"])
def test_ocr_text_preview_keeps_only_length_without_explicit_opt_in(monkeypatch, value):
    monkeypatch.setattr(ocr, "get_cached_ocr_config", lambda: {})
    assert ocr._text_preview(value) == f"<redacted; {len(value or '')} chars>"


def test_ocr_diagnostic_opt_in_keeps_escaped_bounded_preview(monkeypatch):
    monkeypatch.setattr(ocr, "get_cached_ocr_config", lambda: {"debug_ocr_artifacts": True})
    assert ocr._text_preview("first\r\nsecond", limit=10) == "first\\r\\ns..."
    assert ocr._text_preview("short") == "short"


def test_ocr_preview_fails_closed_when_diagnostics_config_is_unavailable(monkeypatch):
    def broken_config():
        raise OSError("test config inaccessible")

    monkeypatch.setattr(ocr, "get_cached_ocr_config", broken_config)
    assert ocr._text_preview(PRIVATE_TEXT) == f"<redacted; {len(PRIVATE_TEXT)} chars>"


@pytest.mark.parametrize("value", [False, None, 1, "false", "true"])
def test_diagnostic_artifacts_require_a_boolean_true(monkeypatch, value):
    monkeypatch.setattr(ocr, "get_cached_ocr_config", lambda: {"debug_ocr_artifacts": value})
    assert ocr._ocr_debug_artifacts_enabled() is False


def test_ocr_diagnostics_do_not_enable_http_debug_request_logging(tmp_path):
    root = logging.Logger("isolated-runtime-privacy")
    http = logging.Logger("urllib3.connectionpool")
    http.parent = root
    log_path = tmp_path / "ocr.log"
    with mock.patch.object(ocr.logging, "getLogger", return_value=root), \
            mock.patch.object(ocr, "get_log_path", return_value=str(log_path)), \
            mock.patch.object(ocr, "_debug_log_path", None):
        try:
            assert ocr._setup_ocr_diagnostics_logging()
            http.debug('GET /translate?q=confidential message HTTP/1.1')
            root.info("OCR metadata remains available")
        finally:
            ocr.close_ocr_diagnostics_logging()
    saved = log_path.read_text(encoding="utf-8")
    assert "confidential message" not in saved
    assert "OCR metadata remains available" in saved


def test_windows_async_bridge_does_not_read_lines_only_for_logging(monkeypatch, caplog):
    monkeypatch.setattr(ocr, "get_cached_ocr_config", lambda: {})

    class PrivateLine:
        @property
        def text(self):
            raise AssertionError("Line text should only be read during actual extraction")

    result = SimpleNamespace(text=PRIVATE_TEXT, lines=[PrivateLine()])

    async def recognize(_bitmap):
        return result

    actual = asyncio.run(ocr.run_ocr_with_engine(object(), SimpleNamespace(recognize_async=recognize)))
    assert actual is result
    assert "confidential message" not in caplog.text
    assert "Line text should only" not in caplog.text


@pytest.mark.parametrize("language", ["en", "auto"])
def test_windows_area_worker_logs_metadata_without_recognized_text(monkeypatch, caplog, language):
    monkeypatch.setattr(ocr, "get_cached_ocr_config", lambda: {})
    monkeypatch.setattr(ocr, "_WINRT_AVAILABLE", True)
    result = SimpleNamespace(text=PRIVATE_TEXT, lines=[SimpleNamespace(text=PRIVATE_TEXT, words=[])])

    async def recognize(_bitmap):
        return result

    monkeypatch.setattr(ocr, "_get_windows_ocr_engine", lambda _tag: SimpleNamespace(recognize_async=recognize))
    monkeypatch.setattr(ocr, "_recognize_with_windows_auto", lambda *_args, **_kwargs: PRIVATE_TEXT)
    worker = ocr.OCRWorker(object(), language)
    values = []
    worker.result_ready.connect(values.append)
    try:
        worker.run()
    finally:
        worker.deleteLater()
    assert values == [PRIVATE_TEXT]
    assert "confidential message" not in caplog.text


@pytest.mark.parametrize("enabled", [False, True])
def test_failed_ocr_screenshots_require_diagnostic_opt_in(monkeypatch, enabled):
    monkeypatch.setattr(ocr, "get_cached_ocr_config", lambda: {"debug_ocr_artifacts": enabled})
    owner = SimpleNamespace(
        _session_id="privacy-fixture",
        _last_ocr_raw_capture=object(),
        _last_ocr_pil_variants=[("raw", object())],
        _last_ocr_capture_meta={"width": 100, "height": 50},
    )
    with mock.patch.object(ocr, "_save_pixmap_debug", return_value="fixture-raw.png") as pixmap, \
            mock.patch.object(ocr, "_save_pil_debug", return_value="fixture-variant.png") as pil:
        ocr.ScreenCaptureOverlay._persist_failed_ocr_artifacts(owner, "empty_result")
    assert pixmap.call_count == int(enabled)
    assert pil.call_count == int(enabled)


def test_fullscreen_does_not_log_the_raw_engine_result(monkeypatch, caplog):
    monkeypatch.setattr(ocr, "get_cached_ocr_config", lambda: {})
    monkeypatch.setattr(ocr, "_WINRT_AVAILABLE", True)
    monkeypatch.setattr(ocr, "_get_windows_ocr_engine", lambda _tag: object())
    monkeypatch.setattr(ocr, "_windows_ocr_lines_in_image", lambda *_args: [])

    async def recognize(_bitmap, _engine):
        return SimpleNamespace(text=PRIVATE_TEXT, lines=[])

    monkeypatch.setattr(ocr, "run_ocr_with_engine", recognize)
    worker = ocr.FullScreenOCRWorker(SimpleNamespace(pixel_width=100, pixel_height=50), "en")
    try:
        worker.run()
    finally:
        worker.deleteLater()
    assert "confidential message" not in caplog.text


def test_fullscreen_exception_text_is_not_persisted_without_opt_in(monkeypatch, caplog, capsys):
    monkeypatch.setattr(ocr, "get_cached_ocr_config", lambda: {})

    def fail_recognition(*_args):
        # External libraries can put source text in their exception message.
        raise RuntimeError(PRIVATE_TEXT)

    monkeypatch.setattr(ocr, "_recognize_image_layout", fail_recognition)
    worker = ocr.FullScreenOCRWorker(object(), "en", engine="rapidocr")
    try:
        worker.run()
    finally:
        worker.deleteLater()
    captured = capsys.readouterr()
    assert "confidential message" not in caplog.text + captured.out + captured.err


@pytest.fixture
def area_overlay(monkeypatch):
    import main

    config = {
        "interface_language": "en", "theme": "Темная",
        "translator_engine": "Google", "ocr_engine": "Windows",
        "ocr_translate_source_language": "en", "ocr_translate_target_language": "ar",
        "result_window_hidden_modes": [], "copy_translated_text": False,
    }
    monkeypatch.setattr(ocr, "get_cached_ocr_config", lambda: config)
    monkeypatch.setattr(ocr, "installed_ocr_language_codes", lambda *_args, **_kwargs: ["en", "ru", "ar"])
    monkeypatch.setattr(ocr, "_safe_prepare_overlay", lambda *_args: None)
    overlay = ocr.ScreenCaptureOverlay("translate", defer_show=True)
    with mock.patch.object(main, "show_translation_dialog") as dialog, \
            mock.patch.object(main, "save_copy_history") as copy_history, \
            mock.patch.object(ocr, "save_translation_history") as history, \
            mock.patch.object(ocr.platform_support, "copy_text") as copy, \
            mock.patch.object(ocr.QMessageBox, "warning") as warning:
        yield SimpleNamespace(overlay=overlay, config=config, dialog=dialog,
                              copy_history=copy_history, history=history, copy=copy, warning=warning)
    try:
        overlay.close()
        overlay.deleteLater()
    except RuntimeError:
        pass  # The deleted-owner regression deliberately destroys this overlay.
    QApplication.processEvents()


def _wait_for(predicate, timeout=2):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        QTest.qWait(10)
    assert predicate(), "timed out waiting for the queued Qt completion"


def test_area_network_translation_leaves_the_qt_event_loop_responsive(area_overlay):
    state = area_overlay
    entered, release = threading.Event(), threading.Event()
    calls = []

    def translate(*args, **kwargs):
        calls.append((args, kwargs, threading.get_ident()))
        entered.set()
        assert release.wait(2)
        return "ترجمة عربية"

    try:
        with mock.patch("translater.translate_text", side_effect=translate):
            state.overlay.handle_ocr_result("A wrapped paragraph.", state.overlay._session_id)
            assert entered.wait(1)
            assert state.overlay._ocr_in_progress
            assert state.overlay._area_translation_worker is not None
            ticks = []
            QtCore.QTimer.singleShot(0, lambda: ticks.append(True))
            _wait_for(lambda: ticks)
            assert calls[0][2] != threading.get_ident()
            state.dialog.assert_not_called()
            release.set()
            _wait_for(lambda: state.dialog.called)
            assert not state.overlay._ocr_in_progress
            assert state.overlay._area_translation_worker is None
            state.history.assert_called_once_with("A wrapped paragraph.", "ترجمة عربية", "ar")
            assert state.dialog.call_args.kwargs["target_lang"] == "ar"
    finally:
        release.set()


@pytest.mark.parametrize("hidden", [False, True])
def test_area_completion_preserves_languages_provider_and_history(area_overlay, hidden):
    state = area_overlay
    state.config["result_window_hidden_modes"] = ["area"] if hidden else []
    entered, release = threading.Event(), threading.Event()
    calls = []

    def translate(text, source, target, **kwargs):
        calls.append((text, source, target, kwargs["engine"]))
        entered.set()
        assert release.wait(2)
        return "The completed translation"

    try:
        with mock.patch("translater.translate_text", side_effect=translate):
            state.overlay.handle_ocr_result("source", state.overlay._session_id)
            assert entered.wait(1)
            state.config["translator_engine"] = "MyMemory"
            state.overlay.current_target_language = "ru"
            release.set()
            _wait_for(lambda: state.history.called)
        assert calls == [("source", "en", "ar", "Google")]
        state.history.assert_called_once_with("source", "The completed translation", "ar")
        if hidden:
            state.dialog.assert_not_called()
            state.copy.assert_called_once_with("The completed translation")
            state.copy_history.assert_called_once_with("The completed translation")
        else:
            state.copy.assert_not_called()
            assert state.dialog.call_args.kwargs["source_lang"] == "en"
            assert state.dialog.call_args.kwargs["target_lang"] == "ar"
            state.dialog.return_value.set_window_engine.assert_called_once_with("Google")
    finally:
        release.set()


def test_closing_area_translation_cancels_and_ignores_queued_results(area_overlay):
    state = area_overlay
    entered, release = threading.Event(), threading.Event()
    callbacks = []

    def translate(*_args, **kwargs):
        callbacks.append(kwargs["cancel_callback"])
        entered.set()
        assert release.wait(2)
        return "Must not be shown or copied"

    try:
        with mock.patch("translater.translate_text", side_effect=translate):
            state.overlay.handle_ocr_result("source", state.overlay._session_id)
            assert entered.wait(1)
            worker = state.overlay._area_translation_worker
            state.overlay.close()
            assert callbacks[0]() is True
            assert state.overlay._area_translation_worker is None
            # A completion can already be queued when the user closes a window.
            state.overlay._on_area_translation_finished(worker, "late response", None)
            release.set()
            worker._thread.join(1)
            assert not worker._thread.is_alive()
            QTest.qWait(10)
        state.dialog.assert_not_called()
        state.warning.assert_not_called()
        state.copy.assert_not_called()
        state.history.assert_not_called()
    finally:
        release.set()


def test_deleted_area_owner_cancels_without_an_orphan_qthread(area_overlay):
    state = area_overlay
    entered, release = threading.Event(), threading.Event()

    def translate(*_args, **_kwargs):
        entered.set()
        assert release.wait(2)
        return "late response"

    with mock.patch("translater.translate_text", side_effect=translate):
        try:
            state.overlay.handle_ocr_result("source", state.overlay._session_id)
            assert entered.wait(1)
            worker = state.overlay._area_translation_worker
            state.overlay.close()
            state.overlay.deleteLater()
            QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
            assert worker.cancelled.is_set()
            release.set()
            worker._thread.join(1)
            assert not worker._thread.is_alive()
            state.dialog.assert_not_called()
        finally:
            release.set()


def test_late_ocr_signal_does_not_clear_a_new_session(area_overlay):
    overlay = area_overlay.overlay
    overlay._session_id = "new-session"
    overlay._ocr_worker_session_id = "new-session"
    overlay._ocr_in_progress = True
    overlay._ocr_status_text = "new status"
    overlay.handle_ocr_result("old text", "old-session")
    assert overlay._ocr_in_progress
    assert overlay._ocr_worker_session_id == "new-session"
    assert overlay._ocr_status_text == "new status"


def test_combined_api_vision_response_is_not_translated_twice(area_overlay):
    state = area_overlay
    state.overlay._api_translation = SimpleNamespace(source="captured source", translation="already translated")
    state.overlay._api_language_pair = ("en", "ar")
    state.overlay._api_translation_engine = "openai"
    with mock.patch("translater.translate_text") as translate:
        state.overlay.handle_ocr_result("captured source", state.overlay._session_id)
    translate.assert_not_called()
    assert getattr(state.overlay, "_area_translation_worker", None) is None
    state.dialog.assert_called_once()
    state.dialog.return_value.set_window_engine.assert_called_once_with("openai")
    state.history.assert_called_once_with("captured source", "already translated", "ar")


@pytest.mark.parametrize("locale", ["en", "ru", "es", "de", "fr", "zh", "pt", "it", "ar", "tr", "hi", "id"])
def test_null_screen_capture_restores_toolbar_and_allows_retry(area_overlay, monkeypatch, locale):
    from capture_regions import text

    state = area_overlay
    overlay = state.overlay
    state.config["interface_language"] = locale
    screen = QApplication.primaryScreen()
    overlay._active_screen = screen
    overlay.setGeometry(screen.geometry())
    overlay._freeze_screen_on_ocr = False
    overlay._ocr_in_progress = True
    overlay._ocr_worker_session_id = overlay._session_id
    overlay._ocr_status_text = "recognizing"
    overlay.capture_toolbar.hide()
    monkeypatch.setattr(overlay, "_select_target_screen_for_rect", lambda _rect: (screen, "test"))
    monkeypatch.setattr(overlay, "_grab_screenshot_region", lambda _screen, rect: (ocr.QtGui.QPixmap(), "test", rect))
    selected = QtCore.QRect(50, 80, 120, 50)
    overlay.capture_and_copy(selected)
    assert not overlay._ocr_in_progress
    assert overlay._ocr_worker_session_id is None
    assert overlay._ocr_status_text == ""
    assert not overlay.capture_toolbar.isHidden()
    assert not overlay.lang_combo.isHidden()
    assert not overlay.memory_hint.isHidden()
    assert overlay.memory_hint.text() == text(locale, "capture_error")
    assert overlay._preview_rect == selected
    assert overlay.repeat_area_button.isEnabled()
    with mock.patch.object(overlay, "capture_and_copy") as capture:
        overlay._repeat_area()
        capture.assert_called_once_with(selected)


@pytest.mark.parametrize("content,expected", [
    (rb"{\rtf1\ansi\uc1 \u1603?\u1578?\u1575?\u1576?}", "كتاب"),
    (rb"{\rtf1\ansi\uc0 \u1603\u1578\u1575\u1576}", "كتاب"),
    (rb"{\rtf1\ansi\uc2 \u1603??{\uc0\u1578}\u1575??\u1576??}", "كتاب"),
    (rb"{\rtf1\ansi \u1603\'3f\u1578\'3f}", "كت"),
    (rb"{\rtf1\ansi\uc1 \u-10179?\u-8704?}", "😀"),
    (rb"{\rtf1\ansi\ansicpg1251 \'cf\'f0\'e8\'e2\'e5\'f2}", "Привет"),
    (b"{\\rtf1\\ansi\\ansicpg1251 " + "Привет".encode("cp1251") + b"}", "Привет"),
    (b"{\\rtf1\\ansi\\ansicpg1256 " + "كتاب".encode("cp1256") + b"}", "كتاب"),
    (rb"{\rtf1\ansi\ansicpg932 \'93\'fa\'96\'7b\'8c\'ea}", "日本語"),
    (rb"{\rtf1\ansi\ansicpg99999 caf\'e9}", "café"),
    (rb"{\rtf1\ansi {\fonttbl{\f0\fcharset204 Arial;}}\f0 \'cf\'f0\'e8\'e2\'e5\'f2}", "Привет"),
    (rb"{\rtf1\ansi First\par\par Second\line next\tab cell}", "First\n\nSecond\nnext\tcell"),
    (rb"{\rtf1\ansi Literal \{braces\} and \\slash}", "Literal {braces} and \\slash"),
    (rb"{\rtf1{\fonttbl{\f0 Arial;}}{\*\generator HiddenName;}{\pict abcdef}{\object hidden}Visible}", "Visible"),
    (rb"{\rtf1{\pict\bin5 {abc}}Visible}", "Visible"),
])
def test_rtf_import_preserves_real_unicode_codepages_and_visible_text(tmp_path, content, expected):
    import document_parser

    path = tmp_path / "fixture.rtf"
    path.write_bytes(content)
    assert document_parser.parse_document(str(path)).text == expected
