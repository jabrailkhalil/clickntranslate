import requests
import json
import os
import sys
import subprocess
import re
from languages import language_english_name, translator_api_code

# Optional Argos Translate (offline). Loaded lazily to keep app startup and tests
# away from ctranslate2/torch DLLs unless offline translation is actually used.
HAS_ARGOS = True
arg_pkg = None
arg_tr = None
_argos_import_error = None


def _ensure_argos_available():
    global HAS_ARGOS, arg_pkg, arg_tr, _argos_import_error
    if not HAS_ARGOS:
        return False
    if arg_pkg is not None and arg_tr is not None:
        return True
    try:
        import argostranslate.package as loaded_pkg
        import argostranslate.translate as loaded_tr
    except Exception as exc:
        HAS_ARGOS = False
        _argos_import_error = exc
        return False
    arg_pkg = loaded_pkg
    arg_tr = loaded_tr
    return True

def get_app_dir():
    if hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(sys.argv[0]))

def get_portable_dir():
    if hasattr(sys, '_MEIPASS'):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(sys.argv[0]))

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


def _build_hymt_prompt(text, source_code, target_code):
    source_name = language_english_name(source_code)
    target_name = language_english_name(target_code)
    user_text = (
        f"Translate the following text from {source_name} to {target_name}. "
        f"Return only the translation, without explanations.\n\n{text}"
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

    base_cmd = [
        runner_path,
        "-m", model_path,
        "-p", prompt,
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

    result = _run(base_cmd)
    if result.returncode != 0:
        err_text = (result.stderr or result.stdout or "").lower()
        if "unknown argument" in err_text or "invalid argument" in err_text:
            result = _run([
                runner_path,
                "-m", model_path,
                "-p", prompt,
                "-n", str(max_tokens),
                "--temp", "0",
                "--top-p", "1",
                "--no-display-prompt",
                "--single-turn",
            ])
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"Hy-MT failed: {err[:1200]}")

    translated = _clean_hymt_output(result.stdout, prompt)
    if not translated:
        err = (result.stderr or "").strip()
        raise RuntimeError(f"Hy-MT returned empty translation. {err[:500]}")
    return translated

# --- helper to auto-install ru<->en models on first run ---

def models_installed_ru_en():
    """Return True if both RU and EN language models are installed in Argos."""
    if not _ensure_argos_available():
        return False
    try:
        langs = _get_argos_languages()
        return {'ru', 'en'}.issubset(langs.keys())
    except Exception:
        return False

def ensure_models(status_callback=None):
    if not _ensure_argos_available():
        return
    langs = _get_argos_languages()
    if {'ru', 'en'}.issubset(langs.keys()):
        return  # обе модели уже есть
    try:
        install_models(status_callback=status_callback)
        _invalidate_argos_cache()  # Сбрасываем кэш после установки
    except Exception as e:
        if status_callback:
            try:
                status_callback(f"Ошибка установки моделей: {e}")
            except Exception:
                pass
        print(f"Не удалось автоматически установить модели Argos Translate: {e}")

def install_models(status_callback=None):
    if not _ensure_argos_available():
        return
    if status_callback:
        try:
            status_callback("Обновление индекса пакетов…")
        except Exception:
            pass
    print("Обновление индекса пакетов...")
    arg_pkg.update_package_index()
    if status_callback:
        try:
            status_callback("Поиск доступных языковых пакетов…")
        except Exception:
            pass
    available_packages = arg_pkg.get_available_packages()
    ru_en_package = None
    en_ru_package = None
    for pkg in available_packages:
        if pkg.from_code == "ru" and pkg.to_code == "en":
            ru_en_package = pkg
        elif pkg.from_code == "en" and pkg.to_code == "ru":
            en_ru_package = pkg
    if ru_en_package:
        msg = f"Найден пакет RU→EN: {ru_en_package}"
        print(msg)
        if status_callback:
            try:
                status_callback("Загрузка RU→EN…")
            except Exception:
                pass
        download_path = ru_en_package.download()
        if status_callback:
            try:
                status_callback("Установка RU→EN…")
            except Exception:
                pass
        arg_pkg.install_from_path(download_path)
        print("Пакет RU->EN установлен.")
        if status_callback:
            try:
                status_callback("Пакет RU→EN установлен")
            except Exception:
                pass
    else:
        print("Пакет перевода для RU->EN не найден.")
        if status_callback:
            try:
                status_callback("Пакет RU→EN не найден")
            except Exception:
                pass
    if en_ru_package:
        msg = f"Найден пакет EN→RU: {en_ru_package}"
        print(msg)
        if status_callback:
            try:
                status_callback("Загрузка EN→RU…")
            except Exception:
                pass
        download_path = en_ru_package.download()
        if status_callback:
            try:
                status_callback("Установка EN→RU…")
            except Exception:
                pass
        arg_pkg.install_from_path(download_path)
        print("Пакет EN->RU установлен.")
        if status_callback:
            try:
                status_callback("Пакет EN→RU установлен")
            except Exception:
                pass
    else:
        print("Пакет перевода для EN->RU не найден.")
        if status_callback:
            try:
                status_callback("Пакет EN→RU не найден")
            except Exception:
                pass

    # Сбрасываем кэш после установки
    _invalidate_argos_cache()


def _try_argos_translate(text, source_code, target_code, status_callback=None, allow_ru_en_install=True):
    if not _ensure_argos_available():
        return None
    if allow_ru_en_install and {source_code, target_code} == {"ru", "en"}:
        ensure_models(status_callback=status_callback)
    translation_obj = _get_translation_object(source_code, target_code)
    if translation_obj is None:
        return None
    return translation_obj.translate(text)

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
            if _ensure_argos_available():
                argos_result = _try_argos_translate(
                    text, source_code, target_code, status_callback=status_callback, allow_ru_en_install=False
                )
                if argos_result:
                    return _cache_and_return(argos_result)
            else:
                raise online_error

    if engine == "argos" or HAS_ARGOS:
        argos_result = _try_argos_translate(text, source_code, target_code, status_callback=status_callback)
        if argos_result:
            return _cache_and_return(argos_result)
        if engine == "argos":
            raise Exception(
                f"Argos offline translation package is not installed for {source_code}->{target_code}."
            )

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

def lingva_translate(text, source_code, target_code):
    """Lingva - прокси для Google Translate (более стабильный)."""
    # Список публичных инстансов Lingva
    instances = [
        'https://lingva.ml',
        'https://translate.plausibility.cloud',
        'https://lingva.pussthecat.org',
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
        except Exception as e:
            last_error = e
            continue
    raise Exception(f"Lingva translate failed: {last_error}")

def libretranslate(text, source_code, target_code):
    """LibreTranslate - открытый переводчик (публичные серверы)."""
    instances = [
        'https://libretranslate.com',
        'https://translate.argosopentech.com',
        'https://translate.terraprint.co',
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
        except Exception as e:
            last_error = e
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
