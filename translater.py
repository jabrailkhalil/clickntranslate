import requests
import json
import os
import sys

# Optional Argos Translate (offline). If missing, we will use Google online.
HAS_ARGOS = True
try:
    import argostranslate.package as arg_pkg
    import argostranslate.translate as arg_tr
except Exception:
    HAS_ARGOS = False

def get_app_dir():
    if hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(sys.argv[0]))

def get_data_file(filename):
    data_dir = os.path.join(get_app_dir(), "data")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    return os.path.join(data_dir, filename)

# --- Кэширование конфигурации ---
_translator_config_cache = None
_translator_config_mtime = 0

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
    if _argos_languages_cache is None and HAS_ARGOS:
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

# --- helper to auto-install ru<->en models on first run ---

def models_installed_ru_en():
    """Return True if both RU and EN language models are installed in Argos."""
    if not HAS_ARGOS:
        return False
    try:
        langs = _get_argos_languages()
        return {'ru', 'en'}.issubset(langs.keys())
    except Exception:
        return False

def ensure_models(status_callback=None):
    if not HAS_ARGOS:
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
    if not HAS_ARGOS:
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

def test_translation():
    if not HAS_ARGOS:
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

def translate_text(text, source_code, target_code, status_callback=None):
    """Перевод текста с выбранным движком и автоматическим фоллбеком."""
    engine = get_cached_translator_config().get("translator_engine", "Argos").lower()

    # Онлайн-переводчики (определяем локально для избежания проблем с порядком)
    online_engines = ['google', 'mymemory', 'lingva', 'libretranslate']

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

    if engine in online_engines:
        try:
            return _call_online(engine, text, source_code, target_code)
        except Exception as e:
            # Фоллбек на другие онлайн-переводчики
            for name in online_engines:
                if name != engine:
                    try:
                        return _call_online(name, text, source_code, target_code)
                    except Exception:
                        continue
            # Последний шанс — Argos офлайн
            if HAS_ARGOS:
                pass  # продолжаем ниже
            else:
                raise e

    # Offline (Argos), если доступен
    if not HAS_ARGOS:
        # Нет Argos — используем Google как дефолт
        return google_translate(text, source_code, target_code)

    ensure_models(status_callback=status_callback)

    # Используем кэшированный объект перевода
    translation_obj = _get_translation_object(source_code, target_code)
    if translation_obj is None:
        raise Exception(f"Нет модели для перевода {source_code}->{target_code}. Проверьте, что установлены обе модели (RU->EN и EN->RU) через Argos Translate.")

    return translation_obj.translate(text)

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

def google_translate(text, source_code, target_code):
    """Google Translate через публичный endpoint."""
    url = 'https://translate.googleapis.com/translate_a/single'
    params = {
        'client': 'gtx',
        'sl': source_code,
        'tl': target_code,
        'dt': 't',
        'q': text,
    }
    session = _get_http_session()
    r = session.get(url, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()
    return ''.join(seg[0] for seg in data[0] if seg and seg[0])

def mymemory_translate(text, source_code, target_code):
    """MyMemory - бесплатный API (до 5000 символов/день без регистрации)."""
    url = 'https://api.mymemory.translated.net/get'
    params = {
        'q': text,
        'langpair': f'{source_code}|{target_code}',
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
    for base_url in instances:
        try:
            url = f'{base_url}/api/v1/{source_code}/{target_code}/{requests.utils.quote(text)}'
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
    for base_url in instances:
        try:
            url = f'{base_url}/translate'
            payload = {
                'q': text,
                'source': source_code,
                'target': target_code,
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
    if HAS_ARGOS:
        install_models()
        _invalidate_argos_cache()  # Сбрасываем кэш после установки
        print("Попытка тестового перевода:")
        test_translation()
    else:
        print("Argos недоступен; используется онлайн-переводчик Google.")