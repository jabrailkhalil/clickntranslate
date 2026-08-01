import requests
import json
import os
import sys
import subprocess
import re
import tempfile
import types
from languages import language_english_name, translator_api_code
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
    if previous_torch is _MODULE_NOT_LOADED:
        sys.modules["torch"] = None
    try:
        import argostranslate.package as loaded_pkg
        import argostranslate.translate as loaded_tr
    except Exception as exc:
        HAS_ARGOS = False
        _argos_import_error = exc
        print(f"Argos Translate недоступен: {exc}")
        return False
    finally:
        if previous_torch is _MODULE_NOT_LOADED:
            sys.modules.pop("torch", None)
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
    path = os.path.join(os.path.dirname(sys.executable), "ArgosWorker.exe")
    return path if os.path.isfile(path) else ""


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


def _find_hymt_runner_under(root_dir):
    if not root_dir or not os.path.isdir(root_dir):
        return ""
    candidates = ("hymt.exe", "llama-cli.exe", "llama-run.exe", "main.exe")
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


def hymt_translate(text, source_code, target_code, status_callback=None):
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
    env = os.environ.copy()
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


def ensure_language_pair(source_code, target_code, status_callback=None):
    """Downloads and installs the Argos packages needed for source->target.

    Returns True when something was installed.
    """
    if not _ensure_argos_available():
        return False
    if _get_translation_object(source_code, target_code) is not None:
        return False
    try:
        _emit_status(status_callback, "Обновление индекса пакетов…")
        print("Обновление индекса пакетов...")
        arg_pkg.update_package_index()
        available = {(pkg.from_code, pkg.to_code): pkg for pkg in arg_pkg.get_available_packages()}
        plan = _plan_language_pair(source_code, target_code, set(available), _installed_pairs())
        if not plan:
            print(f"Пакет перевода для {source_code}->{target_code} не найден.")
            _emit_status(status_callback, f"Пакет {source_code.upper()}→{target_code.upper()} не найден")
            return False
        for pair in plan:
            label = f"{pair[0].upper()}→{pair[1].upper()}"
            _emit_status(status_callback, f"Загрузка {label}…")
            download_path = available[pair].download()
            _emit_status(status_callback, f"Установка {label}…")
            arg_pkg.install_from_path(download_path)
            print(f"Пакет {pair[0]}->{pair[1]} установлен.")
            _emit_status(status_callback, f"Пакет {label} установлен")
        _invalidate_argos_cache()
        return True
    except Exception as e:
        _emit_status(status_callback, f"Ошибка установки моделей: {e}")
        print(f"Не удалось автоматически установить модели Argos Translate: {e}")
        return False


def install_models(status_callback=None):
    """Installs the RU<->EN packages (used by the module CLI and first run)."""
    ensure_language_pair("ru", "en", status_callback=status_callback)
    ensure_language_pair("en", "ru", status_callback=status_callback)


def ensure_models(status_callback=None):
    if models_installed_ru_en():
        return  # обе модели уже есть
    install_models(status_callback=status_callback)


def _try_argos_translate_local(text, source_code, target_code, status_callback=None, allow_install=True):
    if not _ensure_argos_available():
        return None
    translation_obj = _get_translation_object(source_code, target_code)
    if translation_obj is None and allow_install:
        if ensure_language_pair(source_code, target_code, status_callback=status_callback):
            translation_obj = _get_translation_object(source_code, target_code)
    if translation_obj is None:
        return None
    return translation_obj.translate(text)


def _try_argos_translate_worker(text, source_code, target_code, status_callback=None, allow_install=True):
    worker_path = _argos_worker_path()
    if not worker_path:
        return _try_argos_translate_local(
            text, source_code, target_code, status_callback=status_callback, allow_install=allow_install
        )

    _emit_status(status_callback, "Preparing Argos offline translation…")
    request_path = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".json", prefix="clickntranslate_argos_", delete=False
        ) as request_file:
            json.dump(
                {
                    "text": str(text or ""),
                    "source_code": source_code,
                    "target_code": target_code,
                    "allow_install": bool(allow_install),
                },
                request_file,
                ensure_ascii=False,
            )
            request_path = request_file.name

        startupinfo = None
        creationflags = 0
        if sys.platform == "win32":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        completed = subprocess.run(
            [worker_path, request_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1800,
            startupinfo=startupinfo,
            creationflags=creationflags,
        )
    finally:
        if request_path:
            try:
                os.unlink(request_path)
            except OSError:
                pass

    output = (completed.stdout or "").strip()
    if completed.returncode != 0:
        detail = (completed.stderr or output or f"exit code {completed.returncode}").strip()
        raise RuntimeError(f"Argos offline worker failed: {detail[:1200]}")
    try:
        payload = json.loads(output)
    except Exception as exc:
        detail = (completed.stderr or output or "empty output").strip()
        raise RuntimeError(f"Argos offline worker returned invalid output: {detail[:1200]}") from exc
    for message in payload.get("statuses") or []:
        _emit_status(status_callback, str(message))
    if payload.get("error"):
        raise RuntimeError(str(payload["error"]))
    return payload.get("result")


def _try_argos_translate(text, source_code, target_code, status_callback=None, allow_install=True):
    if _argos_worker_path():
        return _try_argos_translate_worker(
            text, source_code, target_code, status_callback=status_callback, allow_install=allow_install
        )
    return _try_argos_translate_local(
        text, source_code, target_code, status_callback=status_callback, allow_install=allow_install
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

def translate_text(text, source_code, target_code, status_callback=None, engine=None):
    """Перевод текста с выбранным движком и автоматическим фоллбеком."""
    config = get_cached_translator_config()
    engine = (engine or config.get("translator_engine", "Google")).lower()
    allow_provider_fallback = bool(config.get("allow_online_provider_fallback", False))
    print(f"Using translator: {engine.upper()}")

    # Check translation cache first
    try:
        from main import get_data_file
        import os
        data_dir = os.path.dirname(get_data_file("config.json"))
        from cache_manager import get_cached_translation, save_cached_translation
        cached = get_cached_translation(data_dir, text, source_code, target_code, engine=engine)
        if cached:
            print(f"Using cached translation ({len(text)} chars)")
            return cached
    except Exception:
        data_dir = None

    online_engines = ['google', 'lingva', 'mymemory', 'libretranslate']

    def _call_online(name, txt, src, tgt):
        if name == 'google':
            return google_translate(txt, src, tgt)
        elif name == 'mymemory':
            return mymemory_translate(txt, src, tgt)
        elif name == 'lingva':
            return lingva_translate(txt, src, tgt)
        elif name == 'libretranslate':
            return libretranslate(txt, src, tgt)
        raise ValueError(f"Unknown engine: {name}")

    def _cache_and_return(result):
        """Save translation to cache and return."""
        if result and data_dir:
            try:
                save_cached_translation(data_dir, text, source_code, target_code, result, engine=engine)
            except Exception:
                pass
        return result

    if engine == HYMT_ENGINE_KEY:
        return _cache_and_return(hymt_translate(text, source_code, target_code, status_callback=status_callback))

    def _online_order(preferred):
        ordered = []
        if preferred in online_engines:
            ordered.append(preferred)
        for name in online_engines:
            if name not in ordered:
                ordered.append(name)
        return ordered

    def _try_online(preferred, allow_fallback=False):
        last_error = None
        engines_to_try = _online_order(preferred) if allow_fallback else [preferred]
        for name in engines_to_try:
            try:
                result = _call_online(name, text, source_code, target_code)
                if result:
                    return result
            except Exception as exc:
                last_error = exc
                continue
        if last_error:
            raise last_error
        return None

    if engine in online_engines:
        try:
            return _cache_and_return(_try_online(engine, allow_fallback=allow_provider_fallback))
        except Exception as online_error:
            # Offline rescue only: never switch to another online provider silently.
            argos_result = _try_argos_translate(
                text, source_code, target_code, status_callback=status_callback, allow_install=False
            )
            if argos_result:
                return _cache_and_return(argos_result)
            raise online_error

    if engine == "argos":
        if not argos_runtime_available():
            raise Exception(argos_unavailable_reason())
        # Packages are large, so only download them when the caller can show progress.
        argos_result = _try_argos_translate(
            text,
            source_code,
            target_code,
            status_callback=status_callback,
            allow_install=bool(status_callback),
        )
        if argos_result:
            return _cache_and_return(argos_result)
        raise Exception(
            f"Argos offline translation package is not installed for {source_code}->{target_code}. "
            "Open the main window and press Translate once to download it."
        )

    # Unknown engine name: use an installed offline package if there is one.
    argos_result = _try_argos_translate(
        text, source_code, target_code, status_callback=status_callback, allow_install=False
    )
    if argos_result:
        return _cache_and_return(argos_result)

    return _cache_and_return(_try_online("google", allow_fallback=allow_provider_fallback))

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

def _google_translate_chunk(text, source_code, target_code):
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
    r.raise_for_status()
    data = r.json()
    return ''.join(seg[0] for seg in data[0] if seg and seg[0])


def google_translate(text, source_code, target_code):
    """Google Translate через публичный endpoint с разбивкой длинного текста."""
    # Normalize line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    # Cyrillic chars expand ~6x in URL encoding, latin ~1x
    # Use conservative limit to avoid 400 errors
    MAX_CHUNK = 1500
    if len(text) <= MAX_CHUNK:
        return _google_translate_chunk(text, source_code, target_code)
    # Split by paragraphs, then sentences
    parts = []
    current = ""
    for line in text.split('\n'):
        if len(current) + len(line) + 1 > MAX_CHUNK:
            if current:
                parts.append(current)
            if len(line) > MAX_CHUNK:
                while len(line) > MAX_CHUNK:
                    cut = line[:MAX_CHUNK].rfind('. ')
                    if cut < MAX_CHUNK // 2:
                        cut = line[:MAX_CHUNK].rfind(' ')
                    if cut < MAX_CHUNK // 4:
                        cut = MAX_CHUNK
                    else:
                        cut += 1
                    parts.append(line[:cut])
                    line = line[cut:]
                current = line if line else ""
            else:
                current = line
        else:
            current = current + '\n' + line if current else line
    if current:
        parts.append(current)
    translated_parts = []
    for part in parts:
        translated_parts.append(_google_translate_chunk(part, source_code, target_code))
    return '\n'.join(translated_parts)

def mymemory_translate(text, source_code, target_code):
    """MyMemory - бесплатный API (до 5000 символов/день без регистрации)."""
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
        return data['responseData']['translatedText']
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

def lingva_translate(text, source_code, target_code):
    """Lingva - прокси для Google Translate (более стабильный)."""
    # Список публичных инстансов Lingva
    instances = [
        'https://lingva.ml',
        'https://translate.plausibility.cloud',
    ]
    session = _get_http_session()
    last_error = None
    source_api = translator_api_code(source_code, "lingva")
    target_api = translator_api_code(target_code, "lingva")
    for base_url in instances:
        try:
            url = f'{base_url}/api/v1/{source_api}/{target_api}/{requests.utils.quote(text)}'
            r = session.get(url, timeout=8)
            if r.status_code == 200:
                data = r.json()
                return data.get('translation', '')
            last_error = f"{base_url}: {_server_error_detail(r)}"
        except Exception as e:
            last_error = f"{base_url}: {e}"
            continue
    raise Exception(f"Lingva translate failed: {last_error}")

def libretranslate(text, source_code, target_code):
    """LibreTranslate - открытый переводчик (публичные серверы)."""
    # libretranslate.com требует API-ключ, argosopentech/terraprint отключены,
    # поэтому первым идёт публичный инстанс, который отвечает без ключа.
    instances = [
        'https://translate.disroot.org',
        'https://libretranslate.com',
    ]
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
            r = session.post(url, json=payload, timeout=10)
            if r.status_code == 200:
                data = r.json()
                return data.get('translatedText', '')
            last_error = f"{base_url}: {_server_error_detail(r)}"
        except Exception as e:
            last_error = f"{base_url}: {e}"
            continue
    raise Exception(f"LibreTranslate failed: {last_error}")

if __name__ == '__main__':
    if _ensure_argos_available():
        install_models()
        _invalidate_argos_cache()  # Сбрасываем кэш после установки
        print("Попытка тестового перевода:")
        test_translation()
    else:
        print("Argos недоступен; используется онлайн-переводчик Google.")
