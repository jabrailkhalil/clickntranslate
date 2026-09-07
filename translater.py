import requests
import json
import os
import sys
import subprocess
import re
import shutil
import tempfile
import time
import types
import zipfile
import zlib
import hashlib
from languages import language_english_name, translator_api_code
from translation_chunks import PROVIDER_BYTE_LIMITS, split_text, restore_boundary_whitespace
import platform_support
import portable_paths

# Optional Argos Translate (offline). main.py preloads its native runtime before
# Qt on Windows; importing this module alone remains lightweight until preloaded.
HAS_ARGOS = True
arg_pkg = None
arg_tr = None
_argos_import_error = None

# argostranslate.sbd imports stanza and minisbd unconditionally to split text into
# sentences. stanza pulls in torch (~2 GB, excluded from the build) and minisbd
# pulls in onnxruntime. Neither native stack is needed here: both imports are
# stubbed and every Argos sentencizer is replaced by _SentenceSplitter below.
ARGOS_DEFAULT_CHUNK_TYPE = "MINISBD"

# Sentence end punctuation, including CJK forms, plus closing quotes/brackets.
# The trailing whitespace is the delimiter; punctuation remains in the sentence.
_SENTENCE_END_RE = re.compile(r"[.!?…。！？]+[\"'”’»)\]]*(?:\s+|$)")
_MAX_SENTENCE_CHARS = 250
_MODULE_NOT_LOADED = object()


class ArgosInstallCancelledError(RuntimeError):
    """Raised when the user cancels an Argos language-package download."""


def split_sentences(text):
    """Splits a paragraph into sentences without any native dependency."""
    text = str(text or "")
    if not text.strip():
        return []
    sentences = []
    parts = []
    start = 0
    for match in _SENTENCE_END_RE.finditer(text):
        # Keep terminal punctuation/quotes, but not the whitespace after them.
        end = match.end()
        while end > match.start() and text[end - 1].isspace():
            end -= 1
        parts.append(text[start:end])
        start = match.end()
    if start < len(text):
        parts.append(text[start:])

    for part in parts or [text]:
        part = part.strip()
        while len(part) > _MAX_SENTENCE_CHARS:
            # Unpunctuated text still has to be cut, or the model degrades badly.
            cut = part.rfind(" ", 0, _MAX_SENTENCE_CHARS)
            if cut <= 0:
                cut = _MAX_SENTENCE_CHARS
            sentences.append(part[:cut].strip())
            part = part[cut:].strip()
        if part:
            sentences.append(part)
    return sentences or [text.strip()]


class _SentenceSplitter:
    """Drop-in replacement for the argostranslate sentencizers."""

    def __init__(self, pkg=None):
        self.pkg = pkg

    def split_sentences(self, text):
        return split_sentences(text)

    def __str__(self):
        return "ClicknTranslate sentence splitter"


def _make_module_stub(name, attributes):
    stub = types.ModuleType(name)
    for attribute, value in attributes.items():
        setattr(stub, attribute, value)
    stub.__argos_stub__ = True
    return stub


def _unavailable_sentencizer(*args, **kwargs):
    raise RuntimeError(
        "This sentence splitter is not bundled; ClicknTranslate splits sentences itself."
    )


def _prepare_argos_environment():
    """Makes argostranslate importable without torch/stanza/onnxruntime."""
    if portable_paths.is_windows_packaged() or platform_support.IS_MAC:
        # Keep native Mac data in Application Support and MSIX data in its
        # writable LocalState. Never write inside the signed application.
        argos_root = os.path.join(portable_paths.portable_base_dir(), "argos")
        os.environ.setdefault("XDG_DATA_HOME", os.path.join(argos_root, "data"))
        os.environ.setdefault("XDG_CONFIG_HOME", os.path.join(argos_root, "config"))
        os.environ.setdefault("XDG_CACHE_HOME", os.path.join(argos_root, "cache"))
    os.environ["ARGOS_CHUNK_TYPE"] = ARGOS_DEFAULT_CHUNK_TYPE
    if "stanza" not in sys.modules:
        sys.modules["stanza"] = _make_module_stub("stanza", {"Pipeline": _unavailable_sentencizer})
    if "minisbd" not in sys.modules:
        models = _make_module_stub(
            "minisbd.models",
            {
                "cache_dir": "",
                "list_models": lambda: [],
                "get_model_file": lambda *args, **kwargs: "",
            },
        )
        sys.modules["minisbd"] = _make_module_stub(
            "minisbd", {"SBDetect": _unavailable_sentencizer, "models": models}
        )
        sys.modules["minisbd.models"] = models


def _install_sentence_splitter(loaded_tr):
    """Points every argostranslate sentencizer at our dependency-free splitter."""
    for attribute in ("MiniSBDSentencizer", "StanzaSentencizer", "SpacySentencizerSmall"):
        if hasattr(loaded_tr, attribute):
            setattr(loaded_tr, attribute, _SentenceSplitter)


def _ensure_argos_available():
    global HAS_ARGOS, arg_pkg, arg_tr, _argos_import_error
    if not HAS_ARGOS:
        return False
    if arg_pkg is not None and arg_tr is not None:
        return True
    _prepare_argos_environment()
    # CTranslate2 imports torch only for model conversion helpers. Translation
    # does not need it, and loading torch after Qt on Windows can crash the
    # process. Make that optional import behave exactly like the frozen build,
    # where torch is excluded, then restore the import table afterwards.
    previous_torch = sys.modules.get("torch", _MODULE_NOT_LOADED)
    previous_spacy = sys.modules.get("spacy", _MODULE_NOT_LOADED)
    if previous_torch is _MODULE_NOT_LOADED:
        sys.modules["torch"] = None
    if previous_spacy is _MODULE_NOT_LOADED:
        # argostranslate.sbd imports SpaCy even when the configured splitter is
        # MiniSBD.  Click'n'Translate replaces every sentencizer below, so
        # loading SpaCy here only adds hundreds of milliseconds to source/Linux
        # startup and cannot affect translation quality.
        sys.modules["spacy"] = None
    try:
        import argostranslate.package as loaded_pkg
        import argostranslate.translate as loaded_tr
        if platform_support.IS_MAC:
            # Source versions before 1.7.1 used the upstream ~/.local path.
            # Continue to read those models without moving or deleting them.
            from pathlib import Path
            legacy = Path.home() / '.local/share/argos-translate/packages'
            if legacy.is_dir() and legacy not in loaded_pkg.settings.package_dirs:
                loaded_pkg.settings.package_dirs.append(legacy)
    except Exception as exc:
        HAS_ARGOS = False
        _argos_import_error = exc
        print(f"Argos Translate недоступен: {exc}")
        return False
    finally:
        if previous_torch is _MODULE_NOT_LOADED:
            sys.modules.pop("torch", None)
        if previous_spacy is _MODULE_NOT_LOADED:
            sys.modules.pop("spacy", None)
    _install_sentence_splitter(loaded_tr)
    arg_pkg = loaded_pkg
    arg_tr = loaded_tr
    return True


def preload_argos_runtime():
    """Loads Argos' native runtime before Qt consumes Windows TLS slots."""
    if _argos_worker_path():
        return True
    return _ensure_argos_available()


def argos_unavailable_reason():
    """Returns why the offline Argos runtime cannot be used, or '' when it can."""
    if getattr(sys, "frozen", False) and not os.environ.get("CLICKNTRANSLATE_ARGOS_WORKER"):
        if _argos_worker_path():
            return ""
        return "Argos offline worker is missing from this build."
    if _ensure_argos_available():
        return ""
    if _argos_import_error is None:
        return "Argos offline runtime is unavailable in this build."
    return f"Argos offline runtime is unavailable in this build: {_argos_import_error}"

def get_app_dir():
    if hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(sys.argv[0]))

def get_portable_dir():
    return portable_paths.portable_base_dir()


def _argos_worker_path():
    """Returns the packaged non-Qt Argos worker, or an empty string."""
    if not getattr(sys, "frozen", False) or os.environ.get("CLICKNTRANSLATE_ARGOS_WORKER"):
        return ""
    executable_dir = os.path.dirname(sys.executable)
    worker_name = platform_support.executable_name("ArgosWorker")
    for path in (
        os.path.join(executable_dir, "_internal", worker_name),
        os.path.join(executable_dir, worker_name),
    ):
        if os.path.isfile(path):
            return path
    return ""


def argos_runtime_available():
    return bool(_argos_worker_path()) or _ensure_argos_available()

def get_data_file(filename):
    data_dir = os.path.join(get_portable_dir(), "data")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    return os.path.join(data_dir, filename)

# --- Кэширование конфигурации ---
_translator_config_cache = None
_translator_config_mtime = 0

HYMT_MODEL_FILE = "HY-MT1.5-1.8B-Q4_K_M.gguf"
HYMT_ENGINE_KEY = "hymt"
HYMT_DISPLAY_NAME = "Hy-MT"
_hymt_runtime_cache = None

def get_cached_translator_config():
    """Возвращает закэшированную конфигурацию переводчика."""
    global _translator_config_cache, _translator_config_mtime
    config_path = get_data_file("config.json")
    try:
        mtime = os.path.getmtime(config_path)
        if _translator_config_cache is None or mtime > _translator_config_mtime:
            with open(config_path, "r", encoding="utf-8") as f:
                _translator_config_cache = json.load(f)
            _translator_config_mtime = mtime
    except Exception:
        if _translator_config_cache is None:
            _translator_config_cache = {}
    return _translator_config_cache

# --- Кэширование языков и объектов перевода Argos ---
_argos_languages_cache = None
_argos_translations_cache = {}

def _get_argos_languages():
    """Возвращает закэшированные языки Argos."""
    global _argos_languages_cache
    if _argos_languages_cache is None and _ensure_argos_available():
        _argos_languages_cache = {lang.code: lang for lang in arg_tr.get_installed_languages()}
    return _argos_languages_cache or {}

def _invalidate_argos_cache():
    """Сбрасывает кэш языков Argos после установки новых моделей."""
    global _argos_languages_cache, _argos_translations_cache
    _argos_languages_cache = None
    _argos_translations_cache = {}

def _get_translation_object(source_code, target_code):
    """Возвращает закэшированный объект перевода."""
    key = (source_code, target_code)
    if key not in _argos_translations_cache:
        langs = _get_argos_languages()
        source_lang = langs.get(source_code)
        target_lang = langs.get(target_code)
        if source_lang and target_lang:
            _argos_translations_cache[key] = source_lang.get_translation(target_lang)
        else:
            _argos_translations_cache[key] = None
    return _argos_translations_cache[key]


def _local_hymt_dir():
    return os.path.join(get_portable_dir(), "translators", "hymt")


def _find_hymt_model_under(root_dir):
    if not root_dir or not os.path.isdir(root_dir):
        return ""
    direct_path = os.path.join(root_dir, HYMT_MODEL_FILE)
    if os.path.isfile(direct_path):
        return direct_path
    for current_root, _dirs, files in os.walk(root_dir):
        for name in files:
            lower = name.lower()
            if lower == HYMT_MODEL_FILE.lower() or (lower.endswith(".gguf") and "hy-mt" in lower):
                return os.path.join(current_root, name)
    return ""


def hymt_runner_names():
    """llama.cpp runner file names for this platform."""
    stems = ("hymt", "llama-cli", "llama-run", "main")
    return tuple(platform_support.executable_name(stem).lower() for stem in stems)


def _find_hymt_runner_under(root_dir):
    if not root_dir or not os.path.isdir(root_dir):
        return ""
    candidates = hymt_runner_names()
    for name in candidates:
        direct_path = os.path.join(root_dir, name)
        if os.path.isfile(direct_path):
            return direct_path
    for current_root, _dirs, files in os.walk(root_dir):
        lower_files = {name.lower(): name for name in files}
        for candidate in candidates:
            if candidate in lower_files:
                return os.path.join(current_root, lower_files[candidate])
    return ""


def _get_hymt_runtime():
    global _hymt_runtime_cache
    if _hymt_runtime_cache is not None:
        return _hymt_runtime_cache
    root_dir = _local_hymt_dir()
    runtime = {
        "root": root_dir,
        "model": _find_hymt_model_under(root_dir),
        "runner": _find_hymt_runner_under(root_dir),
    }
    _hymt_runtime_cache = runtime
    return runtime


def hymt_installed():
    runtime = _get_hymt_runtime()
    return bool(runtime.get("model") and runtime.get("runner"))


_HYMT_CHINESE_LANGUAGE_NAMES = {
    "en": "英语", "ru": "俄语", "de": "德语", "fr": "法语",
    "es": "西班牙语", "it": "意大利语", "pt": "葡萄牙语", "pl": "波兰语",
    "uk": "乌克兰语", "tr": "土耳其语", "nl": "荷兰语", "zh": "中文",
    "ja": "日语", "ko": "韩语", "ar": "阿拉伯语", "hi": "印地语",
}


def _build_hymt_prompt(text, source_code, target_code):
    target_name = language_english_name(target_code)
    if source_code == "zh" or target_code == "zh":
        target_name = _HYMT_CHINESE_LANGUAGE_NAMES.get(target_code, target_name)
        user_text = f"将以下文本翻译为{target_name}，注意只需要输出翻译后的结果，不要额外解释：\n\n{text}"
    else:
        user_text = (
            f"Translate the following segment into {target_name}, "
            f"without additional explanation.\n\n{text}"
        )
    return f"<｜hy_begin▁of▁sentence｜><｜hy_User｜>{user_text}<｜hy_Assistant｜>"


def _clean_hymt_output(output, prompt):
    text = (output or "").strip()
    if not text:
        return ""
    if prompt and prompt in text:
        text = text.rsplit(prompt, 1)[-1].strip()
    markers = [
        "<｜hy_Assistant｜>",
        "<|assistant|>",
        "Assistant:",
    ]
    for marker in markers:
        if marker in text:
            text = text.split(marker)[-1].strip()
    text = re.sub(r"^\s*>\s*", "", text).strip()
    stop_markers = [
        "<｜hy_place▁holder▁no▁2｜>",
        "<｜hy_place▁holder▁no▁8｜>",
        "<｜hy_User｜>",
        "<|end|>",
        "</s>",
        "Exiting...",
        "llama_perf_",
    ]
    for marker in stop_markers:
        if marker in text:
            text = text.split(marker)[0].strip()
    service_lines = (
        "Loading model...",
        "available commands:",
        "/exit",
        "/regen",
        "/clear",
        "/read",
        "/glob",
        "build      :",
        "model      :",
        "modalities :",
    )
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            if lines:
                lines.append("")
            continue
        if any(stripped.startswith(prefix) for prefix in service_lines):
            continue
        if set(stripped) <= {"▄", "▀", "█", " ", "\t"}:
            continue
        lines.append(line)
    text = "\n".join(lines).strip()
    text = re.sub(r"^translation\s*:\s*", "", text, flags=re.IGNORECASE).strip()
    return text.strip("\"' \r\n")


def hymt_translate(text, source_code, target_code, status_callback=None, *, cancel_callback=None, _cache=None):
    # Bound each generation as well as its prompt; otherwise a long input can
    # silently hit the output-token cap and return an incomplete translation.
    return _translate_chunks(text, 1000, lambda chunk: _hymt_translate_chunk(
        chunk, source_code, target_code, status_callback=status_callback,
    ), cache=_cache, engine='hymt', cancel_callback=cancel_callback)


def _hymt_translate_chunk(text, source_code, target_code, status_callback=None):
    runtime = _get_hymt_runtime()
    model_path = runtime.get("model")
    runner_path = runtime.get("runner")
    if not model_path or not runner_path:
        raise RuntimeError(
            "Hy-MT не установлен. Установите пакет Hy-MT в настройках переводчика."
        )

    if status_callback:
        try:
            status_callback("Запуск Hy-MT…")
        except Exception:
            pass

    prompt = _build_hymt_prompt(text, source_code, target_code)
    max_tokens = max(96, min(2048, int(len(text) * 1.6) + 64))
    runner_dir = os.path.dirname(runner_path)
    env = platform_support.system_subprocess_env()
    env["PATH"] = runner_dir + os.pathsep + env.get("PATH", "")
    startupinfo = None
    creationflags = 0
    if sys.platform == "win32":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    def _run(cmd):
        return subprocess.run(
            cmd,
            cwd=runner_dir,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
            startupinfo=startupinfo,
            creationflags=creationflags,
        )

    # llama.cpp on Windows does not reliably decode non-ASCII prompt text from
    # argv. A UTF-8 prompt file keeps Cyrillic/CJK input intact end to end.
    prompt_path = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".txt", prefix="clickntranslate_hymt_", delete=False
        ) as prompt_file:
            prompt_file.write(prompt)
            prompt_path = prompt_file.name

        base_cmd = [
            runner_path,
            "-m", model_path,
            "-f", prompt_path,
            "-n", str(max_tokens),
            "--temp", "0",
            "--top-p", "1",
            "--no-display-prompt",
            "--single-turn",
            "--no-warmup",
            "--no-perf",
            "--no-show-timings",
            "--log-disable",
            "--simple-io",
        ]

        result = _run(base_cmd)
        if result.returncode != 0:
            err_text = (result.stderr or result.stdout or "").lower()
            if "unknown argument" in err_text or "invalid argument" in err_text:
                result = _run([
                    runner_path,
                    "-m", model_path,
                    "-f", prompt_path,
                    "-n", str(max_tokens),
                    "--temp", "0",
                    "--top-p", "1",
                    "--no-display-prompt",
                    "--single-turn",
                ])
    finally:
        if prompt_path:
            try:
                os.unlink(prompt_path)
            except OSError:
                pass

    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"Hy-MT failed: {err[:1200]}")

    translated = _clean_hymt_output(result.stdout, prompt)
    if not translated:
        err = (result.stderr or "").strip()
        raise RuntimeError(f"Hy-MT returned empty translation. {err[:500]}")
    return translated

# --- helpers to install language packages on demand ---

def _emit_status(status_callback, message):
    if not status_callback:
        return
    try:
        status_callback(message)
    except Exception:
        pass


def _emit_argos_progress(progress_callback, message, downloaded_bytes, total_bytes):
    if not progress_callback:
        return
    try:
        progress_callback(str(message), int(downloaded_bytes), int(total_bytes))
    except Exception:
        pass


def _check_argos_install_cancelled(cancel_callback):
    if cancel_callback and cancel_callback():
        raise ArgosInstallCancelledError("Argos language-package installation was canceled.")


def _argos_archive_valid(path):
    try:
        with zipfile.ZipFile(path) as archive:
            return bool(archive.namelist()) and archive.testzip() is None
    except (OSError, zipfile.BadZipFile, RuntimeError, EOFError, zlib.error, ValueError, NotImplementedError):
        return False


def _download_argos_package(
    available_package,
    label,
    progress_callback=None,
    cancel_callback=None,
):
    """Download an Argos model atomically while reporting byte progress."""
    downloads_dir = os.fspath(arg_pkg.settings.downloads_dir)
    os.makedirs(downloads_dir, exist_ok=True)
    filename = f"{arg_pkg.argospm_package_name(available_package)}.argosmodel"
    destination = os.path.join(downloads_dir, filename)

    if os.path.isfile(destination) and _argos_archive_valid(destination):
        size = os.path.getsize(destination)
        _emit_argos_progress(progress_callback, label, size, size)
        return destination
    if os.path.exists(destination):
        try:
            os.remove(destination)
        except OSError:
            pass

    links = list(getattr(available_package, "links", None) or [])
    if not links:
        _check_argos_install_cancelled(cancel_callback)
        downloaded_path = os.fspath(available_package.download())
        _check_argos_install_cancelled(cancel_callback)
        if not _argos_archive_valid(downloaded_path):
            raise RuntimeError(f"Downloaded Argos package {label} is not a valid archive.")
        return downloaded_path

    # Two translation requests may prepare the same missing direction at once.
    # Never let them truncate or remove each other's in-progress download.
    descriptor, partial_path = tempfile.mkstemp(prefix=filename + '.', suffix='.part', dir=downloads_dir)
    os.close(descriptor)
    last_error = None
    download_attempts = [url for url in links for _attempt in range(3)]
    for url in download_attempts:
        try:
            _check_argos_install_cancelled(cancel_callback)
            try:
                os.remove(partial_path)
            except OSError:
                pass
            with requests.get(
                url,
                stream=True,
                timeout=(20, 180),
                headers={"User-Agent": "ClicknTranslate Argos package installer", "Accept-Encoding": "identity"},
            ) as response:
                response.raise_for_status()
                try:
                    total_bytes = int((response.headers.get("Content-Length") or "0").strip() or "0")
                except Exception:
                    total_bytes = 0
                downloaded_bytes = 0
                _emit_argos_progress(progress_callback, label, downloaded_bytes, total_bytes)
                with open(partial_path, "wb") as package_file:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        _check_argos_install_cancelled(cancel_callback)
                        if not chunk:
                            continue
                        package_file.write(chunk)
                        downloaded_bytes += len(chunk)
                        _emit_argos_progress(progress_callback, label, downloaded_bytes, total_bytes)
            _check_argos_install_cancelled(cancel_callback)
            if total_bytes and downloaded_bytes != total_bytes:
                raise RuntimeError(
                    f"Incomplete Argos package download for {label}: "
                    f"received {downloaded_bytes} of {total_bytes} bytes."
                )
            if not _argos_archive_valid(partial_path):
                raise RuntimeError(f"Downloaded Argos package {label} is not a valid archive.")
            os.replace(partial_path, destination)
            return destination
        except ArgosInstallCancelledError:
            try:
                os.remove(partial_path)
            except OSError:
                pass
            raise
        except Exception as exc:
            last_error = exc
            try:
                os.remove(partial_path)
            except OSError:
                pass

    raise RuntimeError(f"Failed to download Argos package {label}: {last_error}")


def models_installed_ru_en():
    """Return True if both RU and EN language models are installed in Argos."""
    if not _ensure_argos_available():
        return False
    try:
        return {("ru", "en"), ("en", "ru")}.issubset(_installed_pairs())
    except Exception:
        return False


def _installed_pairs():
    try:
        return {(pkg.from_code, pkg.to_code) for pkg in arg_pkg.get_installed_packages()}
    except Exception:
        return set()


def _argos_package_data_dirs():
    """Return plausible Argos package roots without importing its native runtime."""
    _prepare_argos_environment()
    candidates = []
    if arg_pkg is not None:
        try:
            candidates.append(os.fspath(arg_pkg.settings.package_data_dir))
        except Exception:
            pass
    xdg_data = os.environ.get("XDG_DATA_HOME")
    if xdg_data:
        candidates.append(os.path.join(xdg_data, "argos-translate", "packages"))
    candidates.extend([
        os.path.join(os.path.expanduser("~"), ".local", "share", "argos-translate", "packages"),
        os.path.join(get_portable_dir(), "argos", "data", "argos-translate", "packages"),
    ])
    result = []
    seen = set()
    for path in candidates:
        normalized = os.path.normcase(os.path.abspath(path))
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(os.path.abspath(path))
    return result


def argos_installed_direct_pairs_fast(package_dirs=None):
    """Read installed Argos directions from metadata without loading CTranslate2."""
    pairs = set()
    roots = _argos_package_data_dirs() if package_dirs is None else package_dirs
    for root in roots:
        if not os.path.isdir(root):
            continue
        try:
            package_names = os.listdir(root)
        except OSError:
            continue
        for package_name in package_names:
            metadata_path = os.path.join(root, package_name, "metadata.json")
            if not os.path.isfile(metadata_path):
                continue
            try:
                with open(metadata_path, "r", encoding="utf-8") as metadata_file:
                    metadata = json.load(metadata_file)
                source = str(metadata.get("from_code") or "").strip().lower()
                target = str(metadata.get("to_code") or "").strip().lower()
                if source and target and source != target:
                    pairs.add((source, target))
            except (OSError, ValueError, TypeError):
                continue
    return pairs


def argos_installed_translation_pairs_fast(package_dirs=None):
    """Return usable direct and English-pivot routes from installed packages."""
    direct = argos_installed_direct_pairs_fast(package_dirs=package_dirs)
    codes = {code for pair in direct for code in pair}
    usable = set(direct)
    for source in codes:
        for target in codes:
            if source == target:
                continue
            if (source, "en") in direct and ("en", target) in direct:
                usable.add((source, target))
    return usable


def _normalize_argos_pairs(pairs):
    """Return unique, valid direct Argos package pairs in input order."""
    normalized = []
    seen = set()
    for pair in pairs or []:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            continue
        source_code = str(pair[0] or "").strip().lower()
        target_code = str(pair[1] or "").strip().lower()
        value = (source_code, target_code)
        if not source_code or not target_code or source_code == target_code or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


def _argos_package_catalog_local(refresh=False):
    """Return serializable direct-package metadata for the package manager."""
    if not _ensure_argos_available():
        raise RuntimeError(argos_unavailable_reason())
    if refresh:
        arg_pkg.update_package_index()

    installed_packages = {
        (pkg.from_code, pkg.to_code): pkg
        for pkg in arg_pkg.get_installed_packages()
        if getattr(pkg, "from_code", "") and getattr(pkg, "to_code", "")
    }
    available_packages = {
        (pkg.from_code, pkg.to_code): pkg
        for pkg in arg_pkg.get_available_packages()
        if getattr(pkg, "from_code", "") and getattr(pkg, "to_code", "")
    }
    rows = []
    for pair in sorted(set(installed_packages) | set(available_packages)):
        installed = installed_packages.get(pair)
        available = available_packages.get(pair)
        package = available or installed
        rows.append(
            {
                "source_code": pair[0],
                "target_code": pair[1],
                "version": str(
                    getattr(installed, "package_version", "")
                    or getattr(available, "package_version", "")
                    or ""
                ),
                "installed": installed is not None,
                "available": available is not None,
                "package_name": (
                    arg_pkg.argospm_package_name(package) if package is not None else ""
                ),
            }
        )
    return rows


def _install_argos_packages_local(
    pairs,
    status_callback=None,
    progress_callback=None,
    cancel_callback=None,
):
    """Install the selected direct Argos packages with one index refresh."""
    if not _ensure_argos_available():
        raise RuntimeError(argos_unavailable_reason())
    requested = _normalize_argos_pairs(pairs)
    if not requested:
        return []

    _check_argos_install_cancelled(cancel_callback)
    _emit_status(status_callback, "Обновление индекса пакетов…")
    arg_pkg.update_package_index()
    _check_argos_install_cancelled(cancel_callback)
    available = {
        (pkg.from_code, pkg.to_code): pkg
        for pkg in arg_pkg.get_available_packages()
    }
    installed = _installed_pairs()
    completed = []
    for pair in requested:
        if pair in installed:
            continue
        package = available.get(pair)
        label = f"{pair[0].upper()}→{pair[1].upper()}"
        if package is None:
            raise RuntimeError(f"Argos package {label} is not available.")
        _check_argos_install_cancelled(cancel_callback)
        _emit_status(status_callback, f"Загрузка {label}…")
        download_path = _download_argos_package(
            package,
            label,
            progress_callback=progress_callback,
            cancel_callback=cancel_callback,
        )
        _check_argos_install_cancelled(cancel_callback)
        _emit_status(status_callback, f"Установка {label}…")
        try:
            arg_pkg.install_from_path(download_path)
        finally:
            # Even a failed batch can have changed files on disk.
            _invalidate_argos_cache()
        installed.add(pair)
        completed.append(pair)
        _emit_status(status_callback, f"Пакет {label} установлен")
    return completed


def _uninstall_argos_packages_local(pairs, status_callback=None):
    """Uninstall selected direct Argos packages through the upstream API."""
    if not _ensure_argos_available():
        raise RuntimeError(argos_unavailable_reason())
    requested = set(_normalize_argos_pairs(pairs))
    if not requested:
        return []
    installed = list(arg_pkg.get_installed_packages())
    removed = []
    for pair in sorted(requested):
        matching = [pkg for pkg in installed if (pkg.from_code, pkg.to_code) == pair]
        if not matching:
            continue
        label = f"{pair[0].upper()}→{pair[1].upper()}"
        _emit_status(status_callback, f"Удаление {label}…")
        for package in matching:
            try:
                arg_pkg.uninstall(package)
            finally:
                _invalidate_argos_cache()
        removed.append(pair)
    return removed


def _plan_language_pair(source_code, target_code, available_pairs, installed_pairs):
    """Packages needed for source->target, pivoting through English when needed.

    Argos ships direct packages only for a subset of pairs; everything else goes
    through English, which Argos then chains automatically.
    """
    if not source_code or not target_code or source_code == target_code:
        return []
    direct = (source_code, target_code)
    if direct in installed_pairs:
        return []
    if direct in available_pairs:
        return [direct]
    pivot = [pair for pair in ((source_code, "en"), ("en", target_code)) if pair[0] != pair[1]]
    if all(pair in installed_pairs or pair in available_pairs for pair in pivot):
        return [pair for pair in pivot if pair not in installed_pairs]
    return []


def ensure_language_pair(
    source_code,
    target_code,
    status_callback=None,
    progress_callback=None,
    cancel_callback=None,
):
    """Downloads and installs the Argos packages needed for source->target.

    Returns True when something was installed.
    """
    if not _ensure_argos_available():
        return False
    if _get_translation_object(source_code, target_code) is not None:
        return False
    try:
        _check_argos_install_cancelled(cancel_callback)
        _emit_status(status_callback, "Обновление индекса пакетов…")
        print("Обновление индекса пакетов...")
        arg_pkg.update_package_index()
        _check_argos_install_cancelled(cancel_callback)
        available = {(pkg.from_code, pkg.to_code): pkg for pkg in arg_pkg.get_available_packages()}
        plan = _plan_language_pair(source_code, target_code, set(available), _installed_pairs())
        if not plan:
            print(f"Пакет перевода для {source_code}->{target_code} не найден.")
            _emit_status(status_callback, f"Пакет {source_code.upper()}→{target_code.upper()} не найден")
            return False
        for pair in plan:
            label = f"{pair[0].upper()}→{pair[1].upper()}"
            _emit_status(status_callback, f"Загрузка {label}…")
            download_path = _download_argos_package(
                available[pair],
                label,
                progress_callback=progress_callback,
                cancel_callback=cancel_callback,
            )
            _check_argos_install_cancelled(cancel_callback)
            _emit_status(status_callback, f"Установка {label}…")
            try:
                arg_pkg.install_from_path(download_path)
            finally:
                _invalidate_argos_cache()
            print(f"Пакет {pair[0]}->{pair[1]} установлен.")
            _emit_status(status_callback, f"Пакет {label} установлен")
        return True
    except ArgosInstallCancelledError:
        _emit_status(status_callback, "Установка языкового пакета Argos отменена")
        raise
    except Exception as e:
        _emit_status(status_callback, f"Ошибка установки моделей: {e}")
        print(f"Не удалось автоматически установить модели Argos Translate: {e}")
        raise RuntimeError(f"Failed to install Argos language package: {e}") from e


def install_models(status_callback=None, progress_callback=None, cancel_callback=None):
    """Installs the RU<->EN packages (used by the module CLI and first run)."""
    ensure_language_pair(
        "ru", "en", status_callback=status_callback,
        progress_callback=progress_callback, cancel_callback=cancel_callback,
    )
    ensure_language_pair(
        "en", "ru", status_callback=status_callback,
        progress_callback=progress_callback, cancel_callback=cancel_callback,
    )


def ensure_models(status_callback=None, progress_callback=None, cancel_callback=None):
    if models_installed_ru_en():
        return  # обе модели уже есть
    install_models(
        status_callback=status_callback,
        progress_callback=progress_callback,
        cancel_callback=cancel_callback,
    )


def _try_argos_translate_local(
    text,
    source_code,
    target_code,
    status_callback=None,
    allow_install=True,
    progress_callback=None,
    cancel_callback=None,
):
    if not _ensure_argos_available():
        return None
    translation_obj = _get_translation_object(source_code, target_code)
    if translation_obj is None and allow_install:
        if ensure_language_pair(
            source_code,
            target_code,
            status_callback=status_callback,
            progress_callback=progress_callback,
            cancel_callback=cancel_callback,
        ):
            translation_obj = _get_translation_object(source_code, target_code)
    if translation_obj is None:
        return None
    return translation_obj.translate(text)


def _run_argos_worker_request(
    request,
    status_callback=None,
    progress_callback=None,
    cancel_callback=None,
    timeout=1800,
):
    worker_path = _argos_worker_path()
    if not worker_path:
        raise RuntimeError("Argos offline worker is missing from this build.")

    request_dir = tempfile.mkdtemp(prefix="clickntranslate_argos_")
    request_path = os.path.join(request_dir, "request.json")
    event_path = os.path.join(request_dir, "events.jsonl")
    cancel_path = os.path.join(request_dir, "cancel")
    stdout_path = os.path.join(request_dir, "stdout.json")
    stderr_path = os.path.join(request_dir, "stderr.txt")
    process = None
    status_events_seen = 0
    event_offset = 0
    event_buffer = ""
    cancel_sent_at = None

    def drain_events():
        nonlocal status_events_seen, event_offset, event_buffer
        if not os.path.isfile(event_path):
            return
        try:
            with open(event_path, "r", encoding="utf-8") as event_file:
                event_file.seek(event_offset)
                event_buffer += event_file.read()
                event_offset = event_file.tell()
        except OSError:
            return
        lines = event_buffer.split("\n")
        event_buffer = lines.pop()
        for line in lines:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except Exception:
                continue
            if event.get("type") == "status":
                status_events_seen += 1
                _emit_status(status_callback, event.get("message", ""))
            elif event.get("type") == "progress":
                _emit_argos_progress(
                    progress_callback,
                    event.get("message", ""),
                    event.get("downloaded_bytes", 0),
                    event.get("total_bytes", 0),
                )

    try:
        request = dict(request or {})
        request["event_path"] = event_path
        request["cancel_path"] = cancel_path
        with open(request_path, "w", encoding="utf-8") as request_file:
            json.dump(request, request_file, ensure_ascii=False)

        startupinfo = None
        creationflags = 0
        if sys.platform == "win32":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        with open(stdout_path, "w", encoding="utf-8") as stdout_file, open(
            stderr_path, "w", encoding="utf-8", errors="replace"
        ) as stderr_file:
            process = subprocess.Popen(
                [worker_path, request_path],
                stdout=stdout_file,
                stderr=stderr_file,
                text=True,
                encoding="utf-8",
                errors="replace",
                startupinfo=startupinfo,
                creationflags=creationflags,
            )
            deadline = time.monotonic() + max(1, int(timeout))
            while process.poll() is None:
                drain_events()
                if cancel_callback and cancel_callback():
                    if cancel_sent_at is None:
                        with open(cancel_path, "w", encoding="utf-8") as cancel_file:
                            cancel_file.write("cancel\n")
                        cancel_sent_at = time.monotonic()
                    elif time.monotonic() - cancel_sent_at > 10:
                        process.terminate()
                if time.monotonic() > deadline:
                    process.kill()
                    raise RuntimeError("Argos offline worker timed out.")
                time.sleep(0.1)
            drain_events()
            return_code = process.wait()

        try:
            with open(stdout_path, "r", encoding="utf-8", errors="replace") as stdout_file:
                output = stdout_file.read().strip()
        except OSError:
            output = ""
        try:
            with open(stderr_path, "r", encoding="utf-8", errors="replace") as stderr_file:
                stderr_output = stderr_file.read().strip()
        except OSError:
            stderr_output = ""
        if return_code != 0:
            if cancel_sent_at is not None:
                raise ArgosInstallCancelledError("Argos language-package installation was canceled.")
            detail = stderr_output or output or f"exit code {return_code}"
            raise RuntimeError(f"Argos offline worker failed: {detail[:1200]}")
        try:
            payload = json.loads(output)
        except Exception as exc:
            detail = stderr_output or output or "empty output"
            raise RuntimeError(f"Argos offline worker returned invalid output: {detail[:1200]}") from exc
        if not status_events_seen:
            for message in payload.get("statuses") or []:
                _emit_status(status_callback, str(message))
        return payload
    finally:
        if process is not None and process.poll() is None:
            try:
                process.kill()
            except Exception:
                pass
        shutil.rmtree(request_dir, ignore_errors=True)


def argos_package_catalog(refresh=False):
    """Return Argos direct packages without loading its native runtime in Qt."""
    if _argos_worker_path():
        payload = _run_argos_worker_request(
            {"action": "catalog", "refresh": bool(refresh)},
            timeout=180,
        )
        if payload.get("error"):
            raise RuntimeError(str(payload["error"]))
        return list(payload.get("packages") or [])
    return _argos_package_catalog_local(refresh=refresh)


def install_argos_packages(
    pairs,
    status_callback=None,
    progress_callback=None,
    cancel_callback=None,
):
    """Install selected direct Argos packages in-process or via ArgosWorker."""
    pairs = _normalize_argos_pairs(pairs)
    if _argos_worker_path():
        payload = _run_argos_worker_request(
            {"action": "install_packages", "pairs": pairs},
            status_callback=status_callback,
            progress_callback=progress_callback,
            cancel_callback=cancel_callback,
        )
        if payload.get("error"):
            error = str(payload["error"])
            if "ArgosInstallCancelledError" in error:
                raise ArgosInstallCancelledError(error)
            raise RuntimeError(error)
        return [tuple(pair) for pair in payload.get("installed") or []]
    return _install_argos_packages_local(
        pairs,
        status_callback=status_callback,
        progress_callback=progress_callback,
        cancel_callback=cancel_callback,
    )


def uninstall_argos_packages(pairs, status_callback=None):
    """Uninstall selected direct Argos packages in-process or via ArgosWorker."""
    pairs = _normalize_argos_pairs(pairs)
    if _argos_worker_path():
        payload = _run_argos_worker_request(
            {"action": "uninstall_packages", "pairs": pairs},
            status_callback=status_callback,
            timeout=180,
        )
        if payload.get("error"):
            raise RuntimeError(str(payload["error"]))
        return [tuple(pair) for pair in payload.get("removed") or []]
    return _uninstall_argos_packages_local(pairs, status_callback=status_callback)


def argos_pair_installed(source_code, target_code):
    """Return whether Argos can translate this pair without a download."""
    if _argos_worker_path():
        payload = _run_argos_worker_request(
            {
                "action": "probe",
                "source_code": source_code,
                "target_code": target_code,
            },
            timeout=60,
        )
        if payload.get("error"):
            raise RuntimeError(str(payload["error"]))
        return bool(payload.get("pair_installed"))
    if not _ensure_argos_available():
        return False
    return _get_translation_object(source_code, target_code) is not None


def _try_argos_translate_worker(
    text,
    source_code,
    target_code,
    status_callback=None,
    allow_install=True,
    progress_callback=None,
    cancel_callback=None,
):
    worker_path = _argos_worker_path()
    if not worker_path:
        return _try_argos_translate_local(
            text,
            source_code,
            target_code,
            status_callback=status_callback,
            allow_install=allow_install,
            progress_callback=progress_callback,
            cancel_callback=cancel_callback,
        )

    def request_translation(install_allowed):
        payload = _run_argos_worker_request(
            {
                "action": "translate",
                "text": str(text or ""),
                "source_code": source_code,
                "target_code": target_code,
                "allow_install": bool(install_allowed),
            },
            status_callback=status_callback,
            progress_callback=progress_callback,
            cancel_callback=cancel_callback,
        )
        if payload.get("error"):
            error = str(payload["error"])
            if "ArgosInstallCancelledError" in error:
                raise ArgosInstallCancelledError(error)
            raise RuntimeError(error)
        return payload.get("result")

    try:
        return request_translation(allow_install)
    except ArgosInstallCancelledError:
        raise
    except Exception as first_error:
        # Each packaged translation runs in a fresh worker. Directly after a
        # package install Windows may still be releasing model files, so retry
        # once only when a fresh probe confirms the complete route is installed.
        if cancel_callback and cancel_callback():
            raise ArgosInstallCancelledError(
                "Argos language-package installation was canceled."
            ) from first_error
        try:
            if not argos_pair_installed(source_code, target_code):
                raise first_error
            _emit_status(status_callback, "Retrying Argos translation…")
            return request_translation(False)
        except ArgosInstallCancelledError:
            raise
        except Exception as retry_error:
            if retry_error is first_error:
                raise
            raise RuntimeError(str(retry_error) or str(first_error)) from retry_error


def _try_argos_translate(
    text,
    source_code,
    target_code,
    status_callback=None,
    allow_install=True,
    progress_callback=None,
    cancel_callback=None,
):
    if _argos_worker_path():
        return _try_argos_translate_worker(
            text,
            source_code,
            target_code,
            status_callback=status_callback,
            allow_install=allow_install,
            progress_callback=progress_callback,
            cancel_callback=cancel_callback,
        )
    return _try_argos_translate_local(
        text,
        source_code,
        target_code,
        status_callback=status_callback,
        allow_install=allow_install,
        progress_callback=progress_callback,
        cancel_callback=cancel_callback,
    )

def test_translation():
    if not _ensure_argos_available():
        print("Argos недоступен в этой сборке.")
        return
    installed_languages = arg_tr.get_installed_languages()
    ru_language = None
    en_language = None
    for language in installed_languages:
        if language.code == "ru":
            ru_language = language
        elif language.code == "en":
            en_language = language
    if ru_language is None or en_language is None:
        print("Модели перевода для ru<->en не установлены.")
        print("Пожалуйста, установите языковые модели через Argos Translate.")
        return
    # Пробуем RU->EN
    translation_ru_en = ru_language.get_translation(en_language)
    # Пробуем EN->RU
    translation_en_ru = en_language.get_translation(ru_language)
    text_ru = "Привет, мир!"
    text_en = "Hello, world!"
    if translation_ru_en is not None:
        print("RU->EN:", translation_ru_en.translate(text_ru))
    else:
        print("Нет модели для RU->EN")
    if translation_en_ru is not None:
        print("EN->RU:", translation_en_ru.translate(text_en))
    else:
        print("Нет модели для EN->RU")

class TranslationCancelledError(RuntimeError):
    """Cancellation is not a provider failure and must never trigger fallback."""


class ProviderRateLimitError(RuntimeError):
    pass


def _is_provider_rate_limit(error):
    return isinstance(error, ProviderRateLimitError) or getattr(getattr(error, 'response', None), 'status_code', None) == 429


def _check_translation_cancelled(callback):
    if callback is not None and callback():
        raise TranslationCancelledError('Translation canceled')


def _libretranslate_server():
    key = os.environ.get('CLICKNTRANSLATE_LIBRETRANSLATE_API_KEY', '').strip()
    url = os.environ.get('CLICKNTRANSLATE_LIBRETRANSLATE_URL', '').strip().rstrip('/')
    return url or ('https://libretranslate.com' if key else 'https://translate.disroot.org'), key


class _TranslationCache:
    def __init__(self, source, target):
        self.source, self.target = source, target
        try:
            from main import get_data_file
            self.data_dir = os.path.dirname(get_data_file('config.json'))
        except Exception:
            self.data_dir = None

    @staticmethod
    def _engine_key(engine, segment=False):
        if engine == 'libretranslate':
            # A custom LibreTranslate server may use different models.
            url, _key = _libretranslate_server()
            engine += ':' + hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]
        return ('segment-v2:' if segment else '') + engine

    def get(self, text, engine, segment=False):
        if self.data_dir:
            try:
                from cache_manager import get_cached_translation
                result = get_cached_translation(self.data_dir, text, self.source, self.target,
                    engine=self._engine_key(engine, segment), strict_engine=True)
                return result if isinstance(result, str) and result.strip() else None
            except Exception:
                pass
        return None

    def save(self, text, result, engine, segment=False):
        if self.data_dir and result:
            try:
                from cache_manager import save_cached_translation
                save_cached_translation(self.data_dir, text, self.source, self.target, result,
                    engine=self._engine_key(engine, segment))
            except Exception:
                pass


def translate_text(
    text,
    source_code,
    target_code,
    status_callback=None,
    engine=None,
    progress_callback=None,
    cancel_callback=None,
):
    """Translate with the selected engine; failures never change providers."""
    config = get_cached_translator_config()
    engine = (engine or config.get("translator_engine", "Google")).lower()
    _check_translation_cancelled(cancel_callback)
    print(f"Using translator: {engine.upper()}")

    # Check translation cache first
    cache = _TranslationCache(source_code, target_code)
    cached = cache.get(text, engine)
    if cached:
        print(f"Using cached translation ({len(text)} chars)")
        return cached

    online_engines = ['google', 'lingva', 'mymemory', 'libretranslate']

    def _call_online(name, txt, src, tgt):
        if name == 'google':
            return google_translate(txt, src, tgt, cancel_callback=cancel_callback, _cache=cache)
        elif name == 'mymemory':
            return mymemory_translate(txt, src, tgt, cancel_callback=cancel_callback, _cache=cache)
        elif name == 'lingva':
            return lingva_translate(txt, src, tgt, cancel_callback=cancel_callback, _cache=cache)
        elif name == 'libretranslate':
            return libretranslate(txt, src, tgt, cancel_callback=cancel_callback, _cache=cache)
        raise ValueError(f"Unknown engine: {name}")

    def _cache_and_return(result, actual_engine=None):
        """Save translation to cache and return."""
        cache.save(text, result, actual_engine or engine)
        return result

    if engine == HYMT_ENGINE_KEY:
        return _cache_and_return(hymt_translate(text, source_code, target_code, status_callback=status_callback,
            cancel_callback=cancel_callback, _cache=cache))

    if engine in online_engines:
        _check_translation_cancelled(cancel_callback)
        result = _call_online(engine, text, source_code, target_code)
        if not result:
            raise RuntimeError(f"{engine} returned an empty translation")
        return _cache_and_return(result, engine)

    if engine == "argos":
        if not argos_runtime_available():
            raise Exception(argos_unavailable_reason())
        # Packages are large, so only download them when the caller provides the
        # dedicated byte-progress flow. A status-only callback (used by document
        # translation) must never trigger an unconfirmed background download.
        argos_result = _try_argos_translate(
            text,
            source_code,
            target_code,
            status_callback=status_callback,
            allow_install=bool(progress_callback),
            progress_callback=progress_callback,
            cancel_callback=cancel_callback,
        )
        if argos_result:
            return _cache_and_return(argos_result)
        raise Exception(
            f"Argos offline translation package is not installed for {source_code}->{target_code}. "
            "Install the required direction in Settings > Language packages > Argos."
        )

    raise ValueError(f"Unknown translation engine: {engine}")

# Кэшированная сессия для HTTP запросов
_http_session = None

def _get_http_session():
    """Возвращает переиспользуемую HTTP сессию."""
    global _http_session
    if _http_session is None:
        _http_session = requests.Session()
        # Оптимизация: keep-alive и пул соединений
        _http_session.headers.update({'Connection': 'keep-alive'})
    return _http_session

def _google_translate_chunk(text, source_code, target_code, *, cancel_callback=None):
    """Translate a single chunk via Google API."""
    url = 'https://translate.googleapis.com/translate_a/single'
    source_api = translator_api_code(source_code, "google")
    target_api = translator_api_code(target_code, "google")
    params = {
        'client': 'gtx',
        'sl': source_api,
        'tl': target_api,
        'dt': 't',
        'q': text,
    }
    session = _get_http_session()
    r = session.get(url, params=params, timeout=10)

    # Google occasionally rate-limits the public ``gtx`` endpoint by IP even
    # for a single short request.  Keep the selected provider as Google and
    # retry through the endpoint used by Google's dictionary extension.  This
    # is deliberately limited to 429: other failures remain visible instead of
    # silently changing the behaviour selected by the user.
    if r.status_code == 429:
        _check_translation_cancelled(cancel_callback)
        fallback_url = 'https://clients5.google.com/translate_a/t'
        fallback_params = {
            'client': 'dict-chrome-ex',
            'sl': source_api,
            'tl': target_api,
            'q': text,
        }
        fallback = session.get(fallback_url, params=fallback_params, timeout=10)
        fallback.raise_for_status()
        fallback_data = fallback.json()
        if (
            isinstance(fallback_data, list)
            and fallback_data
            and isinstance(fallback_data[0], str)
            and fallback_data[0]
        ):
            return fallback_data[0]
        raise ValueError("Google fallback returned an unexpected response")

    r.raise_for_status()
    data = r.json()
    if not isinstance(data, list) or not data or not isinstance(data[0], list):
        raise ValueError("Google returned an unexpected response")
    segments = [seg[0] for seg in data[0] if isinstance(seg, list) and seg and isinstance(seg[0], str)]
    return _validated_translation(''.join(segments), 'Google')


def google_translate(text, source_code, target_code, *, cancel_callback=None, _cache=None):
    """Google Translate через публичный endpoint с разбивкой длинного текста."""
    return _translate_chunks(text, PROVIDER_BYTE_LIMITS['google'], lambda chunk: _google_translate_chunk(chunk, source_code, target_code, cancel_callback=cancel_callback),
        cache=_cache, engine='google', cancel_callback=cancel_callback)


def _validated_translation(value, provider):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{provider} returned an empty or invalid translation")
    return value


def _translate_chunks(text, byte_limit, translate_chunk, *, cache=None, engine='', cancel_callback=None):
    """Translate the common request plan; retain completed parts after failure."""
    translated = []
    chunks = split_text(text, max_bytes=byte_limit)
    for chunk in chunks:
        _check_translation_cancelled(cancel_callback)
        content = chunk.strip()
        if not content:
            translated.append(chunk)
            continue
        result = cache.get(content, engine, segment=True) if cache is not None else None
        if not result:
            result = _validated_translation(translate_chunk(content), 'Provider')
            if cache is not None and len(chunks) > 1:
                cache.save(content, result, engine, segment=True)
        translated.append(restore_boundary_whitespace(chunk, result))
    return ''.join(translated)

def mymemory_translate(text, source_code, target_code, *, cancel_callback=None, _cache=None):
    """Respect MyMemory's 500-byte UTF-8 limit without losing chunk separators."""
    # https://mymemory.translated.net/doc/spec.php specifies bytes, not characters.
    return _translate_chunks(text, PROVIDER_BYTE_LIMITS['mymemory'], lambda chunk: _mymemory_translate_chunk(chunk, source_code, target_code),
        cache=_cache, engine='mymemory', cancel_callback=cancel_callback)


def _mymemory_translate_chunk(text, source_code, target_code):
    url = 'https://api.mymemory.translated.net/get'
    source_api = translator_api_code(source_code, "mymemory")
    target_api = translator_api_code(target_code, "mymemory")
    params = {
        'q': text,
        'langpair': f'{source_api}|{target_api}',
    }
    session = _get_http_session()
    r = session.get(url, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()
    if data.get('responseStatus') == 200:
        return _validated_translation(data['responseData']['translatedText'], 'MyMemory')
    raise Exception(f"MyMemory error: {data.get('responseDetails', 'Unknown error')}")

def _server_error_detail(response):
    """Server-provided error text, so dead or key-gated instances explain themselves."""
    try:
        payload = response.json()
        if isinstance(payload, dict):
            detail = payload.get('error') or payload.get('message')
            if detail:
                return str(detail)
    except Exception:
        pass
    return f"HTTP {response.status_code}"

def lingva_translate(text, source_code, target_code, *, cancel_callback=None, _cache=None):
    return _translate_chunks(text, PROVIDER_BYTE_LIMITS['lingva'], lambda chunk: _lingva_translate_chunk(chunk, source_code, target_code, cancel_callback=cancel_callback),
        cache=_cache, engine='lingva', cancel_callback=cancel_callback)


def _lingva_translate_chunk(text, source_code, target_code, *, cancel_callback=None):
    """Translate through the public Lingva APIs."""
    # Список публичных инстансов Lingva
    instances = [
        # Active Vercel deployment. Keep it first: the older public domains
        # below remain useful fallbacks but currently fail intermittently.
        'https://lingva.vercel.app',
        'https://lingva.ml',
        'https://translate.plausibility.cloud',
    ]
    session = _get_http_session()
    last_error = None
    source_api = translator_api_code(source_code, "lingva")
    target_api = translator_api_code(target_code, "lingva")
    for base_url in instances:
        _check_translation_cancelled(cancel_callback)
        try:
            if '/' in text:
                # Some deployments decode %2F before routing REST requests,
                # turning a file path into extra URL segments. GraphQL keeps
                # the complete text in a JSON variable instead.
                query = ('query ($source: String, $target: String, $text: String!) '
                         '{ translation(source: $source, target: $target, query: $text) '
                         '{ target { text } } }')
                r = session.post(base_url + '/api/graphql', json={
                    'query': query,
                    'variables': {'source': source_api, 'target': target_api, 'text': text},
                }, timeout=8)
                if r.status_code == 200:
                    data = r.json()
                    if data.get('errors'):
                        last_error = f"{base_url}: {data['errors'][0].get('message', 'GraphQL error')}"
                        continue
                    return _validated_translation(data['data']['translation']['target']['text'], 'Lingva')
            else:
                encoded_text = requests.utils.quote(text, safe='')
                url = f'{base_url}/api/v1/{source_api}/{target_api}/{encoded_text}'
                r = session.get(url, timeout=8)
            if r.status_code == 200:
                data = r.json()
                return _validated_translation(data.get('translation'), 'Lingva')
            last_error = f"{base_url}: {_server_error_detail(r)}"
        except Exception as e:
            last_error = f"{base_url}: {e}"
            continue
    raise Exception(f"Lingva translate failed: {last_error}")

def libretranslate(text, source_code, target_code, *, cancel_callback=None, _cache=None):
    return _translate_chunks(text, PROVIDER_BYTE_LIMITS['libretranslate'], lambda chunk: _libretranslate_chunk(chunk, source_code, target_code),
        cache=_cache, engine='libretranslate', cancel_callback=cancel_callback)


class _BatchNotSupportedError(RuntimeError):
    pass


def _libretranslate_chunk(text, source_code, target_code):
    return _libretranslate_request(text, source_code, target_code)


def _libretranslate_batch(texts, source_code, target_code):
    return _libretranslate_request(list(texts), source_code, target_code)


def _libretranslate_request(text, source_code, target_code):
    """LibreTranslate - открытый переводчик (публичные серверы)."""
    # The managed service requires a key; retrying it anonymously only masks
    # the public server's actual error. A configured key goes to one selected
    # server, never to a different public instance during a fallback.
    server, api_key = _libretranslate_server()
    instances = [server]
    session = _get_http_session()
    last_error = None
    source_api = translator_api_code(source_code, "libretranslate")
    target_api = translator_api_code(target_code, "libretranslate")
    for base_url in instances:
        try:
            url = f'{base_url}/translate'
            payload = {
                'q': text,
                'source': source_api,
                'target': target_api,
                'format': 'text'
            }
            if api_key:
                payload['api_key'] = api_key
            r = session.post(url, json=payload, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if isinstance(text, list):
                    result = data.get('translatedText')
                    if not isinstance(result, list) or len(result) != len(text):
                        raise ValueError('LibreTranslate returned an invalid batch response')
                    return [_validated_translation(item, 'LibreTranslate') for item in result]
                return _validated_translation(data.get('translatedText'), 'LibreTranslate')
            last_error = f"{base_url}: {_server_error_detail(r)}"
            if isinstance(text, list) and r.status_code in (400, 413, 422):
                raise _BatchNotSupportedError(last_error)
            if r.status_code == 429:
                raise ProviderRateLimitError(last_error)
        except (_BatchNotSupportedError, ProviderRateLimitError):
            raise
        except Exception as e:
            last_error = f"{base_url}: {e}"
            continue
    raise Exception(f"LibreTranslate failed: {last_error}")

def iter_translate_texts(texts, source_code, target_code, *, engine=None,
                         status_callback=None, cancel_callback=None):
    """Yield (index, translation, error) in source order, retaining partial work.

    Documents pass the shared provider plan here. LibreTranslate can send up
    to four planned pieces in one request. Every request and cache lookup stays
    with the selected engine, including after a provider failure.
    """
    config = get_cached_translator_config()
    engine = (engine or config.get('translator_engine', 'Google')).lower()
    texts = list(texts)
    cache = _TranslationCache(source_code, target_code)
    batch_size = 4 if engine == 'libretranslate' else 1
    offset = 0
    rate_limit_error = ''
    while offset < len(texts):
        _check_translation_cancelled(cancel_callback)
        if rate_limit_error:
            cached = cache.get(texts[offset], engine) if texts[offset].strip() else texts[offset]
            yield offset, cached or '', '' if cached else rate_limit_error
            offset += 1
            continue
        group = texts[offset:offset + batch_size]
        if len(group) == 1 or any(len(text.encode('utf-8')) > 1500 for text in group):
            text = group[0]
            try:
                result = translate_text(text, source_code, target_code, engine=engine,
                    status_callback=status_callback, cancel_callback=cancel_callback)
                error = ''
            except TranslationCancelledError:
                raise
            except Exception as exc:
                _check_translation_cancelled(cancel_callback)
                result, error = '', str(exc)
                if _is_provider_rate_limit(exc):
                    rate_limit_error = error
            yield offset, result, error
            offset += 1
            continue

        results = {}
        pending = []
        for index, text in enumerate(group):
            cached = cache.get(text, engine) if text.strip() else text
            if cached is not None:
                results[index] = (cached, '')
            else:
                pending.append(index)
        try:
            _check_translation_cancelled(cancel_callback)
            if len(pending) > 1:
                values = _libretranslate_batch([group[i].strip() for i in pending], source_code, target_code)
            elif pending:
                values = [_libretranslate_chunk(group[pending[0]].strip(), source_code, target_code)]
            else:
                values = []
            for index, value in zip(pending, values):
                translated = restore_boundary_whitespace(group[index], value)
                cache.save(group[index], translated, engine)
                results[index] = (translated, '')
        except _BatchNotSupportedError:
            # Instance owners can disable arrays or set a smaller batch limit.
            # Remember it for this operation; never switch servers or leak keys.
            batch_size = 1
            continue
        except TranslationCancelledError:
            raise
        except Exception as exc:
            if _is_provider_rate_limit(exc):
                rate_limit_error = str(exc)
            for index in pending:
                _check_translation_cancelled(cancel_callback)
                results[index] = ('', str(exc))
        for index in range(len(group)):
            result, error = results[index]
            yield offset + index, result, error
        offset += len(group)


if __name__ == '__main__':
    if _ensure_argos_available():
        install_models()
        _invalidate_argos_cache()  # Сбрасываем кэш после установки
        print("Попытка тестового перевода:")
        test_translation()
    else:
        print("Argos недоступен; используется онлайн-переводчик Google.")
