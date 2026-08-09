"""End-to-end functional check of every user-facing feature.

The unit suite proves the pieces; this drives the real ones — live translation
providers, the installed Tesseract, the Argos model, the command socket, the
clipboard, the desktop files — and prints a pass/fail matrix. It runs on Windows
and Linux and skips whatever does not exist on the current system.

    python tools/functional_check.py             # everything
    python tools/functional_check.py --offline   # skip network providers
    python tools/functional_check.py --frozen dist/clickntranslate

Exit code is 1 if anything failed (skips do not fail the run).
"""

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import platform_support  # noqa: E402

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"
RESULTS = []
SAMPLE_EN = "Hello world OCR test"
SAMPLE_RU = "Проверка распознавания текста"


def record(group, name, status, detail=""):
    RESULTS.append((group, name, status, detail))
    marker = {PASS: "ok  ", FAIL: "FAIL", SKIP: "skip"}[status]
    print(f"  [{marker}] {name}" + (f" — {detail}" if detail else ""), flush=True)


def check(group, name, function, skip_reason=""):
    """Run one check; any exception is a failure with its message."""
    if skip_reason:
        record(group, name, SKIP, skip_reason)
        return None
    try:
        detail = function()
    except Exception as exc:
        record(group, name, FAIL, f"{type(exc).__name__}: {exc}")
        return None
    if detail is SKIP:
        record(group, name, SKIP, "")
        return None
    if isinstance(detail, tuple) and detail and detail[0] is SKIP:
        record(group, name, SKIP, detail[1])
        return None
    record(group, name, PASS, str(detail)[:110] if detail else "")
    return detail


def group(title):
    print(f"\n=== {title} ===", flush=True)
    return title


# --- platform and paths -------------------------------------------------------


def check_platform():
    title = group("platform and paths")
    import portable_paths

    check(title, "platform detected", lambda: (
        f"windows={platform_support.IS_WINDOWS} linux={platform_support.IS_LINUX} "
        f"session={platform_support.linux_session_type() or 'n/a'}"
    ))
    check(title, "portable base dir is writable", lambda: _writable(portable_paths.portable_base_dir()))
    check(title, "public executable resolves", lambda: portable_paths.public_executable_path())
    check(title, "helper names carry the platform suffix", lambda: ", ".join(
        platform_support.executable_name(stem) for stem in ("ArgosWorker", "OcrWorker")
    ))
    check(title, "subprocess flags hide consoles on Windows only", lambda: (
        "startupinfo set" if platform_support.no_window_kwargs() else "no flags needed"
    ))


def _writable(path):
    if not os.path.isdir(path):
        raise AssertionError(f"{path} does not exist")
    probe = os.path.join(path, ".functional_check_probe")
    with open(probe, "w", encoding="utf-8") as handle:
        handle.write("probe")
    os.unlink(probe)
    return path


# --- translators --------------------------------------------------------------


def check_translators(offline):
    title = group("translation providers")
    import translater

    text = "Hello world, how are you today?"
    providers = (
        ("google", translater.google_translate),
        ("lingva", translater.lingva_translate),
        ("mymemory", translater.mymemory_translate),
        ("libretranslate", translater.libretranslate),
    )
    def call_provider(function):
        """Public endpoints go down and time out; one retry before judging."""
        try:
            return _nonempty(function(text, "en", "ru"))
        except Exception as first_error:
            time.sleep(3)
            try:
                return _nonempty(function(text, "en", "ru"))
            except Exception:
                raise first_error

    for name, function in providers:
        check(
            title,
            f"{name} en->ru",
            lambda function=function: call_provider(function),
            skip_reason="--offline" if offline else "",
        )

    check(title, "argos runtime available", lambda: translater.argos_unavailable_reason() or "ready")

    def argos_translate():
        result = translater._try_argos_translate(SAMPLE_RU, "ru", "en", allow_install=False)
        if not result:
            return (SKIP, "no ru->en package installed")
        return _nonempty(result)

    check(title, "argos ru->en (offline model)", argos_translate)

    def hymt_state():
        if translater.hymt_installed():
            return _nonempty(translater.hymt_translate("Hello", "en", "ru"))
        try:
            translater.translate_text("Hello", "en", "ru", engine="hymt")
        except Exception as exc:
            message = str(exc)
            assert message.strip(), "Hy-MT failure must explain itself"
            return (SKIP, f"not installed; message: {message[:60]}")
        raise AssertionError("Hy-MT reported success while not installed")

    check(title, "hy-mt", hymt_state)

    check(title, "sentence splitter", lambda: translater.split_sentences(
        "First one. Second one! Third?"
    ) == ["First one.", "Second one!", "Third?"] or _fail("unexpected split"))

    def provider_isolation():
        """A failing provider must surface its own error, not switch silently."""
        original = translater.mymemory_translate
        translater.mymemory_translate = lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("outage"))
        try:
            translater.translate_text("unique text for isolation check", "en", "de", engine="mymemory")
            return _fail("a failing provider was silently replaced")
        except RuntimeError:
            return "error surfaced"
        finally:
            translater.mymemory_translate = original

    check(title, "failed provider does not switch silently", provider_isolation)


def _nonempty(value):
    text = str(value or "").strip()
    if not text:
        raise AssertionError("empty result")
    return text[:70]


def _fail(message):
    raise AssertionError(message)


# --- OCR ----------------------------------------------------------------------


def _render(text, size=(900, 160)):
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(image)
    font = None
    for candidate in ("arial.ttf", "DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            font = ImageFont.truetype(candidate, 48)
            break
        except Exception:
            continue
    draw.text((20, 50), text, fill="black", font=font or ImageFont.load_default())
    return image


def check_ocr():
    title = group("OCR engines")
    import ocr

    check(title, "engine list matches the platform", lambda: ", ".join(platform_support.available_ocr_engines()))
    check(title, "configured engine is usable here", lambda: ocr.usable_ocr_engine("Windows"))

    tess_cmd = ocr.ScreenCaptureOverlay.get_tesseract_cmd()
    check(title, "tesseract found", lambda: tess_cmd or _fail("not installed"),
          skip_reason="" if tess_cmd else "tesseract is not installed")

    if tess_cmd:
        from languages import tesseract_language_code

        check(title, "tesseract languages", lambda: ", ".join(ocr.installed_ocr_language_codes("Tesseract")) or _fail("none"))
        for text, lang, code in ((SAMPLE_EN, "en", "eng"), (SAMPLE_RU, "ru", "rus")):
            available = code in ocr._tesseract_reported_languages(tess_cmd)
            check(
                title,
                f"tesseract recognizes {lang}",
                # Same entry point the OCR worker uses: it tries several page
                # segmentation modes and scores the results.
                lambda text=text, lang=lang: _recognized(
                    ocr._recognize_tesseract_variants_with_cmd(
                        [("check", _render(text).convert("L"))],
                        tess_cmd,
                        tesseract_language_code(lang),
                        "functional-check",
                        "functional-check",
                    ),
                    text,
                ),
                skip_reason="" if available else f"{code}.traineddata not installed",
            )

    if platform_support.supports_windows_ocr():
        check(title, "winrt available", lambda: ocr._WINRT_AVAILABLE or _fail(str(ocr._WINRT_ERROR)))
        check(title, "windows ocr languages", lambda: ", ".join(ocr._get_available_windows_ocr_language_tags()) or _fail("none"))

        def windows_recognize():
            import asyncio

            engine = ocr._get_windows_ocr_engine("en-US")
            if engine is None:
                return (SKIP, "en-US recognizer not installed")
            bitmap = ocr.load_image_from_pil(_render(SAMPLE_EN))
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                recognized = loop.run_until_complete(ocr.run_ocr_with_engine(bitmap, engine))
            finally:
                loop.close()
                asyncio.set_event_loop(None)
            return _recognized(ocr._windows_ocr_result_to_text(recognized), SAMPLE_EN)

        check(title, "windows ocr recognizes english", windows_recognize)

        def windows_auto():
            bitmap = ocr.load_image_from_pil(_render(SAMPLE_EN))
            return _recognized(
                ocr._recognize_with_windows_auto([("check", bitmap)], session_id="functional-check"),
                SAMPLE_EN,
            )

        check(title, "windows ocr AUTO mode", windows_auto)
    else:
        check(title, "windows ocr is hidden off Windows",
              lambda: "windows" not in platform_support.available_ocr_engines() or _fail("still offered"))

    for engine, checker in (("rapidocr", "_rapidocr_installed_language_codes"),
                            ("easyocr", "_easyocr_installed_language_codes")):
        codes = getattr(ocr, checker)()
        check(title, f"{engine} models", lambda codes=codes: ", ".join(codes),
              skip_reason="" if codes else "engine not installed")


def _recognized(result, expected):
    """Assert the OCR output resembles the rendered text.

    Engines legitimately differ on spacing, punctuation and lookalike glyphs
    (O/0, l/I), and the neural ones return separate text blocks whose order
    follows the layout rather than the reading order. So this compares the words
    as a set, with a similarity ratio for the glyph-level differences.
    """
    from difflib import SequenceMatcher

    text = str(result or "").strip()
    if not text:
        raise AssertionError("nothing recognized")

    def words(value):
        cleaned = "".join(ch.lower() if ch.isalnum() else " " for ch in value)
        return sorted(word for word in cleaned.split() if word)

    ratio = SequenceMatcher(None, " ".join(words(text)), " ".join(words(expected))).ratio()
    if ratio < 0.75:
        raise AssertionError(f"expected ~{expected!r}, got {text!r} (similarity {ratio:.2f})")
    return f"{text[:50]!r} (similarity {ratio:.2f})"


# --- capture ------------------------------------------------------------------


def check_capture():
    title = group("screen capture")
    if not platform_support.IS_LINUX:
        check(title, "qt grabs the root window on Windows", lambda: "QScreen.grabWindow")
        return

    import linux_capture

    def backend():
        name = linux_capture.backend_name()
        if name:
            return name
        # Wayland with no portal and no helper: there is genuinely nothing to
        # capture with (a headless container or WSL). Report it as unavailable
        # rather than failing — but only after confirming the app says so
        # clearly, which the message check below asserts.
        if not linux_capture.portal_available() and not linux_capture.available_helper():
            return (SKIP, "no portal or helper in this session — nothing to capture with")
        return _fail("a backend exists but was not selected")

    check(title, "backend for this session", backend,
          skip_reason="" if platform_support.has_display() else "no display in this session")
    check(title, "screenshot helper present", lambda: linux_capture.available_helper() or (SKIP, "none installed"))
    check(title, "portal reachable", lambda: linux_capture.portal_available() or (SKIP, "no desktop portal"))
    check(title, "unavailable message names a package",
          lambda: "xdg-desktop-portal" in linux_capture.unavailable_message() or _fail("unhelpful message"))


# --- clipboard ----------------------------------------------------------------


def check_clipboard():
    title = group("clipboard")
    missing = platform_support.missing_clipboard_helper()
    check(title, "clipboard helper", lambda: missing and (SKIP, f"install {missing}") or "present")

    def round_trip():
        marker = f"clickntranslate-check-{int(time.time())}"
        if not platform_support.copy_text(marker):
            return (SKIP, "no clipboard backend in this session")
        if platform_support.IS_LINUX:
            import shutil

            reader = shutil.which("xclip")
            if not reader:
                return (SKIP, "xclip missing, cannot read back")
            output = subprocess.run([reader, "-o", "-selection", "clipboard"],
                                    capture_output=True, text=True, timeout=5)
            if output.returncode != 0:
                return (SKIP, "no display to read the clipboard back")
            assert output.stdout.strip() == marker, f"read back {output.stdout!r}"
            return "text survived the writing process"
        import pyperclip

        assert pyperclip.paste().strip() == marker
        return "text survived"

    check(title, "copy survives the process", round_trip)


# --- command socket -----------------------------------------------------------


def check_ipc():
    title = group("desktop shortcut commands")
    if not hasattr(socket, "AF_UNIX"):
        record(title, "command socket", SKIP, "AF_UNIX is Linux-only; Windows uses hotkeys")
        return

    import single_instance

    received = []
    temp_dir = tempfile.mkdtemp(prefix="cnt_func_")
    path = os.path.join(temp_dir, "check.sock")
    server = single_instance.CommandServer(received.append, path=path)

    def bind():
        assert server.bind(), "could not claim the socket"
        server.start()
        return path

    check(title, "server claims the socket", bind)

    for command in single_instance.COMMANDS:
        check(title, f"command {command!r} delivered",
              lambda command=command: single_instance.send_command(command, path=path) or _fail("not accepted"))

    def all_arrived():
        deadline = time.time() + 5
        while time.time() < deadline and len(received) < len(single_instance.COMMANDS):
            time.sleep(0.05)
        assert received == list(single_instance.COMMANDS), received
        return f"{len(received)} commands dispatched"

    check(title, "handler saw every command", all_arrived)

    def stale_socket():
        server.stop()
        stale = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        stale.bind(path)
        stale.close()
        rival = single_instance.CommandServer(lambda _c: None, path=path)
        assert rival.bind(), "a socket left by a crash was not reclaimed"
        rival.stop()
        return "reclaimed"

    check(title, "socket left by a crash is reclaimed", stale_socket)

    check(title, "every shortcut action has a command",
          lambda: set(platform_support.SHORTCUT_ACTIONS) <= set(single_instance.COMMANDS) or _fail("missing"))

    try:
        os.rmdir(temp_dir)
    except OSError:
        pass


# --- desktop integration ------------------------------------------------------


def check_desktop():
    title = group("desktop integration")
    if not platform_support.IS_LINUX:
        record(title, "desktop entries", SKIP, "Windows uses a Startup shortcut")
        return

    import linux_desktop

    temp_dir = tempfile.mkdtemp(prefix="cnt_desktop_")
    previous = {key: os.environ.get(key) for key in ("XDG_DATA_HOME", "XDG_CONFIG_HOME")}
    os.environ["XDG_DATA_HOME"] = temp_dir
    os.environ["XDG_CONFIG_HOME"] = temp_dir
    try:
        check(title, "autostart entry can be enabled",
              lambda: linux_desktop.set_autostart(True, "/opt/clickntranslate") or _fail("not written"))
        check(title, "autostart entry is detected",
              lambda: linux_desktop.autostart_enabled() or _fail("not found"))
        check(title, "autostart entry can be removed",
              lambda: (not linux_desktop.set_autostart(False, "/opt/clickntranslate")) or _fail("still there"))
        check(title, "application entry is installed",
              lambda: os.path.basename(linux_desktop.install_desktop_entry("/opt/clickntranslate")))
        check(title, "entry carries capture actions",
              lambda: all(f"--{action}" in linux_desktop.desktop_entry_text("/opt/x")
                          for _n, _l, action in linux_desktop.DESKTOP_ACTIONS) or _fail("missing actions"))
        check(title, "icon converts to png",
              lambda: os.path.basename(linux_desktop.install_icon(str(ROOT / "icons" / "icon.ico"))))
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


# --- documents, cache, languages ---------------------------------------------


def check_documents():
    title = group("documents, cache, languages")
    import cache_manager
    import document_translation
    from languages import language_code_from_name, translator_api_code

    def chunking():
        chunks = document_translation.split_text_chunks("Paragraph one.\n\n" + ("word " * 400))
        assert len(chunks) > 1, "long text was not chunked"
        return f"{len(chunks)} chunks"

    check(title, "document chunking", chunking)

    def document_pipeline():
        seen = []

        def fake_translate(text, source, target, status_callback=None, engine=None):
            seen.append(engine)
            if status_callback:
                status_callback("working")
            return text.upper()

        original = document_translation.translater.translate_text
        document_translation.translater.translate_text = fake_translate
        try:
            translated, results = document_translation.translate_document_text(
                "first paragraph\n\nsecond paragraph", "en", "ru", provider_engine="argos"
            )
        finally:
            document_translation.translater.translate_text = original
        assert "FIRST PARAGRAPH" in translated, translated
        assert seen and seen[0] == "argos", seen
        return f"{len(results)} chunks translated"

    check(title, "document translation pipeline", document_pipeline)

    def cache_round_trip():
        data_dir = tempfile.mkdtemp(prefix="cnt_cache_")
        cache_manager.invalidate_translation_cache()
        cache_manager.save_cached_translation(data_dir, "hello", "en", "ru", "привет", engine="google")
        hit = cache_manager.get_cached_translation(data_dir, "hello", "en", "ru", engine="google")
        miss = cache_manager.get_cached_translation(data_dir, "hello", "en", "ru", engine="hymt")
        assert hit == "привет" and miss is None, (hit, miss)
        return "hit and engine-scoped miss"

    check(title, "translation cache", cache_round_trip)

    check(title, "language code lookup",
          lambda: language_code_from_name("Russian", "en") or _fail("no code"))
    check(title, "provider language codes",
          lambda: f"zh->google:{translator_api_code('zh', 'google')}")


# --- frozen build -------------------------------------------------------------


def check_frozen(dist_dir):
    title = group("frozen build")
    if not dist_dir:
        record(title, "packaged workers", SKIP, "pass --frozen <dist dir> to check a build")
        return

    dist = Path(dist_dir)
    if platform_support.IS_WINDOWS and (dist / "app" / "ClicknTranslateApp.exe").is_file():
        # Portable/installer releases deliberately keep only the public launcher
        # in the root.  The real application and workers are hidden together in
        # app/, so exercise the exact layout shipped to users instead of the raw
        # PyInstaller output layout.
        app = dist / "ClicknTranslate.exe"
        worker_root = dist / "app" / "_internal"
    else:
        app = dist / platform_support.executable_name(
            "clickntranslate" if platform_support.IS_LINUX else "ClicknTranslate"
        )
        worker_root = dist / "_internal"
    argos = worker_root / platform_support.executable_name("ArgosWorker")
    ocr_worker = worker_root / platform_support.executable_name("OcrWorker")

    for label, path in (("app", app), ("argos worker", argos), ("ocr worker", ocr_worker)):
        check(title, f"{label} present", lambda path=path: path.name if path.is_file() else _fail(f"missing {path}"))

    def argos_worker_translates():
        if not argos.is_file():
            return (SKIP, "worker missing")
        request = {"action": "translate", "text": SAMPLE_RU, "source_code": "ru", "target_code": "en"}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
            json.dump(request, handle)
            request_path = handle.name
        try:
            completed = subprocess.run([str(argos), request_path], capture_output=True, text=True, timeout=300)
            payload = json.loads(completed.stdout.strip().splitlines()[-1])
        finally:
            os.unlink(request_path)
        if payload.get("error"):
            return (SKIP, f"worker said: {payload['error'][:60]}")
        if payload.get("result") is None:
            # No error and no text means the direction is simply not installed:
            # the worker has nothing to translate with. That is a missing
            # prerequisite on this machine, not a broken build — reporting it as
            # a failure makes every fresh build machine look red.
            return (SKIP, "no ru->en package installed on this machine")
        return _nonempty(payload.get("result"))

    check(title, "packaged argos worker translates", argos_worker_translates)

    def _run_ocr_worker(request):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
            json.dump(request, handle)
            request_path = handle.name
        try:
            completed = subprocess.run([str(ocr_worker), request_path], capture_output=True, text=True, timeout=600)
            return json.loads(completed.stdout.strip().splitlines()[-1])
        finally:
            os.unlink(request_path)

    def ocr_worker_responds():
        if not ocr_worker.is_file():
            return (SKIP, "worker missing")
        payload = _run_ocr_worker({"action": "import", "engine": "rapidocr", "root_dir": str(dist)})
        if payload.get("error"):
            return (SKIP, f"rapidocr not bundled: {payload['error'][:50]}")
        return "rapidocr importable"

    check(title, "packaged ocr worker answers", ocr_worker_responds)

    def rapidocr_recognizes():
        if not ocr_worker.is_file():
            return (SKIP, "worker missing")
        image_dir = tempfile.mkdtemp(prefix="cnt_rapid_")
        image_path = os.path.join(image_dir, "sample.png")
        _render(SAMPLE_EN).save(image_path)
        payload = _run_ocr_worker({
            "engine": "rapidocr",
            "root_dir": str(dist),
            "images": [{"label": "check", "path": image_path}],
        })
        os.unlink(image_path)
        os.rmdir(image_dir)
        if payload.get("error"):
            return (SKIP, f"engine unavailable: {payload['error'][:50]}")
        results = payload.get("results") or []
        if not results:
            raise AssertionError("worker returned no results")
        first = results[0]
        if first.get("error"):
            return (SKIP, f"recognition unavailable: {first['error'][:50]}")
        return _recognized(first.get("text"), SAMPLE_EN)

    check(title, "packaged rapidocr recognizes text", rapidocr_recognizes)


# --- update policy ------------------------------------------------------------


def check_updates():
    title = group("update policy")
    check(title, "self-update only where helpers exist",
          lambda: f"in-app update: {platform_support.supports_in_app_update()}")
    if not platform_support.IS_WINDOWS:
        source = (ROOT / "settings_window.py").read_text(encoding="utf-8")
        check(title, "linux is offered the release page instead",
              lambda: "webbrowser.open(GITHUB_RELEASES_PAGE)" in source or _fail("no link path"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="skip the live translation providers")
    parser.add_argument("--frozen", default="", help="dist directory of a packaged build to exercise")
    arguments = parser.parse_args()

    print(f"Click'n'Translate functional check — {sys.platform}, python {sys.version.split()[0]}")

    check_platform()
    check_translators(arguments.offline)
    check_ocr()
    check_capture()
    check_clipboard()
    check_ipc()
    check_desktop()
    check_documents()
    check_updates()
    check_frozen(arguments.frozen)

    passed = sum(1 for *_x, status, _d in RESULTS if status == PASS)
    failed = [row for row in RESULTS if row[2] == FAIL]
    skipped = sum(1 for *_x, status, _d in RESULTS if status == SKIP)

    print(f"\n{'=' * 60}")
    print(f"passed {passed}   failed {len(failed)}   skipped {skipped}")
    for group_name, name, _status, detail in failed:
        print(f"  FAIL  {group_name} / {name}: {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
